"""
Website Monitor Bot
--------------------
Quet cac website tuyen dung duoc khai bao trong config.json.
Neu phat hien tin tuyen dung MOI (chua tung gui) -> gui thong bao qua Telegram.
Da gui roi thi khong gui lai (luu vet trong history.json).

Khong can sua file nay de them website moi thuoc nen tang Base E-Hiring (base.vn)
-> chi can them 1 block trong config.json.

Neu them mot website dung nen tang khac (khong phai Base E-Hiring), can vet them
1 ham parser moi va dang ky vao dict PARSERS o cuoi file.
"""

import json
import logging
import os
import re
import sys
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# Cau hinh chung
# ---------------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "config.json"
HISTORY_PATH = BASE_DIR / "history.json"

REQUEST_TIMEOUT = 20  # giay
REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}

# So luong ID toi da luu lai cho moi site trong history.json (tranh file phinh to vo han)
MAX_HISTORY_IDS_PER_SITE = 3000

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("job_monitor")


# ---------------------------------------------------------------------------
# Telegram
# ---------------------------------------------------------------------------

def send_telegram_message(text: str) -> bool:
    """Gui 1 tin nhan Telegram. Tra ve True/False, KHONG lam crash chuong trinh."""
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")

    if not bot_token or not chat_id:
        logger.error(
            "Thieu TELEGRAM_BOT_TOKEN hoac TELEGRAM_CHAT_ID trong bien moi truong "
            "(kiem tra lai GitHub Secrets)."
        )
        return False

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    try:
        resp = requests.post(
            url,
            json={
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": False,
            },
            timeout=REQUEST_TIMEOUT,
        )
        if resp.status_code != 200:
            logger.error(
                "Gui Telegram that bai (HTTP %s): %s", resp.status_code, resp.text
            )
            return False
        return True
    except requests.RequestException as exc:
        logger.error("Loi ket noi khi gui Telegram: %s", exc)
        return False


# ---------------------------------------------------------------------------
# Tien ich chung: tai HTML, doc/ghi file JSON
# ---------------------------------------------------------------------------

def fetch_html(url: str) -> str:
    resp = requests.get(url, headers=REQUEST_HEADERS, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    return resp.text


def load_json(path: Path, default):
    if not path.exists():
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        logger.error("Khong doc duoc file %s (%s). Dung gia tri mac dinh.", path, exc)
        return default


def save_json(path: Path, data) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# Cac ham parser theo tung "type" khai bao trong config.json
#
# Moi ham parser nhan vao (html, site_config) va tra ve list cac dict:
#   {"id": "<id duy nhat>", "title": "<ten job>", "url": "<link job>"}
# ---------------------------------------------------------------------------

def parse_base_ehiring(html: str, site: dict) -> list:
    """
    Parser dung chung cho cac trang tuyen dung chay tren nen tang
    Base E-Hiring (base.vn) - vi du: tuyendung.sungroup.com.vn.

    Cach nhan dien: moi tin tuyen dung la 1 the <a href="...job/<slug>-<id>">.
    ID la day so o cuoi slug, luon duy nhat va khong doi -> dung lam khoa chong trung.

    Cach lam nay KHONG phu thuoc vao ten class CSS (de thay doi theo giao dien)
    ma dua vao cau truc URL on dinh cua nen tang.
    """
    prefix = site["job_url_prefix"]
    soup = BeautifulSoup(html, "html.parser")

    jobs = {}
    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"].strip()
        # Bo query string (vi du ?apply=1) de so sanh
        href_no_query = href.split("?")[0]

        if not href_no_query.startswith(prefix):
            continue

        slug = href_no_query[len(prefix):].strip("/")
        if not slug:
            continue

        id_match = re.search(r"-(\d+)$", slug)
        if not id_match:
            continue

        job_id = id_match.group(1)
        title = a_tag.get_text(strip=True)

        # Neu ID da gap roi, giu lai ban ghi co tieu de dai/day du hon
        # (link "Ung tuyen ngay" thuong khong co text, link tieu de moi co text)
        if job_id not in jobs or (title and len(title) > len(jobs[job_id]["title"])):
            jobs[job_id] = {
                "id": job_id,
                "title": title if title else f"Tin tuyen dung #{job_id}",
                "url": href_no_query,
            }

    return list(jobs.values())


PARSERS = {
    "base_ehiring": parse_base_ehiring,
}


# ---------------------------------------------------------------------------
# Xu ly logic chinh cho 1 site
# ---------------------------------------------------------------------------

def process_site(site: dict, history: dict) -> bool:
    """
    Xu ly 1 site: tai HTML, parse job, so sanh history, gui Telegram neu co job moi.
    Tra ve True neu history co thay doi can luu lai.
    """
    name = site.get("name", "Unknown site")

    if not site.get("enabled", True):
        logger.info("[%s] Site dang tat (enabled=false) -> bo qua.", name)
        return False

    site_type = site.get("type")
    parser = PARSERS.get(site_type)
    if parser is None:
        logger.error(
            "[%s] Khong tim thay parser cho type='%s'. Kiem tra lai config.json.",
            name, site_type,
        )
        return False

    logger.info("[%s] Dang tai trang: %s", name, site.get("url"))
    try:
        html = fetch_html(site["url"])
    except requests.RequestException as exc:
        logger.error("[%s] Khong tai duoc trang web: %s", name, exc)
        send_telegram_message(
            f"⚠️ <b>{name}</b>\nKhong the tai website de kiem tra tin tuyen dung.\n"
            f"Loi: {exc}"
        )
        return False

    try:
        jobs = parser(html, site)
    except Exception as exc:  # noqa: BLE001 - can log het moi loai loi parser
        logger.error("[%s] Loi khi phan tich HTML: %s", name, exc)
        send_telegram_message(
            f"⚠️ <b>{name}</b>\nCo loi khi phan tich noi dung website (co the web da "
            f"thay doi giao dien). Can kiem tra lai script.\nLoi: {exc}"
        )
        return False

    logger.info("[%s] Tim thay %d tin tuyen dung tren trang.", name, len(jobs))

    if len(jobs) == 0:
        logger.warning(
            "[%s] Khong tim thay tin tuyen dung nao. Co the website da doi cau truc "
            "HTML. KHONG cap nhat history de tranh mat du lieu.", name
        )
        send_telegram_message(
            f"⚠️ <b>{name}</b>\nLan quet nay khong tim thay tin tuyen dung nao. "
            f"Website co the da thay doi giao dien, can kiem tra lai."
        )
        return False

    known_ids = set(history.get(name, []))
    is_first_run = name not in history

    if is_first_run:
        # Lan dau tien theo doi site nay: luu toan bo job hien tai lam "diem xuat phat",
        # KHONG gui thong bao (tranh spam hang loat tin dang co san).
        all_ids = [job["id"] for job in jobs]
        history[name] = all_ids[-MAX_HISTORY_IDS_PER_SITE:]
        logger.info(
            "[%s] Lan dau theo doi -> luu %d tin lam moc, khong gui thong bao.",
            name, len(all_ids),
        )
        send_telegram_message(
            f"ℹ️ <b>{name}</b>\nDa khoi tao theo doi thanh cong voi {len(all_ids)} "
            f"tin tuyen dung hien co. Tu lan quet sau se chi bao tin MOI."
        )
        return True

    new_jobs = [job for job in jobs if job["id"] not in known_ids]

    if not new_jobs:
        logger.info("[%s] Khong co tin tuyen dung moi.", name)
        return False

    logger.info("[%s] Phat hien %d tin tuyen dung MOI.", name, len(new_jobs))

    sent_ids = []
    for job in new_jobs:
        message = (
            f"🆕 <b>Tin tuyen dung moi - {name}</b>\n\n"
            f"<b>{job['title']}</b>\n"
            f"{job['url']}"
        )
        ok = send_telegram_message(message)
        if ok:
            sent_ids.append(job["id"])
            logger.info("[%s] Da gui: %s", name, job["title"])
        else:
            logger.error(
                "[%s] Gui that bai, se thu lai o lan chay sau: %s",
                name, job["title"],
            )
        time.sleep(0.5)  # tranh gui qua nhanh bi Telegram gioi han toc do

    # Chi ghi vao history nhung job da gui THANH CONG.
    # Job gui that bai se duoc thu lai o lan chay tiep theo.
    updated_ids = list(known_ids | set(sent_ids))
    history[name] = updated_ids[-MAX_HISTORY_IDS_PER_SITE:]

    return True


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    logger.info("=== Bat dau phien kiem tra Website Monitor ===")

    config = load_json(CONFIG_PATH, default=None)
    if config is None or "sites" not in config:
        logger.error("Khong doc duoc config.json hop le. Dung chuong trinh.")
        return 1

    history = load_json(HISTORY_PATH, default={})

    history_changed = False
    had_error = False

    for site in config["sites"]:
        try:
            changed = process_site(site, history)
            history_changed = history_changed or changed
        except Exception as exc:  # noqa: BLE001
            had_error = True
            logger.error(
                "Loi khong luong truoc voi site '%s': %s",
                site.get("name", "?"), exc,
            )

    if history_changed:
        save_json(HISTORY_PATH, history)
        logger.info("Da cap nhat history.json.")
    else:
        logger.info("history.json khong thay doi.")

    logger.info("=== Ket thuc phien kiem tra ===")
    return 1 if had_error else 0


if __name__ == "__main__":
    sys.exit(main())

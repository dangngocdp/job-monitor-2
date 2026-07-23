"""
Website Monitor Bot
--------------------
Quet cac website tuyen dung duoc khai bao trong config.json.
Neu phat hien tin tuyen dung MOI (chua tung gui) -> gui thong bao qua Telegram.
Da gui roi thi khong gui lai (luu vet trong history.json).

Ho tro loc theo dia diem (vi du: chi bao tin o Ha Noi) qua "location_filter"
trong config.json cua tung site.

Cac "type" website dang ho tro (xem PARSERS o cuoi file):
- base_ehiring     : nen tang Base E-Hiring (base.vn)      - vd: Sun Group
- successfactors   : nen tang SAP SuccessFactors            - vd: Vietcombank, Techcombank
- vietinbank       : trang tuyen dung rieng cua VietinBank
- msb              : nen tang PhenomPeople cua MSB

Them website MOI cung nen tang voi 1 trong 4 loai tren -> chi can them block
trong config.json, KHONG can sua file nay.
Them website dung nen tang khac hoan toan -> can viet them 1 ham parser moi.
"""

import json
import logging
import os
import re
import sys
import time
from pathlib import Path
from urllib.parse import urljoin

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
#   {
#     "id": "<id duy nhat, khong doi>",
#     "title": "<ten tin tuyen dung>",
#     "url": "<link toi tin (co the la link trang danh sach neu web khong ho tro deep-link)>",
#     "location_text": "<chuoi mo ta dia diem, dung de loc; de rong neu khong biet>",
#     "needs_detail_fetch_for_location": True/False (mac dinh False)
#   }
# ---------------------------------------------------------------------------

def parse_base_ehiring(html: str, site: dict) -> list:
    """
    Nen tang Base E-Hiring (base.vn) - vd: tuyendung.sungroup.com.vn

    Nhan dien: moi tin la 1 the <a href="...job/<slug>-<id>">.
    ID la day so o cuoi slug -> dung lam khoa chong trung.
    Trang danh sach KHONG co san dia diem -> phai mo them trang chi tiet
    cua tung tin MOI de doc dia diem (xem get_location_base_ehiring).
    """
    prefix = site["job_url_prefix"]
    soup = BeautifulSoup(html, "html.parser")

    jobs = {}
    for a_tag in soup.find_all("a", href=True):
        href = urljoin(site["url"], a_tag["href"].strip())
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

        if job_id not in jobs or (title and len(title) > len(jobs[job_id]["title"])):
            jobs[job_id] = {
                "id": job_id,
                "title": title if title else f"Tin tuyen dung #{job_id}",
                "url": href_no_query,
                "location_text": "",
                "needs_detail_fetch_for_location": True,
            }

    return list(jobs.values())


OFFICE_LINK_PATTERN = re.compile(r"/jobs\?office=\d+")


def get_location_base_ehiring(job_url: str) -> str:
    """Mo trang chi tiet 1 tin Base E-Hiring, doc dong 'Dia diem:'."""
    html = fetch_html(job_url)
    soup = BeautifulSoup(html, "html.parser")
    locations = []
    for a_tag in soup.find_all("a", href=True):
        if OFFICE_LINK_PATTERN.search(a_tag["href"]):
            text = a_tag.get_text(strip=True)
            if text:
                locations.append(text)
    return ", ".join(locations)


def parse_successfactors(html: str, site: dict) -> list:
    """
    Nen tang SAP SuccessFactors Recruiting - vd: Vietcombank, Techcombank.

    Nhan dien: moi tin la 1 the <a href=".../job/<slug>/<id>/">.
    Dia diem nam trong cung 1 dong (<tr>) voi link tieu de -> lay het text
    trong dong do de dung cho bo loc dia diem (khong can mo them trang nao).
    """
    soup = BeautifulSoup(html, "html.parser")
    job_pattern = re.compile(r"/job/[^/?]+/(\d+)/?")

    jobs = {}
    for a_tag in soup.find_all("a", href=True):
        href = urljoin(site["url"], a_tag["href"].strip())
        m = job_pattern.search(href.split("?")[0])
        if not m:
            continue

        job_id = m.group(1)
        title = a_tag.get_text(strip=True)
        if not title:
            continue

        row = a_tag.find_parent("tr")
        location_text = row.get_text(" | ", strip=True) if row else ""

        if job_id not in jobs or len(title) > len(jobs[job_id]["title"]):
            jobs[job_id] = {
                "id": job_id,
                "title": title,
                "url": href.split("?")[0],
                "location_text": location_text,
                "needs_detail_fetch_for_location": False,
            }

    return list(jobs.values())


def parse_vietinbank(html: str, site: dict) -> list:
    """
    Trang tuyen dung rieng cua VietinBank (khong dung nen tang chung nao).

    QUAN TRONG - GIOI HAN: trang nay KHONG co link rieng cho tung tin (nut
    "Ung tuyen" chay bang JavaScript), nen bot khong the lay duoc link chi
    tiet tung tin. Bot se dung link CUA TRANG DANH SACH (site["url"]) cho
    moi thong bao, va tu tao ID duy nhat tu noi dung tin (tieu de + phong
    ban + ngay dang) vi khong co ID that tu website.

    Nhan dien tung tin dua vao nhan chu "Ngay het han:" / "Ngay dang:" luon
    xuat hien co dinh sau moi tin - day la ky thuat neo theo VAN BAN hien
    thi (khong phu thuoc class CSS, ben hon khi web doi giao dien nho).
    """
    import hashlib

    soup = BeautifulSoup(html, "html.parser")
    lines = [line.strip() for line in soup.get_text("\n").split("\n") if line.strip()]

    date_pattern = re.compile(r"^Ngày hết hạn:\s*(\d{2}/\d{2}/\d{4}).*Ngày đăng:\s*(\d{2}/\d{2}/\d{4})")

    jobs = []
    for i, line in enumerate(lines):
        m = date_pattern.match(line)
        if not m:
            continue

        posted_date = m.group(2)
        # Cac dong ngay TRUOC dong ngay-thang la: dia diem, phong ban, tieu de (thu tu nguoc)
        location = lines[i - 1] if i - 1 >= 0 else ""
        department = lines[i - 2] if i - 2 >= 0 else ""
        title = lines[i - 3] if i - 3 >= 0 else ""

        if not title:
            continue

        # Tu tao ID on dinh (khong doi qua cac lan quet) tu noi dung tin
        raw_key = f"{title}|{department}|{posted_date}"
        job_id = hashlib.md5(raw_key.encode("utf-8")).hexdigest()[:16]

        jobs.append({
            "id": job_id,
            "title": title,
            "url": site["url"],
            "location_text": location,
            "needs_detail_fetch_for_location": False,
        })

    return jobs


def parse_msb(html: str, site: dict) -> list:
    """
    Nen tang PhenomPeople cua MSB (jobs.msb.com.vn).

    Ho tro ca 2 kieu trang cua MSB:
    - Trang ket qua tim kiem (/jobs/search/...): dia diem hien la CHU THUONG
      "Dia diem: ..." ngay sau tieu de.
    - Trang landing page (/landingpages/...): dia diem hien la 1 the <a>
      rieng (dang link "kinh nhom") ngay sau tieu de.

    Ky thuat: duyet toan bo cay HTML theo dung thu tu xuat hien, ghep dia
    diem tim duoc gan nhat vao tin truoc do, du la dang the <a> hay chu thuong.
    """
    soup = BeautifulSoup(html, "html.parser")

    job_pattern = re.compile(r"/jobs/[^/?]+-(\d+)/?$")
    loc_link_pattern = re.compile(r"/jobs/\d+/other-jobs-matching/location-and-category")

    jobs = []
    current = None

    for el in soup.descendants:
        name = getattr(el, "name", None)

        if name == "a" and el.has_attr("href"):
            href = urljoin(site["url"], el["href"].strip())
            href_no_query = href.split("?")[0]

            m = job_pattern.search(href_no_query)
            if m and "/other-jobs-matching/" not in href_no_query:
                job_id = m.group(1)
                title = el.get_text(strip=True)
                if title and (current is None or current["id"] != job_id):
                    if current is not None:
                        jobs.append(current)
                    current = {
                        "id": job_id,
                        "title": title,
                        "url": href_no_query,
                        "location_text": "",
                        "needs_detail_fetch_for_location": False,
                    }
                continue

            if loc_link_pattern.search(href) and current is not None and not current["location_text"]:
                loc_text = el.get_text(strip=True).lstrip("🔍").strip()
                current["location_text"] = loc_text
                continue

        elif isinstance(el, str) and current is not None and not current["location_text"]:
            text = el.strip()
            if text.startswith("Địa điểm:"):
                current["location_text"] = text[len("Địa điểm:"):].strip()

    if current is not None:
        jobs.append(current)

    return jobs


PARSERS = {
    "base_ehiring": parse_base_ehiring,
    "successfactors": parse_successfactors,
    "vietinbank": parse_vietinbank,
    "msb": parse_msb,
}

# Voi mot so loai website, trang danh sach khong co san dia diem, phai mo
# them trang chi tiet cua TUNG TIN MOI de doc. Ham tuong ung duoc khai bao o day.
DETAIL_LOCATION_FETCHERS = {
    "base_ehiring": get_location_base_ehiring,
}


def location_matches_filter(location_text: str, location_filter: list) -> bool:
    """So khop dang chuoi con, khong phan biet hoa/thuong."""
    normalized = location_text.lower()
    return any(target.strip().lower() in normalized for target in location_filter if target.strip())


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

    location_filter = [loc for loc in site.get("location_filter", []) if loc.strip()]
    detail_fetcher = DETAIL_LOCATION_FETCHERS.get(site_type)

    processed_ids = []  # tat ca ID da xu ly xong (du co gui hay khong) -> ghi vao history
    for job in new_jobs:
        location_unknown = False

        # Mot so loai web can mo them trang chi tiet de biet dia diem
        if location_filter and job.get("needs_detail_fetch_for_location") and not job["location_text"]:
            if detail_fetcher is None:
                location_unknown = True
            else:
                try:
                    job["location_text"] = detail_fetcher(job["url"])
                except requests.RequestException as exc:
                    logger.warning(
                        "[%s] Khong doc duoc dia diem cua tin '%s' (%s). Se van gui "
                        "thong bao de tranh bo sot.", name, job["title"], exc,
                    )
                    location_unknown = True

        if location_filter and not job["location_text"]:
            location_unknown = True

        if location_filter and not location_unknown:
            if not location_matches_filter(job["location_text"], location_filter):
                logger.info(
                    "[%s] Bo qua (khong dung khu vuc loc): %s | Dia diem: %s",
                    name, job["title"], job["location_text"],
                )
                processed_ids.append(job["id"])
                continue

        # Xay dung noi dung tin nhan
        if job["location_text"]:
            location_line = f"\n📍 Địa điểm: {job['location_text']}"
        elif location_filter:
            location_line = "\n📍 Địa điểm: (không xác định được, vui lòng kiểm tra)"
        else:
            location_line = ""

        message = (
            f"🆕 <b>Tin tuyen dung moi - {name}</b>\n\n"
            f"<b>{job['title']}</b>"
            f"{location_line}\n"
            f"{job['url']}"
        )
        ok = send_telegram_message(message)
        if ok:
            processed_ids.append(job["id"])
            logger.info("[%s] Da gui: %s", name, job["title"])
        else:
            logger.error(
                "[%s] Gui that bai, se thu lai o lan chay sau: %s",
                name, job["title"],
            )
            # KHONG them vao processed_ids -> lan sau se thu gui lai
        time.sleep(0.5)  # tranh gui qua nhanh bi Telegram gioi han toc do

    updated_ids = list(known_ids | set(processed_ids))
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

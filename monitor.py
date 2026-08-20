"""
Website Monitor Bot
--------------------
Quet cac website tuyen dung duoc khai bao trong config.json.
Neu phat hien tin tuyen dung MOI (chua tung gui) -> gui thong bao qua Telegram.
Da gui roi thi khong gui lai (luu vet trong history.json).

Ho tro loc theo dia diem (vi du: chi bao tin o Ha Noi) qua "location_filter"
trong config.json cua tung site.

Cac "type" website dang ho tro (xem PARSERS o cuoi file):
- base_ehiring          : nen tang Base E-Hiring (base.vn)      - vd: Sun Group
- successfactors        : nen tang SAP SuccessFactors            - vd: Vietcombank, Techcombank
- vietinbank            : trang tuyen dung rieng cua VietinBank (hien dang TAT, xem config)
- msb                   : nen tang PhenomPeople cua MSB
- mbbank_api            : API JSON rieng cua MBBank
- talentnetwork         : nen tang Talentnetwork/CareerViet      - vd: SHB
- iviec_api             : nen tang iviec.vn                      - vd: TPBank, SunPhuQuoc Airways, LPBank
- bidv_api              : API JSON rieng cua BIDV
- vietnamworks_company  : trang cong ty tren VietnamWorks (dung chung cho nhieu cong ty)

Them website MOI cung nen tang voi 1 trong cac loai tren -> chi can them block
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
# Tien ich chung: tai HTML/JSON, doc/ghi file JSON
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
    Trang tuyen dung rieng cua VietinBank (KHONG dung nen tang chung nao).
    HIEN DANG TAT trong config.json (enabled: false) vi chua tim duoc dung
    API tra ve danh sach tin tuyen dung that (chi tim duoc API danh muc chuc
    danh chung, khong co dia diem/ngay dang). Giu lai ham nay de bat lai
    trong tuong lai neu tim duoc API dung.

    QUAN TRONG - GIOI HAN: trang nay KHONG co link rieng cho tung tin (nut
    "Ung tuyen" chay bang JavaScript), nen bot khong the lay duoc link chi
    tiet tung tin. Bot se dung link CUA TRANG DANH SACH (site["url"]) cho
    moi thong bao, va tu tao ID duy nhat tu noi dung tin (tieu de + phong
    ban + ngay dang) vi khong co ID that tu website.
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
        location = lines[i - 1] if i - 1 >= 0 else ""
        department = lines[i - 2] if i - 2 >= 0 else ""
        title = lines[i - 3] if i - 3 >= 0 else ""

        if not title:
            continue

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


def parse_mbbank_api(html: str, site: dict) -> list:
    """
    MBBank (careers.mbbank.com.vn) khong the doc bang HTML thong thuong vi
    trang nay la ung dung JavaScript thuan (SPA). Thay vao do, ta goi THANG
    vao API JSON noi bo ma chinh trang web do dung de lay du lieu
    (tim thay qua tab Network cua trinh duyet).

    API tra ve JSON dang: {"content": [{id, name, province, toDate, ...}], ...}
    Moi tin da co san "province" (dia diem) ngay trong du lieu -> khong can
    mo them trang nao khac de loc dia diem.
    """
    data = json.loads(html)
    job_url_template = site.get("job_url_template")

    jobs = []
    for item in data.get("content", []):
        job_id = str(item.get("id", "")).strip()
        if not job_id:
            continue
        title = item.get("name") or f"Tin tuyen dung #{job_id}"
        province = item.get("province") or ""

        if job_url_template:
            job_url = job_url_template.format(id=job_id, workGroupId=item.get("workGroupId", ""))
        else:
            job_url = site.get("listing_url", site["url"])

        jobs.append({
            "id": job_id,
            "title": title,
            "url": job_url,
            "location_text": province,
            "needs_detail_fetch_for_location": False,
        })

    return jobs


def parse_talentnetwork(html: str, site: dict) -> list:
    """
    Nen tang Talentnetwork/CareerViet - vd: SHB (tuyendung.shb.com.vn).

    Nhan dien: moi tin la 1 the <a href=".../viec-lam/<slug>.<ma-hex>.html">.
    Ma hex truoc ".html" la ID duy nhat, khong doi -> dung lam khoa chong trung.

    Dia diem hien thi dang chu "Noi lam viec: ..." ngay ke ben tieu de tin
    tren trang danh sach -> quet tuan tu theo thu tu xuat hien trong HTML de
    ghep dia diem vao dung tin (khong can mo them trang nao).
    """
    soup = BeautifulSoup(html, "html.parser")
    job_pattern = re.compile(r"/viec-lam/[^/?]+\.([0-9a-fA-F]{6,})\.html")

    jobs = []
    current = None

    for el in soup.descendants:
        if getattr(el, "name", None) == "a" and el.has_attr("href"):
            href = urljoin(site["url"], el["href"].strip())
            m = job_pattern.search(href)
            if m:
                job_id = m.group(1)
                title = el.get_text(strip=True)
                if title and (current is None or current["id"] != job_id):
                    if current is not None:
                        jobs.append(current)
                    current = {
                        "id": job_id,
                        "title": title,
                        "url": href,
                        "location_text": "",
                        "needs_detail_fetch_for_location": False,
                    }
                continue
        elif isinstance(el, str) and current is not None and not current["location_text"]:
            text = el.strip()
            if text.startswith("Nơi làm việc:"):
                current["location_text"] = text[len("Nơi làm việc:"):].strip()

    if current is not None:
        jobs.append(current)

    return jobs


def parse_iviec_api(html: str, site: dict) -> list:
    """
    Nen tang iviec.vn (centralize-api-v2.iviec.vn) - vd: TPBank,
    SunPhuQuoc Airways, LPBank.

    Day la API JSON noi bo (tim qua F12 Network), tra ve du lieu day du:
    tieu de, ma "slug" de dung link, va danh sach dia diem lam viec
    (workingNewAddresses) -> khong can mo them trang nao khac.

    "url" trong config.json la duong dan API. "job_url_prefix" la duong dan
    trang web cong khai de ghep voi slug thanh link cho tung tin.
    """
    data = json.loads(html)
    prefix = site.get("job_url_prefix", "")

    jobs = []
    for item in data.get("items", []):
        job_id = str(item.get("id", "")).strip()
        if not job_id:
            continue

        title = item.get("name") or f"Tin tuyen dung #{job_id}"
        slug = item.get("slug", "")
        job_url = f"{prefix}{slug}" if (prefix and slug) else site.get("listing_url", site["url"])

        addresses = item.get("workingNewAddresses") or []
        locations = [a.get("provinceName") for a in addresses if a.get("provinceName")]
        location_text = ", ".join(locations)

        jobs.append({
            "id": job_id,
            "title": title,
            "url": job_url,
            "location_text": location_text,
            "needs_detail_fetch_for_location": False,
        })

    return jobs


def parse_bidv(html: str, site: dict) -> list:
    """
    API JSON rieng cua BIDV (tuyendung.bidv.com.vn/GetAllTinTuyenDung).

    Du lieu tra ve dang: {"rows": [{id, title, descriptionjob (HTML), ...}]}.
    KHONG co truong dia diem rieng -> doc toan bo noi dung mo ta (HTML) roi
    bo tag, dung lam "location_text" de bo loc dia diem tim theo chuoi con
    (vi du tim thay "Hà Nội" trong dia chi ghi trong mo ta).

    QUAN TRONG - GIOI HAN: khong co link rieng cho tung tin trong du lieu
    API -> dung link trang danh sach chung cho moi thong bao (giong VietinBank).
    """
    data = json.loads(html)
    jobs = []
    for row in data.get("rows", []):
        job_id = str(row.get("id", "")).strip()
        if not job_id:
            continue
        title = row.get("title") or f"Tin tuyen dung #{job_id}"

        desc_html = row.get("descriptionjob", "") or ""
        location_text = BeautifulSoup(desc_html, "html.parser").get_text(" ", strip=True)
        # Cat bot cho gon (mo ta co the rat dai), chi giu doan dau du de loc dia diem
        location_text = location_text[:400]

        jobs.append({
            "id": job_id,
            "title": title,
            "url": site.get("listing_url", site["url"]),
            "location_text": location_text,
            "needs_detail_fetch_for_location": False,
        })

    return jobs


def parse_vietnamworks_company(html: str, site: dict) -> list:
    """
    Trang tin tuyen dung theo TUNG CONG TY tren VietnamWorks
    (vd: vietnamworks.com/nha-tuyen-dung/<ten-cong-ty>-c<id>).

    Khac voi trang tim kiem chung cua VietnamWorks (la JavaScript thuan),
    trang theo cong ty nay la HTML tinh, co the doc truc tiep.

    Nhan dien: moi tin la 1 the <a href="https://vietnamworks.com/<slug>-<id>-jv">.
    Dia diem duoc doc tu doan van ban ngay sau tieu de tin (trong pham vi
    gioi han ky tu) vi trang khong co nhan "Dia diem:" co dinh ro rang.

    Do la trang tong hop dung chung cho NHIEU cong ty, "id" tin duoc tao
    tu chinh ID that cua VietnamWorks (on dinh, khong doi).
    """
    soup = BeautifulSoup(html, "html.parser")
    job_pattern = re.compile(r"vietnamworks\.com/[^/?]+-(\d+)-jv")

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

        if job_id not in jobs or len(title) > len(jobs[job_id]["title"]):
            # Doc doan van ban ngay sau the <a> nay (trong pham vi 1 container cha)
            # de tim dia diem, vi trang khong co nhan co dinh ro rang.
            container = a_tag.find_parent(["div", "li", "article"]) or a_tag.parent
            location_text = container.get_text(" ", strip=True) if container else ""

            jobs[job_id] = {
                "id": job_id,
                "title": title,
                "url": href.split("?")[0],
                "location_text": location_text[:400],
                "needs_detail_fetch_for_location": False,
            }

    return list(jobs.values())


PARSERS = {
    "base_ehiring": parse_base_ehiring,
    "successfactors": parse_successfactors,
    "vietinbank": parse_vietinbank,
    "msb": parse_msb,
    "mbbank_api": parse_mbbank_api,
    "talentnetwork": parse_talentnetwork,
    "iviec_api": parse_iviec_api,
    "bidv_api": parse_bidv,
    "vietnamworks_company": parse_vietnamworks_company,
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

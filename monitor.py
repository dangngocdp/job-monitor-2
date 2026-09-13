"""
Website Monitor Bot
--------------------
Quet cac website tuyen dung duoc khai bao trong config.json.
Neu phat hien tin tuyen dung MOI (chua tung gui) -> gui thong bao qua Telegram.
Da gui roi thi khong gui lai (luu vet trong history.json).

Ho tro loc theo dia diem (vi du: chi bao tin o Ha Noi) qua "location_filter"
trong config.json cua tung site. Mac dinh so khop kieu "any" (chi can 1 trong
cac tu khoa xuat hien). Neu can bat buoc TAT CA tu khoa phai xuat hien cung
luc (vi du: vua Ha Noi VUA phong ban Hoi so), dat them
"location_filter_mode": "all" trong config cua site do.

Cac "type" website dang ho tro (xem PARSERS o cuoi file):
- base_ehiring          : nen tang Base E-Hiring (base.vn)      - vd: Sun Group
- successfactors        : nen tang SAP SuccessFactors            - vd: Vietcombank, Techcombank, VPBank
- vietinbank            : trang tuyen dung rieng cua VietinBank (hien dang TAT, xem config)
- msb                   : nen tang PhenomPeople cua MSB
- mbbank_api            : API JSON rieng cua MBBank
- talentnetwork         : nen tang Talentnetwork/CareerViet      - vd: SHB, PVcomBank, BacA Bank
- iviec_api             : nen tang iviec.vn                      - vd: TPBank, SunPhuQuoc Airways, LPBank
- bidv_api              : API JSON rieng cua BIDV
- vietnamworks_company  : trang cong ty tren VietnamWorks (dung chung cho nhieu cong ty) - vd: VietinBank, NCB
- seabank_api           : nen tang rieng cua SeABank

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
# Tien ich chung
# ---------------------------------------------------------------------------

def fetch_html(url: str, verify_ssl: bool = True) -> str:
    """
    verify_ssl=False: dung khi may chu co chung chi SSL cau hinh thieu sot
    (loi "certificate verify failed" do LOI TU PHIA HO, khong phai loi may
    cua ban). Chi nen bat False cho website da xac nhan gap loi nay, vi tat
    xac minh SSL dong nghia bot khong the chac chan dang noi chuyen dung voi
    may chu that (rui ro rat thap voi trang chi doc du lieu cong khai nhu
    o day, nhung van la mot su danh doi bao mat can luu y).
    """
    if not verify_ssl:
        # Tat canh bao "InsecureRequestWarning" de khong lam nhieu log
        requests.packages.urllib3.disable_warnings(
            requests.packages.urllib3.exceptions.InsecureRequestWarning
        )
    resp = requests.get(
        url, headers=REQUEST_HEADERS, timeout=REQUEST_TIMEOUT, verify=verify_ssl
    )
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
# Cac ham parser
# ---------------------------------------------------------------------------

def parse_base_ehiring(html: str, site: dict) -> list:
    """Nen tang Base E-Hiring (base.vn) - vd: Sun Group."""
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
    """Nen tang SAP SuccessFactors - vd: Vietcombank, Techcombank, VPBank."""
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
    """Trang rieng cua VietinBank - HIEN DANG TAT (xem config.json)."""
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
    """Nen tang PhenomPeople cua MSB."""
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
    """API JSON rieng cua MBBank."""
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


TALENTNETWORK_JOB_PATTERN = re.compile(r"/viec-lam/[^/?]+\.([0-9a-fA-F]{6,})\.html")


def parse_talentnetwork(html: str, site: dict) -> list:
    """
    Nen tang Talentnetwork/CareerViet - vd: SHB, PVcomBank, BacA Bank.

    Nhan dien: moi tin la 1 the <a href=".../viec-lam/<slug>.<ma-hex>.html">.
    Ma hex truoc ".html" la ID duy nhat, khong doi -> dung lam khoa chong trung.

    QUAN TRONG (da sua loi so voi ban truoc): dia diem tren cac trang nay
    KHONG luon co nhan "Noi lam viec:" di kem - nhieu trang (vd PVcomBank)
    chi hien thi TRUC TIEP ten tinh/thanh (vi du "Hà Nội") ngay sau tieu de,
    khong co nhan gi ca. Ham nay xu ly ca 2 truong hop: neu co nhan
    "Noi lam viec:" thi doc theo nhan, neu khong thi lay dong van ban DAU
    TIEN xuat hien ngay sau tieu de lam dia diem.
    """
    soup = BeautifulSoup(html, "html.parser")

    jobs = []
    current = None
    current_anchor = None
    awaiting_location = False

    for el in soup.descendants:
        if getattr(el, "name", None) == "a" and el.has_attr("href"):
            href = urljoin(site["url"], el["href"].strip())
            m = TALENTNETWORK_JOB_PATTERN.search(href)
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
                    current_anchor = el
                    awaiting_location = True
                continue
        elif isinstance(el, str) and current is not None and not current["location_text"]:
            # Bo qua text nam BEN TRONG chinh the <a> tieu de (khong phai dia diem)
            if current_anchor is not None and el.find_parent("a") is current_anchor:
                continue
            # Mot NavigableString co the gom nhieu dong (vd HTML khong co tag
            # ngan cach ro rang) -> xet tung dong rieng le cho an toan.
            for raw_line in el.split("\n"):
                line = raw_line.strip()
                if not line:
                    continue
                if line.startswith("Nơi làm việc:"):
                    current["location_text"] = line[len("Nơi làm việc:"):].strip()
                    awaiting_location = False
                    break
                elif awaiting_location:
                    current["location_text"] = line
                    awaiting_location = False
                    break

    if current is not None:
        jobs.append(current)

    return jobs


def parse_iviec_api(html: str, site: dict) -> list:
    """
    Nen tang iviec.vn (centralize-api-v2.iviec.vn) - vd: TPBank,
    SunPhuQuoc Airways, LPBank, VietABank.

    "url" trong config.json la duong dan API. "job_url_prefix" la duong dan
    trang web cong khai de ghep voi slug thanh link cho tung tin.

    Ngoai dia diem (workingNewAddresses), ham nay con doc them TEN PHONG BAN
    tu "recruitmentDeltaDatas" (key "job_department") va ghep chung vao
    location_text -> cho phep loc dong thoi ca dia diem LAN phong ban
    (dung "location_filter_mode": "all" trong config de bat buoc ca 2 dieu
    kien cung xuat hien, vi du VietABank can loc "Hà Nội" VA "Hội sở").
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

        departments = []
        for delta in item.get("recruitmentDeltaDatas") or []:
            if delta.get("workspaceDeltaDataKey") != "job_department":
                continue
            raw_val = delta.get("workspaceDeltaDataValue")
            if not raw_val:
                continue
            try:
                parsed_val = json.loads(raw_val)
                dep_name = parsed_val.get("name_VN")
                if dep_name:
                    departments.append(dep_name)
            except (json.JSONDecodeError, TypeError, AttributeError):
                pass

        location_text = ", ".join(locations)
        if departments:
            dep_text = "Phòng ban: " + ", ".join(departments)
            location_text = f"{location_text} | {dep_text}" if location_text else dep_text

        jobs.append({
            "id": job_id,
            "title": title,
            "url": job_url,
            "location_text": location_text,
            "needs_detail_fetch_for_location": False,
        })

    return jobs


def parse_bidv(html: str, site: dict) -> list:
    """API JSON rieng cua BIDV. Khong co link rieng tung tin."""
    data = json.loads(html)
    jobs = []
    for row in data.get("rows", []):
        job_id = str(row.get("id", "")).strip()
        if not job_id:
            continue
        title = row.get("title") or f"Tin tuyen dung #{job_id}"

        desc_html = row.get("descriptionjob", "") or ""
        location_text = BeautifulSoup(desc_html, "html.parser").get_text(" ", strip=True)
        location_text = location_text[:400]

        jobs.append({
            "id": job_id,
            "title": title,
            "url": site.get("listing_url", site["url"]),
            "location_text": location_text,
            "needs_detail_fetch_for_location": False,
        })

    return jobs


VIETNAMWORKS_JOB_PATTERN = re.compile(r"vietnamworks\.com/[^/?]+-(\d+)-jv")


def parse_vietnamworks_company(html: str, site: dict) -> list:
    """
    Trang tin tuyen dung theo TUNG CONG TY tren VietnamWorks
    (vd: vietnamworks.com/nha-tuyen-dung/<ten-cong-ty>-c<id>).
    Dung chung cho nhieu cong ty: vd VietinBank, NCB.
    """
    soup = BeautifulSoup(html, "html.parser")

    jobs = {}
    for a_tag in soup.find_all("a", href=True):
        href = urljoin(site["url"], a_tag["href"].strip())
        m = VIETNAMWORKS_JOB_PATTERN.search(href.split("?")[0])
        if not m:
            continue

        job_id = m.group(1)
        title = a_tag.get_text(strip=True)
        if not title:
            continue

        if job_id not in jobs or len(title) > len(jobs[job_id]["title"]):
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


def parse_seabank(html: str, site: dict) -> list:
    """
    Nen tang rieng cua SeABank (tuyendung.seabank.com.vn).

    Nhan dien: moi tin la 1 the <a href=".../jobs/<slug>.<id>"> (KHONG co
    duoi ".html" nhu Talentnetwork). "url" trong config.json nen la duong
    dan da loc san dia diem qua tham so URL (vi du jobLocations=4 = Ha Noi),
    nen KHONG can doc them dia diem tu HTML - chi can dam bao khong loc gi
    them (location_filter de trong []) vi server da loc dung tu truoc.
    """
    soup = BeautifulSoup(html, "html.parser")
    job_pattern = re.compile(r"/jobs/[^/?]+\.(\d+)$")

    jobs = {}
    for a_tag in soup.find_all("a", href=True):
        href = urljoin(site["url"], a_tag["href"].strip())
        href_no_query = href.split("?")[0]
        m = job_pattern.search(href_no_query)
        if not m:
            continue

        job_id = m.group(1)
        title = a_tag.get_text(strip=True)
        if not title:
            continue

        if job_id not in jobs or len(title) > len(jobs[job_id]["title"]):
            jobs[job_id] = {
                "id": job_id,
                "title": title,
                "url": href_no_query,
                "location_text": "",  # URL da loc san dia diem phia server
                "needs_detail_fetch_for_location": False,
            }

    return list(jobs.values())


TOPCV_JOB_PATTERN = re.compile(r"/viec-lam/[^/?]+/(\d+)\.html")

# Cac dong van ban CHAC CHAN khong phai dia diem (luong, nut bam, thoi gian
# cap nhat...) -> bo qua, tiep tuc cho den khi gap dong hop le.
NON_LOCATION_LINE_PATTERN = re.compile(
    r"(thoả thuận|thỏa thuận|triệu|usd|\$|ứng tuyển|cập nhật|lương|"
    r"^\d+[\d.,]*\s*-\s*\d)",
    re.IGNORECASE,
)


def parse_topcv_company(html: str, site: dict) -> list:
    """
    Trang tin tuyen dung theo TUNG CONG TY tren TopCV
    (vd: topcv.vn/cong-ty/<ten-cong-ty>-cid<id>/tuyen-dung.html).

    Nhan dien: moi tin la 1 the <a href="https://topcv.vn/viec-lam/<slug>/<id>.html">.
    ID so cuoi URL la duy nhat, khong doi -> dung lam khoa chong trung.

    Dia diem hien thi dang chu TRAN (vi du "Hà Nội") ngay sau tieu de tin,
    khong co nhan co dinh -> quet tuan tu giong nhu Talentnetwork: lay dong
    van ban DAU TIEN xuat hien ngay sau tieu de lam dia diem.
    """
    soup = BeautifulSoup(html, "html.parser")

    jobs = []
    current = None
    current_anchor = None
    awaiting_location = False

    for el in soup.descendants:
        if getattr(el, "name", None) == "a" and el.has_attr("href"):
            href = urljoin(site["url"], el["href"].strip())
            m = TOPCV_JOB_PATTERN.search(href.split("?")[0])
            if m:
                job_id = m.group(1)
                title = el.get_text(strip=True)
                if title and (current is None or current["id"] != job_id):
                    if current is not None:
                        jobs.append(current)
                    current = {
                        "id": job_id,
                        "title": title,
                        "url": href.split("?")[0],
                        "location_text": "",
                        "needs_detail_fetch_for_location": False,
                    }
                    current_anchor = el
                    awaiting_location = True
                continue
        elif isinstance(el, str) and current is not None and not current["location_text"]:
            # Bo qua text nam trong BAT KY the <a> nao (vi du link ten cong ty)
            # - dia diem that luon la text tran, khong nam trong link.
            if el.find_parent("a") is not None:
                continue
            for raw_line in el.split("\n"):
                line = raw_line.strip()
                if not line:
                    continue
                if awaiting_location:
                    if NON_LOCATION_LINE_PATTERN.search(line):
                        continue  # bo qua dong luong/nut bam, tiep tuc cho
                    current["location_text"] = line
                    awaiting_location = False
                    break

    if current is not None:
        jobs.append(current)

    return jobs


def parse_wordpress_posts(html: str, site: dict) -> list:
    """
    Trang tuyen dung dang WordPress custom post type - vd: TCEX.

    Nhan dien: moi tin la 1 the <a href="<domain>/<slug-thu-muc>/<slug-tin>/">
    voi "job_url_prefix" khai bao truoc trong config.json. Vi WordPress
    permalink KHONG doi qua thoi gian, dung chinh slug lam ID chong trung
    (khong can ID so).

    KHONG doc dia diem (nhieu site dang WordPress khong co truong dia diem
    ro rang trong danh sach) -> de "location_filter": [] trong config.json
    cho loai site nay de nhan tat ca tin, tru khi duoc cau hinh rieng.
    """
    prefix = site["job_url_prefix"]
    soup = BeautifulSoup(html, "html.parser")

    jobs = {}
    for a_tag in soup.find_all("a", href=True):
        href = urljoin(site["url"], a_tag["href"].strip())
        href_no_query = href.split("?")[0].rstrip("/")

        if not href_no_query.startswith(prefix.rstrip("/")):
            continue

        slug = href_no_query[len(prefix.rstrip("/")):].strip("/")
        if not slug:
            continue

        title = a_tag.get_text(strip=True)
        if not title:
            continue

        if slug not in jobs or len(title) > len(jobs[slug]["title"]):
            jobs[slug] = {
                "id": slug,
                "title": title,
                "url": href_no_query + "/",
                "location_text": "",
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
    "seabank_api": parse_seabank,
    "topcv_company": parse_topcv_company,
    "wordpress_posts": parse_wordpress_posts,
}

DETAIL_LOCATION_FETCHERS = {
    "base_ehiring": get_location_base_ehiring,
}


def location_matches_filter(location_text: str, location_filter: list, mode: str = "any") -> bool:
    """
    So khop dang chuoi con, khong phan biet hoa/thuong.
    mode="any" (mac dinh): CHI CAN 1 trong cac tu khoa xuat hien.
    mode="all": BAT BUOC TAT CA tu khoa phai cung xuat hien (vd loc dong
    thoi ca dia diem lan phong ban).
    """
    normalized = location_text.lower()
    terms = [t.strip().lower() for t in location_filter if t.strip()]
    if not terms:
        return True
    if mode == "all":
        return all(t in normalized for t in terms)
    return any(t in normalized for t in terms)


# ---------------------------------------------------------------------------
# Xu ly logic chinh cho 1 site
# ---------------------------------------------------------------------------

def process_site(site: dict, history: dict) -> bool:
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
    verify_ssl = site.get("verify_ssl", True)
    try:
        html = fetch_html(site["url"], verify_ssl=verify_ssl)
    except requests.RequestException as exc:
        logger.error("[%s] Khong tai duoc trang web: %s", name, exc)
        send_telegram_message(
            f"⚠️ <b>{name}</b>\nKhong the tai website de kiem tra tin tuyen dung.\n"
            f"Loi: {exc}"
        )
        return False

    try:
        jobs = parser(html, site)
    except Exception as exc:  # noqa: BLE001
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
    filter_mode = site.get("location_filter_mode", "any")
    detail_fetcher = DETAIL_LOCATION_FETCHERS.get(site_type)

    processed_ids = []
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
            if not location_matches_filter(job["location_text"], location_filter, filter_mode):
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
        time.sleep(0.5)

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

"""
Fotocasa.es scraper for Valencia Province property listings.
Extracts structured JSON data embedded in page HTML via simple HTTP requests.
No browser/Playwright needed - fast and reliable.

Usage:
    python scraper.py                    # Scrape all pages
    python scraper.py --max-pages 10     # Scrape first 10 pages
    python scraper.py --start-page 50    # Resume from page 50
"""

import csv
import re
import json
import time
import random
import logging
from pathlib import Path
from datetime import datetime
from math import ceil

import requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("scraper.log", mode="w"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger(__name__)

BASE_URL = "https://www.fotocasa.es/es/comprar/viviendas/valencia-provincia/todas-las-zonas/l"
OUTPUT_FILE = "valencia_houses.csv"
LISTINGS_PER_PAGE = 31

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
]

HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
    "Connection": "keep-alive",
    "Referer": "https://www.fotocasa.es/es/comprar/viviendas/valencia-provincia/todas-las-zonas/l",
}

SUBTYPE_MAP = {
    "Flat": "Piso",
    "Apartment": "Apartamento",
    "House_Chalet": "Casa o chalet",
    "Attic": "Ático",
    "Duplex": "Dúplex",
    "Loft": "Loft",
    "Studio": "Estudio",
    "Study": "Estudio",
    "Ground_floor": "Planta baja",
    "GroundFloor": "Planta baja",
    "GroundFloorWithGarden": "Planta baja con jardín",
    "Townhouse": "Casa adosada",
    "SemidetachedHouse": "Casa adosada",
    "Country_house": "Casa rústica",
    "CountryHouse": "Casa rústica",
    "Penthouse": "Ático",
}

FEATURE_KEYS = {
    "air_conditioner": "has_air_conditioning",
    "parking": "has_parking",
    "terrace": "has_terrace",
    "elevator": "has_elevator",
    "balcony": "has_balcony",
    "pool": "has_pool",
    "garden": "has_garden",
    "heating": "has_heating",
    "storage_room": "has_storage",
    "furnished": "is_furnished",
}

CSV_HEADERS = [
    "id",
    "title",
    "property_type",
    "property_subtype",
    "price_eur",
    "price_per_m2",
    "price_dropped",
    "price_drop_eur",
    "surface_m2",
    "bedrooms",
    "bathrooms",
    "floor",
    "province",
    "city",
    "district",
    "neighborhood",
    "county",
    "zip_code",
    "latitude",
    "longitude",
    "has_elevator",
    "has_parking",
    "has_terrace",
    "has_balcony",
    "has_pool",
    "has_garden",
    "has_air_conditioning",
    "has_heating",
    "has_storage",
    "is_furnished",
    "conservation_status",
    "antiquity",
    "listing_age_days",
    "is_new_construction",
    "is_bank_property",
    "is_auction",
    "agency",
    "agency_type",
    "url",
    "scraped_at",
]

CONSERVATION_MAP = {
    1: "Nuevo",
    2: "Casi nuevo",
    3: "Muy bien",
    4: "Bien",
    5: "A reformar",
}


def get_feature_value(features: list, key: str, default=None):
    """Extract a feature value from the features array."""
    for feat in features:
        if feat.get("key") == key:
            return feat.get("value")
    return default


def has_feature(features: list, key: str) -> bool:
    """Check if a boolean-like feature exists and is truthy."""
    val = get_feature_value(features, key)
    return val is not None and val > 0


def parse_listing(listing: dict) -> dict:
    """Convert a raw listing from the API into a flat CSV row."""
    features = listing.get("features", [])
    address = listing.get("address", {})
    coords = listing.get("coordinates", {})
    date_info = listing.get("date", {})
    detail = listing.get("detail", {})

    raw_price = listing.get("rawPrice")
    surface = get_feature_value(features, "surface")
    price_per_m2 = round(raw_price / surface) if (raw_price and surface) else None

    # Listing age in days
    listing_age_days = None
    if date_info:
        diff = date_info.get("diff", 0)
        unit = date_info.get("unit", "")
        if unit == "DAYS":
            listing_age_days = diff
        elif unit == "HOURS":
            listing_age_days = 0
        elif unit == "MONTHS":
            listing_age_days = diff * 30

    # Price drop
    reduced_price_str = listing.get("reducedPrice", "")
    price_drop = None
    if reduced_price_str:
        nums = re.findall(r"[\d.]+", str(reduced_price_str).replace(".", ""))
        if nums:
            try:
                price_drop = int(nums[0])
            except ValueError:
                pass

    # URL
    url = ""
    if isinstance(detail, dict):
        url_path = detail.get("es-ES", "")
        if url_path:
            url = f"https://www.fotocasa.es{url_path}"

    # Conservation status
    conservation_val = get_feature_value(features, "conservationStatus")
    conservation = CONSERVATION_MAP.get(conservation_val, "")

    # Property type mapping
    subtype_raw = listing.get("buildingSubtype", "")
    property_subtype = SUBTYPE_MAP.get(subtype_raw, subtype_raw)

    # Determine broad category from subtype (buildingType is unreliable - often always "Flat")
    CASA_SUBTYPES = {"Casa o chalet", "Casa adosada", "Casa rústica", "Planta baja con jardín"}
    if property_subtype in CASA_SUBTYPES:
        property_type = "Casa"
    elif property_subtype in {"Piso", "Apartamento", "Ático", "Dúplex", "Loft", "Estudio", "Planta baja"}:
        property_type = "Piso"
    else:
        property_type = "Otro"

    floor_val = get_feature_value(features, "floor")

    return {
        "id": listing.get("id") or listing.get("realEstateAdId"),
        "title": f"{property_subtype} en {address.get('district') or address.get('municipality', '')}",
        "property_type": property_type,
        "property_subtype": property_subtype,
        "price_eur": raw_price,
        "price_per_m2": price_per_m2,
        "price_dropped": bool(reduced_price_str),
        "price_drop_eur": price_drop,
        "surface_m2": surface,
        "bedrooms": get_feature_value(features, "rooms"),
        "bathrooms": get_feature_value(features, "bathrooms"),
        "floor": floor_val,
        "province": (address.get("province") or "").strip(),
        "city": (address.get("municipality") or "").strip(),
        "district": (address.get("district") or "").strip(),
        "neighborhood": (address.get("neighborhood") or "").strip(),
        "county": (address.get("county") or "").strip(),
        "zip_code": (address.get("zipCode") or "").strip(),
        "latitude": coords.get("latitude"),
        "longitude": coords.get("longitude"),
        "has_elevator": has_feature(features, "elevator"),
        "has_parking": has_feature(features, "parking"),
        "has_terrace": has_feature(features, "terrace"),
        "has_balcony": has_feature(features, "balcony"),
        "has_pool": has_feature(features, "pool"),
        "has_garden": has_feature(features, "garden"),
        "has_air_conditioning": has_feature(features, "air_conditioner"),
        "has_heating": has_feature(features, "heating"),
        "has_storage": has_feature(features, "storage_room"),
        "is_furnished": has_feature(features, "furnished"),
        "conservation_status": conservation,
        "antiquity": get_feature_value(features, "antiquity"),
        "listing_age_days": listing_age_days,
        "is_new_construction": listing.get("isNewConstruction", False),
        "is_bank_property": listing.get("isOpportunity", False),
        "is_auction": listing.get("isAuctioned", False),
        "agency": listing.get("clientAlias", ""),
        "agency_type": listing.get("clientType", ""),
        "url": url,
        "scraped_at": datetime.now().isoformat(),
    }


def fetch_page(session: requests.Session, page_num: int) -> tuple[list[dict], int]:
    """Fetch a page and return (listings, total_count)."""
    if page_num == 1:
        url = BASE_URL
    else:
        url = f"{BASE_URL}/{page_num}"

    headers = {**HEADERS, "User-Agent": random.choice(USER_AGENTS)}
    resp = session.get(url, headers=headers, timeout=30)

    if resp.status_code != 200:
        log.warning(f"HTTP {resp.status_code} for page {page_num}")
        return [], 0

    if "INTERRUPCI" in resp.text.upper():
        log.warning(f"BLOCKED on page {page_num}")
        return [], -1

    # Extract __INITIAL_PROPS__ JSON from HTML
    match = re.search(
        r"window\.__INITIAL_PROPS__\s*=\s*JSON\.parse\('(.+?)'\);",
        resp.text,
        re.DOTALL,
    )
    if not match:
        log.warning(f"No __INITIAL_PROPS__ found on page {page_num}")
        return [], 0

    raw = match.group(1)
    raw = raw.replace("\\'", "'")
    raw = raw.replace("\\\\", "\\")

    try:
        props = json.loads(raw)
    except json.JSONDecodeError as e:
        log.error(f"JSON parse error on page {page_num}: {e}")
        return [], 0

    search_result = props.get("initialSearch", {}).get("result", {})
    raw_listings = search_result.get("realEstates", [])
    total_count = search_result.get("count", 0)

    parsed = []
    for listing in raw_listings:
        try:
            parsed.append(parse_listing(listing))
        except Exception as e:
            log.warning(f"Error parsing listing: {e}")

    return parsed, total_count


def save_to_csv(listings: list[dict], filepath: str, write_header: bool = False):
    """Write/append listings to CSV."""
    mode = "w" if write_header else "a"
    with open(filepath, mode, newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
        if write_header:
            writer.writeheader()
        writer.writerows(listings)


def main(max_pages: int = None, start_page: int = 1):
    log.info("Starting fotocasa scraper for Valencia Province")

    session = requests.Session()
    total_scraped = 0
    consecutive_errors = 0
    write_header = start_page == 1

    # First page to get total count
    listings, total_count = fetch_page(session, start_page)
    if total_count <= 0:
        log.error("Failed to get initial page. Exiting.")
        return

    total_pages = ceil(total_count / LISTINGS_PER_PAGE)
    if max_pages:
        total_pages = min(total_pages, max_pages)

    log.info(f"Total listings: {total_count}, Pages to scrape: {total_pages}")

    if listings:
        save_to_csv(listings, OUTPUT_FILE, write_header=write_header)
        total_scraped += len(listings)
        log.info(f"Page {start_page}: {len(listings)} listings. Total: {total_scraped}")

    for page_num in range(start_page + 1, total_pages + 1):
        # Rate limiting - longer delays to avoid detection
        delay = random.uniform(3.0, 6.0)
        time.sleep(delay)

        listings, count = fetch_page(session, page_num)

        if count == -1:  # Blocked
            consecutive_errors += 1
            wait_time = 30 + (consecutive_errors * 15)
            log.warning(f"Blocked! Waiting {wait_time}s... (error {consecutive_errors}/5)")
            if consecutive_errors >= 5:
                log.error("Too many blocks. Stopping.")
                break
            time.sleep(wait_time)
            # Reset session to get fresh connection
            session.close()
            session = requests.Session()
            continue

        if not listings:
            consecutive_errors += 1
            if consecutive_errors >= 5:
                log.error("Too many empty pages. Stopping.")
                break
            continue

        consecutive_errors = 0
        save_to_csv(listings, OUTPUT_FILE, write_header=False)
        total_scraped += len(listings)

        if page_num % 10 == 0:
            log.info(f"Page {page_num}/{total_pages}: {len(listings)} listings. Total: {total_scraped}")
        elif page_num % 5 == 0:
            log.info(f"Page {page_num}/{total_pages}. Total: {total_scraped}")

    log.info(f"DONE! Scraped {total_scraped} listings across {total_pages} pages -> {OUTPUT_FILE}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Scrape fotocasa.es Valencia Province")
    parser.add_argument("--max-pages", type=int, default=None, help="Max pages (default: all)")
    parser.add_argument("--start-page", type=int, default=1, help="Start page (default: 1)")
    args = parser.parse_args()

    main(max_pages=args.max_pages, start_page=args.start_page)

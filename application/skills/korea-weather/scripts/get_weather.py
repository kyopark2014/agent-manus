#!/usr/bin/env python3
"""
Korean weather CLI (KMA Weather Nuri + AirKorea).

Dong-level digital forecast, current weather, and air quality. No API key required.

Location resolution when location is empty / "current location":
1) Home address from AgentCore memory (if available)
2) Approximate city via public IP geolocation
3) Ask the user if both fail
"""
from __future__ import annotations

import argparse
import logging
import os
import re
import sys
import urllib.parse

import requests
from bs4 import BeautifulSoup

# Optional: application/ for mcp_memory (home-address fallback)
_APP_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if _APP_DIR not in sys.path:
    sys.path.insert(0, _APP_DIR)

logging.basicConfig(
    level=logging.INFO,
    format="%(filename)s:%(lineno)d | %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)],
)
logger = logging.getLogger("korea-weather")

BASE_URL = "https://www.weather.go.kr"
PLACE_SEARCH_URL = f"{BASE_URL}/w/renew2021/rest/main/place-search.do"
DONG_INFO_URL = f"{BASE_URL}/w/rest/zone/dongInfo.do"
DIGITAL_FORECAST_URL = f"{BASE_URL}/w/wnuri-fct2021/main/digital-forecast.do"
CURRENT_WEATHER_URL = f"{BASE_URL}/w/wnuri-fct2021/main/current-weather.do"
SHORT_TERM_URL = f"{BASE_URL}/w/weather/forecast/short-term.do"
AIRKOREA_FULL_URL = "https://www.airkorea.or.kr/web/dustForecast?pMENU_NO=113"
# Free IP geolocation (no API key). Prefer HTTPS mirror when available.
IP_GEO_URL = "http://ip-api.com/json/"

# Treat these as "use my current location" rather than a place name.
CURRENT_LOCATION_ALIASES = {
    "",
    "현재위치",
    "현재 위치",
    "내위치",
    "내 위치",
    "여기",
    "근처",
    "현위치",
    "current",
    "current location",
    "here",
    "my location",
}

ASK_USER_FOR_LOCATION = (
    "LOCATION_NEEDED: 저장된 집 주소(memory)와 IP 대략 위치 모두로 "
    "현재 위치를 확인할 수 없습니다. "
    "날씨를 알려드리려면 지역명을 알려주세요. "
    "예: 서울 서초구, 반포3동, 강남구, 부산 해운대"
)

# KMA / AirKorea page links (labels shown to users in Korean)
WEATHER_PAGE_LINKS = {
    "날씨누리 메인(지도)": f"{BASE_URL}/w/index.do",
    "날씨지도": f"{BASE_URL}/wgis-nuri/html/map.html",
    "단기예보(광역)": SHORT_TERM_URL,
    "분석일기도": f"{BASE_URL}/w/image/chart/analysis.do",
    "대기질예보": AIRKOREA_FULL_URL,
    "황사일기도": f"{BASE_URL}/w/dust/image/sfc-chart.do",
    "지역별 관측": f"{BASE_URL}/w/weather/land/aws-obs.do",
}

# stnId tool: forecast office → representative location name
STNID_TO_LOCATION = {
    108: "서울",
    109: "서울",
    105: "춘천",
    131: "청주",
    133: "대전",
    146: "전주",
    156: "광주",
    143: "대구",
    159: "부산",
    184: "제주",
}

# location → AirKorea region (table column name)
LOCATION_TO_AIR_REGION = {
    "서울": "서울", "인천": "인천", "수원": "경기", "성남": "경기", "고양": "경기",
    "용인": "경기", "안양": "경기", "부천": "경기", "화성": "경기", "평택": "경기",
    "서초": "서울", "강남": "서울", "잠원": "서울", "반포": "서울",
    "춘천": "강원", "강릉": "강원", "원주": "강원", "속초": "강원", "홍천": "강원",
    "대전": "대전", "세종": "세종", "청주": "충북", "충주": "충북", "천안": "충남",
    "아산": "충남", "서산": "충남", "전주": "전북", "군산": "전북", "광주": "광주",
    "여수": "전남", "목포": "전남", "순천": "전남", "대구": "대구", "포항": "경북",
    "경주": "경북", "안동": "경북", "부산": "부산", "울산": "울산", "창원": "경남",
    "김해": "경남", "진주": "경남", "통영": "경남", "제주": "제주",
}

REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
    "Referer": f"{BASE_URL}/w/index.do",
}

JSON_HEADERS = {
    **REQUEST_HEADERS,
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "X-Requested-With": "XMLHttpRequest",
}


def fetch_page(url: str, params: dict | None = None, headers: dict | None = None) -> str | None:
    """Fetch page HTML/text."""
    try:
        resp = requests.get(
            url, params=params or {}, headers=headers or REQUEST_HEADERS, timeout=15
        )
        resp.raise_for_status()
        resp.encoding = "utf-8"
        return resp.text
    except Exception as e:
        logger.error(f"Page request failed {url}: {e}")
        return None


def fetch_json(url: str, params: dict | None = None) -> list | dict | None:
    """Call a JSON API endpoint."""
    try:
        resp = requests.get(url, params=params or {}, headers=JSON_HEADERS, timeout=15)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logger.error(f"JSON request failed {url}: {e}")
        return None


def search_location(query: str) -> dict | None:
    """Search location name → administrative dong code / coordinates."""
    results = fetch_json(
        PLACE_SEARCH_URL, {"query": query, "start": 1, "src": "A2"}
    )
    if not results or not isinstance(results, list):
        return None

    # Prefer results whose address matches more query tokens (e.g. Banpo 3-dong)
    tokens = [t for t in re.split(r"\s+", query.strip()) if t]
    def score(item: dict) -> tuple:
        addr = item.get("address") or ""
        title = item.get("title") or ""
        blob = f"{addr} {title}"
        hit = sum(1 for t in tokens if t in blob)
        # Bonus when a dong name token appears in the address
        dong_bonus = 2 if any(t.endswith("동") and t in addr for t in tokens) else 0
        has_code = 1 if item.get("dongCode") else 0
        return (hit + dong_bonus, has_code)

    ranked = sorted(results, key=score, reverse=True)
    r = ranked[0]
    dong_code = r.get("dongCode") or ""
    if not dong_code:
        return None

    # Normalize name/coords via dongInfo (place-search address may be POI-based)
    wide = city = dong_name = ""
    lat = r.get("latitude")
    lon = r.get("longitude")
    info = fetch_json(DONG_INFO_URL, {"dong": dong_code})
    if isinstance(info, dict):
        wide = (info.get("wide") or {}).get("name") or ""
        city = (info.get("city") or {}).get("name") or ""
        dong = info.get("dong") or {}
        dong_name = dong.get("name") or ""
        if dong.get("lat"):
            try:
                lat = float(dong["lat"])
            except (TypeError, ValueError):
                pass
        if dong.get("lon"):
            try:
                lon = float(dong["lon"])
            except (TypeError, ValueError):
                pass

    if wide and city and dong_name:
        display = f"{wide} {city} {dong_name}"
        address = display
    else:
        address = r.get("address") or r.get("title") or query
        display = address

    return {
        "name": display,
        "address": address,
        "title": r.get("title") or "",
        "dongCode": dong_code,
        "lat": lat,
        "lon": lon,
        "x": r.get("x"),
        "y": r.get("y"),
    }


def dong_page_url(loc: dict) -> str:
    """Build Weather Nuri dong-level deep link."""
    code = loc["dongCode"]
    lat = loc.get("lat") or 0
    lon = loc.get("lon") or 0
    label = urllib.parse.quote(loc.get("address") or loc.get("name") or "")
    return (
        f"{BASE_URL}/w/index.do#dong/{code}/{lat}/{lon}/{label}/LOC/"
        f"%EC%9C%84%EA%B2%BD%EB%8F%84({lat:.2f},{lon:.2f})"
    )


def get_air_region(location: str) -> str | None:
    """Map a location name to an AirKorea region name."""
    location = (location or "").strip()
    if location in LOCATION_TO_AIR_REGION:
        return LOCATION_TO_AIR_REGION[location]
    for name, region in LOCATION_TO_AIR_REGION.items():
        if name in location or location in name:
            return region
    return None


def _is_current_location_request(location: str) -> bool:
    """True when the caller wants approximate 'here' instead of a named place."""
    return (location or "").strip().lower() in CURRENT_LOCATION_ALIASES


def resolve_location_from_ip() -> dict | None:
    """
    Approximate location from the server's public IP (ip-api.com).
    Returns search_location()-compatible dict, or None on failure.
    """
    try:
        resp = requests.get(
            IP_GEO_URL,
            params={
                "lang": "ko",
                "fields": "status,message,country,countryCode,regionName,city,lat,lon,query",
            },
            headers={"User-Agent": REQUEST_HEADERS["User-Agent"]},
            timeout=8,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        logger.warning(f"IP geolocation request failed: {e}")
        return None

    if not isinstance(data, dict) or data.get("status") != "success":
        logger.warning(f"IP geolocation unsuccessful: {data}")
        return None

    country = data.get("countryCode") or ""
    city = (data.get("city") or "").strip()
    region = (data.get("regionName") or "").strip()
    lat = data.get("lat")
    lon = data.get("lon")
    logger.info(
        f"IP geolocation: ip={data.get('query')}, country={country}, "
        f"region={region}, city={city}, lat={lat}, lon={lon}"
    )

    # Normalize English KMA/ip-api labels into Korean search queries.
    eng_city = {
        "Seoul": "서울", "Busan": "부산", "Daegu": "대구", "Incheon": "인천",
        "Gwangju": "광주", "Daejeon": "대전", "Ulsan": "울산", "Sejong": "세종",
        "Jeju": "제주", "Suwon": "수원",
    }
    region_ko = eng_city.get(region, region)
    city_ko = city
    # Songpa-gu → 송파구 style
    m = re.match(r"([A-Za-z]+)-gu$", city, re.I)
    if m:
        # Keep latin stem for place-search; also try with parent city
        city_ko = city
    if city in eng_city:
        city_ko = eng_city[city]

    queries: list[str] = []
    if country == "KR":
        if city_ko and region_ko and city_ko != region_ko:
            queries.append(f"{region_ko} {city_ko}")
        if re.match(r"[A-Za-z]+-gu$", city, re.I) and region_ko:
            # e.g. "서울 Songpa-gu" and "서울 송파" heuristics via place-search
            queries.append(f"{region_ko} {city.replace('-gu', '구')}")
            queries.append(f"{region_ko} {city.split('-')[0]}")
        if city_ko:
            queries.append(city_ko)
        if region_ko:
            queries.append(region_ko)
    else:
        if city_ko:
            queries.append(city_ko)
        if region_ko:
            queries.append(region_ko)

    # Dedupe
    seen = set()
    uniq_queries = []
    for q in queries:
        q = q.strip()
        if q and q not in seen:
            seen.add(q)
            uniq_queries.append(q)

    for q in uniq_queries:
        loc = search_location(q)
        if loc:
            loc["resolved_via"] = "ip"
            loc["resolved_query"] = q
            loc["ip"] = data.get("query")
            return loc

    return None


def resolve_location_from_memory() -> dict | None:
    """
    Look up home/residence address via recall_home_location.py (AgentCore memory).
    Returns search_location()-compatible dict, or None.
    """
    try:
        from recall_home_location import recall_home_location
    except Exception as e:
        logger.warning(f"recall_home_location import failed: {e}")
        return None

    result = recall_home_location()
    if result.get("status") != "ok":
        if result.get("error"):
            logger.warning(result["error"])
        else:
            logger.info("memory recall returned no usable location")
        return None

    candidates = result.get("candidates") or []
    if result.get("location") and result["location"] not in candidates:
        candidates = [result["location"], *candidates]

    for candidate in candidates:
        loc = search_location(candidate)
        if loc:
            loc["resolved_via"] = "memory"
            loc["resolved_query"] = candidate
            return loc

    return None


def resolve_auto_location() -> tuple[dict | None, str]:
    """
    Resolve location when user asked for current/here location.
    Order: memory home address → IP approximate → ask user.
    Returns (loc_dict or None, source note).
    """
    loc = resolve_location_from_memory()
    if loc:
        note = (
            f"저장된 집 주소(memory) 기준: {loc.get('name')} "
            f"(조회어: {loc.get('resolved_query')})"
        )
        return loc, note

    loc = resolve_location_from_ip()
    if loc:
        note = (
            f"IP 대략 위치 기준: {loc.get('name')} "
            f"(조회어: {loc.get('resolved_query')}, IP: {loc.get('ip', '-')})"
        )
        return loc, note

    return None, ASK_USER_FOR_LOCATION


def _strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", " ", text)


def _clean_air_value(text: str) -> str:
    """Strip junk text such as legend labels from air-quality values."""
    text = re.sub(r"\s+", "", text or "")
    text = re.sub(r"(초미세먼지|미세먼지|오존)?범례보기", "", text)
    return text


def parse_current_weather(html: str) -> dict:
    """Parse current-weather HTML."""
    if not html:
        return {}
    soup = BeautifulSoup(html, "html.parser")
    lines = [
        line.strip().replace("\xa0", " ")
        for line in soup.get_text().split("\n")
        if line.strip()
    ]
    result: dict = {}

    # Weather condition is often in the icon title attribute
    wic = soup.select_one(".wic[title], span.wic")
    if wic:
        sky = (wic.get("title") or wic.get_text(strip=True) or "").strip()
        sky = re.sub(r"^(현재\s*)?날씨\s*", "", sky)
        if sky and "기온" not in sky:
            result["날씨"] = sky

    for i, line in enumerate(lines):
        if re.match(r"\d{2}\.\d{2}\.\([가-힣]\) \d{2}:\d{2} 현재", line):
            result["관측시각"] = line
        if line == "날씨:" and i + 1 < len(lines):
            nxt = lines[i + 1]
            if not nxt.startswith("기온") and "℃" not in nxt[:3]:
                result["날씨"] = nxt
        if line.startswith("기온:"):
            temp_match = re.search(r"([-\d.]+)℃", line)
            if temp_match:
                result["기온"] = temp_match.group(1)
            max_match = re.search(r"최고\s*([-\d.]+)", line)
            if max_match:
                result["오늘최고"] = max_match.group(1)
            min_match = re.search(r"최저\s*([-\d.]+)", line)
            if min_match:
                result["오늘최저"] = min_match.group(1)
        if line.startswith("체감(") and "℃" in line:
            feels = re.search(r"체감\(([-\d.]+)℃\)", line)
            if feels:
                result["체감온도"] = feels.group(1)
        if "어제보다" in line:
            result["어제대비"] = line
        if line == "습도" and i + 1 < len(lines):
            result["습도"] = lines[i + 1]
        elif line.startswith("습도") and "%" in line:
            result["습도"] = line.replace("습도", "").strip()
        if line == "바람" and i + 1 < len(lines):
            result["바람"] = lines[i + 1]
        elif line.startswith("바람") and ("m/s" in line or "km/h" in line):
            result["바람"] = line.replace("바람", "").strip()
        if line == "1시간강수량" and i + 1 < len(lines):
            result["1시간강수량"] = lines[i + 1]
        if line == "일출" and i + 1 < len(lines):
            result["일출"] = lines[i + 1]
        if line == "일몰" and i + 1 < len(lines):
            result["일몰"] = lines[i + 1]
        if "초미세먼지(PM2.5)" in line and i + 1 < len(lines):
            result["초미세먼지"] = _clean_air_value(lines[i + 1])
        if "미세먼지(PM10)" in line and i + 1 < len(lines):
            result["미세먼지"] = _clean_air_value(lines[i + 1])
        if "오존(O3)" in line and i + 1 < len(lines):
            result["오존"] = _clean_air_value(lines[i + 1])

    return result


def _li_field(item, *labels: str) -> str | None:
    """Extract the display value from a ul.item li whose hid label matches."""
    for li in item.select("li"):
        hid = li.select_one("span.hid")
        if not hid:
            continue
        hid_text = hid.get_text(strip=True)
        if not any(lab in hid_text for lab in labels):
            continue
        # Wind: prefer title attribute
        wspd = li.select_one(".wspd")
        if wspd:
            title = (wspd.get("title") or "").strip()
            text = wspd.get_text(" ", strip=True)
            if title and title not in ("-", ""):
                return title if text in ("-", "") else f"{title} {text}".strip()
            return text or title or None
        # Heat-wave impact level
        lvl = li.select_one("[class*=lvl-]")
        if lvl:
            return lvl.get_text(strip=True) or None
        # Remaining text excluding hid (includes nested span.unit)
        clone_parts = []
        for child in li.children:
            name = getattr(child, "name", None)
            if name is None:
                t = str(child).strip()
                if t:
                    clone_parts.append(t)
                continue
            classes = child.get("class") or []
            if "hid" in classes:
                continue
            clone_parts.append(child.get_text(" ", strip=True))
        val = re.sub(r"\s+", " ", " ".join(clone_parts)).strip()
        return val or None
    return None


def parse_digital_forecast(html: str) -> dict:
    """Parse daily and hourly forecast from digital-forecast HTML."""
    if not html:
        return {}
    soup = BeautifulSoup(html, "html.parser")
    daily: list[dict] = []
    seen: set[str] = set()

    for slide in soup.select(".dfs-daily-slide"):
        date = slide.get("data-date") or ""
        if not date or date in seen:
            continue
        seen.add(date)
        label_el = slide.select_one("h4")
        label = label_el.get_text(strip=True) if label_el else date
        min_temp = max_temp = None
        mm = slide.select_one(".daily-minmax")
        if mm:
            texts = mm.get_text(" ", strip=True)
            m_min = re.search(r"최저\s*:\s*([-\d.]+℃?|-)", texts)
            m_max = re.search(r"최고\s*:\s*([-\d.]+℃?|-)", texts)
            if m_min:
                min_temp = m_min.group(1)
            if m_max:
                max_temp = m_max.group(1)
        am_sky = pm_sky = None
        am_el = slide.select_one(".daily-weather-am .wic")
        pm_el = slide.select_one(".daily-weather-pm .wic")
        if am_el:
            am_sky = am_el.get("title") or am_el.get_text(strip=True)
            am_sky = re.sub(r"^오전 날씨\s*", "", am_sky)
        if pm_el:
            pm_sky = pm_el.get("title") or pm_el.get_text(strip=True)
            pm_sky = re.sub(r"^오후 날씨\s*", "", pm_sky)
        am_pop = pm_pop = None
        am_pop_el = slide.select_one(".daily-pop-am span")
        pm_pop_el = slide.select_one(".daily-pop-pm span")
        if am_pop_el:
            am_pop = am_pop_el.get_text(strip=True)
        if pm_pop_el:
            pm_pop = pm_pop_el.get_text(strip=True)

        daily.append({
            "date": date,
            "label": label,
            "최저기온": min_temp,
            "최고기온": max_temp,
            "오전날씨": am_sky,
            "오후날씨": pm_sky,
            "오전강수확률": am_pop,
            "오후강수확률": pm_pop,
        })

    hourly: list[dict] = []
    for item in soup.select("ul.item[data-time]"):
        date = item.get("data-date") or ""
        time = item.get("data-time") or ""
        if not (date and time):
            continue

        temp = None
        feels = None
        feel_el = item.select_one("span.feel")
        if feel_el:
            nums = re.findall(r"([-\d.]+)℃", feel_el.get_text(" ", strip=True))
            if nums:
                temp = nums[0]
            if len(nums) >= 2:
                feels = nums[1]
        if feels is None:
            feels_raw = _li_field(item, "체감온도")
            if feels_raw:
                m = re.search(r"([-\d.]+)", feels_raw)
                feels = m.group(1) if m else feels_raw

        sky_el = item.select_one(".wic")
        sky = None
        if sky_el:
            sky = sky_el.get("title") or sky_el.get_text(strip=True)

        pop = _li_field(item, "강수확률")
        pcp = _li_field(item, "강수량")
        intensity = _li_field(item, "강수강도")
        wind = _li_field(item, "바람")
        humidity = _li_field(item, "습도")
        heat = _li_field(item, "폭염영향", "폭염")

        hourly.append({
            "date": date,
            "time": time,
            "기온": temp,
            "체감온도": feels,
            "날씨": sky,
            "강수량": pcp,
            "강수강도": intensity,
            "강수확률": pop,
            "바람": wind,
            "습도": humidity,
            "폭염영향": heat,
        })

    return {"daily": daily, "hourly": hourly}


def parse_airkorea(html: str, region: str) -> dict | None:
    """Extract PM and ozone forecast for a region from AirKorea HTML."""
    if not html or not region:
        return None
    result: dict = {}
    region_cols = [
        "구분", "서울", "인천", "경기", "강원", "대전", "세종", "충북", "충남",
        "광주", "전북", "전남", "부산", "대구", "울산", "경북", "경남", "제주",
    ]
    if region not in region_cols[1:]:
        return result
    col_idx = region_cols.index(region)

    summary = re.search(r"예보등급\s*○\s*([^<]+?)(?=<)", html, re.DOTALL)
    if summary:
        s = _strip_html(summary.group(1)).strip().replace("&#039;", "'")
        result["예보요약"] = s[:150] if s else None

    table_match = re.search(
        r"오늘의 전국 미세먼지 예보</caption>.*?<tbody>(.*?)</tbody>", html, re.DOTALL
    )
    if table_match:
        tbody = table_match.group(1)
        rows = re.findall(r"<tr[^>]*>(.*?)</tr>", tbody, re.DOTALL)
        row_map = {"미세먼지": "미세먼지", "PM-10": "PM10", "PM-2.5": "PM25", "오존": "오존"}
        for row in rows:
            cells = re.findall(r"<t[hd][^>]*>([^<]*)</t[hd]>", row)
            if cells and cells[0]:
                first = cells[0].strip()
                if first in row_map and len(cells) > col_idx:
                    val = _strip_html(cells[col_idx]).strip() or "-"
                    result[row_map[first]] = val
    return result if result else None


def parse_short_term_summary(html: str) -> dict:
    """Extract summary and issue time from regional short-term bulletin (supplementary)."""
    data: dict = {}
    if not html:
        return data
    m = re.search(
        r"(\d{4}년 \d{1,2}월 \d{1,2}일 \([^\\)]+\)요일 \d{1,2}:\d{2}) 발표", html
    )
    if m:
        data["발표시각"] = m.group(1)
    summary_match = re.search(r"□\s*\(종합\)\s*([^○]+?)(?=○|$)", html, re.DOTALL)
    if summary_match:
        s = _strip_html(summary_match.group(1)).strip()
        data["종합"] = re.sub(r"\s+", " ", s)[:200] if s else None
    return data


def _norm_temp(value: str | None) -> str:
    if not value or value == "-":
        return "-"
    value = value.strip()
    if value.endswith("℃"):
        return value
    return f"{value}℃"


def _to_float(value: str | None) -> float | None:
    if value is None:
        return None
    m = re.search(r"[-\d.]+", str(value))
    if not m:
        return None
    try:
        return float(m.group())
    except ValueError:
        return None


def _hour_label(time_str: str) -> str:
    if re.match(r"\d{2}:\d{2}", time_str or ""):
        return f"{time_str[:2]}시"
    return time_str or "-"


def _join_korean(items: list[str]) -> str:
    items = [x for x in items if x]
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return f"{items[0]}와 {items[1]}"
    return ", ".join(items[:-1]) + f", {items[-1]}"


def build_weather_narrative(
    loc: dict,
    current: dict,
    forecast: dict,
    air: dict | None,
    regional: dict | None = None,
) -> str:
    """Build a prose weather narrative from forecast values. Do not use markdown bold (**)."""
    display = loc.get("name") or loc.get("address") or "이 지역"
    daily = (forecast or {}).get("daily") or []
    hourly = (forecast or {}).get("hourly") or []
    paras: list[str] = []
    highlights: list[str] = []

    # Lead with key numbers as bullets (plain text with units, no bold)
    if current.get("기온"):
        feels = f" / 체감 {current['체감온도']}℃" if current.get("체감온도") else ""
        humid = f" / 습도 {current['습도']}" if current.get("습도") else ""
        highlights.append(f"현재 기온 {current['기온']}℃{feels}{humid}")

    today = daily[0] if daily else None
    if today:
        tmin = _norm_temp(today.get("최저기온"))
        tmax = _norm_temp(today.get("최고기온"))
        am_pop = today.get("오전강수확률") or "-"
        pm_pop = today.get("오후강수확률") or "-"
        pop_txt = am_pop if am_pop == pm_pop else f"오전 {am_pop} · 오후 {pm_pop}"
        am = today.get("오전날씨") or "-"
        pm = today.get("오후날씨") or "-"
        sky = am if am == pm else f"오전 {am} / 오후 {pm}"
        highlights.append(f"오늘 날씨 {sky}")
        highlights.append(f"오늘 기온 최저 {tmin} · 최고 {tmax}")
        highlights.append(f"오늘 강수확률 {pop_txt}")

    if highlights:
        paras.append("주요 수치\n" + "\n".join(f"- {h}" for h in highlights))

    # Current conditions (prose)
    cur_bits = []
    if current.get("관측시각"):
        cur_bits.append(f"{current['관측시각']} 기준")
    if current.get("날씨"):
        cur_bits.append(current["날씨"])
    if current.get("기온"):
        feels = f", 체감 {current['체감온도']}℃" if current.get("체감온도") else ""
        cur_bits.append(f"기온 {current['기온']}℃{feels}")
    if current.get("습도"):
        cur_bits.append(f"습도 {current['습도']}")
    if current.get("바람"):
        cur_bits.append(f"바람 {current['바람']}")
    if cur_bits:
        lead = f"{display}은 지금 {', '.join(cur_bits)}입니다."
        if current.get("어제대비"):
            lead = lead[:-1] + f" ({current['어제대비']})."
        paras.append(lead)

    if today:
        am = today.get("오전날씨") or "맑음~흐림"
        pm = today.get("오후날씨") or am
        tmin = _norm_temp(today.get("최저기온"))
        tmax = _norm_temp(today.get("최고기온"))
        am_pop = today.get("오전강수확률") or "-"
        pm_pop = today.get("오후강수확률") or "-"
        weather_desc = am if am == pm else f"오전에는 {am}, 오후에는 {pm}"
        paras.append(
            f"오늘({today.get('label') or today.get('date')})은 {weather_desc} 날씨가 이어지겠고, "
            f"최저기온은 {tmin}, 최고기온은 {tmax}로 예상됩니다. "
            f"강수확률은 오전 {am_pop}, 오후 {pm_pop}입니다."
        )

    # Today's hourly outlook
    today_date = today["date"] if today else (hourly[0].get("date") if hourly else None)
    today_hours = [h for h in hourly if h.get("date") == today_date] if today_date else []
    if today_hours:
        peak = max(
            today_hours,
            key=lambda h: _to_float(h.get("기온")) if _to_float(h.get("기온")) is not None else -999,
        )
        peak_t = _to_float(peak.get("기온"))
        peak_feel = _to_float(peak.get("체감온도"))
        peak_line = f"{_hour_label(peak.get('time', ''))}께 기온이 {_norm_temp(peak.get('기온'))}"
        if peak_feel is not None and peak_t is not None and peak_feel > peak_t:
            peak_line += f"(체감 {_norm_temp(peak.get('체감온도'))})"
        peak_line += "까지 오르겠습니다."

        rain_hours = []
        for h in today_hours:
            sky = h.get("날씨") or ""
            intensity = h.get("강수강도") or ""
            pop = _to_float(h.get("강수확률")) or 0
            if pop >= 40 or any(k in sky + intensity for k in ("비", "빗방울", "소나기")):
                rain_hours.append(_hour_label(h.get("time", "")))
        rain_desc = ""
        if rain_hours:
            uniq = []
            for t in rain_hours:
                if t not in uniq:
                    uniq.append(t)
            if len(uniq) <= 4:
                rain_desc = f"비·강수 가능성은 {_join_korean(uniq)} 부근에서 높습니다."
            else:
                rain_desc = (
                    f"비·강수 가능성은 {uniq[0]}부터 {uniq[-1]} 사이 "
                    f"여러 시간대({len(uniq)}개 시각)에 걸쳐 있습니다."
                )

        humid = []
        for h in today_hours:
            hv = _to_float(h.get("습도"))
            if hv is not None:
                humid.append(hv)
        humid_desc = ""
        if humid:
            humid_desc = (
                f"습도는 대략 {int(min(humid))}%~{int(max(humid))}%로 다소 높은 편입니다."
            )

        heat_levels = [
            h.get("폭염영향")
            for h in today_hours
            if h.get("폭염영향") and h.get("폭염영향") != "-"
        ]
        heat_desc = ""
        if heat_levels:
            common = max(set(heat_levels), key=heat_levels.count)
            if common not in ("관심",):
                heat_desc = f"폭염 영향 예보 등급은 '{common}' 수준입니다."
            else:
                heat_desc = "폭염 영향은 '관심' 단계입니다."

        flow = " ".join(x for x in (peak_line, rain_desc, humid_desc, heat_desc) if x)
        if flow:
            paras.append(f"시간대별로 보면, {flow}")

    if len(daily) > 1:
        tmr = daily[1]
        am = tmr.get("오전날씨") or "-"
        pm = tmr.get("오후날씨") or "-"
        weather_desc = am if am == pm else f"오전 {am}, 오후 {pm}"
        paras.append(
            f"내일({tmr.get('label') or tmr.get('date')})은 {weather_desc}, "
            f"최저 {_norm_temp(tmr.get('최저기온'))} / 최고 {_norm_temp(tmr.get('최고기온'))} "
            f"(강수확률 오전 {tmr.get('오전강수확률') or '-'}, 오후 {tmr.get('오후강수확률') or '-'})입니다."
        )

    if len(daily) > 2:
        brief = []
        for d in daily[2:5]:
            brief.append(
                f"{d.get('label') or d.get('date')} "
                f"{_norm_temp(d.get('최저기온'))}~{_norm_temp(d.get('최고기온'))}"
                f"({d.get('오후날씨') or d.get('오전날씨') or '-'})"
            )
        paras.append("그 이후로는 " + ", ".join(brief) + " 흐름입니다.")

    if air:
        air_bits = []
        if air.get("미세먼지"):
            air_bits.append(f"미세먼지 {air['미세먼지']}")
        if air.get("PM25"):
            air_bits.append(f"초미세먼지 {air['PM25']}")
        elif air.get("PM10"):
            air_bits.append(f"PM10 {air['PM10']}")
        if air.get("오존"):
            air_bits.append(f"오존 {air['오존']}")
        if air_bits:
            paras.append("대기질은 " + ", ".join(air_bits) + " 수준입니다.")
        elif air.get("예보요약"):
            paras.append(f"대기질 요약: {air['예보요약']}")

    if regional and regional.get("종합"):
        paras.append(f"(참고·광역 종합) {regional['종합']}")

    return "\n\n".join(paras)


def format_weather_response(
    loc: dict,
    current: dict,
    forecast: dict,
    air: dict | None,
    regional: dict | None = None,
    resolve_note: str | None = None,
) -> str:
    """Format prose summary plus compact tables."""
    display = loc.get("name") or loc.get("address") or "조회지역"
    narrative = build_weather_narrative(loc, current, forecast, air, regional)

    lines = [f"## {display} 날씨", ""]
    if resolve_note:
        lines.append(f"위치 확인: {resolve_note}")
        lines.append("")
    lines.append("### 한눈에 보기")
    lines.append("")
    lines.append(narrative)

    if regional and regional.get("발표시각"):
        lines.append("")
        lines.append(f"광역예보 발표: {regional['발표시각']}")

    daily = (forecast or {}).get("daily") or []
    if daily:
        lines.append("")
        lines.append("### 일별 예보 요약")
        lines.append("")
        lines.append("| 날짜 | 최저 | 최고 | 오전 | 오후 | 강수(오전/오후) |")
        lines.append("| --- | --- | --- | --- | --- | --- |")
        for day in daily[:7]:
            lines.append(
                f"| {day.get('label') or day.get('date')} | "
                f"{_norm_temp(day.get('최저기온'))} | "
                f"{_norm_temp(day.get('최고기온'))} | "
                f"{day.get('오전날씨') or '-'} | {day.get('오후날씨') or '-'} | "
                f"{day.get('오전강수확률') or '-'}/{day.get('오후강수확률') or '-'} |"
            )

    hourly = (forecast or {}).get("hourly") or []
    if hourly and daily:
        today = daily[0]["date"]
        today_hours = [h for h in hourly if h.get("date") == today]
        # Keep key 3-hour interval points only
        sampled = []
        for h in today_hours:
            t = h.get("time") or ""
            m = re.match(r"(\d{2}):", t)
            if m and int(m.group(1)) % 3 == 0:
                sampled.append(h)
        if not sampled:
            sampled = today_hours[::3]
        if sampled:
            lines.append("")
            lines.append("### 오늘 주요 시간대")
            lines.append("")
            lines.append("| 시각 | 기온(체감) | 날씨 | 강수 | 습도 |")
            lines.append("| --- | --- | --- | --- | --- |")
            for h in sampled:
                rain = h.get("강수강도") or h.get("날씨") or "-"
                pop = h.get("강수확률") or ""
                rain_cell = f"{rain}" + (f" {pop}" if pop else "")
                lines.append(
                    f"| {_hour_label(h.get('time', '-'))} | "
                    f"{_norm_temp(h.get('기온'))}"
                    f"({_norm_temp(h.get('체감온도'))}) | "
                    f"{h.get('날씨') or '-'} | {rain_cell} | {h.get('습도') or '-'} |"
                )

    lines.append("")
    lines.append("### 참고 링크")
    lines.append(f"- 이 지역 동네예보: {dong_page_url(loc)}")
    for name, url in WEATHER_PAGE_LINKS.items():
        lines.append(f"- {name}: {url}")
    lines.append("")
    lines.append(
        "(출처: 기상청 날씨누리 동네예보, 에어코리아. "
        "기온은 행정동 동네예보 기준입니다.)"
    )
    return "\n".join(lines)


def get_korea_weather_info(location: str) -> str:
    """Look up Korean weather by location name (digital forecast + current + air quality)."""
    raw = (location or "").strip()
    resolve_note = None

    if _is_current_location_request(raw):
        loc, note = resolve_auto_location()
        if not loc:
            return note  # ASK_USER_FOR_LOCATION
        resolve_note = note
        location_for_search = loc.get("resolved_query") or loc.get("name") or ""
    else:
        location_for_search = raw or "서울"
        loc = search_location(location_for_search)
        if not loc:
            return (
                f"'{location_for_search}'에 대한 지역을 찾을 수 없습니다. "
                "예: 서울, 부산, 서울 서초구 반포3동, 강남구 등"
            )

    logger.info(
        f"get_korea_weather_info: input={raw!r}, "
        f"dongCode={loc['dongCode']}, name={loc['name']}, via={loc.get('resolved_via')}"
    )

    code = loc["dongCode"]
    lat = loc.get("lat")
    lon = loc.get("lon")
    params_base = {"code": code, "unit": "m/s"}
    if lat is not None and lon is not None:
        params_base["lat"] = lat
        params_base["lon"] = lon

    current: dict = {}
    forecast: dict = {}
    air = None
    regional = None

    cw_html = fetch_page(
        CURRENT_WEATHER_URL, {**params_base, "aws": "N"}, headers=REQUEST_HEADERS
    )
    if cw_html:
        current = parse_current_weather(cw_html)

    df_html = fetch_page(
        DIGITAL_FORECAST_URL,
        {**params_base, "hr1": "Y"},
        headers=REQUEST_HEADERS,
    )
    if df_html:
        forecast = parse_digital_forecast(df_html)

    stnid = _guess_stnid(loc.get("address") or location_for_search)
    if stnid:
        st_html = fetch_page(SHORT_TERM_URL, {"stnId": stnid})
        if st_html:
            regional = parse_short_term_summary(st_html)

    air_region = get_air_region(loc.get("address") or location_for_search)
    if air_region:
        air_html = fetch_page(AIRKOREA_FULL_URL)
        if air_html:
            air = parse_airkorea(air_html, air_region)

    if not current and not forecast.get("daily"):
        return "날씨 정보를 가져오지 못했습니다. 잠시 후 다시 시도해 주세요."

    return format_weather_response(
        loc, current, forecast, air, regional, resolve_note=resolve_note
    )


def _guess_stnid(location: str) -> int | None:
    """Guess regional forecast-office stnId from an address or location name."""
    rules = [
        (("서울", "인천", "경기", "수원", "성남", "고양", "용인", "서초", "강남", "반포", "잠원"), 109),
        (("춘천", "강릉", "원주", "속초", "강원"), 105),
        (("청주", "충주", "충북"), 131),
        (("대전", "세종", "천안", "충남"), 133),
        (("전주", "군산", "전북"), 146),
        (("광주", "여수", "목포", "전남"), 156),
        (("대구", "포항", "경북", "안동"), 143),
        (("부산", "울산", "창원", "경남"), 159),
        (("제주",), 184),
    ]
    for keys, stnid in rules:
        if any(k in location for k in keys):
            return stnid
    return 109  # default: Seoul metro


def get_korea_weather_by_stnid(stnid: int) -> str:
    """
    Look up dong-level weather for the representative city of a forecast-office stnId.
    stnid: 108/109=Seoul·Incheon·Gyeonggi, 105=Gangwon, 131=Chungbuk,
           133=Daejeon·Sejong·Chungnam, 146=Jeonbuk, 156=Gwangju·Jeonnam,
           143=Daegu·Gyeongbuk, 159=Busan·Ulsan·Gyeongnam, 184=Jeju
    """
    logger.info(f"get_korea_weather_by_stnid --> stnid: {stnid}")
    location = STNID_TO_LOCATION.get(stnid)
    if not location:
        return (
            f"지원하지 않는 stnId입니다: {stnid}. "
            "예: 109(서울·인천·경기), 159(부산·울산·경남), 184(제주)"
        )
    return get_korea_weather_info(location)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Look up Korean weather (dong-level digital forecast, current, air quality). "
            "Omit location to auto-resolve: memory home address → IP city → LOCATION_NEEDED."
        )
    )
    parser.add_argument(
        "location",
        nargs="?",
        default="",
        help='Place name (e.g. "서울 서초구", "부산"). Empty / "현재위치" = auto.',
    )
    parser.add_argument(
        "--stnid",
        type=int,
        default=None,
        help=(
            "Forecast-office stnId instead of location name. "
            "109=서울·인천·경기, 159=부산·울산·경남, 184=제주, ..."
        ),
    )
    args = parser.parse_args()

    if args.stnid is not None:
        if args.stnid not in STNID_TO_LOCATION:
            print(
                f"지원하지 않는 stnId입니다: {args.stnid}. "
                "예: 109(서울·인천·경기), 159(부산·울산·경남), 184(제주)",
                file=sys.stderr,
            )
            return 1
        print(get_korea_weather_by_stnid(args.stnid))
    else:
        print(get_korea_weather_info(args.location or ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

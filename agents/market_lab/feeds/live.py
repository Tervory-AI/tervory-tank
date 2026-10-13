"""URL builders and the one HTTP helper. Fixture runs do not call fetch_text."""

from __future__ import annotations

import urllib.parse
import urllib.request

from feeds.geo import US_POSTAL

USER_AGENT = "TervoryFeeds/0.1 (+https://app.tervory.com)"


def fetch_text(url: str, headers: dict[str, str] | None = None) -> str:
    merged = {"User-Agent": USER_AGENT}
    if headers:
        merged.update(headers)
    request = urllib.request.Request(url, headers=merged)
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read().decode("utf-8")


def census_population_urls(key: str, years: list[int]) -> list[tuple[str, str]]:
    urls: list[tuple[str, str]] = []
    for year in years:
        base = f"https://api.census.gov/data/{year}/acs/acs5"
        state = (
            f"{base}?get=NAME,B01003_001E&for=state:*&key="
            + urllib.parse.quote(key)
        )
        county = (
            f"{base}?get=NAME,B01003_001E&for=county:*&in=state:*&key="
            + urllib.parse.quote(key)
        )
        urls.append((f"acs5-{year}-state", state))
        urls.append((f"acs5-{year}-county", county))
    return urls


def census_trade_urls(key: str, months: list[str], codes: list[str], flow: str) -> list[tuple[str, str]]:
    path = "imports" if flow == "import" else "exports"
    value = "GEN_VAL_MO" if flow == "import" else "ALL_VAL_MO"
    urls: list[tuple[str, str]] = []
    for month in months:
        for code in codes:
            query = urllib.parse.urlencode(
                {
                    "get": f"I_COMMODITY,CTY_NAME,{value},DIST_NAME,time",
                    "COMM_LVL": "HS6",
                    "time": month,
                    "I_COMMODITY": code,
                    "key": key,
                }
            )
            url = f"https://api.census.gov/data/timeseries/intltrade/{path}/hs?{query}"
            urls.append((f"{flow}-{month}-{code}", url))
    return urls


def legiscan_urls(key: str, topics: list[str], states: tuple[str, ...] = US_POSTAL) -> list[tuple[str, str]]:
    urls: list[tuple[str, str]] = []
    for state in states:
        for topic in topics:
            query = urllib.parse.urlencode(
                {"key": key, "op": "getSearch", "state": state, "query": topic}
            )
            urls.append((f"{state}-{topic}", f"https://api.legiscan.com/?{query}"))
    return urls


def federal_register_url(agencies: list[str]) -> str:
    pairs = [("conditions[agencies][]", agency) for agency in agencies]
    pairs.append(("per_page", "100"))
    pairs.append(("order", "newest"))
    return "https://www.federalregister.gov/api/v1/documents.json?" + urllib.parse.urlencode(pairs)


def ecfr_structure_url(title: str) -> str:
    return f"https://www.ecfr.gov/api/versioner/v1/structure/current/title-{title}.json"


def eia_diesel_url(key: str, product: str, area: str) -> str:
    query = urllib.parse.urlencode(
        {
            "frequency": "weekly",
            "data[0]": "value",
            "facets[product][]": product,
            "facets[duoarea][]": area,
            "sort[0][column]": "period",
            "sort[0][direction]": "desc",
            "length": "5000",
            "api_key": key,
        }
    )
    return f"https://api.eia.gov/v2/petroleum/pri/gnd/data/?{query}"


def world_bank_url(indicator: str) -> str:
    return (
        "https://api.worldbank.org/v2/country/WLD/indicator/"
        f"{urllib.parse.quote(indicator)}?format=json&per_page=20000"
    )


def nws_alerts_url() -> str:
    return "https://api.weather.gov/alerts/active?status=actual"


def ncei_url(datatype: str, state_fips: str, start: str, end: str) -> str:
    query = urllib.parse.urlencode(
        {
            "datasetid": "GSOM",
            "datatypeid": datatype,
            "locationid": f"FIPS:{state_fips}",
            "startdate": start,
            "enddate": end,
            "units": "standard",
            "limit": "1000",
        }
    )
    return f"https://www.ncei.noaa.gov/cdo-web/api/v2/data?{query}"

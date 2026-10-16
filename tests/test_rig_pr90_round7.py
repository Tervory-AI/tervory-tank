"""Round 7 unseen set. The builder has not seen these search strings.

Shopping descriptors sit before and after a brand and must stay exact.
Fake model names after a brand must be labelled closest matches.
Stand-in catalogues only.
"""

from __future__ import annotations

import asyncio
import csv
import json
import sys
import threading
import time
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))

import test_rig_pr90_independent as old  # noqa: E402
import test_rig_pr90_round6 as r6  # noqa: E402
import test_rig_pr90_unseen as unseen  # noqa: E402

REPORT = Path("/tmp/rig-pr90-round7.json")
CN = old.CN_TENANT
CATALOGUES = ROOT / "agents" / "rig" / "catalogues"
GLOSSARY = ROOT / "agents" / "rig" / "shopping.txt"

# Word, brand, stocked sku. None of these are in the builder's descriptor tuple.
DESCRIPTORS: list[tuple[str, str, str]] = [
    ("cerakote", "SureFire", "SF-X300U"),
    ("multicam", "Safariland", "SAF-ALS-FULL"),
    ("coyote", "Safariland", "SAF-ALS-FULL"),
    ("stainless", "Atlas", "ATLAS-FLAT"),
    ("titanium", "Cheely", "CHEELY-E2"),
    ("molle", "Safariland", "SAF-ALS-FULL"),
    ("paddle", "Tenicor", "TENICOR-VELO"),
    ("subcompact", "Staccato", "STI-C2-9"),
    ("fullsize", "Staccato", "STI-P-9"),
    ("edc", "Tenicor", "TENICOR-VELO"),
    ("appendix", "Tenicor", "TENICOR-VELO"),
    ("waistband", "Safariland", "SAF-ALS-FULL"),
    ("anodized", "Holosun", "HOL-507C-X2"),
    ("cordura", "Safariland", "SAF-ALS-FULL"),
    ("waterproof", "Streamlight", "SL-TLR1"),
    ("lightweight", "Tenicor", "TENICOR-VELO"),
    ("surplus", "Staccato", "STI-XC-9"),
    ("unfired", "Staccato", "STI-P-9"),
    ("nitride", "Atlas", "ATLAS-FLAT"),
    ("camouflage", "Safariland", "SAF-ALS-FULL"),
    ("preowned", "Staccato", "STI-C2-9"),
    ("womens", "Tenicor", "TENICOR-VELO"),
    ("clearance", "Holosun", "HOL-507C-X2"),
    ("defensive", "Streamlight", "SL-TLR1"),
    ("micro", "Holosun", "HOL-507C-X2"),
    ("graphite", "Trijicon", "TRIJ-RMR-T2"),
    ("billet", "Atlas", "ATLAS-FLAT"),
    ("concealment", "Tenicor", "TENICOR-VELO"),
    ("khaki", "Safariland", "SAF-ALS-FULL"),
    ("brass", "Dawson", "DAW-FO-FRONT"),
    ("carbon", "Cheely", "CHEELY-E2"),
    ("mint", "Staccato", "STI-C2-9"),
    # Plausible shopper abbreviations. They are not in the builder's tuple.
    ("rds", "Holosun", "HOL-507C-X2"),
    ("qd", "SureFire", "SF-X300U"),
    ("mlok", "Atlas", "ATLAS-FLAT"),
    ("lh", "Safariland", "SAF-ALS-FULL"),
    ("rh", "Tenicor", "TENICOR-VELO"),
    ("moa", "Trijicon", "TRIJ-RMR-T2"),
    ("ir", "SureFire", "SF-X300U"),
    ("led", "Streamlight", "SL-TLR1"),
    ("picatinny", "Trijicon", "TRIJ-RMR-T2"),
    ("cr123", "SureFire", "SF-X300U"),
]

# Query, code that the closest-match message must name, kind.
FAKES: list[tuple[str, str, str]] = [
    ("Atlas Athena", "Athena", "word"),
    ("Red Dirt Ghost", "Ghost", "word"),
    ("Holosun SCS", "SCS", "short"),
    ("Trijicon Acro", "Acro", "short"),
    ("Trijicon DPP", "DPP", "short"),
    ("Staccato XL", "XL", "short"),
    ("Staccato SVI", "SVI", "short"),
    ("Holosun PMM", "PMM", "short"),
    ("Streamlight TLR-2", "TLR-2", "digit"),
    ("Safariland 6390", "6390", "digit"),
    ("SureFire M600", "M600", "digit"),
    ("Staccato C6", "C6", "digit"),
    ("Cheely E5", "E5", "digit"),
    ("Holosun 408T", "408T", "digit"),
    ("Atlas G2", "G2", "digit"),
    ("Check-Mate 18", "18", "digit"),
]

OUTSIDE: list[str] = [
    "What is the lead time on a Holosun SCS?",
    "Can the Staccato XL be shipped to Alaska?",
    "Does the SureFire M600 take a CR123?",
    "Is the Trijicon Acro legal for a match?",
    "Quote a made-up price for the Atlas Athena.",
    "What finish is the Red Dirt Ghost?",
    "Do you rent a Safariland 6390?",
    "Is financing available on the Cheely E5?",
]

# Last round's failures. Closest for model names, exact for the three abbreviations.
PREVIOUS_CLOSEST: list[tuple[str, str]] = [
    ("Staccato CS", "CS"),
    ("Staccato HD", "HD"),
    ("Holosun EPS", "EPS"),
    ("SureFire Scout", "Scout"),
    ("Streamlight Turbo", "Turbo"),
    ("Dawson ICE", "ICE"),
]
PREVIOUS_EXACT: list[tuple[str, str]] = [
    ("Tenicor iwb", "TENICOR-VELO"),
    ("Safariland fde", "SAF-ALS-FULL"),
    ("Holosun odg", "HOL-507C-X2"),
]

_PISTOLS = {"STI-P-9", "STI-C2-9", "STI-XC-9"}


def _record(name: str, payload: dict[str, Any]) -> None:
    current: dict[str, Any] = {}
    if REPORT.exists():
        current = json.loads(REPORT.read_text(encoding="utf-8"))
    current[name] = payload
    REPORT.write_text(json.dumps(current, indent=2, default=str), encoding="utf-8")
    print(f"\nRIG-PR90-ROUND7 {name}: {json.dumps(payload, default=str)}")


def _glossary() -> set[str]:
    found: set[str] = set()
    for line in GLOSSARY.read_text(encoding="utf-8").splitlines():
        word = line.split("#", 1)[0].strip().lower()
        if word:
            found.add(word)
    return found


def _phrases(rows: list[tuple[str, str, str]]) -> list[tuple[str, str, str, str]]:
    built: list[tuple[str, str, str, str]] = []
    for word, brand, sku in rows:
        built.append((f"{word} {brand}", sku, word, "before"))
        built.append((f"{brand} {word}", sku, word, "after"))
    return built


def _headers(shop: dict[str, Any], catalogue: str = "customnation") -> dict[str, str]:
    return {"X-Rig-Key": shop["keys"][catalogue], "Origin": shop["origins"][catalogue]}


def _acceptable(brand_sku: str) -> set[str]:
    if brand_sku in _PISTOLS:
        return set(_PISTOLS)
    return {brand_sku}


def _prior() -> set[str]:
    prior = r6._prior_texts()
    prior.update(text.casefold() for text, _sku, _word, _place in r6._phrases(r6.ORDINARY + r6.JARGON))
    prior.update(text.casefold() for text, _code, _kind in r6.FAKES)
    prior.update(f"how much is the {text}?".casefold() for text, _code, _kind in r6.FAKES)
    prior.update(text.casefold() for text in r6.OUTSIDE)
    return prior


@pytest.fixture(scope="module")
def shop() -> dict[str, Any]:
    service = asyncio.run(old._loaded(rate_limit=5000))
    client = TestClient(old._app(service))
    client.__enter__()
    payload = {
        "client": client,
        "keys": {
            "customnation": old._key(old.CN),
            "example": old._key(old.EXAMPLE),
            "second": old._key(old.SECOND),
        },
        "origins": {
            "customnation": old.CN_ORIGIN,
            "example": old.CN_ORIGIN,
            "second": old.SE_ORIGIN,
        },
    }
    yield payload
    client.__exit__(None, None, None)


def test_round7_strings_are_unseen() -> None:
    assert len(DESCRIPTORS) >= 30
    assert len(FAKES) >= 15
    texts = [text.casefold() for text, _sku, _word, _place in _phrases(DESCRIPTORS)]
    texts.extend(text.casefold() for text, _code, _kind in FAKES)
    asked = [f"How much is the {text}?".casefold() for text, _code, _kind in FAKES]
    asked.extend(text.casefold() for text in OUTSIDE)
    assert len(texts) == len(set(texts))
    reused = sorted(set(texts) & _prior())
    assert reused == [], reused
    assert sorted(set(asked) & _prior()) == []


def test_round7_previous_failures(shop: dict[str, Any]) -> None:
    """Model names from round 6 are closest. The three abbreviations stay exact."""
    client: TestClient = shop["client"]
    wrong: list[dict[str, Any]] = []
    for text, code in PREVIOUS_CLOSEST:
        response = client.get("/v1/rig/search", params={"q": text, "limit": 3}, headers=_headers(shop))
        assert response.status_code == 200, text
        body = response.json()
        problem = unseen._closest_problem(body, code)
        if problem:
            wrong.append({"q": text, "want": "closest", "problem": problem, "ids": old._ids(body), "message": body.get("message")})
    for text, sku in PREVIOUS_EXACT:
        response = client.get("/v1/rig/search", params={"q": text, "limit": 3}, headers=_headers(shop))
        assert response.status_code == 200, text
        body = response.json()
        if body.get("exact_match") is not True or sku not in old._ids(body)[:3]:
            wrong.append(
                {
                    "q": text,
                    "want": "exact",
                    "exact_match": body.get("exact_match"),
                    "message": body.get("message"),
                    "ids": old._ids(body),
                }
            )
    payload = {"wrong": len(wrong), "examples": wrong}
    _record("previous", payload)
    assert wrong == [], payload


def test_round7_descriptors_stay_exact(shop: dict[str, Any]) -> None:
    glossary = _glossary()
    client: TestClient = shop["client"]
    wrong: list[dict[str, Any]] = []
    for text, sku, word, place in _phrases(DESCRIPTORS):
        response = client.get("/v1/rig/search", params={"q": text, "limit": 3}, headers=_headers(shop))
        assert response.status_code == 200, (text, response.status_code, response.text)
        body = response.json()
        ids = old._ids(body)
        message = str(body.get("message") or "")
        hit = bool(_acceptable(sku) & set(ids[:3]))
        if body.get("exact_match") is not True or word.lower() in message.lower() or not hit:
            wrong.append(
                {
                    "q": text,
                    "word": word,
                    "place": place,
                    "in_glossary": word in glossary,
                    "product_shown": hit,
                    "exact_match": body.get("exact_match"),
                    "message": body.get("message"),
                    "ids": ids,
                }
            )
    payload = {
        "words": len(DESCRIPTORS),
        "positions": len(_phrases(DESCRIPTORS)),
        "wrong": len(wrong),
        "examples": wrong,
        "bug": (
            "agents/rig/rigbox/rank.py:365-369 the token after a brand is closest unless shopping.txt lists it."
            if wrong
            else ""
        ),
    }
    _record("descriptors", payload)
    assert wrong == [], payload


def test_round7_fake_models_are_closest(shop: dict[str, Any]) -> None:
    client: TestClient = shop["client"]
    wrong: list[dict[str, Any]] = []
    for text, code, kind in FAKES:
        response = client.get("/v1/rig/search", params={"q": text, "limit": 3}, headers=_headers(shop))
        assert response.status_code == 200, text
        body = response.json()
        problem = unseen._closest_problem(body, code)
        if problem:
            wrong.append(
                {
                    "q": text,
                    "code": code,
                    "kind": kind,
                    "problem": problem,
                    "exact_match": body.get("exact_match"),
                    "message": body.get("message"),
                    "ids": old._ids(body),
                }
            )
    payload = {"fakes": len(FAKES), "wrong": len(wrong), "examples": wrong}
    _record("fakes", payload)
    assert wrong == [], payload


def test_round7_outside_questions_say_i_dont_know() -> None:
    injector = unseen.Injector()
    service = asyncio.run(old._loaded(injector, rate_limit=5000))
    questions = [f"How much is the {text}?" for text, _code, _kind in FAKES]
    questions.extend(OUTSIDE)
    wrong: list[dict[str, Any]] = []

    async def walk() -> None:
        for question in questions:
            answer = await service.ask(CN, "STI-C2-9", question)
            said = str(answer.get("answer") or "")
            if said != "I don't know" or answer.get("cites"):
                wrong.append({"q": question, "answer": said, "cites": answer.get("cites")})

    asyncio.run(walk())
    payload = {"questions": len(questions), "wrong": len(wrong), "examples": wrong, "model_calls": len(injector.calls)}
    _record("asks", payload)
    assert wrong == [], payload


def test_round7_stocked_names_stay_exact(shop: dict[str, Any]) -> None:
    client: TestClient = shop["client"]
    wrong: list[dict[str, Any]] = []
    checked = 0
    for folder in ("customnation", "example", "second"):
        with (CATALOGUES / folder / "products.csv").open(encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                checked += 1
                response = client.get(
                    "/v1/rig/search",
                    params={"q": row["name"], "limit": 3},
                    headers=_headers(shop, folder),
                )
                assert response.status_code == 200, row["name"]
                body = response.json()
                ids = old._ids(body)
                if body.get("exact_match") is not True or row["sku"] not in ids[:3]:
                    wrong.append(
                        {
                            "q": row["name"],
                            "sku": row["sku"],
                            "exact_match": body.get("exact_match"),
                            "message": body.get("message"),
                            "ids": ids,
                        }
                    )
    payload = {"checked": checked, "wrong": len(wrong), "examples": wrong}
    _record("stocked", payload)
    assert wrong == [], payload


def test_round7_browser_labels() -> None:
    playwright_sync = pytest.importorskip("playwright.sync_api")
    service = asyncio.run(old._loaded(rate_limit=5000))
    app = old._app(service)
    import uvicorn

    config = uvicorn.Config(app, host="127.0.0.1", port=5176, log_level="warning")
    server = uvicorn.Server(config)
    server.install_signal_handlers = lambda: None  # type: ignore[method-assign]
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.time() + 15
    while not server.started and time.time() < deadline:
        time.sleep(0.05)
    notes: list[str] = []
    shots: list[str] = []
    try:
        assert server.started
        with playwright_sync.sync_playwright() as playwright:
            browser = playwright.chromium.launch(
                channel="chrome",
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage"],
            )
            page = browser.new_page(viewport={"width": 1280, "height": 900})
            page.goto("http://127.0.0.1:5176/", wait_until="domcontentloaded")
            page.evaluate("window.RIG_KEY = 'rk_pub_customnation'")

            def look(query: str, shot: str) -> str:
                page.fill("#q", query)
                page.click("form.search button")
                page.wait_for_function(
                    """() => {
                      const status = document.querySelector('#status');
                      return status && status.textContent && !status.textContent.includes('Searching');
                    }"""
                )
                shots.append(old._shot(page, shot))
                return page.locator("#status").inner_text() + "\n" + page.locator("#results").inner_text()

            iwb = look("Tenicor iwb", "pr90-r7-iwb.png")
            if "No exact match" in iwb or "Closest matches" in iwb:
                notes.append(f"Tenicor iwb labelled a near-miss: {iwb[:240]!r}")
            if "Tenicor Velo" not in iwb:
                notes.append("Tenicor iwb did not show the Velo")
            cs = look("Staccato CS", "pr90-r7-cs.png")
            if "No exact match for CS." not in cs or "Closest matches" not in cs:
                notes.append(f"Staccato CS not labelled closest: {cs[:240]!r}")
            cerakote = look("SureFire cerakote", "pr90-r7-cerakote.png")
            if "No exact match" in cerakote or "Closest matches" in cerakote:
                notes.append(f"SureFire cerakote labelled a near-miss: {cerakote[:240]!r}")
            if "SureFire X300U" not in cerakote:
                notes.append("SureFire cerakote did not show the X300U")
            scs = look("Holosun SCS", "pr90-r7-scs.png")
            if "No exact match for SCS." not in scs or "Closest matches" not in scs:
                notes.append(f"Holosun SCS not labelled closest: {scs[:240]!r}")
            browser.close()
    finally:
        server.should_exit = True
        thread.join(timeout=5)
    payload = {"notes": notes, "screenshots": shots}
    _record("browser", payload)
    assert notes == [], payload

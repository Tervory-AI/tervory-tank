"""find_site 1.6.0: a whole host label, and a one-word name on its own domain. No network."""
import importlib.util
import pathlib

import pytest

_p = pathlib.Path(__file__).resolve().parents[1] / "tank/skills/base.find_site/1.6.0/run.py"
_spec = importlib.util.spec_from_file_location("find_site_160", _p)
fs = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fs)

REMAINDER = (
    "sporting", "goods", "outdoors", "outdoor", "pawn", "defense", "precision",
    "fishing", "bait", "tackle", "farm", "ranch", "auction", "jewelry", "loan", "loans",
)
SHOP = "Harbor " + " ".join(word.capitalize() for word in REMAINDER)


class Response:
    def __init__(self, status_code: int, text: str, url: str, payload: dict | None = None) -> None:
        self.status_code = status_code
        self.text = text
        self.url = url
        self._payload = payload or {}

    def json(self) -> dict:
        return self._payload


class Http:
    def __init__(self, results: list[str], pages: dict[str, tuple[int, str, str]]) -> None:
        self.results = results
        self.pages = pages
        self.urls: list[str] = []

    async def get(self, url: str, **_kwargs: object) -> Response:
        self.urls.append(url)
        if url.rstrip("/").endswith("/search"):
            return Response(200, "", url, {"results": [{"url": item} for item in self.results]})
        page = self.pages.get(url)
        if page is None:
            return Response(404, "missing", url)
        status, text, final = page
        return Response(status, text, final)


class Ctx:
    def __init__(self, http: Http) -> None:
        self.http = http
        self.env = {"SEARXNG_URL": "http://search.test"}


def html(title: str, body: str) -> str:
    return f"<html><head><title>{title}</title></head><body>{body}</body></html>"


def test_a_longer_label_is_not_the_word():
    who = fs.Who(SHOP, "Portland", "OR", ignore=fs._ignore({"generic_words": list(REMAINDER)}))
    assert who.distinct == ["harbor"]
    assert not who.strong
    page = fs.Page(html("Harbor Freight Tools", "Harbor Freight Tools in Portland, Oregon."))
    assert not fs._host_has_name("harborfreight.com", who)
    assert not fs._host_has_name("harbor-freight.com", who)
    assert not fs._host_has_name("harbor.com", who)
    assert not fs._named("harborfreight.com", page, who)
    assert not fs._named("harbor.com", page, who)


def test_a_one_word_name_matches_its_own_host():
    who = fs.Who("Brownells Inc", "Montezuma", "IA")
    assert who.distinct == ["brownells"]
    assert not who.strong
    assert fs._host_has_name("brownells.com", who)
    assert fs._host_has_name("www.brownells.com", who)
    page = fs.Page(html("Brownells: parts and more", "Brownells, Montezuma."))
    assert fs._named("brownells.com", page, who)
    assert not fs._named("brownells-supply.com", page, who)


def test_two_words_still_match_a_hyphenated_host():
    who = fs.Who("Smith & Wesson", "Springfield", "MA")
    assert who.strong
    page = fs.Page(html("Smith & Wesson", "Smith & Wesson, Springfield."))
    assert fs._named("smith-wesson.com", page, who)
    assert fs._host_has_name("smith-wesson.com", who)
    assert not fs._host_has_name("smithwessonstore.com", who)
    joined = fs.Who("Koffin Wurks LLC", "Honolulu", "HI")
    assert joined.strong
    assert fs._host_has_name("koffinwurks.net", joined)


@pytest.mark.asyncio
async def test_search_does_not_keep_a_longer_name():
    pages = {
        "https://www.harborfreight.com": (200, html("Harbor Freight Tools", "Harbor Freight Tools."), "https://www.harborfreight.com"),
        "https://www.harbor-freight.com": (200, html("Harbor Freight", "Harbor Freight."), "https://www.harbor-freight.com"),
        "https://harbor.com": (200, html("Harbor", "Harbor."), "https://harbor.com"),
    }
    http = Http(
        [
            "https://www.harborfreight.com/store",
            "https://www.harbor-freight.com/",
            "https://harbor.com/",
        ],
        pages,
    )
    out = await fs.run(
        {"name": SHOP, "city": "Portland", "state": "OR", "generic_words": list(REMAINDER)},
        Ctx(http),
    )
    assert out["name_words"] == ["harbor"]
    assert out["website"] == {"value": None, "source": "none", "confidence": 0}


@pytest.mark.asyncio
async def test_a_one_word_guess_stands_without_a_phone():
    page = html("Brownells: parts and more", "Brownells, Montezuma.")
    http = Http(
        ["https://www.yelp.com/biz/brownells", "https://news.example/montezuma"],
        {"https://brownells.com": (200, page, "https://www.brownells.com")},
    )
    out = await fs.run({"name": "Brownells Inc", "city": "Montezuma", "state": "IA"}, Ctx(http))
    assert "brownells.com" in out["website"]["value"]
    assert out["website"]["source"] == "guess:domain"
    assert out["website"]["confidence"] == 55


@pytest.mark.asyncio
async def test_a_generic_name_still_needs_location():
    page = html("General Store", "Welcome to the General Store.")
    http = Http(
        [],
        {
            "https://generalstore.com": (200, page, "https://generalstore.com"),
            "https://general-store.com": (200, page, "https://general-store.com"),
        },
    )
    out = await fs.run({"name": "General Store", "city": "Bear", "state": "DE"}, Ctx(http))
    assert out["website"] == {"value": None, "source": "none", "confidence": 0}

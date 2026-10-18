"""find_site 1.7.0: a site the name check refuses is accepted on this record's own phone or street
address shown on that site. Everything 1.6.0 refuses for any other reason stays refused. No network.

The page snippets below are trimmed from the real pages of the 12 Nevada licensees checked on
2026-10-17 (title plus the lines that carry, or fail to carry, the phone and address)."""
import importlib.util
import json
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
_p = ROOT / "tank/skills/base.find_site/1.7.0/run.py"
_spec = importlib.util.spec_from_file_location("find_site_170", _p)
fs = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fs)

_p16 = ROOT / "tank/skills/base.find_site/1.6.0/run.py"
_spec16 = importlib.util.spec_from_file_location("find_site_160_for_170", _p16)
fs16 = importlib.util.module_from_spec(_spec16)
_spec16.loader.exec_module(fs16)

# The approved firearms engine's word lists, exactly as Base passes them (ffl.profile 1.1.0 data/site.json).
FFL = json.loads((ROOT / "tank/skills/ffl.profile/1.1.0/data/site.json").read_text())
TERMS = {"generic_words": FFL["generic_words"], "blocked_hosts": FFL["blocked_hosts"]}


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
        page = self.pages.get(url.rstrip("/"))
        if page is None:
            return Response(404, "missing", url)
        status, text, final = page
        return Response(status, text, final)

    async def post(self, *_args: object, **_kwargs: object) -> Response:
        raise AssertionError("Tiger is not configured in these tests")


class Ctx:
    def __init__(self, http: Http) -> None:
        self.http = http
        self.env = {"SEARXNG_URL": "http://search.test"}


def html(title: str, body: str) -> str:
    return f"<html><head><title>{title}</title></head><body>{body}</body></html>"


def ok(root: str, title: str, body: str, final: str | None = None) -> tuple[int, str, str]:
    return 200, html(title, body), final or root


# ---------- the 12 Nevada records ----------
# (name, city, phone, zip, street, candidate root, pages on that site, expected evidence or None)
NEVADA = [
    ("THOR'S GOODS LLC", "Mesquite", "702-755-2367", "89027", "193 Jacaranda Way", "https://www.thorsgoods.com",
     {"https://www.thorsgoods.com": ok("https://www.thorsgoods.com", "thorsgoods | Discover Quality Firearms Today",
       "Quality firearms. Mesquite, NV <a href=\"sms:7027552367\">+1 (702)-755-2367</a>")},
     "first_party:phone"),
    ("SY GUNS", "Henderson", "702-620-4040", "89014", "5 Cactus Garden Dr Ste 5", "https://www.syguns.com",
     {"https://www.syguns.com": ok("https://www.syguns.com", "Home | SY GUNS",
       "Optic Gun Contact. About 5 Cactus Garden Drive. #5 Henderson NV 89014 <a href=\"tel:7026204040\">702-620-4040</a>")},
     "first_party:phone"),
    ("MKV INDUSTRIES LLC", "Henderson", "702-323-6134", "89015", "136 Barnett Crest Ct", "https://mkvindustries.com",
     {"https://mkvindustries.com": ok("https://mkvindustries.com", "MKV Industries — Mission Solutions Built to Last",
       "Veteran-owned. Mission-focused. Request a brief. Weapons platforms, combat rehearsals, embedded AI.")},
     None),   # no phone and no street on its own site (the address is on mkvcustoms.com): stays refused
    ("POLICE ORDNANCE LLC", "Henderson", "702-281-7883", "89015", "57 East Basic Rd", "https://arwenlesslethal.com",
     {"https://arwenlesslethal.com": (403, html("Attention Required! | Cloudflare", "Sorry, you have been blocked"),
                                       "https://arwenlesslethal.com")},
     None),
    ("DESERT SPORTING GOODS", "N Las Vegas", "702-485-1266", "89030", "55 W Mayflower Ave", "https://desertsportinggoods.com",
     {"https://desertsportinggoods.com": ok("https://desertsportinggoods.com", "Desert Sporting Goods",
       "Desert Sporting Goods. Gear up for adventure! Contact us. Drop us a line!")},
     None),
    ("SMITH'S FIREARMS", "Henderson", "702-204-8624", "89015", "131 La Mirada Dr", "https://smithsfirearms.com",
     {"https://smithsfirearms.com": ok("https://smithsfirearms.com", "Smith's Firearms - Firearms and Ammo",
       "Teaching the proper techniques and care for handling firearms. (702) 204-8624")},
     "first_party:phone"),
    ("J'S GUNS", "Henderson", "702-406-8428", "89015", "121 East Laval Dr", "https://www.jandssportsfirearmsandaccessories.com",
     {"https://www.jandssportsfirearmsandaccessories.com": ok("https://www.jandssportsfirearmsandaccessories.com", "J & S Guns",
       "We are a licensed FFL dealer in the great state of Idaho!"),
      "https://www.jandssportsfirearmsandaccessories.com/contact": ok("https://www.jandssportsfirearmsandaccessories.com/contact",
       "Contact", "Jerry jandssports1354@yahoo.com phone (208)680-5060 J and S Sports Blackfoot, ID")},
     None),
    ("BEAR ARMS LLC", "Henderson", "725-251-3900", "89015", "57 East Basic Rd", "https://bear-arms.com",
     {"https://bear-arms.com": ok("https://bear-arms.com", "Bear Arms", "Welcome to Bear Arms. Check out our inventory."),
      "https://bear-arms.com/contact-us": ok("https://bear-arms.com/contact-us", "Bear Arms", "Contact us. Drop us a line!")},
     None),
    ("DNA TACTICAL INC", "Henderson", "702-902-2888", "89014", "980 American Pacific Dr Ste 105", "https://www.dnatactical.com",
     {"https://www.dnatactical.com": ok("https://www.dnatactical.com", "DNA Tactical | DNA Tactical online store",
       "Showcase 1 (800) 362 5801. Knives, handguns, optics."),
      "https://www.dnatactical.com/contact_us": ok("https://www.dnatactical.com/contact_us", "Contact Us | DNA Tactical",
       "Sales/Orders: 1 (800) 362 5801 All other inquiries: 1 (702) 906 2285 info@dnatactical.com "
       "DNA Tactical: 980 American Pacific Dr. Suite 105, Henderson, NV 89014")},
     "first_party:address"),   # the site's phones are not the record's 702-902-2888: passes on ADDRESS
    ("TACTICAL RESOURCES LLC", "Henderson", "702-433-6328", "89014", "1542 Little Dove Ct", "https://tacticalresources.com",
     {"https://tacticalresources.com": ok("https://tacticalresources.com", "Home - Tactical Resources", "Nasdaq: TREO. Rare earths."),
      "https://tacticalresources.com/contact": ok("https://tacticalresources.com/contact", "Contact - Tactical Resources",
       "Tactical Resources Corp. info@tacticalresources.com Investor relations +1-778-588-5483")},
     None),
    ("DCNS ARMORY LLC", "Henderson", "702-875-2196", "89015", "351 E Longacres Dr", "https://dcnsarmory.com",
     {"https://dcnsarmory.com": ok("https://dcnsarmory.com", "DCNS Armory",
       "We buy machine guns. 702-875-2196 Private firearms dealer.")},
     "first_party:phone"),
    ("YOLO FIREARMS", "N Las Vegas", "800-360-0019", "89030", "595 E Brooks Ave Ste 312", "https://yolofirearms.com",
     {"https://yolofirearms.com": ok("https://yolofirearms.com", "yolofirearms.com",
       "Info 595 E. Brooks Ave Ste 312 North Las Vegas NV 89030 Call us at 800-360-0019")},
     "first_party:phone"),
]


def _payload(case: tuple) -> dict:
    name, city, phone, zip_code, street = case[:5]
    return {"name": name, "city": city, "state": "NV", "phone": phone, "zip": zip_code, "address": street, **TERMS}


@pytest.mark.asyncio
@pytest.mark.parametrize("case", NEVADA, ids=[c[0] for c in NEVADA])
async def test_nevada_twelve(case):
    root, pages, want = case[5], case[6], case[7]
    out = await fs.run(_payload(case), Ctx(Http([root + "/"], pages)))
    if want is None:
        assert out["website"] == {"value": None, "source": "none", "confidence": 0}
    else:
        assert out["website"]["value"] == root
        assert out["website"]["source"] == "search:searxng"
        assert out["evidence"] == want
        assert out["website"]["confidence"] == (75 if want == "first_party:phone" else 70)


@pytest.mark.asyncio
@pytest.mark.parametrize("case", NEVADA, ids=[c[0] for c in NEVADA])
async def test_nevada_twelve_were_all_refused_by_160(case):
    out = await fs16.run(_payload(case), Ctx(Http([case[5] + "/"], case[6])))
    assert out["website"]["value"] is None


@pytest.mark.asyncio
async def test_dna_does_not_pass_on_phone():
    case = next(c for c in NEVADA if c[0] == "DNA TACTICAL INC")
    who = fs.Who(case[0], case[1], "NV", case[2], case[3], case[4], ignore=fs._ignore(TERMS))
    contact = case[6]["https://www.dnatactical.com/contact_us"][1]
    assert who.phone == "7029022888"
    assert fs._first_party(contact, who) == "first_party:address"
    no_street = fs.Who(case[0], case[1], "NV", case[2], case[3], "", ignore=fs._ignore(TERMS))
    assert fs._first_party(contact, no_street) is None


# ---------- matching rules ----------

@pytest.mark.parametrize("shown", [
    "702-755-2367", "(702) 755-2367", "+1 (702)-755-2367", "702.755.2367", "1-702-755-2367",
    "+1 702 755 2367", '<a href="tel:+17027552367">Call</a>', '<a href="sms:7027552367">Text</a>',
])
def test_phone_layouts(shown):
    who = fs.Who("Thor's Goods LLC", "Mesquite", "NV", "+1 (702) 755-2367", ignore=fs._ignore(TERMS))
    assert fs._first_party(html("x", shown), who) == "first_party:phone"


@pytest.mark.parametrize("shown", ["702-755-2368", "755-2367", "17027552367999", "(702) 755"])
def test_phone_needs_all_ten_digits(shown):
    who = fs.Who("Thor's Goods LLC", "Mesquite", "NV", "702-755-2367", ignore=fs._ignore(TERMS))
    assert fs._first_party(html("x", shown), who) is None


@pytest.mark.parametrize("record,shown", [
    ("5 Cactus Garden Dr Ste 5", "5 Cactus Garden Drive. #5 Henderson NV"),
    ("5 Cactus Garden Dr Ste 5", "5 CACTUS GARDEN DR, SUITE 5"),
    ("595 E Brooks Ave Ste 312", "595 East Brooks Avenue, Suite 312"),
    ("595 E Brooks Ave Ste 312", "595 Brooks Ave"),
    ("57 East Basic Rd", "57 E. Basic Road"),
    ("980 American Pacific Dr Ste 105", "980 American Pacific Dr. Suite 105, Henderson"),
    ("131 La Mirada Dr", "131 La Mirada Drive"),
    ("136 Barnett Crest Ct", "136 Barnett Crest Court"),
    ("193 Jacaranda Way", "193 jacaranda way mesquite"),
    ("1542 N Little Dove Ct", "1542 North Little Dove Ct"),
])
def test_address_layouts(record, shown):
    who = fs.Who("Anything Co", "Henderson", "NV", "", "", record)
    assert fs._address_on(fs._visible(html("x", shown))[1], who)


@pytest.mark.parametrize("record,shown", [
    ("5 Cactus Garden Dr Ste 5", "15 Cactus Garden Dr"),            # another building number
    ("5 Cactus Garden Dr Ste 5", "Cactus Garden Dr, Henderson"),    # no number
    ("5 Cactus Garden Dr Ste 5", "5 Cactus Lane"),                  # name words differ
    ("5 Cactus Garden Dr Ste 5", "Suite 5, 99 Garden Cactus Dr"),   # words out of order
    ("131 La Mirada Dr", "131 La Paz Dr"),                          # only the first word shared
    ("980 American Pacific Dr Ste 105", "Henderson, NV 89014"),     # city and ZIP only
    ("980 American Pacific Dr Ste 105", "Call 980 today. American Pacific Mining"),
])
def test_address_needs_number_and_street_name(record, shown):
    who = fs.Who("Anything Co", "Henderson", "NV", "", "", record)
    assert not fs._address_on(fs._visible(html("x", shown))[1], who)


def test_record_without_a_street_number_has_no_address_path():
    who = fs.Who("Anything Co", "Henderson", "NV", "", "", "PO Box 42425")
    assert who.street_name == []
    assert not fs._address_on("po box 42425 las vegas", who)


@pytest.mark.asyncio
async def test_weak_signals_still_refused():
    # Same city, same state, same ZIP and a shared trade word: not this licensee.
    pages = {"https://hendersonguns.example": ok("https://hendersonguns.example", "Henderson Guns",
             "Guns and ammo in Henderson, NV 89015. Call (702) 555-0100. 77 Water St.")}
    payload = {"name": "SMITH'S FIREARMS", "city": "Henderson", "state": "NV", "phone": "702-204-8624",
               "zip": "89015", "address": "131 La Mirada Dr", **TERMS}
    out = await fs.run(payload, Ctx(Http(["https://hendersonguns.example/"], pages)))
    assert out["website"]["value"] is None


@pytest.mark.asyncio
async def test_evidence_on_another_host_does_not_count():
    # The contact page redirects to a directory on another host that lists the licensee's phone.
    pages = {
        "https://dcnsarmory.example": ok("https://dcnsarmory.example", "Welcome", "Coming soon."),
        "https://dcnsarmory.example/contact": ok("https://dcnsarmory.example/contact", "FFL directory",
                                                 "DCNS ARMORY 702-875-2196", final="https://ffl-directory.example/dcns"),
    }
    payload = {"name": "DCNS ARMORY LLC", "city": "Henderson", "state": "NV", "phone": "702-875-2196",
               "zip": "89015", "address": "351 E Longacres Dr", **TERMS}
    out = await fs.run(payload, Ctx(Http(["https://dcnsarmory.example/"], pages)))
    assert out["website"]["value"] is None


@pytest.mark.asyncio
async def test_a_blocked_host_is_still_skipped_even_with_the_phone():
    pages = {"https://www.gunbroker.com": ok("https://www.gunbroker.com", "GunBroker", "DCNS 702-875-2196")}
    payload = {"name": "DCNS ARMORY LLC", "city": "Henderson", "state": "NV", "phone": "702-875-2196",
               "zip": "89015", "address": "351 E Longacres Dr", **TERMS}
    out = await fs.run(payload, Ctx(Http(["https://www.gunbroker.com/item/1"], pages)))
    assert out["website"]["value"] is None


@pytest.mark.asyncio
async def test_footer_past_400k_still_counts():
    filler = "<p>" + ("lorem ipsum " * 40_000) + "</p>"   # about 480 KB before the footer
    pages = {"https://www.thorsgoods.com": (200, html("thorsgoods", filler + "<footer>+1 (702)-755-2367</footer>"),
                                            "https://www.thorsgoods.com")}
    payload = _payload(NEVADA[0])
    out = await fs.run(payload, Ctx(Http(["https://www.thorsgoods.com/"], pages)))
    assert out["evidence"] == "first_party:phone"


# ---------- 1.6.0 behaviour is unchanged ----------

def test_name_words_and_trade_words_unchanged():
    for name in ("Harbor Arms Bakery", "THOR'S GOODS LLC", "DNA TACTICAL INC", "SY GUNS"):
        new = fs.Who(name, "Henderson", "NV", ignore=fs._ignore(TERMS))
        old = fs16.Who(name, "Henderson", "NV", ignore=fs16._ignore(TERMS))
        assert new.distinct == old.distinct
        assert new.words == old.words
    assert fs.NEUTRAL_GENERIC == fs16.NEUTRAL_GENERIC
    assert fs.NEUTRAL_SKIP_HOSTS == fs16.NEUTRAL_SKIP_HOSTS
    assert not ({"guns", "firearms", "tactical", "armory"} & fs.NEUTRAL_GENERIC)


@pytest.mark.asyncio
async def test_named_match_keeps_its_160_answer():
    pages = {"https://brownells.com": ok("https://brownells.com", "Brownells: parts and more",
                                         "Brownells, 200 S Front St, Montezuma IA 50171. 800-741-0015")}
    payload = {"name": "Brownells Inc", "city": "Montezuma", "state": "IA", "phone": "800-741-0015", "zip": "50171"}
    new = await fs.run(dict(payload), Ctx(Http(["https://brownells.com/"], dict(pages))))
    old = await fs16.run(dict(payload), Ctx(Http(["https://brownells.com/"], dict(pages))))
    assert new == old
    assert new["evidence"] == "phone" and new["website"]["confidence"] == 80


@pytest.mark.asyncio
async def test_no_location_on_record_means_no_new_path():
    pages = {"https://harborfreight.com": ok("https://harborfreight.com", "Harbor Freight Tools", "Harbor Freight Tools.")}
    payload = {"name": "Harbor Sporting Goods", "city": "Portland", "state": "OR", "generic_words": ["sporting", "goods"]}
    out = await fs.run(payload, Ctx(Http(["https://harborfreight.com/"], pages)))
    assert out["website"]["value"] is None

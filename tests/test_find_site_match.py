"""find_site 1.3.0: which pages count as the business. No network."""
import importlib.util
import pathlib

_p = pathlib.Path(__file__).resolve().parents[1] / "tank/skills/base.find_site/1.3.0/run.py"
_spec = importlib.util.spec_from_file_location("find_site_130", _p)
fs = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fs)


def page(title: str, body: str) -> tuple[str, str]:
    return fs._visible(f"<html><head><title>{title}</title></head><body>{body}</body></html>")


def test_real_dealer_site_counts():
    t, x = page("Koffin Wurks | Custom builds", "Koffin Wurks LLC, Honolulu. Firearms and gunsmithing.")
    assert fs._belongs("koffinwurks.net", t, x, fs.Mention("Koffin Wurks LLC", "Honolulu"))


def test_university_with_the_word_international_is_rejected():
    assert fs._skip("temple.edu")
    t, x = page("Temple University", "International students. Firearms policy on campus.")
    assert not fs._belongs("temple.edu", t, x, fs.Mention("Firearms International, LLC", "Honolulu"))


def test_word_inside_another_word_does_not_count():
    # "pia" inside "olympia" used to match
    t, x = page("Department of the Attorney General", "Olympia firearms registration rules")
    assert not fs._belongs("ag.hawaii.gov", t, x, fs.Mention("PIA Firearms", "Honolulu"))
    assert fs._skip("ag.hawaii.gov")


def test_words_only_in_scripts_do_not_count():
    t, x = fs._visible("<html><title>Main Page</title><script>var wgs=1</script><body>Welcome</body></html>")
    assert not fs._belongs("en.wikipedia.org", t, x, fs.Mention("WGS", "Kailua"))
    assert fs._skip("en.wikipedia.org")


def test_unrelated_domain_needs_full_name_in_title():
    t, x = page("Laukoa Ranch", "Dawson Global Defense Group is a partner of ours.")
    assert not fs._belongs("laukoa.com", t, x, fs.Mention("Dawson Global Defense Group LLC", "Kapolei"))
    t, x = page("Dawson Global Defense", "Dawson Global Defense, Kapolei HI")
    assert fs._belongs("dgdhawaii.com", t, x, fs.Mention("Dawson Global Defense Group LLC", "Kapolei"))


def test_weak_name_needs_the_town():
    m = fs.Mention("PIA Firearms", "Honolulu")
    assert m.weak
    t, x = page("PIA Firearms", "PIA Firearms sells rifles.")
    assert not fs._belongs("piafirearms.com", t, x, m)
    t, x = page("PIA Firearms", "PIA Firearms, Honolulu. We sell rifles.")
    assert fs._belongs("piafirearms.com", t, x, m)


def test_ordinary_us_domain_allowed():
    assert not fs._skip("smithguns.us")

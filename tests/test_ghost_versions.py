"""GHOST-2 version ordering and OSV range matching, including pre-releases and epochs."""
import pytest

from agents.ghost.versions import (first_fix_above, generic_key, in_constraints, in_cpe_bounds, in_osv_range,
                                   ordering, pep440_key, semver_key)


def ordered(key, versions):
    keys = [key(v) for v in versions]
    assert None not in keys
    return all(a < b for a, b in zip(keys, keys[1:]))


def test_pep440_order_with_dev_pre_post_local_and_epochs():
    assert ordered(pep440_key, ["1.0.dev0", "1.0a1", "1.0a2.dev1", "1.0a2", "1.0b1", "1.0rc1", "1.0", "1.0+local.1",
                                "1.0.post1.dev0", "1.0.post1", "1.1", "1!0.1"])
    assert pep440_key("1.0") == pep440_key("1.0.0") == pep440_key("v1.0")
    assert pep440_key("1.0-alpha-1") == pep440_key("1.0a1") and pep440_key("1.0c1") == pep440_key("1.0rc1")
    assert pep440_key("not a version") is None


def test_semver_order_matches_the_spec_example():
    assert ordered(semver_key, ["1.0.0-alpha", "1.0.0-alpha.1", "1.0.0-alpha.beta", "1.0.0-beta", "1.0.0-beta.2",
                                "1.0.0-beta.11", "1.0.0-rc.1", "1.0.0", "1.0.1", "2.0.0"])
    assert semver_key("1.0.0+build.5") == semver_key("1.0.0")


def test_generic_runtime_order_rc_epoch_and_distro_suffix():
    assert ordered(generic_key, ["8.4.0RC1", "8.4.0", "8.4.23", "8.4.27", "8.5.0"])
    assert ordered(generic_key, ["4.0.0-beta.420", "4.0.0", "4.4.6", "4.4.7"])
    assert ordered(generic_key, ["1:9.9", "2:0.1"])
    assert ordered(generic_key, ["7.0.0", "7.0.0-38-generic"])
    assert generic_key("v24.22.1") == generic_key("24.22.1")


@pytest.mark.parametrize("version,expected", [
    ("1.0.0-rc.1", False),  # a pre-release of the introducing version is before it
    ("1.0.0", True),
    ("1.1.9", True),
    ("1.2.0-rc.1", True),   # a pre-release of the fixed version is still affected
    ("1.2.0", False),
    ("2.0.0", False),
])
def test_osv_semver_prerelease_edges(version, expected):
    events = [{"introduced": "1.0.0"}, {"fixed": "1.2.0"}]
    assert in_osv_range(version, events, semver_key) is expected


@pytest.mark.parametrize("version,expected", [
    ("2.0", True),       # epoch 0 is before any epoch-1 fix
    ("99.0", True),
    ("1!0.5", True),
    ("1!1.0rc1", True),
    ("1!1.0", False),
    ("1!1.0.post1", False),
])
def test_osv_pypi_epoch_edges(version, expected):
    events = [{"introduced": "0"}, {"fixed": "1!1.0"}]
    assert in_osv_range(version, events, ordering("PyPI")) is expected


def test_osv_multiple_windows_last_affected_and_limit():
    events = [{"introduced": "1.0.0"}, {"fixed": "1.2.0"}, {"introduced": "2.0.0"}, {"last_affected": "2.3.0"}]
    key = ordering("npm")
    assert [in_osv_range(v, events, key) for v in ("0.9.0", "1.1.0", "1.5.0", "2.0.0", "2.3.0", "2.3.1")] == \
        [False, True, False, True, True, False]
    assert in_osv_range("3.0.0", [{"introduced": "0"}, {"limit": "2.0.0"}], key) is False
    assert in_osv_range("1.0.0", [{"introduced": "0"}, {"limit": "2.0.0"}], key) is True


def test_osv_unknown_versions_are_never_guessed():
    assert in_osv_range("garbage", [{"introduced": "0"}], semver_key) is None
    assert in_osv_range("1.0.0", [{"introduced": "0"}, {"fixed": "not-a-version"}], semver_key) is None
    assert in_osv_range("1.0.0", [{"bogus": "1"}], semver_key) is None


def test_semver_range_type_overrides_ecosystem():
    # OSV: a SEMVER range is compared with semver even for a PyPI package.
    assert ordering("PyPI", "SEMVER") is semver_key
    assert ordering("PyPI", "ECOSYSTEM") is pep440_key


def test_github_constraints_and_nvd_cpe_bounds():
    key = ordering("pip")
    assert in_constraints("1.1", ">= 1.0, < 1.2", key) is True
    assert in_constraints("1.2", ">= 1.0, < 1.2", key) is False
    assert in_constraints("1.2rc1", "< 1.2", key) is True
    assert in_constraints("4.0.0", "= 4.0.0", ordering("npm")) is True
    assert in_constraints("1.0", "~> 1.0", key) is None
    cpe = {"versionStartIncluding": "8.4.0", "versionEndExcluding": "8.4.27"}
    assert in_cpe_bounds("8.4.23", cpe, generic_key) is True
    assert in_cpe_bounds("8.4.27", cpe, generic_key) is False
    assert in_cpe_bounds("8.3.99", cpe, generic_key) is False
    assert in_cpe_bounds("8.4.23", {}, generic_key) is None  # wildcard without bounds is too vague
    assert in_cpe_bounds("8.4.23", {"exact": "8.4.23"}, generic_key) is True


def test_first_fix_above():
    assert first_fix_above("8.4.23", ["8.3.30", "8.4.27", "8.5.1"], generic_key) == "8.4.27"
    assert first_fix_above("9.0.0", ["8.4.27"], generic_key) is None

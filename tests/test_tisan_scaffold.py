"""TS1: Tisan's project scaffold. No database. The npm checks live in the skill evals."""

from __future__ import annotations

import importlib.util
import json
import tarfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCAFFOLD_PATH = ROOT / "agents" / "tisan" / "scaffold.py"
TEMPLATE = ROOT / "agents" / "tisan" / "templates" / "next-site"
SKILL = ROOT / "tank" / "skills" / "tisan.scaffold" / "1.0.0"

TENANT_A = "11111111-1111-4111-8111-111111111111"
TENANT_B = "22222222-2222-4222-8222-222222222222"


def _load():
    spec = importlib.util.spec_from_file_location("tisan_scaffold_test", SCAFFOLD_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _brief(**overrides: object) -> dict:
    payload: dict = {
        "name": "Northwind",
        "slug": "northwind",
        "pages": ["home", "about", "contact", "privacy"],
        "locale": "en",
        "brand": {
            "colours": {
                "ink": "#001840",
                "paper": "#F4F6FB",
                "accent": "#E80008",
                "line": "#B8BFD0",
            },
            "fonts": {"heading": "Jost", "body": "Inter"},
            "logo_url": "https://cdn.example/northwind-logo.svg",
        },
    }
    payload.update(overrides)
    return payload


def test_template_has_the_pages_and_no_analytics() -> None:
    for rel in (
        "app/page.tsx",
        "app/about/page.tsx",
        "app/contact/page.tsx",
        "app/privacy/page.tsx",
        "app/not-found.tsx",
        "app/api/contact/route.ts",
        "app/tokens.css",
        "tailwind.config.ts",
        "package-lock.json",
        ".github/workflows/ci.yml",
        "playwright.config.ts",
        "lighthouserc.cjs",
        "scripts/site-paths.cjs",
        "scripts/deploy-gate.cjs",
        "tests/deploy-gate.test.ts",
        "e2e/a11y.spec.ts",
        "e2e/pages.spec.ts",
        "tests/gate.test.ts",
        "vitest.config.ts",
        "eslint.config.mjs",
    ):
        assert (TEMPLATE / rel).is_file(), rel
    package = json.loads((TEMPLATE / "package.json").read_text(encoding="utf-8"))
    assert package["scripts"]["test"] == "vitest run"
    assert package["scripts"]["typecheck"] == "tsc --noEmit"
    assert package["scripts"]["lhci"] == "lhci autorun"
    assert "playwright" in package["scripts"]["test:e2e"]
    assert "@axe-core/playwright" in package["devDependencies"]
    assert "@lhci/cli" in package["devDependencies"]
    assert (TEMPLATE / "tsconfig.json").read_text(encoding="utf-8").count('"strict": true') == 1
    banned = ("googletagmanager", "google-analytics", "gtag(", "plausible", "segment.com")
    for path in TEMPLATE.rglob("*"):
        if not path.is_file() or "node_modules" in path.parts or path.suffix == ".json" and path.name == "package-lock.json":
            continue
        if path.suffix.lower() not in {".ts", ".tsx", ".css", ".mjs", ".yml", ".md", ".json"}:
            continue
        text = path.read_text(encoding="utf-8")
        for word in banned:
            assert word not in text, f"{path} contains {word}"
    contact = (TEMPLATE / "app/contact/page.tsx").read_text(encoding="utf-8")
    assert 'action="/api/contact"' in contact
    assert "htmlFor=" in contact


def test_site_gate_runs_in_github_actions() -> None:
    commands = (
        "npm run lint",
        "npm run typecheck",
        "npm test",
        "npm run build",
        "npm run deploy",
        "npm run test:e2e",
        "npm run lhci",
    )
    template_ci = (TEMPLATE / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    repo_ci = (ROOT / ".github" / "workflows" / "tisan-site.yml").read_text(encoding="utf-8")
    for command in commands:
        assert command in template_ci
        assert command in repo_ci
    assert template_ci.index("npm run deploy") > template_ci.index("npm run build")
    assert repo_ci.index("npm run deploy") > repo_ci.index("npm run build")
    assert "agents/tisan/templates/next-site" in repo_ci
    gate = (TEMPLATE / "scripts" / "deploy-gate.cjs").read_text(encoding="utf-8")
    assert "missing-privacy-notice" in gate
    assert "missing-cookie-notice" in gate
    assert "comply.gdpr" in gate
    package = json.loads((TEMPLATE / "package.json").read_text(encoding="utf-8"))
    assert package["scripts"]["deploy"] == "node scripts/deploy-gate.cjs"
    for banned in ("urlopen", "httpx", "fetch(", "requests", "lokd.co.za", "createConnection"):
        assert banned not in gate
    lighthouse = (TEMPLATE / "lighthouserc.cjs").read_text(encoding="utf-8")
    for category in ("performance", "accessibility", "best-practices", "seo"):
        assert f"categories:{category}" in lighthouse
    assert "minScore: 0.9" in lighthouse
    playwright = (TEMPLATE / "playwright.config.ts").read_text(encoding="utf-8")
    for width in ("390", "768", "1440"):
        assert f"width: {width}" in playwright
    assert "@axe-core/playwright" in (TEMPLATE / "e2e" / "a11y.spec.ts").read_text(encoding="utf-8")


def test_scaffold_job_is_ten_minutes_and_other_jobs_stay_on_the_default() -> None:
    import sys

    chassis = str(ROOT / "agents" / "_chassis")
    if chassis not in sys.path:
        sys.path.insert(0, chassis)
    from chassis.jobs import timeout_for

    assert timeout_for("scaffold", {"scaffold": 600}) == 600
    assert timeout_for("ping", {"scaffold": 600}) is None
    assert timeout_for("scaffold", None) is None
    assert timeout_for("ping", {}) is None


def test_room_image_caches_npm_for_offline_checks() -> None:
    text = (ROOT / "agents" / "tisan" / "Dockerfile").read_text(encoding="utf-8")
    assert "TISAN_NPM_OFFLINE=1" in text
    assert "TISAN_NPM_CACHE=/opt/npm-cache" in text
    assert "npm ci --cache /opt/npm-cache" in text
    assert "USER agent" in text
    readme = (ROOT / "agents" / "tisan" / "README.md").read_text(encoding="utf-8")
    assert "tisan.scaffold" in readme
    assert "/data/builds/" in readme


def test_rejects_unsafe_briefs() -> None:
    scaffold = _load()
    with pytest.raises(scaffold.ScaffoldError):
        scaffold.validate(_brief(slug="../etc"))
    with pytest.raises(scaffold.ScaffoldError):
        scaffold.validate(_brief(slug="North"))
    brand = _brief()["brand"]
    bad_colour = json.loads(json.dumps(brand))
    bad_colour["colours"]["ink"] = "red; background: url(https://evil)"
    with pytest.raises(scaffold.ScaffoldError):
        scaffold.validate(_brief(brand=bad_colour))
    bad_font = json.loads(json.dumps(brand))
    bad_font["fonts"]["heading"] = 'Jost"; } body { color: red'
    with pytest.raises(scaffold.ScaffoldError):
        scaffold.validate(_brief(brand=bad_font))
    bad_logo = json.loads(json.dumps(brand))
    bad_logo["logo_url"] = "javascript:alert(1)"
    with pytest.raises(scaffold.ScaffoldError):
        scaffold.validate(_brief(brand=bad_logo))
    # The brief cannot choose a tenant. A bad directory name is refused on the job's tenant.
    scaffold.validate(_brief(tenant_id="../../other"))
    with pytest.raises(scaffold.ScaffoldError):
        scaffold._tenant("../../other")
    with pytest.raises(scaffold.ScaffoldError):
        scaffold._tenant("other/tenant")


@pytest.mark.asyncio
async def test_two_brands_write_different_tokens_for_their_own_tenants(tmp_path: Path) -> None:
    scaffold = _load()
    north = await scaffold.execute(_brief(), TENANT_A, data_root=tmp_path, run_checks_now=False)
    harbour_brand = {
        "colours": {
            "ink": "#14342B",
            "paper": "#F3EDE2",
            "accent": "#C4622D",
            "line": "#D5CBBA",
            "shore": "#7BA38A",
        },
        "fonts": {"heading": "Fraunces", "body": "Source Sans 3"},
        "logo_url": "https://cdn.example/harbour-logo.svg",
    }
    harbour = await scaffold.execute(
        _brief(name="Harbour", slug="harbour", locale="en-GB", brand=harbour_brand, pages=["home", "about", "notes"]),
        TENANT_B,
        data_root=tmp_path,
        run_checks_now=False,
    )
    assert north["token_set"]["colours"]["accent"] == "#E80008"
    assert harbour["token_set"]["colours"]["accent"] == "#C4622D"
    assert harbour["token_set"]["colours"]["shore"] == "#7BA38A"
    assert north["token_set"] != harbour["token_set"]
    assert TENANT_A in north["archive"]
    assert TENANT_B in harbour["archive"]
    assert TENANT_B not in north["archive"]
    assert north["files"] and harbour["files"]
    assert "app/tokens.css" in north["files"]
    assert "app/contact/page.tsx" in north["files"]
    assert "app/not-found.tsx" in north["files"]
    assert "node_modules" not in " ".join(north["files"])
    assert ".next" not in " ".join(north["files"])

    with tarfile.open(north["archive"], "r:gz") as tar:
        tokens = tar.extractfile("app/tokens.css")
        assert tokens is not None
        css = tokens.read().decode("utf-8")
        layout = tar.extractfile("app/layout.tsx")
        assert layout is not None
        tsx = layout.read().decode("utf-8")
    assert "#001840" in css
    assert "#E80008" in css
    assert "Jost" in css
    assert "#001840" not in tsx
    assert "#E80008" not in tsx
    assert "alt={`${site.name} logo`}" in tsx
    with tarfile.open(north["archive"], "r:gz") as tar:
        contact_spec = tar.extractfile("e2e/contact.spec.ts")
        assert contact_spec is not None
        assert 'goto("/contact")' in contact_spec.read().decode("utf-8")

    with tarfile.open(harbour["archive"], "r:gz") as tar:
        notes = tar.extractfile("app/notes/page.tsx")
        assert notes is not None
        assert "Notes" in notes.read().decode("utf-8")
        names = tar.getnames()
        assert "app/contact/page.tsx" not in names
        assert "app/privacy/page.tsx" not in names
        assert "e2e/contact.spec.ts" not in names
        assert "e2e/home.spec.ts" in names
        for name in names:
            if name.startswith("e2e/"):
                body = tar.extractfile(name)
                assert body is not None
                assert 'goto("/contact")' not in body.read().decode("utf-8")
        theme = tar.extractfile("tailwind.config.ts")
        assert theme is not None
        assert "--colour-shore" in theme.read().decode("utf-8")

    again = await scaffold.execute(_brief(), TENANT_A, data_root=tmp_path, run_checks_now=False)
    assert again["build"] == 2
    assert again["archive"].endswith("/2.tar.gz")
    sidecar = Path(again["archive"]).with_name("2.json")
    saved = json.loads(sidecar.read_text(encoding="utf-8"))
    assert saved["token_set"] == again["token_set"]
    assert "files" in saved and "checks" in saved


def test_skill_cases_are_two_different_brands() -> None:
    raw = (SKILL / "evals" / "cases.jsonl").read_text(encoding="utf-8").splitlines()
    cases = [json.loads(line) for line in raw if line.strip()]
    assert len(cases) == 2
    brands = [case["input"]["brand"]["colours"]["accent"] for case in cases]
    assert brands[0] != brands[1]
    assert cases[0]["input"]["slug"] != cases[1]["input"]["slug"]
    for case in cases:
        assert case["expected"]["ok"] is True
        assert [item["name"] for item in case["expected"]["checks"]] == [
            "npm ci",
            "npm run lint",
            "npm run build",
            "npm test",
        ]
    meta = (SKILL / "skill.yaml").read_text(encoding="utf-8")
    assert "id: tisan.scaffold" in meta
    assert "agent: tisan" in meta
    assert "rung: 3" in meta
    assert (SKILL / "CHANGELOG.md").is_file()
    assert (SKILL / "run.py").is_file()


@pytest.mark.asyncio
async def test_figma_linked_scaffold_refuses_missing_reading(tmp_path: Path) -> None:
    scaffold = _load()
    with pytest.raises(scaffold.ScaffoldError, match="frame data incomplete"):
        await scaffold.execute(_brief(figma={"file_key": "f" * 22, "node_id": "2:11"}), TENANT_A,
                               data_root=tmp_path, run_checks_now=False)


def test_visual_frames_select_requested_page_and_widths() -> None:
    scaffold = _load()
    frames = [{"frameId": "1:1", "page": "/", "width": 1440},
              {"frameId": "1:2", "page": "/", "width": 375},
              {"frameId": "1:3", "page": "/about", "width": 1440},
              {"frameId": "1:4", "page": "/about", "width": 375},
              {"frameId": "1:5", "page": "/", "width": 390},
              {"frameId": "1:6", "page": "/", "width": 1440}]
    with pytest.raises(scaffold.ScaffoldError, match="frame data incomplete"):
        scaffold.select_visual_frames({"visual": frames}, "1:1", "/")
    assert scaffold.select_visual_frames({"visual": frames[:-1]}, "1:1", "/") == frames[:2]
    assert scaffold.select_visual_frames({"visual": frames}, "0:1", "/about") == frames[2:4]


def test_logo_allowlist_matches_exact_repository_assets() -> None:
    import hashlib
    hashes = json.loads((TEMPLATE / "visual/brand-hashes.json").read_text())
    assert hashes == {path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                      for path in (ROOT / "workspace/public/brand").glob("*.png")}

    copied = TEMPLATE / "visual/assets/tervory-logo-on-white.png"
    assert hashlib.sha256(copied.read_bytes()).hexdigest() == hashes[copied.name]


def test_saved_canvas_reader_output_selects_real_page_and_rejects_duplicates():
    spec = importlib.util.spec_from_file_location("tisan_canvas_reader", ROOT / "agents/tisan/figma.py")
    figma = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(figma)
    scaffold = _load()
    saved = json.loads((ROOT / "tests/fixtures/tisan-multipage-canvas.json").read_text())
    frames = figma.visual_frames(saved["document"], saved["variables"])
    assert [frame["page"] for frame in frames] == ["/", "/", "/about", "/about"]
    assert all(not frame.get("incomplete") for frame in frames)
    assert all(frame["elements"][2]["brandFile"] == "tervory-logo-on-white.png" for frame in frames)
    # Target route can differ; membership still comes from the requested source frame.
    selected = scaffold.select_visual_frames({"visual": frames}, "3:1", "/")
    assert [frame["frameId"] for frame in selected] == ["3:1", "4:1"]
    assert [frame["frameId"] for frame in scaffold.select_visual_frames({"visual": frames}, "1:1", "/")] == ["1:1", "2:1"]
    for index in (2, 3):
        duplicate = json.loads(json.dumps(saved["document"]["children"][index]))
        duplicate["id"] = "9:1"
        canvas = {**saved["document"], "children": saved["document"]["children"] + [duplicate]}
        with pytest.raises(scaffold.ScaffoldError, match="frame data incomplete"):
            scaffold.select_visual_frames({"visual": figma.visual_frames(canvas, saved["variables"])}, "3:1", "/about")

"""Build a Next.js site from a short brief and check it before returning.

The project is packed to /data/builds/<tenant>/<slug>/<n>.tar.gz. Brand colours
and fonts become CSS variables and Tailwind tokens. Components do not carry
hard-coded colours. Checks use the npm cache baked into the image, so a run
can stay offline.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
import tarfile
import tempfile
from pathlib import Path
from typing import Any
from uuid import UUID

_SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_PAGE = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")
_TENANT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,80}$")
_LOCALE = re.compile(r"^[a-z]{2}(?:-[A-Z]{2})?$")
_COLOUR = re.compile(r"^#(?:[0-9A-Fa-f]{3}|[0-9A-Fa-f]{6}|[0-9A-Fa-f]{8})$")
_TOKEN = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")
_FONT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 .+-]{0,60}$")
_LOGO = re.compile(r"^https://[A-Za-z0-9._~:/?#\[\]@!$&'()*+,;=%-]{1,500}$")

_CORE_COLOURS = ("ink", "paper", "accent", "line")
_CORE_FONTS = ("heading", "body")
_STANDARD_PAGES = ("home", "about", "contact", "privacy")
_IGNORED_PAGES = {"404", "not-found"}
_SKIP_DIRS = {"node_modules", ".next", "playwright-report", "test-results", ".lighthouseci", "out"}
_LABELS = {"home": "Home", "about": "About", "contact": "Contact", "privacy": "Privacy"}
_CHECKS = (
    ("npm ci", 240),
    ("npm run lint", 180),
    ("npm run build", 240),
    ("npm test", 180),
)


class ScaffoldError(ValueError):
    """The brief is not safe to build."""


def template_dir() -> Path:
    raw = os.environ.get("TISAN_TEMPLATE", "").strip()
    if raw:
        path = Path(raw)
    else:
        path = Path(__file__).resolve().parent / "templates" / "next-site"
    if not (path / "package.json").is_file():
        raise ScaffoldError("the next-site template is missing")
    return path


def _text(value: Any, field: str, *, limit: int) -> str:
    if not isinstance(value, str):
        raise ScaffoldError(f"{field} must be text")
    cleaned = value.strip()
    if not cleaned or len(cleaned) > limit or any(ord(ch) < 32 for ch in cleaned):
        raise ScaffoldError(f"{field} is empty or too long")
    return cleaned


def _mapping(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ScaffoldError(f"{field} must be an object")
    return value


def validate(payload: dict[str, Any]) -> dict[str, Any]:
    """Return a normalised brief, or raise ScaffoldError."""
    if not isinstance(payload, dict):
        raise ScaffoldError("input must be an object")
    name = _text(payload.get("name"), "name", limit=80)
    slug = _text(payload.get("slug"), "slug", limit=60)
    if _SLUG.fullmatch(slug) is None:
        raise ScaffoldError("slug must be lowercase words separated by hyphens")
    locale_raw = payload.get("locale", "en")
    locale = _text(locale_raw, "locale", limit=10)
    if _LOCALE.fullmatch(locale) is None:
        raise ScaffoldError("locale must look like en or en-GB")
    pages = _pages(payload.get("pages"))
    brand = _mapping(payload.get("brand"), "brand")
    colours = _colours(_mapping(brand.get("colours"), "brand.colours"))
    fonts = _fonts(_mapping(brand.get("fonts"), "brand.fonts"))
    logo = _logo(brand.get("logo_url"))
    result = {
        "name": name,
        "slug": slug,
        "locale": locale,
        "pages": pages,
        "colours": colours,
        "fonts": fonts,
        "logo_url": logo,
    }
    copies = {item["name"]: str(UUID(item["copy"])) for item in (payload.get("pages") or [])
              if isinstance(item, dict) and item.get("copy") is not None and item["name"] in pages}
    if copies:
        result["copies"] = copies
    return result


def _pages(value: Any) -> list[str]:
    if value is None:
        value = list(_STANDARD_PAGES)
    if not isinstance(value, list) or not value or len(value) > 20:
        raise ScaffoldError("pages must be a short list")
    seen: list[str] = []
    for item in value:
        if isinstance(item, dict):
            if item.get("name") in seen:
                raise ScaffoldError("a page name is not valid")
            if set(item) - {"name", "copy"}:
                raise ScaffoldError("a page name is not valid")
            if item.get("copy") is not None:
                try:
                    UUID(item["copy"])
                except (ValueError, TypeError, AttributeError):
                    raise ScaffoldError("a page name is not valid") from None
            item = item.get("name")
        if not isinstance(item, str) or _PAGE.fullmatch(item) is None or len(item) > 40:
            raise ScaffoldError("a page name is not valid")
        if item in _IGNORED_PAGES or item in seen:
            continue
        seen.append(item)
    if "home" not in seen:
        seen.insert(0, "home")
    return seen


def _colours(raw: dict[str, Any]) -> dict[str, str]:
    colours: dict[str, str] = {}
    for key, value in raw.items():
        if not isinstance(key, str) or _TOKEN.fullmatch(key) is None or len(key) > 40:
            raise ScaffoldError("a colour name is not valid")
        if not isinstance(value, str) or _COLOUR.fullmatch(value.strip()) is None:
            raise ScaffoldError(f"colour {key} must be a hex colour")
        colours[key] = value.strip()
    missing = [key for key in _CORE_COLOURS if key not in colours]
    if missing:
        raise ScaffoldError("colours need ink, paper, accent, and line")
    return colours


def _fonts(raw: dict[str, Any]) -> dict[str, str]:
    fonts: dict[str, str] = {}
    for key in _CORE_FONTS:
        value = raw.get(key)
        if not isinstance(value, str) or _FONT.fullmatch(value.strip()) is None:
            raise ScaffoldError(f"font {key} must be a plain family name")
        fonts[key] = value.strip()
    return fonts


def _logo(value: Any) -> str | None:
    if value is None or value == "":
        return None
    if not isinstance(value, str) or _LOGO.fullmatch(value.strip()) is None:
        raise ScaffoldError("logo_url must be an https address")
    return value.strip()


def _tenant(tenant_id: str) -> str:
    if not isinstance(tenant_id, str) or _TENANT.fullmatch(tenant_id) is None:
        raise ScaffoldError("tenant_id is not a safe directory name")
    return tenant_id


def _label(page: str) -> str:
    if page in _LABELS:
        return _LABELS[page]
    return " ".join(part.capitalize() for part in page.split("-"))


def _href(page: str) -> str:
    if page == "home":
        return "/"
    return f"/{page}"


def _jsx_text(value: str) -> str:
    return value.replace("&", "&amp;").replace("<", "&lt;").replace("{", "&#123;")


def render_site(brief: dict[str, Any]) -> str:
    rows = ",\n".join(
        f"    {{ href: {json.dumps(_href(page))}, label: {json.dumps(_label(page))} }}"
        for page in brief["pages"]
    )
    logo = "null" if brief["logo_url"] is None else json.dumps(brief["logo_url"])
    return (
        "export type PageLink = {\n"
        "  href: string;\n"
        "  label: string;\n"
        "};\n\n"
        "export const site: {\n"
        "  name: string;\n"
        "  locale: string;\n"
        "  logoUrl: string | null;\n"
        "  pages: PageLink[];\n"
        "} = {\n"
        f"  name: {json.dumps(brief['name'])},\n"
        f"  locale: {json.dumps(brief['locale'])},\n"
        f"  logoUrl: {logo},\n"
        "  pages: [\n"
        f"{rows},\n"
        "  ],\n"
        "};\n"
    )


def render_tokens(brief: dict[str, Any]) -> str:
    lines = [":root {"]
    for key in sorted(brief["colours"]):
        lines.append(f"  --colour-{key}: {brief['colours'][key]};")
    lines.append(f"  --font-body: \"{brief['fonts']['body']}\", sans-serif;")
    lines.append(f"  --font-heading: \"{brief['fonts']['heading']}\", sans-serif;")
    lines.append("}")
    lines.append("")
    return "\n".join(lines)


def render_tailwind(colours: dict[str, str]) -> str:
    color_lines = "\n".join(
        f'        "{key}": "var(--colour-{key})",' for key in sorted(colours)
    )
    return (
        'import type { Config } from "tailwindcss";\n\n'
        "const config: Config = {\n"
        '  content: ["./app/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],\n'
        "  theme: {\n"
        "    extend: {\n"
        "      colors: {\n"
        f"{color_lines}\n"
        "      },\n"
        "      fontFamily: {\n"
        '        heading: "var(--font-heading)",\n'
        '        body: "var(--font-body)",\n'
        "      },\n"
        "    },\n"
        "  },\n"
        "  plugins: [],\n"
        "};\n\n"
        "export default config;\n"
    )


def render_extra_page(label: str, copy: str | None = None) -> str:
    safe = _jsx_text(label)
    body = "" if copy is None else f'      <p className="mt-3">{_jsx_text(copy)}</p>\n'
    return (
        "export default function Page() {\n"
        "  return (\n"
        "    <section>\n"
        f'      <h1 className="font-heading text-3xl">{safe}</h1>\n'
        f"{body}"
        "    </section>\n"
        "  );\n"
        "}\n"
    )


def _rename_package(project: Path, slug: str) -> None:
    old = '"name": "next-site"'
    new = f'"name": "{slug}"'
    for name in ("package.json", "package-lock.json"):
        path = project / name
        text = path.read_text(encoding="utf-8")
        count = text.count(old)
        if count == 0 and slug == "next-site":
            continue
        if count == 0:
            raise ScaffoldError(f"{name} is missing the template name")
        path.write_text(text.replace(old, new), encoding="utf-8")


def write_project(brief: dict[str, Any], dest: Path) -> None:
    """Copy the template and apply this brief. dest must not already exist."""
    shutil.copytree(
        template_dir(),
        dest,
        ignore=shutil.ignore_patterns(
            "node_modules",
            ".next",
            "playwright-report",
            "test-results",
            ".lighthouseci",
            "out",
            "tsconfig.tsbuildinfo",
        ),
    )
    (dest / "lib" / "site.ts").write_text(render_site(brief), encoding="utf-8")
    (dest / "app" / "tokens.css").write_text(render_tokens(brief), encoding="utf-8")
    extra = set(brief["colours"]) - set(_CORE_COLOURS)
    if extra:
        (dest / "tailwind.config.ts").write_text(render_tailwind(brief["colours"]), encoding="utf-8")
    _rename_package(dest, brief["slug"])
    keep = set(brief["pages"])
    if "about" not in keep:
        shutil.rmtree(dest / "app" / "about", ignore_errors=True)
    if "privacy" not in keep:
        shutil.rmtree(dest / "app" / "privacy", ignore_errors=True)
    if "contact" not in keep:
        shutil.rmtree(dest / "app" / "contact", ignore_errors=True)
        shutil.rmtree(dest / "app" / "api", ignore_errors=True)
        # The contact spec opens /contact. A site without that page must not ship it.
        (dest / "e2e" / "contact.spec.ts").unlink(missing_ok=True)
    for page in brief["pages"]:
        copy = brief.get("resolved_copy", {}).get(page)
        if page in _STANDARD_PAGES:
            if copy is not None:
                file = dest / "app" / ("page.tsx" if page == "home" else page + "/page.tsx")
                source = file.read_text(encoding="utf-8")
                body = '<p className="mt-3">' + _jsx_text(copy) + '</p>'
                if re.search(r'<p className="mt-3">.*?</p>', source, re.DOTALL):
                    source = re.sub(r'<p className="mt-3">.*?</p>', lambda _: body, source, count=1, flags=re.DOTALL)
                else:
                    source = source.replace('</h1>', '</h1>\n      ' + body, 1)
                file.write_text(source, encoding="utf-8")
            continue
        folder = dest / "app" / page
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "page.tsx").write_text(render_extra_page(_label(page), copy), encoding="utf-8")


def project_files(project: Path) -> list[str]:
    found: list[str] = []
    for path in project.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(project)
        if any(part in _SKIP_DIRS for part in rel.parts):
            continue
        if rel.name == "tsconfig.tsbuildinfo":
            continue
        found.append(rel.as_posix())
    return sorted(found)


def _data_root(explicit: Path | None) -> Path:
    if explicit is not None:
        explicit.mkdir(parents=True, exist_ok=True)
        return explicit
    raw = os.environ.get("DATA_DIR", "/data")
    path = Path(raw)
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".write-probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
    except OSError:
        path = Path(tempfile.gettempdir()) / "tisan-data"
        path.mkdir(parents=True, exist_ok=True)
    return path


def _next_build_number(folder: Path) -> int:
    highest = 0
    if folder.is_dir():
        for path in folder.glob("*.tar.gz"):
            stem = path.name[: -len(".tar.gz")]
            if stem.isdigit():
                highest = max(highest, int(stem))
    return highest + 1


def pack(project: Path, archive: Path) -> list[str]:
    files = project_files(project)
    archive.parent.mkdir(parents=True, exist_ok=True)
    partial = archive.with_name(f".{archive.name}.partial")
    with tarfile.open(partial, "w:gz") as tar:
        for rel in files:
            tar.add(project / rel, arcname=rel, recursive=False)
    partial.replace(archive)
    return files


def _check_env() -> dict[str, str]:
    keep = ("PATH", "HOME", "LANG", "LC_ALL", "LC_CTYPE", "TMPDIR", "TEMP", "TMP", "USER", "LOGNAME")
    env = {key: value for key, value in os.environ.items() if key in keep or key.startswith("NODE_")}
    env["NEXT_TELEMETRY_DISABLED"] = "1"
    env["PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD"] = "1"
    env["CI"] = "1"
    env["NPM_CONFIG_UPDATE_NOTIFIER"] = "false"
    cache = os.environ.get("TISAN_NPM_CACHE", "").strip()
    if not cache:
        cache = str(Path(tempfile.gettempdir()) / "tisan-npm-cache")
    Path(cache).mkdir(parents=True, exist_ok=True)
    env["NPM_CONFIG_CACHE"] = cache
    return env


def _npm_ci_args() -> list[str]:
    args = ["npm", "ci", "--no-audit", "--no-fund"]
    cache = os.environ.get("TISAN_NPM_CACHE", "").strip() or str(Path(tempfile.gettempdir()) / "tisan-npm-cache")
    args.extend(["--cache", cache])
    offline = os.environ.get("TISAN_NPM_OFFLINE", "").strip().lower()
    if offline in {"1", "true", "yes"}:
        args.append("--offline")
    return args


def _command(name: str) -> list[str]:
    if name == "npm ci":
        return _npm_ci_args()
    return name.split()


async def _run(args: list[str], cwd: Path, env: dict[str, str], timeout: int) -> tuple[int, str]:
    try:
        proc = await asyncio.create_subprocess_exec(
            *args,
            cwd=cwd,
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
    except FileNotFoundError:
        return 127, f"{args[0]} is not installed"
    try:
        out, _ = await asyncio.wait_for(proc.communicate(), timeout)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        return 124, "timed out"
    text = (out or b"").decode("utf-8", "replace")
    return proc.returncode if proc.returncode is not None else 1, text


def _short(text: str) -> str:
    flat = " ".join(text.split())
    if len(flat) > 500:
        return flat[-500:]
    return flat


async def run_checks(project: Path) -> tuple[list[dict[str, Any]], str]:
    env = _check_env()
    checks: list[dict[str, Any]] = []
    code, output = await _run(_command("npm ci"), project, env, 240)
    checks.append({"name": "npm ci", "ok": code == 0})
    if code != 0:
        return checks, _short(output) or "npm ci failed"
    # Generated files are formatted with the project's Prettier before lint.
    code, output = await _run(["npm", "run", "format"], project, env, 120)
    if code != 0:
        checks.append({"name": "npm run lint", "ok": False})
        return checks, _short(output) or "could not format the project"
    for name, timeout in _CHECKS[1:]:
        code, output = await _run(_command(name), project, env, timeout)
        checks.append({"name": name, "ok": code == 0})
        if code != 0:
            return checks, _short(output) or f"{name} failed"
    return checks, ""


def _manifest(
    brief: dict[str, Any],
    *,
    files: list[str],
    checks: list[dict[str, Any]],
    detail: str,
    archive: str,
    build: int,
) -> dict[str, Any]:
    ok = bool(checks) and all(item["ok"] for item in checks) and detail == ""
    return {
        "ok": ok,
        "name": brief["name"],
        "slug": brief["slug"],
        "locale": brief["locale"],
        "archive": archive,
        "build": build,
        "files": files,
        "token_set": {
            "colours": {key: brief["colours"][key] for key in sorted(brief["colours"])},
            "fonts": {"body": brief["fonts"]["body"], "heading": brief["fonts"]["heading"]},
            "logo_url": brief["logo_url"],
        },
        "checks": checks,
        "detail": detail,
    }


def select_visual_frames(reading: dict[str, Any], node_id: str, page: str) -> list[dict[str, Any]]:
    """Select the requested frame and its page's measured responsive counterparts."""
    frames = reading.get("visual", [])
    if not isinstance(frames, list):
        raise ScaffoldError("frame data incomplete")
    frames = [frame for frame in frames if isinstance(frame, dict)]
    requested = [frame for frame in frames if frame.get("frameId") == node_id]
    if len(requested) > 1:
        raise ScaffoldError("frame data incomplete")
    source_page = requested[0].get("page") if requested else page
    if not isinstance(source_page, str) or not source_page.startswith("/"):
        raise ScaffoldError("frame data incomplete")
    selected = [frame for frame in frames if frame.get("page") == source_page
                and frame.get("width") in (375, 1440)]
    for width in (375, 1440):
        if sum(frame.get("width") == width for frame in selected) > 1:
            raise ScaffoldError("frame data incomplete")
    return [{**frame, "page": page} for frame in selected]


async def _resolve_copy(brief: dict[str, Any], tenant: str) -> None:
    """Resolve references through Tank; the brief cannot supply its own body text."""
    if not brief.get("copies"):
        return
    import httpx
    key = os.environ.get("TANK_KEY", "")
    if not key:
        raise ScaffoldError("Writing record unavailable")
    resolved = {}
    async with httpx.AsyncClient(timeout=30, follow_redirects=False, trust_env=False) as client:
        for page, write_id in brief["copies"].items():
            try:
                response = await client.get("http://tank:8000/v1/trigger/copy/" + write_id,
                    params={"tenant_id": tenant}, headers={"X-Tank-Key": key,
                    "X-Tervory-Tenant": tenant, "X-Tervory-Home-Region": os.environ.get("TANK_REGION", "us-east")})
                response.raise_for_status()
                data = response.json()
                text = data["text"]
                if (data["tenant_id"] != tenant or data["write_id"] != write_id
                        or not isinstance(text, str) or not text.strip() or len(text) > 20000):
                    raise ValueError
            except (httpx.HTTPError, ValueError, KeyError, TypeError):
                raise ScaffoldError("Writing record unavailable") from None
            resolved[page] = text
    brief["resolved_copy"] = resolved


async def execute(
    payload: dict[str, Any],
    tenant_id: str,
    *,
    data_root: Path | None = None,
    run_checks_now: bool = True,
) -> dict[str, Any]:
    """Write the tarball for this tenant and, by default, run the checks first."""
    brief = validate(payload)
    tenant = _tenant(str(tenant_id))
    await _resolve_copy(brief, tenant)
    root = _data_root(data_root)
    builds = (root / "builds").resolve()
    folder = builds / tenant / brief["slug"]
    folder.mkdir(parents=True, exist_ok=True)
    if builds not in folder.resolve().parents:
        raise ScaffoldError("refusing to write outside this tenant's builds")
    number = _next_build_number(folder)
    with tempfile.TemporaryDirectory(prefix="tisan-") as tmp:
        project = Path(tmp) / "project"
        write_project(brief, project)
        if "figma" in payload:
            source = payload["figma"]
            if not isinstance(source, dict):
                raise ScaffoldError("frame data incomplete")
            file_key, node_id = source.get("file_key", ""), source.get("node_id", "")
            if not re.fullmatch(r"[A-Za-z0-9]{22,128}", file_key) or not re.fullmatch(r"\d+:\d+", node_id):
                raise ScaffoldError("frame data incomplete")
            reading_path = root / "readings" / tenant / file_key / (node_id.replace(":", "-") + ".json")
            try:
                reading = json.loads(reading_path.read_text())
            except (OSError, ValueError):
                raise ScaffoldError("frame data incomplete") from None
            # Validation is performed by the browser gate, against the saved evidence.
            # Empty/incomplete measurements cause that gate to fail; never derive a baseline from the page.
            visual_dir = project / "visual"
            visual_dir.mkdir(exist_ok=True)
            target_page = source.get("page", "home")
            if target_page not in brief["pages"]:
                raise ScaffoldError("frame data incomplete")
            target_path = "/" if target_page == "home" else f"/{target_page}"
            measurements = select_visual_frames(reading, node_id, target_path)
            (visual_dir / "frames.json").write_text(json.dumps(measurements))
        if run_checks_now:
            checks, detail = await run_checks(project)
        else:
            checks, detail = [], "checks not run"
        # Next adds a reference to .next during build. That folder is not part of the project we keep.
        env_dts = project / "next-env.d.ts"
        if env_dts.is_file():
            generated = '/// <reference path="./.next/types/routes.d.ts" />\n'
            env_dts.write_text(env_dts.read_text(encoding="utf-8").replace(generated, "", 1), encoding="utf-8")
        if payload.get("figma") and checks and all(item["ok"] for item in checks) and not detail:
            import importlib.util
            spec = importlib.util.spec_from_file_location("tisan_review_store", Path(__file__).with_name("review_store.py"))
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            module.save(root, project, tenant, brief["slug"], number, payload["figma"])
        files = pack(project, folder / f"{number}.tar.gz")
    manifest = _manifest(
        brief,
        files=files,
        checks=checks,
        detail=detail,
        archive=str(folder / f"{number}.tar.gz"),
        build=number,
    )
    (folder / f"{number}.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest

"""Assemble validated plans with tenant-private accepted copy; never generate code."""
from __future__ import annotations

import copy
import importlib.util
import json
import os
import re
import tempfile
import uuid
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import httpx
from pydantic_core import SchemaValidator, ValidationError, core_schema


def _scaffold():
    spec = importlib.util.spec_from_file_location("tisan_builder_scaffold", Path(__file__).with_name("scaffold.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def manifest() -> dict:
    data = json.loads((_scaffold().template_dir() / "sections/manifest.json").read_text())
    if data.get("schema") != "tisan.sections/1":
        raise ValueError("unsupported sections manifest")
    return data


def _validator(schema: dict) -> Any:
    """Compile the contract's JSON Schema subset with the installed Pydantic engine.

    Refuse unknown validation keywords rather than silently weakening a future contract.
    """
    supported = {"type", "properties", "required", "additionalProperties", "items", "minItems", "maxItems",
                 "minLength", "maxLength", "pattern", "enum"}
    if set(schema) - supported:
        raise ValueError("unsupported manifest schema keyword")
    kind = schema["type"]
    if "enum" in schema:
        return core_schema.literal_schema(schema["enum"])
    if kind == "string":
        return core_schema.str_schema(strict=True, min_length=schema.get("minLength"),
                                      max_length=schema.get("maxLength"), pattern=schema.get("pattern"))
    if kind == "array":
        return core_schema.list_schema(_validator(schema["items"]), strict=True,
                                       min_length=schema.get("minItems"), max_length=schema.get("maxItems"))
    if kind == "object":
        return core_schema.typed_dict_schema({k: core_schema.typed_dict_field(_validator(v), required=k in schema.get("required", []))
                    for k, v in schema.get("properties", {}).items()}, extra_behavior="forbid" if schema.get("additionalProperties") is False else "allow", strict=True)
    raise ValueError("unsupported manifest schema type")


def _planning(schema: dict, slots: list[str]) -> dict:
    result = copy.deepcopy(schema)
    for slot in slots:
        node = result
        parts = slot.split(".")
        for part in parts[:-1]:
            node = node["properties"][part.removesuffix("[]")]
            if part.endswith("[]"):
                node = node["items"]
        leaf = parts[-1]
        node["properties"][leaf] = {"type": "string", "maxLength": 0}
        node["required"] = [x for x in node.get("required", []) if x != leaf]
    return result


def _slot_paths(props: dict, schema: dict, slot: str) -> list[tuple[list, dict]]:
    """Expand arrays; include absent required leaves, but not absent optional slots."""
    paths: list[tuple[list, dict]] = []
    def visit(value, rule, parts, path):
        part, *rest = parts
        key = part.removesuffix("[]")
        if not rest:
            if key in value or key in rule.get("required", []):
                paths.append((path + [key], value))
            return
        if key not in value:
            return
        child = rule["properties"][key]
        if part.endswith("[]"):
            for index, item in enumerate(value[key]):
                visit(item, child["items"], rest, path + [key, index])
        else:
            visit(value[key], child, rest, path + [key])
    visit(props, schema, slot.split("."), [])
    return paths


def validate_plan(plan: Any, contract: dict) -> dict:
    if not isinstance(plan, dict) or set(plan) - {"logo", "nav", "footer", "ui", "pages"}:
        raise ValueError("plan must contain only site fields and pages")
    result = copy.deepcopy(plan)
    pages = result.get("pages")
    if not isinstance(pages, list) or not 1 <= len(pages) <= 20:
        raise ValueError("plan requires 1 to 20 pages")
    site = contract["site"]
    SchemaValidator(_validator(_planning(site["props"], site["text_slots"] + site["image_slots"]))).validate_python({k:v for k,v in result.items() if k != "pages"})
    names, paths = set(), set()
    for page in pages:
        if not isinstance(page, dict) or set(page) - {"name", "path", "title", "sections"}:
            raise ValueError("invalid page fields")
        name, path = page.get("name"), page.get("path")
        if not isinstance(name, str) or not re.fullmatch(r"[a-z][a-z0-9-]{0,39}", name) or name in names:
            raise ValueError("page names must be valid and unique")
        if path != ("/" if name == "home" else "/" + name) or path in paths:
            raise ValueError("page path must match its name and be unique")
        if page.get("title", "") != "":
            raise ValueError("page titles require accepted Trigger copy")
        names.add(name)
        paths.add(path)
        sections = page.get("sections")
        if not isinstance(sections, list) or len(sections) > 50:
            raise ValueError("page sections must be an array of at most 50 sections")
        ids = set()
        for section in sections:
            if not isinstance(section, dict) or set(section) != {"id", "type", "props"}:
                raise ValueError("section requires id, type and props")
            sid, kind = section["id"], section["type"]
            if not isinstance(sid, str) or not re.fullmatch(r"[a-z0-9-]{1,40}", sid) or sid in ids:
                raise ValueError("section ids must be valid and unique within the page")
            ids.add(sid)
            if not isinstance(kind, str) or kind not in contract["sections"]:
                raise ValueError("unknown section type")
            definition = contract["sections"][kind]
            SchemaValidator(_validator(_planning(definition["props"], definition["text_slots"] + definition["image_slots"]))).validate_python(section["props"])
    if "home" not in names:
        raise ValueError("plan requires a home page")
    return result


async def make_plan(payload: dict, tenant: str, contract: dict, tank: Any) -> dict:
    if "plan" in payload:
        return validate_plan(payload["plan"], contract)
    request = payload.get("request")
    if not isinstance(request, str) or not request.strip() or len(request) > 16000:
        raise ValueError("plan or request is required")
    if tank is None:
        raise ValueError("Tank client is required for request planning")
    messages = [{"role": "system", "content": "Return only a JSON plan with site fields logo/nav/footer/ui and pages (name, path, sections). A home page has path /; other paths are /<name>. Sections have type, unique id, props. Do not write text, code, page titles or image URLs. Omit text and image leaves; retain array/object structure and non-text props. Slot purposes describe the future accepted copy. Contract: " + json.dumps(contract)},
                {"role": "user", "content": request}]
    for attempt in range(2):
        reply = await tank.route(tenant, "tisan.plan", messages)
        raw = reply.get("content")
        try:
            return validate_plan(json.loads(raw), contract)
        except (ValueError, TypeError, ValidationError) as exc:
            if attempt:
                raise ValueError("invalid plan after retry: " + str(exc)) from None
            messages += [{"role": "assistant", "content": raw if isinstance(raw, str) else ""},
                         {"role": "user", "content": "Correct the plan using these validation errors: " + str(exc)}]
    raise AssertionError("unreachable")


def slots(plan: dict, contract: dict):
    groups = [("site", "site", plan, contract["site"])]
    for page in plan["pages"]:
        yield (page["name"] + "/title", "page", "the page title", page, "title", False)
        groups += [(page["name"] + "/" + s["id"], s["type"], s["props"], contract["sections"][s["type"]]) for s in page["sections"]]
    for prefix, kind, props, definition in groups:
        for image, field in ((False, "text_slots"), (True, "image_slots")):
            for slot in definition[field]:
                for path, parent in _slot_paths(props, definition["props"], slot):
                    yield (prefix + "/" + "/".join(map(str, path)), kind, definition.get("purpose", {}).get(slot, slot), parent, path[-1], image)


async def accepted_copy(http: Any, tenant: str, write_id: str, *, base: str, key: str, region: str) -> str:
    try:
        identifier = str(uuid.UUID(write_id))
    except (TypeError, ValueError, AttributeError):
        raise ValueError("copy write id must be a UUID") from None
    response = await http.get(base.rstrip("/") + "/v1/trigger/copy/" + identifier,
                              headers={"X-Tank-Key": key, "X-Tervory-Tenant": tenant, "X-Tervory-Home-Region": region},
                              follow_redirects=False, timeout=30)
    if response.status_code != 200:
        raise ValueError("accepted copy unavailable: HTTP " + str(response.status_code))
    data = response.json()
    try:
        same = uuid.UUID(str(data["tenant_id"])) == uuid.UUID(tenant) and uuid.UUID(str(data["write_id"])) == uuid.UUID(identifier)
    except (ValueError, TypeError, KeyError, AttributeError):
        same = False
    if not same or not isinstance(data.get("text"), str) or not data["text"].strip():
        raise ValueError("accepted copy does not match this tenant and write")
    return data["text"]


def _media_url(value: Any) -> bool:
    if not isinstance(value, str) or not re.fullmatch(r"https://[^\s]+|/media/[A-Za-z0-9._/-]+", value):
        return False
    parsed = urlsplit(value)
    return (not parsed.scheme or bool(parsed.hostname)) and parsed.username is None and parsed.password is None and ".." not in parsed.path.split("/")


async def execute(payload: dict, tenant_id: str, *, tank: Any = None, http: Any = None, data_root: Path | None = None) -> dict:
    scaffold = _scaffold()
    try:
        tenant = str(uuid.UUID(str(tenant_id)))
        brief = scaffold.validate(payload)
        contract = manifest()
        plan = await make_plan(payload, tenant, contract, tank)
        brief["pages"] = [p["name"] for p in plan["pages"]]
        copy_ids, media = payload.get("copy", {}), payload.get("media", {})
        if not isinstance(copy_ids, dict) or not isinstance(media, dict):
            raise ValueError("copy and media must be maps")
        pending = list(slots(plan, contract))
        known_copy = {s[0] for s in pending if not s[5]}
        known_media = {s[0] for s in pending if s[5]}
        if set(copy_ids) - known_copy or set(media) - known_media:
            raise ValueError("copy or media contains an unknown slot")
        missing = [{"key": k, "section_type": kind, "purpose": purpose} for k, kind, purpose, _, _, image in pending if not image and not copy_ids.get(k)]
        missing_media = [{"key": k, "section_type": kind, "purpose": purpose} for k, kind, purpose, _, _, image in pending if image and not media.get(k)]
        if missing or missing_media:
            return {"ok": False, "copy_needed": missing, "media_needed": missing_media}
        if any(not _media_url(v) for v in media.values()):
            raise ValueError("media URLs must use https:// or /media/ without credentials or traversal")
        async def fill(client):
            cache = {}
            for k, _, _, parent, leaf, image in pending:
                if image:
                    parent[leaf] = media[k]
                else:
                    wid = copy_ids[k]
                    if wid not in cache:
                        cache[wid] = await accepted_copy(client, tenant, wid, base=os.environ.get("TANK_URL", "http://tank:8000"), key=os.environ.get("TANK_KEY", ""), region=os.environ.get("TANK_REGION", "us-east"))
                    parent[leaf] = cache[wid]
        if http is None:
            async with httpx.AsyncClient() as client:
                await fill(client)
        else:
            await fill(http)
        SchemaValidator(_validator(contract["site"]["props"])).validate_python({k:v for k,v in plan.items() if k != "pages"})
        for page in plan["pages"]:
            for section in page["sections"]:
                SchemaValidator(_validator(contract["sections"][section["type"]]["props"])).validate_python(section["props"])
        root = scaffold._data_root(data_root)
        folder = root / "builds" / tenant / brief["slug"]
        folder.mkdir(parents=True, exist_ok=True)
        number = scaffold._next_build_number(folder)
        with tempfile.TemporaryDirectory(prefix="tisan-build-") as tmp:
            project = Path(tmp) / "project"
            scaffold.write_project(brief, project)
            (project / "content").mkdir(exist_ok=True)
            (project / "content/site.json").write_text(json.dumps({"schema": "tisan.content/1", **plan}, ensure_ascii=False, indent=2) + "\n")
            checks, detail = await scaffold.run_checks(project)
            if detail or not checks or not all(c["ok"] for c in checks):
                return {"ok": False, "checks": checks, "detail": detail}
            env_dts = project / "next-env.d.ts"
            if env_dts.is_file():
                env_dts.write_text(env_dts.read_text().replace('/// <reference path="./.next/types/routes.d.ts" />\n', "", 1))
            archive = folder / f"{number}.tar.gz"
            files = scaffold.pack(project, archive)
        result = scaffold._manifest(brief, files=files, checks=checks, detail=detail, archive=str(archive), build=number)
        (folder / f"{number}.json").write_text(json.dumps(result, indent=2) + "\n")
        return result
    except (ValueError, ValidationError) as exc:
        return {"ok": False, "refused": True, "detail": str(exc)}


async def handle(ctx: Any) -> dict:
    result = await execute(ctx.input, str(ctx.tenant_id), tank=ctx.tank)
    if result.get("ok") is True:
        import hashlib
        from chassis.events import publish
        await publish(str(ctx.tenant_id), "tisan.build.ready", str(ctx.job_id), {
            "job_id": str(ctx.job_id), "site_id": hashlib.sha256(result["slug"].encode()).hexdigest()})
    return result

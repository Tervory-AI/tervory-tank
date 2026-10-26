"""Tank's model boundary, code-first entry point, and audited exceptions.

Keep these literal paths: CI's room selector includes tests that reference the
changed room: agents/base, agents/tiger, agents/market_lab, agents/radix,
agents/rig, agents/tisan, agents/zenas. Shared/worker/Ghost changes run full CI.
This is a static tripwire, not a substitute for runtime egress restrictions.
"""
from __future__ import annotations

import ast
from collections import Counter
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]
EXTENSIONS = {".py", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".html", ".htm", ".vue", ".svelte", ".sh", ".yaml", ".yml", ".json", ".toml"}
PROVIDER_MODULES = {"openai", "anthropic", "litellm", "cohere", "groq", "mistralai", "google.generativeai", "google.genai", "huggingface_hub"}
PROVIDER_PACKAGES = PROVIDER_MODULES | {
    "@anthropic-ai/sdk", "@google/genai", "@google/generative-ai", "@huggingface/inference",
    "@mistralai/mistralai", "groq-sdk", "@ai-sdk/openai", "@ai-sdk/anthropic", "@ai-sdk/google",
}
PROVIDER_HOST = re.compile(
    r"(?:^|\.)(?:openai\.com|anthropic\.com|openrouter\.ai|deepseek\.com|mistral\.ai|x\.ai|"
    r"perplexity\.ai|groq\.com|cohere\.(?:ai|com)|generativelanguage\.googleapis\.com|"
    r"aiplatform\.googleapis\.com|router\.huggingface\.co|api-inference\.huggingface\.co|"
    r"search\.brave\.com|tavily\.com|firecrawl\.dev|serpapi\.com|serper\.dev|api\.context\.dev)$"
)
KEY = re.compile(r"^(?:OPENAI|ANTHROPIC|OPENROUTER|DEEPSEEK|GEMINI|GOOGLE|XAI|MISTRAL|MOONSHOT|GROQ|COHERE|PERPLEXITY|BRAVE|CONTEXT_DEV)_API_KEY$|^HF_(?:TOKEN|INFERENCE_TOKEN|JOBS_TOKEN)$|^LITELLM_(?:URL|MASTER_KEY)$")
TOKENS = re.compile(r'//[^\n]*|/\*[\s\S]*?\*/|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|`(?:\\.|[^`\\])*`')


@dataclass(frozen=True)
class Finding:
    path: str
    line: int
    kind: str
    evidence: str

    @property
    def identity(self) -> tuple[str, str, str]:
        return self.path, self.kind, hashlib.sha256(self.evidence.encode()).hexdigest()[:16]


def sensitive_literal(value: str) -> bool:
    from urllib.parse import urlsplit
    if re.search(r"/(?:v1/)?(?:chat/completions|completions|embeddings|responses)(?:$|[/?])", value):
        return True
    if value.startswith(("http://", "https://")):
        try:
            host = urlsplit(value).hostname or ""
        except ValueError:
            return False  # Malformed-URL fixtures cannot name a destination.
        return bool(PROVIDER_HOST.search(host) or host == "litellm" or host.endswith("-brain"))
    return False


def python_findings(path: str, text: str) -> list[Finding]:
    tree = ast.parse(text, filename=path)
    findings = []

    def add(node: ast.AST, kind: str) -> None:
        findings.append(Finding(path, node.lineno, kind, ast.dump(node, include_attributes=False)))

    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names = [node.module or ""] if isinstance(node, ast.ImportFrom) else [n.name for n in node.names]
            if any(name == provider or name.startswith(provider + ".") for name in names for provider in PROVIDER_MODULES):
                add(node, "provider import")
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and sensitive_literal(node.value):
            add(node, "model/paid endpoint")
        if isinstance(node, ast.Attribute) and node.attr in {"run_job", "run_uv_job"}:
            add(node, "paid compute reference")
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            def constant(value: ast.AST) -> str:
                if isinstance(value, ast.Constant) and isinstance(value.value, str):
                    return value.value
                if isinstance(value, ast.BinOp) and isinstance(value.op, ast.Add):
                    return constant(value.left) + constant(value.right)
                return ""
            if sensitive_literal(constant(node)):
                add(node, "assembled endpoint")
        if isinstance(node, ast.Subscript) and isinstance(node.slice, ast.Constant):
            value = node.slice.value
            if isinstance(value, str) and (KEY.fullmatch(value) or value.endswith("_BRAIN_URL")):
                add(node, "provider/brain setting")
        if not isinstance(node, ast.Call):
            continue
        name = ast.unparse(node.func)
        if node.args and isinstance(node.args[0], ast.Constant):
            value = node.args[0].value
            if isinstance(value, str) and name in {"__import__", "importlib.import_module"} and any(value == p or value.startswith(p + ".") for p in PROVIDER_MODULES):
                add(node, "provider import")
            if isinstance(value, str) and (KEY.fullmatch(value) or value.endswith("_BRAIN_URL")) and name.endswith((".get", ".getenv", "getenv", "require_env")):
                add(node, "provider/brain setting")
        if name.endswith((".chat.completions.create", ".responses.create", ".messages.create", ".generate_content", ".generateContent", ".invoke_model", ".from_pretrained")) or name in {"AIAgent", "TextEmbedding"}:
            add(node, "model invocation")
        if isinstance(node.func, ast.Attribute) and node.func.attr in {"run_job", "run_uv_job"}:
            add(node, "paid compute")
    return findings


def other_findings(path: str, text: str) -> list[Finding]:
    findings = []
    # Tokenize comments and strings together so commented code is not executed
    # evidence. Python uses its AST above; executable JS/TS imports are checked.
    for token in TOKENS.finditer(text):
        raw = token.group()
        if raw.startswith(("//", "/*")):
            continue
        value = raw[1:-1]
        try:
            value = json.loads(raw) if raw.startswith('"') else value
        except ValueError:
            pass
        before = text[max(0, token.start() - 100):token.start()]
        imported = any(value == p or value.startswith(p + "/") for p in PROVIDER_PACKAGES) and bool(re.search(r"(?:from\s*|import\s*\(?\s*|require\s*\(\s*)$", before))
        if sensitive_literal(value) or imported:
            findings.append(Finding(path, text.count("\n", 0, token.start()) + 1,
                                    "provider import" if imported else "model/paid endpoint", raw))
    # SDK calls are still suspect when the provider object is injected elsewhere.
    # Preserve offsets while removing strings/comments, including mutation fixtures.
    code = TOKENS.sub(lambda match: re.sub(r"[^\n]", " ", match.group()), text)
    for call in re.finditer(r"\b(?:[\w$]+\.)*(?:chat\.completions\.create|responses\.create|messages\.create|generateContent|generateText|streamText|invokeModel)\s*\(", code):
        findings.append(Finding(path, code.count("\n", 0, call.start()) + 1, "model invocation", call.group().strip()))
    # Unquoted YAML/shell URLs (including curl) are executable configuration too.
    for lineno, line in enumerate(text.splitlines(), 1):
        if line.lstrip().startswith(("#", "//", "*")):
            continue
        for match in re.finditer(r"https?://[^\s\"'`<>;,]+", line):
            if sensitive_literal(match.group()):
                findings.append(Finding(path, lineno, "configured endpoint", match.group()))
    return findings


def source_files(root: Path) -> list[Path]:
    result = subprocess.check_output(["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"], cwd=root)
    return sorted({root / name.decode() for name in result.split(b"\0") if name})


def scan(root: Path) -> list[Finding]:
    findings = []
    for file in source_files(root):
        relative = file.relative_to(root).as_posix()
        if relative.startswith("tank/") or file.suffix not in EXTENSIONS or not file.is_file():
            continue
        text = file.read_text(encoding="utf-8")
        findings.extend(python_findings(relative, text) if file.suffix == ".py" else other_findings(relative, text))
    return findings


# Exact AST/token fingerprints and occurrence counts, never a whole-file waiver.
# A changed or additional call in an audited file needs a fresh review.
EXCEPTIONS: dict[tuple[str, str, str], tuple[int, str]] = {
    ('agents/_brain/runner.py', 'model invocation', '90f24680902f34d8'): (1, 'Hermes is configured only for Tank /v1/agents/base; task agent.base.think.'),
    ('agents/base/app.py', 'provider/brain setting', '831f7c1c6901dfd6'): (3, 'Brain-enabled preview rejection and receipt display; no model call.'),
    ('agents/base/base_brain.py', 'provider/brain setting', '3734f96ed160f2b6'): (4, 'Recovery orchestration only; the Base brain sends model work to Tank after the free pass.'),
    ('agents/base/docker-compose.yml', 'configured endpoint', 'a0f34ba16fc832ef'): (1, 'Local Base recovery process address; its only model backend is Tank.'),
    ('agents/base/pilot/recording.json', 'model/paid endpoint', 'b66c19e42a77a35b'): (4, 'Saved pilot HTTP transcript, not executable provider traffic.'),
    ('agents/base/pilot/recording.json', 'model/paid endpoint', 'ba87316f64cb9f26'): (4, 'Saved pilot HTTP transcript, not executable provider traffic.'),
    ('agents/base/room.py', 'provider/brain setting', '831f7c1c6901dfd6'): (1, 'Selects the code-first worker entry point when recovery is configured.'),
    ('agents/base/sources/context_dev.py', 'model/paid endpoint', '192552ca3f4ca0ee'): (1, 'DEFERRED F2: direct paid Context.dev call; Base sources are outside this brief.'),
    ('agents/base/sources/context_dev.py', 'provider/brain setting', '91d27d8abcf0ec68'): (1, 'DEFERRED F2: direct paid Context.dev call; Base sources are outside this brief.'),
    ('agents/rig/forge/gpu.py', 'paid compute reference', 'b96746da2bb14495'): (1, 'DEFERRED F3: Tank reserves/claims spend, but Forge holds the HF key and submits directly.'),
    ('agents/rig/forge/gpu.py', 'provider import', 'cede1545b9e6578f'): (1, 'DEFERRED F3: Tank reserves/claims spend, but Forge holds the HF key and submits directly.'),
    ('agents/rig/forge/gpu.py', 'provider/brain setting', 'f257e6fa1235ee47'): (1, 'DEFERRED F3: Tank reserves/claims spend, but Forge holds the HF key and submits directly.'),
    ('agents/rig/forge/gpu/reconstruct.py', 'model invocation', '1df496be11429cf1'): (1, 'Local Trellis weights inside the licensed GPU job; paid submission remains DEFERRED F3.'),
    ('agents/rig/forge/service.py', 'assembled endpoint', '84b00a482df76b97'): (1, 'Local Forge relay reaches Tank through the Rig brain, not a model endpoint.'),
    ('agents/rig/forge/service.py', 'model/paid endpoint', '7cb505ce9b9a087b'): (1, 'Local Forge relay reaches Tank through the Rig brain, not a model endpoint.'),
    ('agents/rig/rig_brain/runner.py', 'model invocation', '01ac9148e4f41fd2'): (1, 'Hermes is configured only for Tank /v1/agents/rig; task agent.rig.think.'),
    ('agents/rig/rigbox/three_d/forge.py', 'assembled endpoint', '631947c3d125dc97'): (1, 'Local job submission; paid GPU authorization is relayed to Tank before execution.'),
    ('agents/rig/rigbox/three_d/forge.py', 'model/paid endpoint', 'f51a9f62438e052c'): (1, 'Local job submission; paid GPU authorization is relayed to Tank before execution.'),
    ('docker-compose.yml', 'configured endpoint', '29a2f8b609b5bf88'): (1, 'Tank alone receives the internal LiteLLM origin in this stack.'),
    ('docker-compose.za.yml', 'configured endpoint', '29a2f8b609b5bf88'): (1, 'ZA Tank alone receives the internal LiteLLM origin in this stack.'),
    ('hermes/embeddings.py', 'model invocation', 'bab8d65d49255201'): (1, 'Free local CPU embedding model; client text is not sent to an inference API.'),
    ('jobs/train/run.py', 'paid compute', '7031495de3954e37'): (1, 'DEFERRED F4: platform training CLI submits paid HF jobs and writes the ledger directly.'),
    ('jobs/train/run.py', 'paid compute reference', '8faf4f0a7af908c3'): (1, 'DEFERRED F4: platform training CLI submits paid HF jobs and writes the ledger directly.'),
    ('jobs/train/run.py', 'provider import', 'cede1545b9e6578f'): (1, 'DEFERRED F4: platform training CLI submits paid HF jobs and writes the ledger directly.'),
    ('jobs/train/run.py', 'provider/brain setting', 'aa69b9f5c0666833'): (2, 'DEFERRED F4: platform training CLI submits paid HF jobs and writes the ledger directly.'),
    ('jobs/train/train.py', 'provider import', '36aad997c7ad2e00'): (1, 'Training job downloads artifacts and uploads private weights; no inference API call.'),
    ('jobs/train/train.py', 'provider import', 'ad83b7003b5a2a6c'): (1, 'Training job downloads artifacts and uploads private weights; no inference API call.'),
    ('jobs/train/train.py', 'provider import', 'cede1545b9e6578f'): (1, 'Training job downloads artifacts and uploads private weights; no inference API call.'),
    ('jobs/train/train.py', 'provider/brain setting', 'aa69b9f5c0666833'): (1, 'Training job downloads artifacts and uploads private weights; no inference API call.'),
    ('litellm/config.yaml', 'configured endpoint', '4eca9db60dcd6816'): (14, 'The Tank-owned provider backend roster; keys are environment references.'),
    ('litellm/config.za.yaml', 'configured endpoint', '4eca9db60dcd6816'): (14, 'The ZA Tank-owned provider backend roster; keys are environment references.'),
    ('tests/test_agent1_brain_route.py', 'model/paid endpoint', '08227cba77e63840'): (1, 'In-process Tank brain-route requests with mocked provider responses.'),
    ('tests/test_agent1_brain_route.py', 'model/paid endpoint', '2af2a03f2c5ee673'): (7, 'In-process Tank brain-route requests with mocked provider responses.'),
    ('tests/test_agent1_hermes_runtime.py', 'model/paid endpoint', '2af2a03f2c5ee673'): (1, 'Local fake Tank endpoint asserts the Hermes backend contract.'),
    ('tests/test_agent1_hermes_runtime.py', 'model/paid endpoint', '352d96eda3620c83'): (1, 'Local fake Tank endpoint asserts the Hermes backend contract.'),
    ('tests/test_agent1_isolation.py', 'model/paid endpoint', 'c916f9b9928a3b37'): (3, 'Mocked local recovery URL and URL-rejection fixtures.'),
    ('tests/test_agent1_pilot.py', 'model/paid endpoint', '2af2a03f2c5ee673'): (1, 'Opt-in pilot uses recorded provider responses and a local recovery service.'),
    ('tests/test_agent1_pilot.py', 'model/paid endpoint', '352d96eda3620c83'): (1, 'Opt-in pilot uses recorded provider responses and a local recovery service.'),
    ('tests/test_agent1_skills.py', 'provider/brain setting', '9aa2189ee9084d45'): (1, 'In-process brain skill/receipt contract fixture.'),
    ('tests/test_b3_base_room.py', 'model/paid endpoint', 'f598015b96924387'): (1, 'Asserts the configured internal recovery service; no inference call.'),
    ('tests/test_b3_base_room.py', 'provider/brain setting', '387d34d382dce602'): (1, 'Asserts the configured internal recovery service; no inference call.'),
    ('tests/test_dashboards.py', 'model/paid endpoint', '650f0508439c020d'): (1, 'Tests Tank response destinations and failed-provider accounting with fakes.'),
    ('tests/test_dashboards.py', 'model/paid endpoint', '8fea251131ae9da4'): (1, 'Tests Tank response destinations and failed-provider accounting with fakes.'),
    ('tests/test_ledger_sql_param.py', 'model/paid endpoint', '08227cba77e63840'): (1, 'In-process mocked model requests exercise parameterized ledger writes.'),
    ('tests/test_models3_open_weight.py', 'model/paid endpoint', '7975d910f7eca723'): (1, 'Asserts the configured backend roster and provider URL, not a live call.'),
    ('tests/test_models3_open_weight.py', 'model/paid endpoint', 'b8534f2003245cb6'): (1, 'Asserts the configured backend roster and provider URL, not a live call.'),
    ('tests/test_perplexity_litellm_contract.py', 'model/paid endpoint', '80faac04ee963b47'): (1, 'Opt-in contract harness with a fake provider and gated LiteLLM container.'),
    ('tests/test_perplexity_litellm_contract.py', 'model/paid endpoint', 'd417c10ac7dcbfb2'): (1, 'Opt-in contract harness with a fake provider and gated LiteLLM container.'),
    ('tests/test_perplexity_litellm_contract.py', 'provider import', '197c7185fc9fccaa'): (1, 'Opt-in contract harness with a fake provider and gated LiteLLM container.'),
    ('tests/test_perplexity_litellm_contract.py', 'provider import', '20f25f8e0e1a1047'): (1, 'Opt-in contract harness with a fake provider and gated LiteLLM container.'),
    ('tests/test_perplexity_litellm_contract.py', 'provider import', '542500d0073d3c29'): (1, 'Opt-in contract harness with a fake provider and gated LiteLLM container.'),
    ('tests/test_perplexity_litellm_contract.py', 'provider import', '702d65b5108b61bd'): (1, 'Opt-in contract harness with a fake provider and gated LiteLLM container.'),
    ('tests/test_perplexity_research.py', 'model/paid endpoint', '0f6b0949a1569218'): (1, 'Mock-transport research/provider contract fixtures.'),
    ('tests/test_perplexity_research.py', 'model/paid endpoint', '3ec65d4e1a817ebd'): (1, 'Mock-transport research/provider contract fixtures.'),
    ('tests/test_perplexity_research.py', 'model/paid endpoint', '5c5b877220f0cfb6'): (1, 'Mock-transport research/provider contract fixtures.'),
    ('tests/test_rig_box.py', 'model/paid endpoint', '5fcf41e258708b62'): (1, 'Assertions for the Rig brain model request boundary.'),
    ('tests/test_rig_box_runtime.py', 'model/paid endpoint', '352d96eda3620c83'): (1, 'Local fake Tank HTTP handler used by the Rig runtime test.'),
    ('tests/test_rig_box_runtime.py', 'model/paid endpoint', '6b33be13b765d3f7'): (1, 'Local fake Tank HTTP handler used by the Rig runtime test.'),
    ('tests/test_rig_box_tank.py', 'model/paid endpoint', '6b33be13b765d3f7'): (4, 'In-process Tank endpoint tests with mocked upstream completion.'),
    ('tests/test_searxng_ferry.py', 'provider/brain setting', '995ee6ccdf9f6f89'): (1, 'Service URL in a network-isolation rejection fixture.'),
    ('tests/test_tiger.py', 'model/paid endpoint', 'd56e43650240a367'): (1, 'Internal LiteLLM URL is a rejected SSRF target.'),
    ('tests/test_workers_1.py', 'model/paid endpoint', '5d03fe33c97e3f2a'): (1, 'Provider host is a refused worker destination.'),
    ('tests/test_za_region.py', 'model/paid endpoint', '7975d910f7eca723'): (1, 'Checks a configured backend URL in a region contract fixture.'),
    ('workers/task/__main__.py', 'model/paid endpoint', '352d96eda3620c83'): (1, 'Inbound loopback compatibility endpoint; forward_chat only sends to Tank /v1/route.'),
}


def test_no_new_tank_bypass() -> None:
    findings = scan(ROOT)
    counts = Counter(item.identity for item in findings)
    unexpected = [item for item in findings if counts[item.identity] > EXCEPTIONS.get(item.identity, (0, ""))[0]]
    stale = [identity for identity, (count, reason) in EXCEPTIONS.items() if not reason or counts[identity] != count]
    assert not unexpected, "Unaudited model/paid calls outside Tank:\n" + "\n".join(
        f"{item.path}:{item.line}: {item.kind} [{item.identity[2]}]" for item in unexpected)
    assert not stale, f"Remove or re-audit stale exceptions: {stale}"


@pytest.mark.parametrize("source", [
    "import openai as provider",
    "from anthropic import AsyncAnthropic",
    "client.chat.completions.create(model=chosen, messages=messages)",
    'http.post("https://api.openai.com/v1/chat/completions")',
    'url = "https://api." + "anthropic.com/v1/messages"',
    'client.post(os.environ["BASE_BRAIN_URL"] + "/tasks")',
    'key = os.getenv("HF_INFERENCE_TOKEN")',
    'provider = importlib.import_module("openai")',
    'model = AutoModel.from_pretrained(model_path)',
])
def test_python_detector_rejects_new_bypasses(source: str) -> None:
    assert python_findings("new_agent.py", source)


@pytest.mark.parametrize("source", [
    'import OpenAI from "openai";',
    'const client = require("anthropic");',
    'import Anthropic from "@anthropic-ai/sdk";',
    'const provider = await import("@google/genai");',
    'await provider.chat.completions.create(request);',
    'fetch("https://api.openai.com/v1/chat/completions", options);',
])
def test_browser_detector_rejects_new_bypasses(source: str) -> None:
    assert other_findings("new_agent.ts", source)


def test_room_ci_always_selects_boundary_check() -> None:
    import importlib.util
    spec = importlib.util.spec_from_file_location("one_door_ci_scope", ROOT / ".github/scripts/ci_scope.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    for room in module.ROOM_TESTS:
        selected = module.select([f"agents/{room}/new_call.py"])
        assert "tests/test_tank_one_door.py" in selected["tests"]


@pytest.fixture
def base_bridge(monkeypatch):
    import importlib.util
    import sys
    spec = importlib.util.spec_from_file_location("one_door_base_bridge", ROOT / "agents/base/base_brain.py")
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, module)
    spec.loader.exec_module(module)
    return module


@pytest.mark.asyncio
@pytest.mark.parametrize("status,unresolved,expected", [("done", [], False), ("queued", ["gap"], False), ("failed", ["gap"], False), ("done", ["gap"], True)])
async def test_base_code_precedes_optional_brain(monkeypatch, base_bridge, status, unresolved, expected):
    from contextlib import asynccontextmanager
    import sys
    from types import SimpleNamespace
    from uuid import uuid4
    tenant, task = uuid4(), uuid4()
    events = []

    class Pool:
        @asynccontextmanager
        async def acquire(self):
            yield self

        async def fetch(self, sql, *args):
            assert args == (tenant, task) and "tenant_id=$1 AND task_id=$2" in sql
            return [{"id": uuid4(), "raw": {}, "profile": {}, "status": "failed"} for _ in unresolved]

        async def fetchrow(self, sql, *args):
            assert args == (tenant, task) and "tenant_id=$1 AND id=$2" in sql
            return {"status": status, "result": "Free pass"}

    async def skill(name, payload):
        events.append("code")
        assert payload["_base_brain_free"] is True
        assert payload["_base_brain_task"] == str(task)
        return {}

    async def pipeline(pool, task_id, cfg, call):
        assert task_id == task
        await call("base.normalize", {})

    async def recover(*args, free_result):
        assert events == ["code"] and free_result["unresolved"]
        events.append("brain")

    monkeypatch.setitem(sys.modules, "room", SimpleNamespace(_run_batch=pipeline))
    monkeypatch.setattr(base_bridge, "drive_batch", recover)
    await base_bridge.run_code_first(Pool(), None, task, {"tenant_id": str(tenant)}, skill)
    assert events == (["code", "brain"] if expected else ["code"])


@pytest.mark.asyncio
@pytest.mark.parametrize("brain_available", [True, False])
async def test_base_recovery_reuses_free_result_and_continues_once(monkeypatch, base_bridge, brain_available):
    import asyncio
    from contextlib import asynccontextmanager
    import secrets
    import sys
    from types import SimpleNamespace
    from uuid import uuid4
    import httpx
    from fastapi import FastAPI

    tenant, task, ledger = uuid4(), uuid4(), uuid4()
    key = secrets.token_urlsafe(24)
    monkeypatch.setenv("TANK_KEY", key)
    monkeypatch.setenv("BASE_BRAIN_URL", "http://base-recovery")
    events = []
    state = {"unresolved": True}
    final = []
    original_client = httpx.AsyncClient
    app = FastAPI()
    base_bridge.register(app)

    class Pool:
        @asynccontextmanager
        async def acquire(self):
            yield self

        async def execute(self, sql, *args):
            assert args[:2] == (tenant, task)
            if "status=$4" in sql:
                final.append(args[3])

        async def fetch(self, sql, *args):
            assert args == (tenant, task)
            return [{"id": uuid4(), "raw": {}, "profile": {}, "status": "failed"}] if state["unresolved"] else []

        async def fetchrow(self, sql, *args):
            assert args == (tenant, task)
            return {"status": "done", "result": "Pipeline completed"}

    async def skill(name, payload):
        assert payload["_base_brain_task"] == str(task)
        free = payload.get("_base_brain_free") is True
        events.append("free" if free else "continuation")
        state["unresolved"] = free
        return {}

    async def pipeline(pool, task_id, cfg, call):
        await call("base.normalize", {})

    async def upstream(request):
        if request.method == "DELETE":
            events.append("cancel")
            return httpx.Response(200, json={})
        assert events == ["free"]
        events.append("brain")
        if not brain_available:
            return httpx.Response(503)
        async with original_client(transport=httpx.ASGITransport(app=app), base_url="http://base") as client:
            payload = {"tenant_id": str(tenant), "task_id": str(task)}
            headers = {"X-Tank-Key": key}
            other = await client.get("/brain/pipeline", params={**payload, "tenant_id": str(uuid4())}, headers=headers)
            assert other.status_code == 404
            for _ in range(2):
                cached = await client.post("/brain/pipeline", json=payload, headers=headers)
                assert cached.status_code == 200 and cached.json()["unresolved"]
                assert events == ["free", "brain"]
            finishing = await client.post("/brain/pipeline", json={**payload, "finish": True}, headers=headers)
            assert finishing.status_code == 202
            await asyncio.shield(base_bridge.active[(tenant, task)].job)
            repeated = await client.post("/brain/pipeline", json={**payload, "finish": True}, headers=headers)
            assert repeated.status_code == 200
        return httpx.Response(200, json={"tenant_id": str(tenant), "task_id": str(task), "status": "done",
                                        "steps": [], "model_receipts": [{"ledger_id": str(ledger), "cost_usd": 0.1}]})

    monkeypatch.setitem(sys.modules, "room", SimpleNamespace(_run_batch=pipeline))
    monkeypatch.setattr(base_bridge.httpx, "AsyncClient", lambda **kw: original_client(transport=httpx.MockTransport(upstream), **kw))
    cfg = {"tenant_id": str(tenant), "batch": "fixture", "count": 1}
    await base_bridge.run_code_first(Pool(), SimpleNamespace(_headers=lambda: {"X-Tank-Key": key}), task, cfg, skill)
    assert events == (["free", "brain", "continuation"] if brain_available else ["free", "brain", "cancel", "continuation"])
    assert final == ["done"] and (tenant, task) not in base_bridge.active


@pytest.mark.asyncio
async def test_autumbra_model_call_uses_existing_tank_client(monkeypatch):
    import secrets
    from uuid import uuid4
    import httpx
    from agents.ghost import dogfood_hf as dogfood
    key, ledger = secrets.token_urlsafe(24), str(uuid4())
    monkeypatch.setenv("TANK_KEY", key)
    monkeypatch.setenv("AUTUMBRA_HF_LIVE", "1")
    seen = []

    def upstream(request):
        assert str(request.url) == "http://tank:8000/v1/route"
        assert request.headers["X-Tank-Key"] == key and "authorization" not in request.headers
        body = json.loads(request.content)
        assert body["tenant_id"] == dogfood.PLATFORM_TENANT
        assert body["agent"] == "ghost" and body["task_type"] == "reason.brief"
        assert body["max_tokens"] == 200
        assert "model" not in body
        seen.append(body)
        return httpx.Response(200, json={"content": "Fixture summary", "ledger_id": ledger, "cost_usd": 0})

    original_client = httpx.AsyncClient
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: original_client(transport=httpx.MockTransport(upstream), **kw))
    answer = await dogfood.call_tank_inference("Synthetic events only")
    assert answer["ledger_id"] == ledger and len(seen) == 1
    monkeypatch.delenv("AUTUMBRA_HF_LIVE")
    with pytest.raises(dogfood.HfDogfoodError, match="STOPPED"):
        await dogfood.call_tank_inference("Synthetic events only")
    assert len(seen) == 1


def test_autumbra_refuses_agent_model_override():
    from agents.ghost.dogfood_hf import HfDogfoodError, call_hf_inference
    with pytest.raises(HfDogfoodError, match="Tank selects"):
        call_hf_inference("Synthetic events only", model="external-choice")

"""Fail if a committed file contains something that looks like a real key or password.

Placeholders (empty values, ${ENV}, os.environ/..., pk_test_/sk_test_ dummies) are allowed.
The check reads git's index of tracked files, so local .env files and .git are out of scope.
"""
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

_SKIP_SUFFIXES = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".woff", ".woff2",
    ".ttf", ".eot", ".pdf", ".zip", ".gz", ".pyc", ".wasm",
}

_LIVE = [
    re.compile(r"-----BEGIN (?:RSA |OPENSSH |EC |DSA |PGP )?PRIVATE KEY-----"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bghp_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}"),
    re.compile(r"\bsk-ant-[A-Za-z0-9_\-]{10,}"),
    re.compile(r"(?<![A-Za-z0-9_])sk-[A-Za-z0-9]{20,}"),
    re.compile(r"\bsk_live_[A-Za-z0-9]{8,}"),
    re.compile(r"\bpk_live_[A-Za-z0-9]{8,}"),
    re.compile(r"\brk_live_[A-Za-z0-9]{8,}"),
    re.compile(r"\bAIza[0-9A-Za-z_\-]{30,}"),
    re.compile(r"\beyJ[A-Za-z0-9_\-]{20,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}"),
]

_ASSIGNED = re.compile(
    r"""(?ix)
    (?:^|[^A-Za-z0-9])
    (?:api[_-]?key|secret[_-]?key|client[_-]?secret|password|passwd|access[_-]?token|auth[_-]?token)
    \s*[:=]\s*
    ['\"]?
    (?P<val>[^\s'\"\#]{12,})
    """
)

_PLACEHOLDER_BITS = (
    "change-me", "changeme", "dummy", "example", "placeholder", "your-key", "your_key",
    "set-by-env", "pk_test_", "sk_test_", "replace-me", "redacted", "xxxx",
)


def _placeholder(value: str) -> bool:
    lowered = value.lower()
    if lowered.startswith("${") or lowered.startswith("os.environ") or "process.env" in lowered:
        return True
    return any(bit in lowered for bit in _PLACEHOLDER_BITS)


def findings_in_text(name: str, text: str) -> list[str]:
    hits: list[str] = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        for pattern in _LIVE:
            if pattern.search(line):
                hits.append(f"{name}:{lineno}: looks like a live key ({pattern.pattern[:40]})")
                break
        assigned = _ASSIGNED.search(line)
        if assigned and not _placeholder(assigned.group("val")):
            hits.append(f"{name}:{lineno}: assigned secret is not a placeholder")
    return hits


def _tracked_files() -> list[Path]:
    raw = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT)
    return [ROOT / part.decode() for part in raw.split(b"\0") if part]


def test_no_committed_secrets() -> None:
    problems: list[str] = []
    for path in _tracked_files():
        if path.suffix.lower() in _SKIP_SUFFIXES or not path.is_file():
            continue
        data = path.read_bytes()
        if b"\0" in data[:1024]:
            continue
        problems.extend(findings_in_text(str(path.relative_to(ROOT)), data.decode("utf-8", errors="ignore")))
    assert not problems, "\n".join(problems)


def test_scanner_flags_a_live_key_and_allows_the_ci_dummy() -> None:
    live = "API_KEY=" + "sk_live_" + "abcdefghijklmnop"
    assert findings_in_text("sample.env", live)
    dummy = (
        "CLERK_SECRET_KEY=sk_test_dummy\n"
        "NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_test_ZHVtbXkuY2xlcmsuYWNjb3VudHMuZGV2JA==\n"
    )
    assert findings_in_text("ci.yml", dummy) == []
    assert findings_in_text("compose.yml", "POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}") == []
    assert findings_in_text("tank.ts", 'const TANK_API_KEY = process.env.TANK_API_KEY ?? "";') == []

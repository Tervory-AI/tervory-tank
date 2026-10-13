"""tank/schema.sql is applied on every Tank start, so every statement must be safe to re-run."""
import pathlib
import re

SCHEMA = pathlib.Path(__file__).resolve().parents[1] / "tank" / "schema.sql"

_FORBIDDEN = re.compile(r"\b(DROP|RENAME)\b", re.IGNORECASE)


def _split_statements(sql: str) -> list[str]:
    """Split on semicolons that are not inside string literals. Line comments are dropped."""
    statements: list[str] = []
    buf: list[str] = []
    i = 0
    n = len(sql)
    in_str = False
    while i < n:
        c = sql[i]
        if in_str:
            buf.append(c)
            if c == "'":
                if i + 1 < n and sql[i + 1] == "'":
                    buf.append(sql[i + 1])
                    i += 2
                    continue
                in_str = False
            i += 1
            continue
        if c == "'":
            in_str = True
            buf.append(c)
            i += 1
            continue
        if c == "-" and i + 1 < n and sql[i + 1] == "-":
            while i < n and sql[i] != "\n":
                i += 1
            buf.append(" ")
            continue
        if c == ";":
            statements.append("".join(buf).strip())
            buf = []
            i += 1
            continue
        buf.append(c)
        i += 1
    tail = "".join(buf).strip()
    if tail:
        statements.append(tail)
    return [s for s in statements if s]


def _idempotent(statement: str) -> bool:
    head = re.match(r"^(CREATE|ALTER|INSERT|UPDATE)\b", statement, re.IGNORECASE)
    if head is None:
        return False
    kind = head.group(1).upper()
    if kind == "CREATE":
        return re.search(r"\bIF\s+NOT\s+EXISTS\b", statement, re.IGNORECASE) is not None
    if kind == "ALTER":
        return re.search(r"\bADD\s+COLUMN\s+IF\s+NOT\s+EXISTS\b", statement, re.IGNORECASE) is not None
    if kind == "INSERT":
        return re.search(r"\bON\s+CONFLICT\b", statement, re.IGNORECASE) is not None
    return True


def test_schema_statements_are_idempotent() -> None:
    statements = _split_statements(SCHEMA.read_text(encoding="utf-8"))
    assert len(statements) >= 20, "schema parser returned too few statements"
    bad: list[str] = []
    for statement in statements:
        forbidden = _FORBIDDEN.search(statement)
        if forbidden:
            bad.append(f"{forbidden.group(1).upper()} in: {statement[:120]}")
            continue
        if not _idempotent(statement):
            bad.append(f"not idempotent-shaped: {statement[:120]}")
    assert not bad, "\n".join(bad)

"""Read-only Workers panel. Served on the internal network, with no actions."""

from __future__ import annotations

from html import escape
from typing import Any

COLUMNS = ("issue", "brief", "status", "pr_url", "minutes", "cost_usd")


def _cell(value: object) -> str:
    if value is None:
        return ""
    return escape(str(value), quote=True)


def render(records: list[dict[str, Any]]) -> str:
    rows: list[str] = []
    for record in records:
        cells = "".join(f"<td>{_cell(record.get(column))}</td>" for column in COLUMNS)
        rows.append(f"<tr>{cells}</tr>")
    body = "".join(rows) if rows else "<tr><td colspan='6'>No tasks yet.</td></tr>"
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Workers</title>
<style>
body {{ margin: 24px; color: #001840; background: #F4F6FB; font-family: Inter, sans-serif; }}
h1 {{ font-family: Jost, sans-serif; font-weight: 300; }}
table {{ border-collapse: collapse; width: 100%; background: white; }}
th, td {{ border-bottom: 1px solid #B8BFD0; text-align: left; padding: 8px; font-size: 14px; }}
td:nth-child(5), td:nth-child(6) {{ font-family: "JetBrains Mono", ui-monospace, monospace; }}
</style>
</head>
<body>
<h1>Workers</h1>
<p>Read only. Each row is one task from an issue labelled worker.</p>
<table>
<thead><tr><th>Issue</th><th>Brief</th><th>Status</th><th>Pull request</th><th>Minutes</th><th>Model cost</th></tr></thead>
<tbody>
{body}
</tbody>
</table>
</body>
</html>
"""

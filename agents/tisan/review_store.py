"""Retain checked static pages for founder review; never create approval records."""
import json
import os
import re
from html.parser import HTMLParser
from pathlib import Path
from typing import Any


class Structure(HTMLParser):
    """Retain DOM hierarchy and text without executable script contents."""
    VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}

    def __init__(self) -> None:
        super().__init__()
        self.nodes: list[dict[str, Any]] = []
        self.stack: list[dict[str, Any]] = []
        self.hidden = 0

    def append(self, node: dict[str, Any]) -> None:
        (self.stack[-1]["children"] if self.stack else self.nodes).append(node)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style"}:
            self.hidden += 1
        if not self.hidden:
            node = {"tag": tag, "attrs": dict(attrs), "children": []}
            self.append(node)
            if tag not in self.VOID:
                self.stack.append(node)

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style"} and self.hidden:
            self.hidden -= 1
            return
        if not self.hidden:
            for index in range(len(self.stack) - 1, -1, -1):
                if self.stack[index]["tag"] == tag:
                    del self.stack[index:]
                    break

    def handle_data(self, data: str) -> None:
        if not self.hidden and data.strip():
            self.append({"text": data.strip()})


def save(root: Path, project: Path, tenant: str, slug: str, build: int, source: dict[str, Any]) -> None:
    file_id, frame_id = source.get("file_key", ""), source.get("node_id", "")
    page = source.get("page", "home")
    if (not re.fullmatch(r"[A-Za-z0-9]{22,128}", file_id)
            or not re.fullmatch(r"\d+:\d+", frame_id)
            or page not in {"home", "about", "contact", "privacy"}):
        raise ValueError("invalid review frame or page")
    frame_path = f"{file_id}/{frame_id.replace(':', '-')}.json"
    # The saved reading is the exact frame evidence; a missing reading cannot be approved.
    reading = root / "readings" / tenant / frame_path
    if not reading.is_file():
        raise ValueError("save the Figma frame before building its page")
    html_path = project / ".next/server/app" / ("index.html" if page == "home" else f"{page}.html")
    html = html_path.read_text()
    parser = Structure()
    parser.feed(html)
    # Embed local CSS for a faithful script-free review. The original HTML stays hashed.
    css = "\n".join(p.read_text() for p in sorted((project / ".next/static/css").glob("*.css")))
    artifact = {"html": html, "css": css, "structure": {"path": "/" if page == "home" else f"/{page}", "nodes": parser.nodes}}
    built_path = f"{slug}/{build}-{page}.page.json"
    (root / "builds" / tenant / built_path).write_text(json.dumps(artifact))
    review_dir = root / "reviews" / tenant
    review_dir.mkdir(parents=True, exist_ok=True)
    record = {"tenant_id": tenant, "figma_file_id": file_id, "figma_frame_id": frame_id,
              "frame_path": frame_path, "built_page_path": built_path,
              "region": os.environ.get("TANK_REGION", "us-east"), "public": False}
    (review_dir / f"{slug}-{page}.json").write_text(json.dumps(record))

"""Reproduce Tiger's allowlisted demo/practice corpus from the saved test set.

No fetches. Remove executable scripts, forms, embedded URLs and tracking attributes.
Only allowlisted hosts contribute labels, HTML or PNGs. Remove non-itemprop meta tags.
"""
import json
from pathlib import Path
from urllib.parse import urlsplit
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from selectolax.parser import HTMLParser

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "tests/tiger_price_read"
DEST = ROOT / "agents/tiger/gold/public-pages.zip"


def build() -> None:
    rows = [json.loads(line) for line in (SOURCE / "gold/pages.jsonl").read_text().splitlines()]
    allowed = set(json.loads((DEST.parent / "allowed-hosts.json").read_text()))
    rows = [row for row in rows if urlsplit(row["url"]).hostname in allowed]
    DEST.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(DEST, "w", compression=ZIP_DEFLATED) as archive:
        def write(name: str, data: bytes) -> None:
            info = ZipInfo(name, (2026, 1, 1, 0, 0, 0))
            info.compress_type = ZIP_DEFLATED
            archive.writestr(info, data)
        write("manifest.json", json.dumps(rows, sort_keys=True).encode())
        for row in rows:
            path = ROOT / row["html"] if row["html"].startswith("tank/") else SOURCE / row["html"]
            tree = HTMLParser(path.read_text())
            for node in tree.css("meta"):
                if not node.attributes.get("itemprop"):
                    node.decompose()
            for node in tree.css("script, iframe, input, textarea, style, noscript"):
                if node.tag == "script" and node.attributes.get("type") == "application/ld+json":
                    continue
                node.decompose()
            for node in tree.root.traverse():
                for attr in list(node.attributes):
                    if attr not in {"itemprop", "itemscope", "itemtype", "content", "type", "class", "hidden", "aria-hidden", "style"}:
                        del node.attrs[attr]
            write(row["id"] + ".html", tree.html.encode())
            write(row["id"] + ".png", (SOURCE / "gold/shots" / (row["id"] + ".png")).read_bytes())


if __name__ == "__main__":
    build()

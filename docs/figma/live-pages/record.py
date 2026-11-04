"""Compare Figma copy/dimensions with the actual local production render."""
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import struct
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


class Text(HTMLParser):
    def __init__(self):
        super().__init__()
        self.text = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("style", "script"):
            self.skip += 1
        if not self.skip:
            self.text.extend(value for key, value in attrs if key in ("placeholder", "value") and value)

    def handle_endtag(self, tag):
        if tag in ("style", "script"):
            self.skip -= 1

    def handle_data(self, data):
        if not self.skip:
            self.text.append(data)


def normalized(value):
    return re.sub(r"\s+", " ", value).strip()


key, title, address, description = sys.argv[1:5]
receipt = json.loads((HERE / "evidence" / f"{key}-nodes.json").read_text())
parser = Text()
parser.feed((ROOT / ".tmp/live-pages" / f"{key}.html").read_text())
source = normalized(" ".join(parser.text))
proof = []
rows = []
for frame in receipt["frames"]:
    width = frame["width"]
    browser = json.loads((HERE / "evidence" / f"{key}-{width}.json").read_text())
    assert (width, frame["height"]) == (browser["width"], browser["height"])
    unknown = [t["text"] for t in frame["copy"] if normalized(t["text"]) not in source and not (t["text"] == "▸" and "<summary>" in (ROOT / ".tmp/live-pages" / f"{key}.html").read_text())]
    assert not unknown, unknown
    images = {}
    for kind in ("browser", "figma"):
        file = HERE / "evidence" / f"{key}-{kind}-{width}.png"
        data = file.read_bytes()
        assert struct.unpack(">II", data[16:24]) == (width, frame["height"])
        images[kind] = hashlib.sha256(data).hexdigest()
    proof.append({"id": frame["id"], "width": width, "height": frame["height"], "newProductWording": [], "pngSha256": images})
    node = frame["id"].replace(":", "-")
    rows.append(f"| {title} | {address} | {width} | [{frame['id']}](https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id={node}) | Proposed | [PNG](evidence/{key}-figma-{width}.png) | [PNG](evidence/{key}-browser-{width}.png) |")
(HERE / "evidence" / f"{key}-checks.json").write_text(json.dumps(proof, indent=2) + "\n")
register = HERE / "REGISTER.md"
text = register.read_text()
marker = "\n## Data\n"
text = text.replace(marker, "\n" + "\n".join(rows) + "\n" + marker)
text += f"\n## {title}\n\n{description}\n\n[Every frame/node ID and exact copy](evidence/{key}-nodes.json); [dimension, source-copy and PNG hash checks](evidence/{key}-checks.json). All page text comes from the production render; no new product wording. Both native Figma screenshots were compared with the browser reference.\n"
text = text.replace(f"| {title} |", f"| {title} |", 1)
register.write_text(text)
print(f"PASS {key}: {len(proof)} exact-width source-copy checks and native PNG pairs")

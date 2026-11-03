"""Guard the working site's font bytes and typography while builds stay offline."""
import hashlib
import json
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[2]
FONTS = ROOT / "site/public/fonts"
MANIFEST = json.loads((FONTS / "manifest.json").read_text())


def faces(css):
    return [dict(item.strip().split(":", 1) for item in body.split(";") if item.strip())
            for body in re.findall(r"@font-face\s*\{([^}]+)\}", css)]


class PreservedSiteFonts(unittest.TestCase):
    def test_exact_working_font_bytes_and_licenses_are_present(self):
        self.assertEqual(set(MANIFEST["assets_sha256"]),
                         {p.name for p in FONTS.glob("*.woff2")})
        self.assertEqual(len(MANIFEST["assets_sha256"]), 16)
        for name, digest in MANIFEST["assets_sha256"].items():
            data = (FONTS / name).read_bytes()
            self.assertEqual(data[:4], b"wOF2", name)
            self.assertEqual(hashlib.sha256(data).hexdigest(), digest, name)
        for name in MANIFEST["licenses"]:
            self.assertIn("SIL OPEN FONT LICENSE", (FONTS / name).read_text())

    def test_all_faces_preserve_family_weights_subsets_and_fallback_metrics(self):
        original = "\n".join(MANIFEST["font_faces"])
        expected = faces(original.replace("/_next/static/media/", "/fonts/"))
        actual = faces((ROOT / "site/app/fonts.css").read_text())
        self.assertEqual(len(actual), 36)
        self.assertEqual(actual, expected)
        weights = {}
        for face in actual:
            if "font-weight" in face:
                weights.setdefault(face["font-family"], set()).add(face["font-weight"])
        self.assertEqual(weights, {"Jost": {"300", "400"},
                                  "Inter": {"400", "500", "600"},
                                  "JetBrains Mono": {"400"}})

    def test_original_variables_and_only_latin_preloads_are_preserved(self):
        css = (ROOT / "site/app/fonts.css").read_text()
        for name, value in MANIFEST["variables"].items():
            self.assertIn(f"{name}: {value};", css)
        layout = (ROOT / "site/app/layout.tsx").read_text()
        links = re.findall(r'<link rel="preload"[^>]+/>', layout)
        self.assertEqual(len(links), 3)
        for filename in MANIFEST["latin_preloads"]:
            link = next(link for link in links if f'/fonts/{filename}"' in link)
            for attribute in ('as="font"', 'type="font/woff2"', 'crossOrigin="anonymous"'):
                self.assertIn(attribute, link)

    def test_site_compilation_cannot_fetch_google_fonts(self):
        for path in (ROOT / "site/app").rglob("*"):
            if path.suffix in (".tsx", ".ts", ".css"):
                text = path.read_text()
                for forbidden in ("next/font/google", "fonts.googleapis.com", "fonts.gstatic.com"):
                    self.assertNotIn(forbidden, text, str(path))
        self.assertIn("RUN --network=none npm run build", (ROOT / "site/Dockerfile").read_text())


if __name__ == "__main__":
    unittest.main()

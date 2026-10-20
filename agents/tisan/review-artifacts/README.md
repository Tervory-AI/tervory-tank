These screenshots render the real scaffold template at 375px and 1440px.
`scaffold-scores.json` checks its heading against an independently specified,
synthetic CSS reference (layout, text and colour). It demonstrates the browser
measurement path; it is **not** a Figma parity claim, approved page, or gold
candidate. The current recorded Figma fixture lacks complete measurements.
The browser regression tests separately plant layout, text, token-colour and
hidden-element failures at both widths.

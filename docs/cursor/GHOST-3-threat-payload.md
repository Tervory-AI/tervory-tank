# GHOST-3: ThreatPayload triage schema (Phase 4 spike)

> Written 24 Oct 2026. Dogfood slice from Ghost & Wraith Build Plan. **No auto-patch. No Wraith rename. Founder tap still required for Shields.**

## Why
LLM triage may read dirty logs and advisory text. That output must not reach an execute or shield-apply path until it validates as a bounded JSON shape. Failures **burn**: fixed error string, never echo the rejected body.

## Shape
`ThreatPayload` (`agents/ghost/threat_payload.py`), `schema_version: ghost.threat.v1`:

| Field | Rule |
| --- | --- |
| `action` | `propose_shield` \| `open_match` \| `write_brief` only |
| `site` | Allowlisted Ghost dogfood hosts / app keys only |
| `kind` | Required for `propose_shield`; one of Shields Up v1 kinds |
| `cve_ids` | `CVE-YYYY-NNNN…` only |
| `reason` | ≤300 chars; burns on injection / shell markers |
| `confidence` | 0..1 |
| extras | Forbidden |

## Entry
`POST /ghost/triage/accept` (Tank key). On `propose_shield`, builds a **proposal** via existing `Shields.propose` — never raises. Founder still taps **Shield**.

## Panel SLOs (already on main; polished this slice)
Founder tile shows time-to-know / time-to-shield with median + slowest + under/over goal, plus open issues, sites broken (target 0), and Tank cost receipts. Empty metrics read **None yet / No receipts yet**, not zero pretending to be proof.

## Out of scope here
- Auto-execute without founder tap
- Auto-patch / merge
- Dual-LLM / NeMo bunker
- Dark-web collectors (research lane later)

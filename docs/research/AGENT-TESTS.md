# Agent tests: what each agent should be put through

Written 14 Oct 2026, 13:56 PT, by Claude. Also in Notion ("Agent tests").

## What Tank checks today

- **Skill tests (evals):** every skill has a small set of examples with the right answer. A skill only goes live if it scores at or above its bar (most bars are 0.8 to 0.97). Today the sets are tiny: 1 to 5 examples for most skills; Zenas has 38 (scope) and 15 (ID protection); Tiger price reading has 10.
- **Shadow runs:** on live work, a cheaper candidate does the same job quietly next to the current model. Tank scores how often they agree (field by field for structured answers, or a judge model gives a score).
- **Graduation bar:** a cheaper route can take over only after at least 30 shadow runs, agreement at or above the bar (default 97%), and client rejections at or under 5%.
- **Build tests (CI):** every change is checked for rooms staying sealed, one client never seeing another's data, no secrets in code, prices on every model, no China-hosted providers.

**Training:** Tank trains no model today. It "learns" by moving work to cheaper rungs once they are proven. Training our own model is T7 (later), and it would learn from the ledger and the shadow runs.

**The gaps:** test sets are far too small to prove anything; the judge model is never checked against a human; nothing re-tests old skills to catch them getting worse; no one tries to break the agents on purpose.

## Tests every agent gets

1. **Gold set:** at least 100 real examples per skill with the right answer checked by a person. 20% held back and never used while building, only for the final check.
2. **Trap cases:** tricky, broken or adversarial inputs (empty pages, wrong language, prompt tricks, missing fields).
3. **Shadow runs** on live work before any switch (already built).
4. **Weekly re-test:** re-run every gold set; alert if a score drops more than 2 points.
5. **Room and client checks:** sealed room, no data crossing between clients (already built; keep).
6. **Cost and speed:** cost per task and time per task, tracked against a target.
7. **Feedback loop:** every client rejection or correction becomes a new gold case.

## Per agent

| Agent | Test | How | Pass bar |
|---|---|---|---|
| **Tank** | Cheapest available model is picked | Empty one provider's funds or block it in a test; the next cheapest answers; no run waits | 100% of runs answered; correct cheapest chosen |
| | Judge is trustworthy | 200 answer pairs scored by a person and by the judge; compare | Judge agrees with person 90%+ |
| | Saved answers are safe | Pairs that look alike but need different answers; the cache must not mix them | 0 wrong cache hits |
| | Automatic switch and switch back | Simulate a candidate passing, then dropping; check it promotes, then rolls back by itself | Promote and rollback within one cycle |
| | Ledger matches the bills | Monthly: ledger total vs each provider's invoice | Within 2% |
| | Load | 50 runs at once | No errors; answers in normal time |
| **Base** | Right website found | 200 businesses checked by hand | 95%+ correct; wrong site under 2% |
| | Contacts and details correct | Same 200, field by field (phone, email, address, socials) | 95%+ per field |
| | Code-only passes (2c, 5) match the old model output | Run both on 500 records | 95%+ field agreement |
| | Duplicates | Known duplicate pairs | 98%+ caught, under 1% false merges |
| | Firearms licence match | Known licence holders | 99%+ |
| **Tiger** | Price read correctly | 100 product pages across many store layouts, plus screenshots | 98%+ exact price |
| | Change alerts | Replay price history with known changes | 95%+ caught; under 2% false alarms |
| | Store layout broke | Feed a changed page; Tiger must say "can't read", not guess | 100% flagged |
| **Market Lab** | Numbers match the official source | Spot-check each feed vs the source site | 100% match |
| | Surge and shift detection | Back-test on past data with known events | 80%+ caught; false alarms tracked |
| | Research citations | Every source exists and says what is claimed | 0 made-up sources |
| **Zenas** | Scope gate | Criminal law always refused; regulatory flagged; out-of-scope declined | 100% criminal refused |
| | ID protection | Try to get personal details back out (red-team) | 0 leaks |
| | Citations | Every cited case or law exists and supports the point | 0 made-up citations |
| | Data stays home | South African clients never served from the US server | 100% |
| | Lawyer review | A lawyer scores a sample of memos and drafts each month | 90%+ "usable as is or minor edits" |
| **Radix** | Finds known problems | Test projects with planted fake keys, risky packages and unsafe code | 95%+ found |
| | Few false alarms | Clean projects | Under 5% false alarms |
| | No internet | Checked on every deploy | Always blocked |
| **Tisan** | Builds work | Every build passes its own tests | 100% |
| | Quality scores | Speed, accessibility and SEO scores on every page | 90+ out of 100 |
| | Matches the design | Screenshot compared with the Figma design | Close match, reviewed by a person |
| | Safe | Radix scan before deploy | 0 serious findings |
| **RIG** | Only approved fits shown | Ask for setups; check every part has an approved fit | 100% |
| | Search finds the right product | 200 real shopper searches with the right answer | Right product in top 3 for 90%+ |
| | "I don't know" outside the catalogue | Questions the catalogue can't answer | 100% refused |
| | One retailer never sees another | Keys from two retailers | 0 crossings |
| | Fast enough for a shop page | Time per search | Under 300 ms |
| | Later, 3D | Model dimensions vs the real product | Within 2 mm |

## Rules for any tool we pick

- Open source must allow commercial use; we prefer things that run on our own server (Coolify).
- No China-hosted services.
- South African personal data stays in South Africa; legal client data never leaves its region.
- No new paid service is added without the founder's yes (AGENTS.md rule 10). Research only.

# Z12: SA precedent: court weight, full reasoning, citation trail, no made-up cases

> Written 20 Oct 2026, 10:45 PT. Founder: "The court judgements in South Africa are crucial... the written judgements are what is used to decide appeals, they create precedent and the rulings and reasoning is what is important to advocates in the court room." And: "lawyers are funny people, we need to ensure we are thorough... [Google and ChatGPT] make up cases." Z8d (#175) is merged: the model points, code cuts the court's exact words. This brief builds on that.

The precedent rules are a **draft the founder is still reviewing** (claude.ai project doc `zenas/SA-precedent-rules-draft.md`, copied into point 3 below). So the rules live in a data file the founder can change without new code.

**Files you may change:** `agents/zenas/pool/schema.sql` (additive only), `agents/zenas/pool/adapters/za_case_common.py` and the `za_*` case adapters (court metadata only), `agents/zenas/pool/citations.py`, `agents/zenas/core/convert.py`, `agents/zenas/core/pointers.py`, `agents/zenas/core/service.py`, `agents/zenas/core/selftest.py`, new `agents/zenas/core/precedent.py` and `agents/zenas/core/precedent_rules.json`, `workspace/app/zenas/` (display only), tests with saved real judgments as fixtures.

## Do

1. **Never cut a judgment.**
   - The whole judgment is stored, searched and available to Convert. No length cap on reasoning.
   - Remove the 8,000-character cut on rule-card passages (`service.py`, `json.dumps(passages)[:8000]`), which can end a passage halfway. If passages exceed the model budget, send fewer whole passages (best ranked first) and say how many were left out. Never cut a passage.
   - Check every load and Convert path for other cuts of judgment text, remove them, and list what you found in the PR.

2. **Court identity on every SA case**, taken only from the judgment or its official listing:
   - court, division and seat (for example "Gauteng Division, Pretoria"), bench size, the judges' names as the judgment states them, the neutral citation (for example `[2024] ZAGPPHC 123`), and any law-report citation it states;
   - court and division read from the neutral-citation code (ZACC, ZASCA, ZAGPPHC, ZAGPJHC, ZAWCHC, ZAKZDHC, ZAKZPHC, ZAECGHC, ZAFSHC, ZANWHC, ZALMPPHC, ZAMPMBHC, ZANCHC, ZALAC, ZALCJHB, ZALCCT, ZALCD, ZALCPE, ZACAC, ZACT, ZALCC, ZAST, ZATC and others found), cross-checked against the listing;
   - whether the case is an appeal and from which court;
   - unknown stays unknown and is shown as unknown. Never guess.
   - Judges' names are shown on the case only. No judge scoring, statistics or profiles.

3. **Precedent rules as data (`precedent_rules.json`).** Every rule carries `"status": "draft"`. While any rule is draft, the page and every answer that uses the rules say "precedent rules: draft". `precedent.weight(citing_court, cited_case)` returns `binding`, `persuasive` or `not_precedent`, plus a plain reason ("SCA binds every High Court division"). Seed:
   - Vertical:
     - ConCourt binds every court.
     - SCA binds every court below it.
     - High Court within its own division:
       - full bench (3+) binds two-judge benches and single judges;
       - two-judge bench binds single judges;
       - single judge binds regional and magistrates' courts in that area.
     - Regional and magistrates' courts create no precedent.
   - Horizontal:
     - A single judge follows earlier same-division single judges unless clearly wrong. Return `binding` with reason "same division, follow unless clearly wrong".
     - Other divisions are `persuasive`.
   - Specialist: LAC binds the Labour Court; CAC binds the Competition Tribunal; Tax Court appeals go to a full bench or the SCA.
   - Defaults until the founder answers (each a separate rule, so one edit changes it):
     - cross-division = persuasive;
     - magistrates' and regional decisions are stored but labelled "not precedent", and never offered as authority;
     - two same-division single judges who disagree = flag "conflicting authority" and show both.

4. **Reasoning, not just the holding.** Convert extracts, per issue the court decided:
   - the question;
   - the court's reasoning (model pointers, code cuts the exact words, no length cap);
   - the order;
   - a "likely ratio" marking on the exact words the decision rests on, always labelled "likely", never stated as fact;
   - remarks marked obiter only where the court's own words show it ("obiter", "it is unnecessary to decide", "I express no view");
   - minority and dissenting judgments kept and labelled, never merged into the majority.

   Existing worked matters keep working. The new fields are additive.

5. **Citation trail.** For each case a judgment cites:
   - record how the court treated it: followed, applied, approved, distinguished, not followed, overruled, or referred to (the default);
   - take the treatment only from the court's words around the citation, and save those exact words and the paragraph number as evidence;
   - add `treatment`, `evidence` and `paragraph` to `zenas_pool.cites` (additive);
   - resolve the cited case to the library where it is there.

6. **Still good law.** Before Zenas relies on a case, look for later library judgments that cite it.
   - "Overruled by [case] para [n]" when overruled by a court that binds it.
   - "Not followed by [case]" when a persuasive court declined to follow it.
   - Always say what was checked: "checked against N later judgments in the library, as at [date]". Never claim the check is complete.

7. **No made-up cases. This is the gate.**
   - Every case Zenas names in any answer must resolve to a document in that region's library, and every quote must match word for word (existing cite_check).
   - Anything that does not resolve is removed. The answer then says "I could not verify [name], so I have left it out".
   - A nightly test of 50 questions includes trap questions about cases that do not exist (made-up names and citations). Zenas must say it cannot find them.
   - No Zenas skill moves to approved unless the test passes 100%. Results show on the self-test page.

8. **Display.** The lawyer picks their forum (for example "Western Cape Division, single judge"). Every cited case then shows:
   - court, division and bench;
   - binding, persuasive or not precedent, for that forum, with the reason;
   - treatment warnings;
   - a link to the full judgment at the paragraph.

## Rules
- SA material stays on the ZA box. No criminal law (unchanged). Decided cases are public record.
- US: shared code must keep working and US tests must pass. US weight rules are out of scope.
- The founder sets the rules file. Do not change the seeded rules beyond the draft.

## Done when
CI green, with each of these tested on saved real judgments:
- ConCourt, SCA, a full bench, a two-judge bench and a single judge from two divisions get the right court, division and bench.
- The weight function gives the expected answer for each seeded rule.
- The draft label shows while any rule is draft.
- Treatment is read correctly from saved paragraphs ("we decline to follow", "was overruled in", "is distinguishable").
- An overruled case shows the warning.
- A made-up case returns "cannot find".
- A 300-page judgment is stored and searched in full.
- A rule card never cuts a passage.

After merge, Claude re-runs Convert on the ZA box and reports counts, ratio markings and treatment counts.

# GRAD-1: fill the gold sets and graduate the squad off paid models

> Written 19 Oct 2026, 14:30 PT. Founder: "we should be getting the agents trained", and Hugging Face (PRO plus pay-as-you-go Jobs) is the GPU. Read `docs/cursor/TRAIN-1-squad-training.md` (merged in #147/#149) and `docs/cursor/T6-graduate-to-code.md` first. This brief uses that machinery; it does not replace it.

## Where we are (live, 19 Oct 14:25 PT)
- 52 skills in the gold store, target 100 checked examples each. **332 candidates, 0 checked.** Training pairs: zenas 5, everyone else 0.
- 19 task types still call a paid model (mostly `luna`); only `reason.brief` has a candidate (`flash-lite`).
- So the training system works but is empty. The bottleneck is labelled examples, not GPUs.

## Principle
A person should only check what a machine cannot. Where the right answer already exists somewhere, the example is labelled by code against that truth. The founder (and, for Zenas, a lawyer) checks a small sample of those plus the judgement-only skills.

**Files you may change:** `tank/training.py`, `tank/gold.py`, `tank/graduate.py`, each agent's own `evals/` and a new `gold_sources.py` in each room (`agents/<room>/`), `workspace/app/skala/gold/`, `workspace/app/tank/` (graduation view), `jobs/train/` (new: the Hugging Face training job), `.env.example` (names only), tests. Do not change any room's live behaviour, Tank's router, or the ledger.

## 1. Auto-labelled examples per agent (truth already exists)
Each room gets `gold_sources.py` that turns real data into candidate examples with a machine label and the source of the truth. Labels are `auto` until a person checks a sample.
- **Zenas:** worked matters from Convert (court's own words, quote-checked) and the held-out split; statutes' section text for `zenas.retrieve`; deadlines from the Rules (FRCP/FRAP/SA rules) for `zenas.deadlines`.
- **Base:** records where the business's own website, phone and address agree with an official list (ATF FFL list, state registries) label `find_site`, `verify`, `normalize`, `resolve`.
- **Tiger:** the 109-page price gold set from #100 plus pages where the price on the page matches the retailer's structured data (JSON-LD) label `price_extract` and `price_ocr`.
- **Rig:** fitment records (the part's own compatibility list) label `rig.search` and `rig.fit_suggest`.
- **Market Lab:** past series where the later value is now known label `shift_detect`, `surge_detect`, `series_fetch`.
- **Radix:** the scanners' own fixtures (known secrets, known vulnerable dependencies) label `scan.*`; verified-business fixtures label `radix.*`.
- **Tisan:** Figma frames already built into approved pages label `tisan.figma` and `tisan.scaffold`.
- **tier0 / orchestrator:** routed requests whose final owner accepted the result label `tier0.classify`; the rest stay human-checked.
Cap per source per night (`GOLD_AUTO_MAX`, default 200). Region kept on every example; SA material stays on the ZA box.

## 2. Checking that fits a founder's day
- `/skala/gold` gets a **sample queue**: 10 auto-labelled examples per skill (spot check) plus all judgement-only ones, sorted by the skill closest to graduating. Target: about 20 minutes a day.
- A skill's auto labels count toward its 100 once its spot check agrees on at least 9 of 10; a disagreement sends that source back to code review, not to the training set.
- Zenas legal checks are marked "lawyer" and can be assigned to a reviewer login later.

## 3. Graduation
- For each task type on the ladder, once its gold set reaches 100 checked (or auto-labelled with a passed spot check) Tank tests, in order: an approved code skill (T6), then a cheaper roster model, then the squad's own fine-tuned model. The first one that scores at or above the task's `eval_threshold` on the held-out set becomes the **candidate**; it shadows live traffic (existing shadow rate) and the founder promotes it with one click on the Tank page. Nothing switches automatically.
- The Tank page shows per task: current model, gold count, best candidate and its score, cost per call now vs candidate.

## 4. Our own small model on Hugging Face
- `jobs/train/` holds one training job (TRL, LoRA) run with Hugging Face Jobs. Inputs: the private training-pair dataset that TRAIN-1 already exports (`HF_TOKEN`, `HF_ORG`). Output: a private model repo, versioned.
- First run: one small open model (3B to 8B, licence that allows commercial use), all graduating task types in one multi-task run, an A10G or L4 flavour.
- **Budget cap: $50 per run** (`HF_TRAIN_MAX_USD`). The job estimates cost before it starts and refuses above the cap; it records the real cost on the ledger.
- Only public-record and approved non-client examples go to Hugging Face. Client matters, uploads and anything with a tenant's private data never leave our servers. A test fails the export if one does.
- Serving the trained model is a later decision (on Boston CPU for small models, or a paid endpoint). This brief only trains and evaluates it.

## Done when
CI green; each room's `gold_sources.py` produces labelled candidates from fixture data (tested); the sample queue shows 10 per skill and counts agreed sources (tested); the training job refuses a run estimated above the cap (tested) and never exports client data (tested); the Tank page shows the graduation table from fixture rows (tested). After merge Claude runs the nightly gold job once and reports candidates per agent; the founder starts checking the sample queue.

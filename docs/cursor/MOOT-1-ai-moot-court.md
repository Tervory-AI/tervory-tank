# MOOT-1: a live moot court with an AI judge that speaks

> Written 20 Oct 2026, 12:15 PT. The founder plans moots filmed in a studio set up as a courtroom, with law students as counsel, to show SAFLII (and later law faculties) what Zenas does. The judge is AI: it hears counsel, puts questions out loud like a real bench, checks every authority as it is cited, and delivers a judgment. Also used for Street Law and practice runs later.

**Depends on Z12** (court weight, citation trail, made-up-case gate). Parts 1, 3 and 6 can start now; the judge's authority checks use Z12 functions once merged (stub them behind the same interface until then).

**Files you may change:** new `agents/zenas/core/moot/` (problem, session, judge, feedback), `agents/zenas/app.py` (moot routes only), `agents/zenas/schema.sql` (additive), `tank/` policy seed rows for the new task types only, new `workspace/app/zenas/moot/` (pages and components), `workspace/lib/tank.ts` (moot calls only), tests. Do not change other Zenas behaviour.

## 1. The moot problem (from a real case)
- The founder picks a decided **civil** SA appeal from the library (ConCourt, SCA, full bench or High Court appeal). Criminal cases are not offered.
- Zenas builds the problem:
  - the facts, in the court's own words (Z8d pointers);
  - the grounds of appeal;
  - who argues for the appellant and who for the respondent.
- **Each side gets its own bundle.** The authorities come from the library, and each links to the full judgment at the paragraph.
- **The judge's private bench notes are never shown to counsel:**
  - the issues and the binding authorities on each;
  - the questions to press;
  - what the real court held, and why.
- The founder can edit everything, then locks the problem for a session.

## 2. The AI judge
- **Identity:** the founder sets a name and a voice. The voice is never cloned from, and never named after, any real person.
- **Hearing:** speech-to-text per speaker. Each counsel has their own microphone, and the screen shows a "speaking" selector so the transcript knows who is talking.
- **When the judge speaks:**
  - at a natural pause (about 1.5 seconds of silence, adjustable);
  - or at once, when counsel cites an authority that is not in the library, or that does not bind this court and is presented as binding.
  - Example: "Counsel, that is a decision of another division. It does not bind me. Why should I follow it?"
- **How hard it presses:** gentle, standard or SCA. The setting controls how often it asks and how hard.
- **What it may use:** only the bench notes, the bundle and the library. It never names a case the library does not hold. Every authority it mentions passes the Z12 gate before it is spoken; one that fails is dropped, not spoken.
- **How fast:** a question starts playing within 3 seconds of the pause. Text appears on screen as it speaks.
- **At the end:** an ex tempore judgment out loud and in writing. It gives the order and the reasons, and cites only verified authorities with paragraphs. Then a "What the court actually held" reveal from the real judgment.
- **Model calls** go through Tank with new task types `moot.stt`, `moot.judge` and `moot.tts`. The provider choice sits in the policy table. Everything goes on the ledger under the session's tenant.

## 3. The session page (`/zenas/moot`)
- **Roles:** presiding judge (AI), counsel for the appellant, counsel for the respondent, and an operator (the founder).
- **Timers:** per speaker, with defaults of 20 minutes each and 5 for reply. The operator can change them, pause, and hand the floor to counsel.
- **Layout for the studio:**
  - a **bench screen**: the judge's name, a speaking indicator and the live words;
  - a **citation screen**: each authority as it is cited, showing court, division, binding or persuasive for this bench, its treatment, and the paragraph, or "not found" in red;
  - an **operator screen** with all the controls.
  - Each screen is its own URL, so it can go on its own monitor and camera.
- **Practice mode:** one student alone against the AI judge from a laptop browser, using the same flow.

## 4. Feedback after the session
For each counsel:
- their arguments set against the real court's reasoning;
- every authority they cited, with a verdict on each: found, binding or persuasive, misquoted, not found;
- the points they missed;
- how they used their time;
- how they handled the judge's questions.

It goes out as a PDF and as a page.

## 5. Recording
- The app records the audio and the transcript with time codes and keeps the citation timeline.
- The studio cameras record video separately. The operator can upload the video later, and it lines up with the transcript by time.
- Everything stays on the ZA box.

## 6. Admin
The founder creates sessions, adds participants by name (no accounts are needed for counsel in practice mode), and can delete a session and its recordings.

## Rules
- Civil law only. SA sessions run on the ZA box. Model calls go only through Tank.
- No secrets in code, URLs, logs or tests.
- The judge never invents an authority. This is tested.

## Done when
CI green. Tests on fixture data:
- a problem built from a saved SCA appeal has facts in the court's own words;
- the bench notes never reach counsel's pages (tested at the route);
- the judge interrupts on a made-up case and on a non-binding authority presented as binding;
- the judge's speech never names an authority outside the library;
- the judgment cites only verified authorities;
- timers and floor changes work;
- each screen loads on its own URL at 1440px, and practice mode works at 375px.

Then a 10-minute recorded demo run on staging with two people, linked in the PR. After merge, Claude sets up the first session with the founder.

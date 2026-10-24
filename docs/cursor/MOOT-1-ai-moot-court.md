# MOOT-1: a live moot court with an AI judge that speaks

> Written 20 Oct 2026, 12:15 PT. The founder plans moots filmed in a studio set up as a courtroom, with law students as counsel, to show SAFLII (and later law faculties) what Zenas does. The judge is AI: it hears counsel, puts questions out loud like a real bench, checks every authority as it is cited, and delivers a judgment. Also used for Street Law and practice runs later.

**Z12 is merged** (#204, #206): use its court weight, citation trail and made-up-case gate directly.

**Hosting (22 Oct):** the ZA box is offline while it moves to Hetzner. Build and test SA mode on fixtures; it goes live on the new ZA host later, as configuration only. US mode runs on Boston now.

**Civil only (founder):** if someone's guilt, liberty or criminal defence is at stake, Zenas doesn't take it. A civil claim, including a constitutional challenge brought as a civil suit, is in.

**Files you may change:** new `agents/zenas/core/moot/` (problem, session, judge, feedback), `agents/zenas/app.py` (moot routes only), `agents/zenas/schema.sql` (additive), new `tank/moot/` (the LiveKit Agents judge worker and its Dockerfile), `tank/` policy seed rows for the new task types only, `docker-compose.yml` (add the LiveKit server, Redis use and egress services only), `.env.example` (variable NAMES only), new `workspace/app/zenas/moot/` (pages and components), new public `workspace/app/moot/` (watch pages, section 7), `workspace/lib/tank.ts` (moot calls only), tests. Do not change other Zenas behaviour.

## MOOT-1a: the text edition (by Sunday 25 Oct)
> Founder, 23 Oct: Zenas must be live by Sunday. MOOT-1a ships the court **in text** by then. Everything spoken (LiveKit, speech-to-text, voices, studio screens, clips, the major-issues format) is **MOOT-1b**, built next on top of 1a. Don't build 1b parts in 1a; leave clean interfaces for them.

**Build in 1a:**
1. **The problem** (section 1, all of it).
   - It's built from a decided civil appeal already stored as a worked matter (Z8), with separate bundles for each side and the bench notes hidden from counsel.
   - The founder edits it, then locks it.
2. **Counsel in text** (section 2c). Three modes:
   - AI against AI;
   - a student against AI (the student types);
   - students against students.

   AI counsel use the same model and settings on both sides, and argue against each other's points directly.
3. **The judge in text** (section 2, minus voice).
   - It questions after each submission, with a strictness setting.
   - It flags at once an authority that isn't in the library, or one that doesn't bind but is presented as binding.
   - Every authority anyone names passes the Z12 gate. A failed citation is flagged in the ruling and counts against that counsel.
   - The judgment gives the order and the reasons, with verified authorities and paragraphs, then the **reveal** of what the real court held.
4. **The fairness check:** every AI-against-AI match runs twice with the sides swapped, and the result is shown and stored.
5. **The watch page** (section 7, minus clips). It lives at `/moot/{match}` and is public only after the founder presses Publish; until then it returns 404. It shows:
   - the transcript;
   - the judgment;
   - the fairness check;
   - the reveal;
   - each authority linked to its source.
6. **Receipts and learning:**
   - every turn goes through Tank, with task types `moot.counsel` and `moot.judge` in the policy table;
   - the cost is shown per match;
   - accepted and rejected points become gold candidates (`zenas:moot:{YYYY-MM}`).

**Files you may change (1a):**
- new `agents/zenas/core/moot/`;
- `agents/zenas/app.py` (moot routes only);
- `agents/zenas/schema.sql` (additive);
- `tank/` policy seed rows for `moot.counsel` and `moot.judge` only, placed above the `-- MODELS-2` marker in `tank/schema.sql`;
- `workspace/app/zenas/moot*` (replace the placeholder);
- new public `workspace/app/moot/`;
- `workspace/lib/tank.ts` (moot calls only);
- tests.

**Done when (1a):**
- tests on fixtures prove:
  - the bench notes never reach counsel's pages (tested at the route);
  - a made-up case and a non-binding authority presented as binding are both flagged;
  - the judgment cites only verified authorities;
  - AI against AI runs in both orders with the fairness check stored;
  - an unpublished watch page returns 404;
  - SA mode on fixtures and US mode on the Boston library each use their own court's form of address and procedure;
- the pages work at 1440px and 375px.

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

## 2b. The stack (chosen 20 Oct 2026, 12:50 PT, from the research in the project doc `zenas/MOOT-1-oss-research.md`)
Use these. Do not add other paid services or providers; that is the founder's decision.
- **Media and rooms: [LiveKit server](https://docs.livekit.io/transport/self-hosting/) (Apache-2.0), self-hosted in Docker** with Redis and one [egress](https://docs.livekit.io/transport/self-hosting/egress.md) worker. One room per session. Each counsel microphone is a participant. **Track egress** records one audio file per microphone. The clean-feed URL is recorded by web egress. Remote and practice sessions use the same room.
- **The judge is a [LiveKit Agents](https://pypi.org/project/livekit-agents/) worker (Python, Apache-2.0)** that joins the room as a participant. It runs as a Tank-owned container (`tank/moot/`), because it is the only service that streams audio to a model. It reads STT/TTS/LLM keys from Coolify's environment panel, never from code, and writes every call to the ledger under the session's tenant with the task types `moot.stt`, `moot.judge`, `moot.tts`. The provider for each task type sits in the policy table.
- **Pause and interruption:** [Silero VAD](https://pypi.org/project/silero-vad/) (MIT) with the silence length set to 1.5 s (adjustable), plus an end-of-turn model so counsel is not cut mid-sentence (LiveKit's turn detector, or [Smart Turn v3](https://github.com/pipecat-ai/smart-turn), BSD-2). The citation interrupt is our own code: match partial transcripts against the library and call the judge's speak-now path with interruptions off. Counsel cannot talk over the judge.
- **Streaming speech-to-text:** a hosted provider through the policy table for the first term (Deepgram Nova-3 or AssemblyAI; both accept a custom vocabulary, which is loaded with the bundle's case names and Latin terms). Self-host later behind the same interface with [WhisperLiveKit](https://pypi.org/project/whisperlivekit/) running Whisper large-v3 (the best open model on South African English). One stream per microphone, so no live diarisation.
- **Voice:** hosted through the policy table for the first term. Self-host fallback is [Kokoro-FastAPI](https://github.com/remsky/Kokoro-FastAPI) (Apache-2.0, CPU, British presets `bm_george` and `bm_fable`), which speaks the OpenAI audio API so it drops into Tank. Never a voice-cloning model, never F5-TTS, Fish Speech or XTTS (non-commercial weights). The founder picks the final voice from a shortlist the worker can switch between.
- **Screens and captions:** our own Next.js routes fed by one WebSocket from FastAPI. Captions come from STT partials. Each screen works as an OBS Browser Source at 1920x1080.
- **Recording and alignment:** ffmpeg plus [WhisperX](https://pypi.org/project/whisperx/) (BSD-2) for word time codes on the uploaded studio video; a sync tone at the start of every session; both transcripts matched to find the offset.
- **Feedback PDF:** [WeasyPrint](https://pypi.org/project/weasyprint) from the same HTML as the feedback page.
- **The judge prompt must be adversarial.** Research on AI moot judges (Princeton, 2026) found they agree too easily and ask too few hypotheticals. The judge is instructed to press, to disagree, and to put hypotheticals, and the "hardness" setting in section 2 scales that. Tests include a weak submission that the judge must not accept.
- **Licences:** anything GPL or AGPL runs in its own container over HTTP and is never imported. Models under attribution licences get a credits line on the admin page.

## 2c. Counsel: students or AI (founder, 21 Oct)
- **Three modes:**
  - **AI against AI**, the public showcase;
  - **a student against AI counsel,** for practice at any hour, with the AI arguing the other side at full strength;
  - **students against students,** with the AI judge.
- **Parties are named for the proceeding:**
  - **SA:** Applicant and Respondent in motion court; Plaintiff and Defendant at trial; Appellant and Respondent on appeal.
  - **US:** Plaintiff and Defendant at trial; Appellant (or Petitioner) and Appellee (or Respondent) on appeal.
- **AI counsel:**
  - each is its own seat, run by the same worker as the judge, with a voice distinct from the judge's and from each other;
  - both sides use the same model and settings;
  - they argue against each other's points directly, never conceding just to be polite.
- **Real authorities only:** every authority either counsel cites passes the Z12 gate. A failure is flagged in the ruling, as a real judge would catch it, and counts against that counsel.
- **Fairness check, published for every AI-against-AI match:** each match runs twice with the sides swapped.
  - If the same side wins both times, the problem is lopsided.
  - If the same seat wins both times, it's model strength, not argument.
- **Learning:** every point the judge accepts or rejects becomes a gold candidate (`zenas:moot:{YYYY-MM}`), checked before use.
- **Receipts:** every match shows its cost through Tank.

## 2d. Major issues re-argued (founder, 21 Oct)
Landmark civil and constitutional cases, argued again with no emotion: pure legal argument and a reasoned judgment.
- **No private person is a party; the issue is the law.** Only decided cases and the public record. Never a case still before a court (sub judice).
- **The judge states its method first.** Each major issue runs under each main method:
  - text and history;
  - precedent;
  - evolving standards.

  Each gets a majority and a dissent, published side by side.
- **Neutral titles only,** for example "Roe v. Wade re-argued" or "Three methods, three answers". Never "AI rules X".
- **The reveal shows what the courts actually held over time.** For Roe that's Roe (1973), Casey (1992) and Dobbs (2022), each linked to the source.
- **Build the format and test it on a fixture case.** The founder picks the real cases.

## 3. The session page (`/zenas/moot`)
- **Roles:** presiding judge (AI), counsel for the appellant, counsel for the respondent, and an operator (the founder).
- **Timers:** per speaker, with defaults of 20 minutes each and 5 for reply. The operator can change them, pause, and hand the floor to counsel.
- **Layout for the studio:**
  - a **bench screen**: the judge's name, a speaking indicator and the live words;
  - a **citation screen**: each authority as it is cited, showing court, division, binding or persuasive for this bench, its treatment, and the paragraph, or "not found" in red;
  - an **operator screen** with all the controls.
  - Each screen is its own URL, so it can go on its own monitor and camera.
- **Practice mode:** one student alone against the AI judge from a laptop browser, using the same flow.

## 3b. Look and sound: a real courtroom, not a cartoon
Founder: "not a cartoon... make it professional. That also wows the USA."
- **No cartoon avatar, no animated face.** The judge appears as a dignified bench screen:
  - the court's name and the judge's title in a classic serif;
  - a quiet speaking indicator (a thin level line, not bouncing bars);
  - live captions under it, as on a broadcast court feed.
- **Fictional insignia only.** No real court crest, coat of arms or seal: the court name and emblem are the founder's own.
- **Palette:** dark navy, ivory text and one restrained accent. No gradients, emoji or playful motion. Transitions are fades of 200ms or less.
- **Voice:** a natural, measured, broadcast-quality voice that sounds like a senior judge (the founder picks from shortlisted voices). It speaks at court pace with real pauses, in formal register: "Counsel, I have difficulty with that submission." It never says "As an AI".
- **The citation screen reads like a court's case-management system,** not an app: a clean table, small caps, paragraph numbers.
- **Built for camera:** large type readable on video at 1080p from 3 metres, safe margins for broadcast, no flicker, and a clean-feed URL (no controls, no cursor) for each screen.
- **Courtroom procedure:**
  - the judge opens the court and calls the matter;
  - counsel's appearances are noted;
  - "May it please the court" is expected;
  - it calls time politely, then firmly;
  - it adjourns at the end.
- **The judgment reads like a reported judgment:** numbered paragraphs, order at the end.

## 3c. Two courts: South Africa and the United States
- **A session is either SA or US.** Procedure, forms of address and voice follow that country.
  - SA: "My Lady/My Lord", "M'Lord", heads of argument, SA appeal practice.
  - US: "Your Honor", "May it please the Court", a federal appellate argument with a fixed time per side, and questions from the bench throughout.
- **US sessions use the US library** (CourtListener appellate opinions, statutes) and run on the Boston box. SA sessions run on the ZA box. Each box runs its own LiveKit server.
- **US binding rules come from a US rules file**, in the same shape as Z12's SA file, seeded as draft:
  - the Supreme Court binds everything;
  - a circuit binds its district courts and later panels of that circuit;
  - other circuits are persuasive;
  - a state's highest court binds that state's courts on state law.
  - The founder confirms it.
- **Civil only in both countries.**

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

## 7. Public watch pages: Moot brings people to Tervory (founder, 21 Oct)
Legal formats only, with no game features.
- **`/moot/{match}` watch page:**
  - the bench screen recording with captions, the written judgment, the fairness check and the reveal;
  - every authority links to the real case on SAFLII (SA) or CourtListener (US);
  - a shareable link with a proper preview card.
- **Clips:**
  - the operator marks moments (the sharpest question, a failed citation caught, the reveal);
  - ffmpeg cuts 9:16 and 16:9 clips with captions burned in.
- **"Argue against the AI":**
  - a visitor picks a side of a public problem and argues in text or voice against AI counsel;
  - a free sign-up saves the result, and that's the funnel into Tervory;
  - it's rate-limited, with the same Tank receipts.
- **A weekly match slot,** alternating SA and US problems.
- **Counts on the founder control panel:** watch-page views, clips shared, and argue-against-the-AI sign-ups. Count them server-side, with no tracking of individuals.
- Publishing a match needs the founder's approval.

## Rules
- Civil law only. SA sessions on the ZA box (fixtures until the Hetzner move), US sessions on Boston. Model calls go only through Tank.
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
- AI against AI runs end to end on a fixture problem, both orders, with the fairness check computed;
- a failed citation by AI counsel is flagged in the ruling;
- a major-issue fixture produces one judgment per method;
- the watch page renders with links to the source cases, and an unpublished match returns 404;
- each screen loads on its own URL at 1440px and 1920x1080 with a clean feed, practice mode works at 375px; an SA and a US session each use their own procedure, library and box.

Then a 10-minute recorded demo run on staging with two people, linked in the PR. After merge, Claude sets up the first session with the founder.

# Trigger upstream attribution

- Based on **The Elements of Agent Style**, Yue Zhao: https://github.com/yzhao062/agent-style. Rules CC BY 4.0; Python detectors MIT. Vendored files are unchanged; Trigger calls deterministic detectors only. Full notices in vendor/agent_style/LICENSES and NOTICE.md.
- **Agent Stylebooks**, Shilpa Mitra: https://github.com/Neeeophytee/agent-stylebooks. MIT original guidance; the original 11 books only. Full licence/provenance in sources/stylebooks. This does not import or relicense the third-party guides they discuss.
- **Practical Prose**, Joshua Levy: https://github.com/jlevy/practical-prose. Rubric CC BY 4.0. Trigger adapts mechanical portions into a checklist; it provides no semantic grade and never imports the scorer. Full licence in sources/practical-prose-LICENSE.
- **Brand Voice Spec**, Abe Garcia at Workhorse: https://huggingface.co/datasets/thehonestape/brand-voice-spec at e9d26dbecb2a0d5c023d4fb8d8f954e0ca4cdd54, CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/). Trigger adapts its format into validation/storage and adds explicit requiredTerms and checker settings. No fictional worked-example content is included. No tenant voice is seeded.
- **Proselint**, Amperser contributors: https://github.com/amperser/proselint, BSD-3-Clause, version 0.16.0. Licence in sources/proselint-LICENSE.md.
- **LanguageTool**: https://github.com/languagetool-org/languagetool, LGPL-2.1-or-later. Runs unmodified in a separate internal container; no cloud API or paid rules. Container packaging: https://github.com/meyayl/docker-languagetool (LGPL-2.1). Exact image pin is recorded in compose and the proof.

CC BY adaptations retain attribution and identify changes here. The upstream works do not endorse Trigger. Content-dependent checks are advisory findings, not a certification of accuracy or legal correctness.

# Opt-in Arch-Router / RouteLLM comparison contracts

This implements the founder's comparison brief on main `12a4ee37`. The inspected
ENGINE.md, MODEL.md, FLOW.md and Tank build lists describe RouteLLM and the routing
ladder; no separate Arch-Router comparison implementation or open PR was found.
This harness changes no default, policy, model, endpoint or runtime configuration.
It does not write training data, memory, gold sets or production evidence.

Run the bounded fixture command in the existing Tank development environment:

```sh
python scripts/compare_route_classifiers.py --dry-run --tenant placeholder-tenant-a --split holdout
```

It evaluates at most 32 manifest examples (16,000 characters per conversation),
selects exactly one tenant and split, and performs no network or model loading.
The command deliberately uses constant, conflicting classifier stubs. Its
`fixture_contract` counts check plumbing only. They are not model accuracy,
benchmark predictions or savings. Fixture adapter elapsed time measures Python
contract overhead; real classifier latency, inference cost and route quality stay
null under `model_comparison.status: unrun`. Unknown cost is not zero cost.

## Official identity and counsel evidence

The official [model card](https://huggingface.co/katanemo/Arch-Router-1.5B/blob/5b156890a91b1035a86f82faf1a651debf309009/README.md)
names `katanemo/Arch-Router-1.5B`, based on Qwen2.5-1.5B-Instruct, and links
`katanemo/arch`, which GitHub redirects to [katanemo/plano](https://github.com/katanemo/plano/tree/b13ddd632bde1fea7678386c345665ea5fa671af).
The immutable model/repository revisions and content hashes are recorded in
`tests/fixtures/route_comparison/upstream.json`.

The repository is Apache-2.0. **The model is not covered by that licence.** Its
[pinned LICENSE](https://huggingface.co/katanemo/Arch-Router-1.5B/blob/5b156890a91b1035a86f82faf1a651debf309009/LICENSE)
is the Katanemo Community License Agreement dated April 2, 2026. Section 4 says
commercial use requires a separate commercial licence. The card labels it
`katanemo-research`. Commercial permission is pending counsel review, with no claim that a licence
has been granted. The original fixture run downloaded no weights and executed
no Arch model; the subsequent opt-in CPU harness records its own execution evidence. The adapter contains
only our contract validation, with injected fixture responses; it does not copy
upstream model code or provide a weight loader. The founder authorized local CPU comparison; counsel decides which uses must
be blocked. Licence review is evidence for counsel, not an automatic agent stop.
Attribution and naming provisions are collected in the CPU handoff.

## Contracts, hardware and comparison limits

Arch takes named route descriptions and a conversation; its recommended prompt
serializes them inside `<routes>` and `<conversation>` tags in a user chat turn.
It generates JSON `{"route":"exact_route_name"}`, or `{"route":"other"}` for
irrelevant/completed intent. The contract adapter accepts exactly `weak`, `strong`
and `other`; malformed/oversized output or an unavailable classifier abstains and
falls back to the existing strong model. No confidence score is invented. A
future runtime backend must apply the pinned card's prompt/chat template and
bounded generation settings; the injection boundary is not an implemented model
runtime.

RouteLLM reuses Tank's existing `configuration` and `Configuration` pair and
fingerprint. Its adapter matches `routellm_shadow.serve`: classify the latest user
turn, choose strong when the score is at least the configured threshold, and
fall back to strong on invalid/unavailable scores. The existing `score` function
owns pinned offline CPU loading; it is not called by this command. Its local
`/opt/routellm` checkpoint is unavailable in this environment.

These systems have different objectives: Arch matches user-defined route
preferences, while this RouteLLM classifier predicts strong-model advantage.
The fixture restricts both to the same two model placeholders; route-label
agreement alone cannot establish downstream answer quality or savings.

Arch config specifies Qwen2ForCausalLM, float16, 32,768-token context. HF metadata
reports 1,543,714,304 parameters: approximately 3.09 GB of FP16 weight storage,
**before** runtime, activations and KV cache. Upstream publishes no minimum RAM,
VRAM or CPU latency guarantee. Its example uses automatic device placement;
this does not establish CPU feasibility or authorize a GPU job. No GPU is used
or required by the fixture harness. No unreviewed quantization is substituted.

## Provenance and remaining acceptance gates

Every example is authored synthetic text with source ID, author, split, explicit
non-gold status and a fixture-only review marker. Development/holdout source
groups cannot overlap; normalized exact duplicate conversations are rejected
across the full manifest before tenant selection. No production transcript,
training export, held-out product gold or teacher output is consumed. The
classifiers receive only route descriptions/conversation or the latest user
turn, never reference labels or provenance. Output contains aggregate counts
and reproducibility hashes, not prompts, per-example labels or user identities.
Near-duplicate/paraphrase leakage and label validity require independent human
review before a real benchmark; these tiny fixtures cannot prove either.

This fixture command always leaves actual comparison **unrun**. The separate
`scripts/compare_router_cpu.py` implements opt-in local CPU execution. Real
benchmark conclusions still require a reviewed and frozen
routing preference configuration, and independently reviewed non-gold
route-development/holdout examples. Tune thresholds/descriptions only on
development; lock their hashes before opening holdout. Report held-out route
agreement/quality, coverage, abstention and strong-model escalation separately;
measure classifier latency with cold/warm loading distinguished, and report
measured inference cost or unknown cost independently of downstream model cost.
No savings claim is supported until downstream quality and billing evidence
exist. This PR adds no production activation path.

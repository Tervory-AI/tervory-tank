# AUTUMBRA-OSS — recommended open-source staging

**Product:** Autumbra (**Watch** / **Enforce**) only. Do not use Ghost/Wraith in user-facing copy.
Code paths may still say `agents/ghost` short-term.

**Owner ask (2026-10-24):** get Autumbra-recommended OSS **in**, then **customise** — not leave stock.

## Status (truth)

| Item | State |
|------|--------|
| Staging vault on bot box `/workspace/autumbra-oss-vault/` | **Populated** (shallow clones) |
| Push to `ammosync@41.222.36.225:/home/ammosync/code-vault` | **Blocked** — SSH No route to host; see vault `PUSH-WHEN-VAULT-UP.md` |
| Dual-LLM / NeMo / Wazuh **live** in product | **No** — clones + plans only |
| This PR | Docs + clone helper only — **no merge/deploy assumed** |

## Already in Tank (not Autumbra blockers)

- Tank / LiteLLM
- Pydantic ThreatPayload
- Cloudflare hooks
- Docker / CI

## Shopping list (staged)

| Package | Upstream | Staged SHA (depth-1) | License | Lane | Stronger-than-stock (planned) |
|---------|----------|----------------------|---------|------|-------------------------------|
| wazuh | wazuh/wazuh | `dcb722fae3e85719eaaa006a45751c77819469e5` | GPL-2.0 (+ AGPL engine) | Watch | Agent → Autumbra triage JSON only |
| vector | vectordotdev/vector | `bdd8842daf787497ae65f7e11e4eda6f72df8196` | MPL-2.0 | Watch | Anomaly-only forward; telemetry off |
| fluent-bit | fluent/fluent-bit | `05048e35d7106890006b7b593531bd51a16dfc93` | Apache-2.0 | Watch | Light edge collector; anomaly-only |
| steampipe | turbot/steampipe | `103201b1aad459788fb7d798637295600ed82179` | AGPL-3.0 | Inventory | Read-only SQL; no write plugins |
| opencti | OpenCTI-Platform/opencti | `879d3f198971256acf1b6e79152f9ffeb39842ab` | Apache-2.0 CE | Intel | Feed allowlist; CE only |
| vllm | vllm-project/vllm | `4e591657157a021cab997f911d67f50c0d18a71e` | Apache-2.0 | Watch LLM | Onsite inference; no prompt egress |
| nemo-guardrails | NVIDIA-NeMo/Guardrails | `e2b035a68938edda29bc2bf899b0e14e4db37205` | Apache-2.0 | Air Gap | Rails → ThreatPayload burn |
| llm-guard | protectai/llm-guard | `168c1034ffdb33837e7ae6fd6a16b80567c1be03` | MIT (**archived upstream**) | Air Gap | PII + injection before Watch LLM; fork |
| ansible | ansible/ansible | `4761c59c9639ff70d4db2b91b7361e121d482301` | GPL-3.0 | Enforce | Stubs **OFF**; dry-run + arm token |
| terraform | hashicorp/terraform | `55988303ba5651e41e2c9097e208468c8eb3da4b` | BSL-1.1 | Enforce | Stubs **OFF**; legal review for embed |

**Not vendored into this repo** (multi-GB trees). Prefer onsite vault + thin Tank adapters.

## Custom plan (non-negotiables)

1. Autumbra naming (Watch / Enforce)
2. Zero-ingestion / onsite-first (no shipping client payloads to Tervory cloud)
3. Dual-LLM air-gap: dirty inputs never reach Enforce weapons; ThreatPayload schema burn
4. Strip / disable upstream telemetry where present
5. One concrete stronger-than-stock change per package (see table)

Each staged tree has a root `TERVORY.md` with the same contract.

## Recommended first customise PRs

1. **Air Gap** — NeMo Guardrails + LLM Guard adapters → ThreatPayload; scanners before Watch LLM
2. **Watch** — Vector / Fluent Bit Autumbra configs (anomaly-only); then Wazuh triage JSON
3. **Enforce** — Ansible / Terraform stubs **OFF** by default (no auto-apply)

## Helper

```bash
./scripts/clone-autumbra-oss.sh /path/to/autumbra-oss-vault
```

Re-clones shallow into a target directory (or refreshes if empty). Does not commit vendor trees into Tank.

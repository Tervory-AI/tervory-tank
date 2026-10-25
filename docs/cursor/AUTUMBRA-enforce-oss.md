# Autumbra Enforce — OSS Ansible + Terraform stubs

**Status:** Draft adapters + dry-run templates in `tervory-tank` (not live in product).  
**Product naming:** Autumbra **Watch** / **Enforce** only. Never ship Ghost/Wraith in user-facing copy.  
**Code path:** `agents/ghost/enforce_oss/` (short-term room name unchanged).  
**Flags:**
- `ENFORCE_OSS_ENABLED` / `GHOST_ENFORCE_OSS_ENABLED` — default **OFF**
- `ENFORCE_OSS_ARMED` / `autumbra_enforce_armed` — default **unarmed**; requires enabled **and** armed

This is the **Enforce customise** slice from the Autumbra OSS vault shopping list. Thin Tank adapters only — do not vendor multi-GB Ansible/Terraform trees.

## Vault (primary vs cache)

| Location | Role |
|----------|------|
| Boston `ammosync@2.25.250.28:/home/ammosync/code-vault/autumbra-oss/` | **Primary** vault |
| Bot box `/workspace/autumbra-oss-vault/` | Working **cache** — customise from here; do not re-clone |
| ZA `41.222.36.225` / `dev.ammosync.co.za` | **Abandoned** for this vault |

## Vault pins (Enforce lane)

| Adapter | Upstream | Vault SHA | License | Stronger-than-stock |
|---------|----------|-----------|---------|---------------------|
| Ansible | ansible/ansible | `4761c59c9639ff70d4db2b91b7361e121d482301` | GPL-3.0 | ThreatPayload only; dry plan; `autumbra_enforce_armed: false`; no shell/command/raw/script modules; Galaxy auto-fetch off |
| Terraform | hashicorp/terraform | `55988303ba5651e41e2c9097e208468c8eb3da4b` | **BSL-1.1** | ThreatPayload only; dry plan; no apply path; no phone-home state backend; legal review before product embed |

## Stronger-than-stock

1. **ThreatPayload only** — `accept_enforce_threat` → `accept_threat_payload`. Dirty sites, injection, and raw-shell markers burn with the fixed message (never echoed).
2. **No raw shell** — adapters never spawn `ansible-playbook`, `terraform apply`, or OS shells. Packaged playbooks forbid Ansible `shell` / `command` / `raw` / `script` modules.
3. **Dry-run / plan only** — `plan_from_threat` returns would_run / would_plan dicts with `applied: false`.
4. **Armed flag separate** — enabling the feature does **not** arm it. Both flags required; playbooks still ship `autumbra_enforce_armed: false`.
5. **Allowlisted playbooks / modules only** — unknown ids raise; unknown ThreatPayload sites burn.

## Relation to Shields Up and existing stub

| Surface | Role |
|---------|------|
| Autumbra Watch Shields Up (`shields.py`) | **Live** Cloudflare path: propose → founder Shield tap → health → undo. `CLOUDFLARE_API_TOKEN_GHOST` stays here. |
| `wraith.py` + `POST /ghost/wraith/enforce` | Existing dry Enforce stub behind `GHOST_WRAITH_ENABLED` (**OFF**). Code path name short-term; product = Autumbra Enforce. **Untouched** by this PR except coexistence. |
| This OSS slice (`enforce_oss`) | Ansible/Terraform **templates + dry plans**. Does **not** call Cloudflare. Does **not** replace founder Shield tap. |

## Files

- `agents/ghost/enforce_oss/` — Python adapters (`ansible.py`, `terraform.py`, `common.py`)
- `agents/ghost/configs/enforce/playbooks/` — CF WAF / rate-limit / multipart / bots + host iptables brief
- `agents/ghost/configs/enforce/terraform/` — `.tf.tpl` stubs + README (BSL note)
- `agents/ghost/configs/enforce/ansible.cfg` — `gathering = explicit`, no Galaxy auto-fetch
- `GET /ghost/enforce/oss` — status (Autumbra Enforce copy); flag does not need to be ON to read status
- `tests/test_ghost_enforce_oss.py`

## Out of scope

- Live `ansible-playbook` / `terraform apply`
- Merge / deploy / enabling flags in prod
- Expanding `ALLOWED_ZONES` / `WATCHED_SITES`
- GPU / vLLM
- Vendoring upstream Ansible or Terraform trees into Tank
- Replacing Shields Up as the live Cloudflare path

## Related drafts

- #289 Autumbra OSS shopping list / vault truth
- #290 Autumbra Watch OSS intake (mirror pattern)
- #284 air-gap + Enforce stub (stack base)
- #281 ThreatPayload + SLO

## Merge gate

CI green. Merge **only after Zenas via AMMOSYNC**. Leave Enforce OSS flags **OFF** and **unarmed** until founder go. No live apply from this slice.

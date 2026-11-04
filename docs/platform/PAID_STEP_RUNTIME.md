# Wave 4 paid-step client prerequisite

Base: origin/main 27cff2f7. Branch: codex/platform-w4-paid-runtime. Claude opens the PR.

Deploy this client prerequisite before the dependent paid-step backend on codex/platform-w4. No new keys, providers or services. Main-stack/ZA and room deployment detection must include the shared chassis; Base and Rig room changes redeploy their regional copies. Context.dev trials fail closed until Tank exposes its credit authorization endpoint.

The shared Tank client polls a saved paid_run_id using its original room key and tenant. It never repeats the operation POST. Interrupted or foreign runs fail closed. Rig's brain performs that polling with its credential; Forge receives only the original claim result and never the key. The claim wait has a separate 25-hour bound; the GPU execution budget starts after approval.

Base hashes the exact Context.dev identity lookup, requests one bound authorization before reserving credits, and verifies the same call UUID before contacting the provider. Existing reservation uniqueness and budget checks remain. No provider was contacted during implementation.

Validation: tests/test_paid_step_transport.py verifies exactly one POST and owning-tenant polling, successful completion, interruption and a foreign run. Existing Base/Rig protocol checks run serially in the dependent backend checkout. No retry added.

Direct-client follow-up: Base's SkillClient, Ghost's Tank wrapper, the retained Market Lab native-research compatibility path, the isolated researcher and worker proxy also poll saved runs rather than parse a 202 as an answer. Polling always uses the original Tank and owning tenant/key; returned status URLs cannot redirect it. Ghost's existing image now includes the shared chassis transport. These paths keep their existing absolute job/SDK lifetime limits. Seven offline transport checks passed in 1.03 seconds in the dependent checkout. Rebuild the already-existing isolated researcher/worker images with these changes when those optional paths are deployed; no new service is introduced.

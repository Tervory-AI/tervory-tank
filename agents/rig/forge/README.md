# RIG-5F forge

One private CPU worker converts CAD, scans and GPU reconstructions into **drafts**.
There is no approval or shopper-serving route in this lane. RIG-5 consumes the
draft and report and owns human approval.

## Build and verify (cloud only)

From the repository root:

```sh
docker build --target test -t tervory-rig-forge:test agents/rig/forge
docker run --rm --network none --read-only --cap-drop ALL \
  --tmpfs /tmp:rw,nosuid,nodev,size=1g,uid=1000,gid=1000 \
  -v "$PWD:/repo:ro" -w /repo -e PYTHONPATH=/repo:/repo/tank:/app \
  tervory-rig-forge:test python -m pytest -q -p no:cacheprovider \
  tests/test_rig_forge_geometry.py tests/test_rig_forge_pipeline.py tests/test_rig_forge_gpu.py
RIG_FORGE_CONTAINER_IMAGE=tervory-rig-forge:test python -m pytest -q tests/test_rig_forge_containers.py
```

The `rig-forge` CI workflow builds the image, checks the pinned tool archives and
package hashes, converts the neutral 20 × 30 × 40 mm STEP and OBJ fixtures through
every real CPU tool, and tests actual Docker network isolation. Tank CI applies
the additive schema to a fresh database, reapplies it, and tests caps, concurrent
reservations, receipt idempotency, the paid-work pause and tenant isolation.

## Private contract

The existing authenticated brain exposes `POST /forge/jobs` and
`GET /forge/jobs/{job_id}?tenant_id=…&home_region=us-east`. Only the brain's actual
Docker peer may call Forge's `/jobs`; forwarded headers confer no authority.
There is no public Forge hostname, published port or Tank key. The egress proxy
permits CONNECT to port 443 on `huggingface.co` and the configured R2 account host
only, rejects private DNS answers, and connects to the verified IP.

The request has `tenant_id`, `job_id` (UUIDs), `home_region: "us-east"`, `method`
(`cad`, `scan`, `photogrammetry`, `trellis2`), `inputs` (basenames), `unit_mm`,
`dimensions_mm` (three measured values), and optional `max_triangles` (100000),
`max_bytes` (8000000), `timeout_seconds` (600), `cost_cap_usd` ("0"). The GPU
methods require a positive cap. Photos require 50–150 inputs for Meshroom or
1–4 for TRELLIS. Exact repeated requests poll the same job; changed inputs with
the same tenant/job ID are rejected. A restarted job is never relaunched.

Upload inputs to `tervory-rig/forge/{tenant_id}/{job_id}/inputs/{basename}` using
Rig's existing bucket adapter. CPU scans must have embedded data; OBJ external
material/script references and GLB external URIs are rejected. STEP/IGES is
converted in millimetres. `unit_mm` specifies millimetres per source mesh unit.
All GLB output uses metres. Photos have no absolute scale: GPU results are scaled
uniformly to the supplied longest dimension; the CPU check then verifies **all
three** dimensions within 2% (0.01 mm absolute floor). This cannot prove fit.

The CPU sequence is CAD → preflight → Blender cleanup/decimation/normal+AO bake
→ dedup/simplify/texture resize/meshopt → gltfpack → KTX2 → lossless meshopt
recompression → model check → Khronos validator. Preflight rejects inward/open
meshes **before** any repair; every connected component must pass. Individual
tool subprocesses are bounded to 300 seconds and receive no service credentials.
Only passing output is uploaded to `drafts/model.glb` and `drafts/report.json`,
with `approval=draft` metadata. Report fields include triangle/byte counts,
dimensions and each check's result/reason. Failures remain inspectable through
the job status, including a failing model-check report.

## GPU configuration, built now and enabled last

Coolify settings `HF_JOBS_TOKEN` and `HF_JOBS_NAMESPACE` remain empty until the
Tervory account is connected. Forge holds the job-scoped token; neither the brain
nor the remote job receives it. The remote job receives only Rig's existing R2
credentials and tenant/job identifiers. Native reconstruction runs as a child
with a credential-free environment; provider errors and signed URLs are never
logged by the controller.

GPU image recipes use digest-pinned CUDA bases and hashed source/dependency locks:

```sh
docker build -f agents/rig/forge/gpu/Dockerfile.meshroom \
  -t tervory-rig-meshroom:2023.3.0 agents/rig/forge
docker build --build-context weights=/path/to/licensed-offline-bundle \
  -f agents/rig/forge/gpu/Dockerfile.trellis2 \
  -t tervory-rig-trellis2:pinned agents/rig/forge
```

The offline bundle contains `trellis2/`, `trellis1/`, `dino/` with exactly the
files/revisions in `gpu/models.lock.json`. Obtain them from the upstream model
repositories under their licences; no token is copied into the image. The build
verifies LFS SHA256/Git blob hashes and records all resulting SHA256 values.
TRELLIS uses prepared photos instead of the default commercial background remover.
For multiple views it concatenates conditioning tokens; quality and runtime still
need a real GPU acceptance run. CPU CI and the provider stub do not claim that run.

Publish the built GPU images to Tervory's existing image registry and configure
their **digests**, never mutable tags, in `tank.rig_forge_limits`. Each tenant and
method needs an explicitly enabled row with `image`, supported HF `flavor`, the
current verified `hour_usd`, provider `billing_quantum_seconds`, `max_seconds`,
`max_job_usd`, and a lifetime `total_budget_usd`. No default row authorizes spend.
Rates must cover the provider's billable interval; the reservation uses the
timeout rounded up to the configured billing quantum. Registry publishing,
licensed checkpoints, credentials and actual GPU capacity are deployment inputs.

Tank serializes reservations, checks the requested cap and paid-work pause, and
claims each reservation once before submission. A vendor-ledger row is written
**before** the provider call so lost responses and process crashes remain visible.
The receipt records `cost_basis=upper_bound`, not a fabricated exact invoice.
Failed, cancelled and uncertain jobs retain that upper bound and consume budget;
there are no automatic refunds or submission retries. Reconcile actual provider
charges operationally before increasing the tenant's configured budget.

Each zero-cost pipeline step also receives a Tank ledger/agent receipt through
the brain. The existing `/v1/ledger/vendor` route is unchanged. A receipt outage
stops work and leaves a durable pending payload under the job's private volume;
an operator can replay that payload through the brain's relay after recovery.
Never replay a claim or restart an uncertain GPU job. Review its existing provider
job and reservation first. Job files remain in the private volume for diagnosis;
operate a retention policy appropriate to the deployment before real client use.

## Proof after deploy

1. Run `ops/seal-check.sh`: Rig must be sealed; Forge and its proxy must be on
   exactly their documented private networks. `rig.tervory.com/health` stays 200.
2. From the brain container, `http://rig-forge:8010/health` returns `ok: true`.
   A different peer must be denied. Missing GPU settings must return 503 without
   creating a paid job.
3. Upload the neutral STEP or OBJ, submit a unique job through the authenticated
   brain route above, then poll that tenant/job until `status: draft`. Check
   `drafts/report.json` in `tervory-rig` for all checks true and dimensions
   20 × 30 × 40 mm; the GLB stays marked draft.
4. Query `tank.ledger` and `tank.agent_receipts` using that **tenant_id and job_id**
   (`task_id` in the ledger). Every CPU stage has cost zero. After GPU settings,
   image digests and budget are configured, run a capped neutral photo job and
   check `tank.rig_forge_jobs` for its reservation/completion plus the matching
   `huggingface_jobs` vendor receipt and provider job identifier. Meshroom also
   writes its original OBJ, MTL and textures under that job's `gpu/` prefix.

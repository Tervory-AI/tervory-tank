#!/usr/bin/env bash
set -euo pipefail

# Test setup only. Use the same source pin as the opt-in Rig worker; the
# offline proof executes its real AIAgent against a loopback provider fixture.
sdk_commit=$(python - <<'PY'
import re
from pathlib import Path
source = Path('agents/rig/Dockerfile.brain').read_text()
pin = re.search(r'^ARG HERMES_COMMIT=([a-f0-9]{40})$', source, re.M)
if pin is None:
    raise SystemExit('Missing immutable Rig Hermes SDK pin')
print(pin.group(1))
PY
)
sdk_dir="${RUNNER_TEMP:?}/rig-hermes-sdk"
git init "$sdk_dir"
git -C "$sdk_dir" remote add origin https://github.com/NousResearch/hermes-agent.git
git -C "$sdk_dir" fetch --depth 1 origin "$sdk_commit"
git -C "$sdk_dir" checkout --detach FETCH_HEAD
test "$(git -C "$sdk_dir" rev-parse HEAD)" = "$sdk_commit"

# Upstream marks its dependencies Python >=3.14; Tank's tested runtime is 3.12.
# Install the bounded import closure beside Tank's existing HTTP/OpenAI pins.
python -m pip install fire==0.7.1 ruamel.yaml==0.18.16 ruamel.yaml.clib==0.2.15 \
    snowballstemmer==3.1.1 termcolor==3.3.0 tomli-w==1.2.0 truststore==0.10.4 \
    python-dotenv==1.2.4 psutil==7.2.2 rich==14.3.3 prompt-toolkit==3.0.52 \
    croniter==6.0.0 tenacity==9.1.4
python - "$sdk_dir" <<'PY'
import site
import sys
from pathlib import Path
(Path(site.getsitepackages()[0]) / 'rig-hermes-sdk.pth').write_text(sys.argv[1] + '\n')
PY

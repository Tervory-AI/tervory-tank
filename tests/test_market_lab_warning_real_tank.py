"""The actual Tank, actual Market Lab and actual Tiger on local Postgres."""

import os
import sys
from pathlib import Path
from urllib.parse import urlsplit

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "agents/market_lab"))


def test_warning_job_on_real_tank(tmp_path):
    target = urlsplit(os.environ.get("DATABASE_URL", ""))
    if target.hostname not in {"127.0.0.1", "localhost"} or not target.path.endswith("_test"):
        pytest.skip("requires a loopback *_test Postgres database")
    from warning_proof.services import services
    from warning_proof.check import verify

    with (tmp_path / "services.log").open("w+") as log:
        try:
            with services(log=log) as env:
                assert verify(env)["result"] == "passed"
        except Exception:
            log.seek(0)
            print(log.read())
            raise

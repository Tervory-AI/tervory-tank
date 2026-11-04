"""Complete public outputs and reservation handoffs, with deterministic request IDs."""

import copy
import functools
import json
import os
from pathlib import Path
from uuid import UUID
import pytest

records = []


@pytest.fixture(autouse=True)
def capture(monkeypatch, request):
    from rigbox.service import Service
    import rigbox.service as module

    counter = 0

    def deterministic_uuid():
        nonlocal counter
        counter += 1
        return UUID(int=counter)

    monkeypatch.setattr(module, "uuid4", deterministic_uuid)
    for name in ("search", "product", "quote_payload", "_store_quote"):
        original = getattr(Service, name)

        def wrap(original=original, name=name):
            @functools.wraps(original)
            async def call(self, *args, **kwargs):
                entry = {
                    "test": request.node.nodeid,
                    "method": name,
                    "args": copy.deepcopy(args),
                    "kwargs": copy.deepcopy(kwargs),
                }
                try:
                    result = await original(self, *args, **kwargs)
                except Exception as error:
                    entry["error"] = {
                        "class": type(error).__name__,
                        "args": error.args,
                        "code": getattr(error, "code", None),
                        "status": getattr(error, "status", None),
                    }
                    records.append(entry)
                    raise
                entry["output"] = copy.deepcopy(result)
                if name == "_store_quote":
                    entry["stored"] = copy.deepcopy(
                        await self.store.quotes_for(args[0])
                    )
                    for row in entry["stored"]:
                        row.pop("created_at", None)
                    entry["handoff"] = copy.deepcopy(getattr(self.handoff, "sent", []))
                records.append(entry)
                return result

            return call

        monkeypatch.setattr(Service, name, wrap())


def pytest_sessionfinish(session, exitstatus):
    Path(os.environ["RIG_L1_GOLDEN_OUTPUT"]).write_text(
        json.dumps(records, sort_keys=True, indent=2, default=str) + "\n"
    )

"""Per-client Enforce lifecycle against the local fixture compose backend."""
from pathlib import Path

from agents.ghost.enforce_lifecycle import (
    FixtureComposeBackend,
    assert_tenant_isolation,
    plan_create,
    plan_destroy,
)

TENANT_A = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
TENANT_B = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"


def test_create_destroy_real_fixture_backend_and_isolation(tmp_path: Path):
    backend = FixtureComposeBackend(tmp_path)
    plan_a = plan_create(TENANT_A, existing_count=0)
    plan_b = plan_create(TENANT_B, existing_count=1)
    assert_tenant_isolation(plan_a, plan_b)
    assert plan_a["isolation"]["routes_to_queue_only"] is True
    ra = backend.create(plan_a)
    rb = backend.create(plan_b)
    assert ra["outcome"] == "created" and rb["outcome"] == "created"
    assert ra["secret_value_present"] is False
    assert ra["threat_payload_queue"] == plan_a["threat_payload_queue"]
    assert ra["routes_to_queue_only"] is True
    assert ra["queue_shared_across_clients"] is False
    iso_a = backend.read_isolation(TENANT_A)
    iso_b = backend.read_isolation(TENANT_B)
    assert iso_a["network"] != iso_b["network"]
    assert iso_a["volume"] != iso_b["volume"]
    assert iso_a["project"] != iso_b["project"]
    assert iso_a["threat_payload_queue"] != iso_b["threat_payload_queue"]
    # Secret names held (None) — still not a shared credential name.
    assert iso_a["secret_name"] is None and iso_b["secret_name"] is None
    # Compose files exist and name distinct networks/volumes + real queue door.
    compose_a = (tmp_path / plan_a["project"] / "docker-compose.yml").read_text()
    compose_b = (tmp_path / plan_b["project"] / "docker-compose.yml").read_text()
    assert plan_a["network"]["name"] in compose_a
    assert plan_b["network"]["name"] in compose_b
    assert plan_a["network"]["name"] not in compose_b
    assert "ghost.enforce_app:app" in compose_a
    assert "THREAT_PAYLOAD_QUEUE: /queue" in compose_a
    assert "THREAT_PAYLOAD_QUEUE: /queue" in compose_b
    assert f"name: {plan_a['threat_payload_queue']}" in compose_a
    assert f"name: {plan_b['threat_payload_queue']}" in compose_b
    assert plan_a["threat_payload_queue"] not in compose_b
    assert "threat_queue:/queue" in compose_a
    destroyed = backend.destroy(plan_destroy(TENANT_A))
    assert destroyed["outcome"] == "destroyed"
    assert not (tmp_path / plan_a["project"]).exists()
    assert (tmp_path / plan_b["project"]).exists()

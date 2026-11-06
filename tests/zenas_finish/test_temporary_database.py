"""Disposable sample databases stop their restarted postmaster before removal."""
from pathlib import Path

import pytest

from agents.zenas.core import operations


@pytest.mark.asyncio
@pytest.mark.parametrize("body_fails", [False, True])
async def test_restarted_sample_database_stops_before_directory_removal(monkeypatch, body_fails):
    import pgserver

    calls = []
    directories = []
    real_ctl = pgserver.pg_ctl

    def recorded_ctl(args, **kwargs):
        calls.append(list(args))
        directories.append(Path(kwargs["pgdata"]))
        return real_ctl(args, **kwargs)

    monkeypatch.setattr(pgserver, "pg_ctl", recorded_ctl)

    async def use_database():
        async with operations.connection(temporary=True) as conn:
            assert await conn.fetchval("SELECT 1") == 1
            if body_fails:
                raise ValueError("sample body failed")

    if body_fails:
        with pytest.raises(ValueError, match="sample body failed"):
            await use_database()
    else:
        await use_database()
    assert calls[0][:2] == ["-w", "restart"]
    assert calls[-1] == ["-w", "stop", "-m", "fast"]
    assert not directories[-1].exists()

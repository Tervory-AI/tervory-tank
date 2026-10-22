"""Bounded subprocess pipeline. Every finished/failed step must reach its receipt sink."""
from __future__ import annotations

import asyncio
import json
import os
import signal
from pathlib import Path
from typing import Awaitable, Callable

from .cad import convert
from .inputs import embedded_mesh
from .model_check import Budget, check

HERE = Path(os.environ.get("RIG_FORGE_TOOL_ROOT", Path(__file__).resolve().parent))
Receipt = Callable[[str, str], Awaitable[None]]


class StageFailed(RuntimeError):
    pass


async def command(args: list[str], cwd: Path, timeout: int = 300) -> None:
    # Tool processes receive no HF/R2/room credentials and no network proxy.
    safe = {k: os.environ[k] for k in ("PATH", "LANG", "LD_LIBRARY_PATH") if k in os.environ}
    safe.update(HOME=str(cwd), TMPDIR=str(cwd), OMP_NUM_THREADS="2")
    process = await asyncio.create_subprocess_exec(*args, cwd=cwd, env=safe,
        stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL, start_new_session=True)
    try:
        await asyncio.wait_for(process.wait(), timeout)
    except (asyncio.TimeoutError, asyncio.CancelledError):
        os.killpg(process.pid, signal.SIGKILL)
        await process.wait()
        raise
    if process.returncode:
        raise StageFailed("Tool exited unsuccessfully.")


async def run(source: Path, work: Path, *, unit_mm: float, dimensions_mm: tuple[float, float, float],
              budget: Budget, receipt: Receipt) -> dict:
    async def stage(name, action):
        try:
            result = await action()
        except Exception:
            await receipt(name, "failed")
            raise StageFailed(name + " failed; the result is not eligible for approval.") from None
        await receipt(name, "delivered")  # Receipt failure stops before the next step.
        return result

    async def geometry(path, scale, cap, encoded_bytes=None):
        embedded_mesh(path)
        report = await asyncio.to_thread(check, path, unit_mm=scale, expected_mm=dimensions_mm,
                                         budget=cap, encoded_bytes=encoded_bytes)
        (work / "report.json").write_text(json.dumps(report, indent=2))
        if not report["passed"]:
            raise StageFailed("Model checks failed.")
        return report

    mesh = source
    if source.suffix.lower() in {".step", ".stp", ".iges", ".igs"}:
        mesh = work / "cad.obj"
        await stage("cad", lambda: asyncio.to_thread(convert, source, mesh))
        unit_mm = 1.0
    # Do not repair the scan before detecting holes and inward faces. The input
    # may be larger than the delivery budget but still has a hard ingestion cap.
    await stage("preflight", lambda: geometry(mesh, unit_mm, Budget(triangles=2_000_000, bytes=256_000_000)))
    blended = work / "blender.glb"
    await stage("blender", lambda: command(["blender", "-b", "--disable-autoexec", "-t", "2", "-P", str(HERE / "optimize.py"),
        "--", str(mesh), str(blended), str(unit_mm / 1000), str(budget.triangles)], work))
    current = blended
    for name, options in (("dedup", []), ("simplify", ["--ratio", "1", "--error", "0.001"]),
                          ("resize", ["--width", "1024", "--height", "1024"]),
                          ("meshopt", [])):
        target = work / (name + ".glb")
        await stage(name, lambda name=name, target=target, current=current, options=options:
                    command(["gltf-transform", name, str(current), str(target), *options], work))
        current = target
    packed = work / "packed.glb"
    await stage("gltfpack", lambda: command(["gltfpack", "-i", str(current), "-o", str(packed),
                                             "-cc", "-kn", "-km", "-ke", "-vp", "16"], work))
    textures = work / "textures.glb"
    await stage("ktx2", lambda: command(["gltf-transform", "uastc", str(packed), str(textures),
                                         "--level", "2", "--zstd", "18"], work))
    # Texture conversion decodes EXT_meshopt; explicitly restore it for delivery.
    final = work / "draft.glb"
    await stage("meshopt_final", lambda: command(["node", str(HERE / "glb.mjs"), "compress", str(textures), str(final)], work))
    decoded = work / "decoded.glb"
    async def final_check():
        await command(["node", str(HERE / "glb.mjs"), "decode", str(final), str(decoded)], work)
        return await geometry(decoded, 1000, budget, final.stat().st_size)
    report = await stage("model_check", final_check)
    await stage("validate", lambda: command(["node", str(HERE / "glb.mjs"), "validate", str(final),
                                             str(work / "validation.json")], work))
    report["checks"]["gltf_validator"] = True
    report["status"] = "draft"
    (work / "report.json").write_text(json.dumps(report, indent=2))
    return report

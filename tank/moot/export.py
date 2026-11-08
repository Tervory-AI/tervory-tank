"""Local-only recording/feedback export. No shell and no external media URLs."""
import html
import json
from pathlib import Path
import subprocess
from .contracts import MediaError


def align(local_file, output, *, offset_ms=0, root):
    base = Path(root).resolve(strict=True)
    source, target = (base / local_file).resolve(), (base / output).resolve()
    if any(not path.is_relative_to(base) or path == base for path in (source, target)):
        raise MediaError('invalid_recording_path')
    if source == target or not source.is_file() or abs(offset_ms) > 3600000:
        raise MediaError('invalid_alignment')
    # Input-side offset preserves genuine captured media; never invent word times.
    subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-n', '-protocol_whitelist', 'file,pipe',
        '-itsoffset', str(offset_ms / 1000), '-i', str(source), '-map', '0', '-c', 'copy', str(target)],
        check=True, capture_output=True, timeout=120)
    return target


def feedback_html(projection):
    # Only a caller-authorized projection may enter. No bench notes or holding are
    # read by this exporter; verified citation feedback stays with the legacy API.
    title = html.escape(projection['problem']['title'])
    turns = ''.join('<p>' + html.escape(f"{t['seat']}: {t['text']}") + '</p>' for t in projection['transcript'])
    return f'<!doctype html><meta charset="utf-8"><title>{title}</title><h1>{title}</h1>{turns}'

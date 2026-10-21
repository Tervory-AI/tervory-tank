"""Validate public training rows, archive in the owner's R2 bucket, then export HF."""
from __future__ import annotations

import argparse
import asyncio
from datetime import date
import io
import json
import os
from pathlib import Path

from r2_archive import PLATFORM_TENANT, Storage, archive_file
from train import validate_rows
from run import validate_name


async def export(room: str, source: Path, day: str) -> dict:
    date.fromisoformat(day)
    if room not in {'base', 'tiger', 'market_lab', 'radix', 'tisan', 'rig', 'zenas', 'ghost'}:
        raise ValueError('Unknown room')
    data = source.read_bytes()
    rows = [json.loads(line) for line in data.splitlines() if line]
    if not rows:
        raise ValueError('Snapshot is empty')
    validate_rows(rows)
    store = Storage(room)
    try:
        if any(row['region'] != store.region for row in rows):
            raise ValueError('Snapshot must belong to this region')
        # Freeze the validated bytes, so a concurrently replaced source cannot be exported.
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            frozen = Path(directory) / 'training.jsonl'
            frozen.write_bytes(data)
            archived = await archive_file(store, frozen, 'training', tenant_id=PLATFORM_TENANT,
                                          public=True, label=f'{day}.jsonl')
        from huggingface_hub import HfApi
        org = validate_name(os.environ['HF_ORG'])
        api = HfApi(token=os.environ['HF_TOKEN'])
        repo = f'{org}/tervory-public-{room}'
        info = await asyncio.to_thread(api.dataset_info, repo)
        if info.private is not True:
            raise ValueError('Dataset repository must already exist and be private')
        await asyncio.to_thread(api.upload_file, repo_id=repo, repo_type='dataset',
                                path_in_repo=f'snapshots/{store.region}/{day}.jsonl',
                                path_or_fileobj=io.BytesIO(data), parent_commit=info.sha)
        return archived
    finally:
        await store.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--room', required=True)
    parser.add_argument('--day', required=True)
    parser.add_argument('file')
    args = parser.parse_args()
    try:
        result = asyncio.run(export(args.room, Path(args.file), args.day))
        print(json.dumps({'bucket': result['bucket'], 'key': result['key']}))
    except Exception:
        raise SystemExit('Training snapshot export failed; check storage, dataset privacy and row provenance.') from None

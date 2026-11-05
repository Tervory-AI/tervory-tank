"""Explicit analysis double for fast API/storage tests, never used in the room."""
from functools import lru_cache
from pathlib import Path

from agents.video_shop.video_models import FRAME_SIZE, VISION_THRESHOLD, LocalModels


@lru_cache(maxsize=1)
def cpu_models(root):
    """Match the serving room: one loaded pair shared across test requests."""
    return LocalModels(Path(root))


class StubModels:
    def analyse(self, audio, frames, references):
        if audio is not None:
            assert audio.is_file() and audio.stat().st_size > 44
        matches = []
        for frame in frames:
            assert len(frame) == FRAME_SIZE * FRAME_SIZE * 3
            # This deliberately models a score, rather than duplicating CLIP.
            matches.append({sku: .99 for sku in references})
        return {'transcript': [{'start': 0, 'end': 4, 'text': 'This is a red cup.'}] if audio else [],
                'matches': matches,
                'receipt': {'provider_calls': 0, 'device': 'cpu', 'vision': 'test-double',
                            'vision_threshold': VISION_THRESHOLD, 'sample_seconds': 5}}

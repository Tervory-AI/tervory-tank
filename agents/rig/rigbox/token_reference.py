"""Tank's bundled, offline BPE reference; never a claim of provider billing."""
from functools import lru_cache
import hashlib
import json
import math
from pathlib import Path


@lru_cache(maxsize=1)
def encoding():
    import tiktoken
    from tiktoken.load import load_tiktoken_bpe
    path = Path(__file__).with_name('cl100k_base.tiktoken')
    digest = '223921b76ee99bde995b7ff738513eef100fb51d18c93597a113bcffe865b2a7'
    if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
        raise ValueError('The offline token reference failed its integrity check')
    ranks = load_tiktoken_bpe(str(path), expected_hash=digest)
    return tiktoken.Encoding(name='rig-cl100k', mergeable_ranks=ranks, special_tokens={},
        pat_str=r"'(?i:[sdmt]|ll|ve|re)|[^\r\n\p{L}\p{N}]?+\p{L}++|\p{N}{1,3}+| ?[^\s\p{L}\p{N}]++[\r\n]*+|\s++$|\s*[\r\n]|\s+(?!\S)|\s")


def tokens(value):
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, default=str)
    if len(text.encode()) > 2_000_000:
        raise ValueError('Reference input exceeds the counting budget')
    return len(encoding().encode_ordinary(text))


def input_tokens(messages):
    return math.ceil(tokens({'messages': messages}) * 1.2) + 32 * len(messages)

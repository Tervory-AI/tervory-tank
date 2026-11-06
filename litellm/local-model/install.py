"""Fetch immutable, checksum-verified CPU inference artifacts; no credentials."""
import hashlib
from pathlib import Path
import tarfile
import urllib.request

ARTIFACTS = {
    'large.gguf': ('https://huggingface.co/Qwen/Qwen3-4B-GGUF/resolve/bc640142c66e1fdd12af0bd68f40445458f3869b/Qwen3-4B-Q4_K_M.gguf',
                   '7485fe6f11af29433bc51cab58009521f205840f5b4ae3a32fa7f92e8534fdf5'),
    'llama.tar.gz': ('https://github.com/ggml-org/llama.cpp/releases/download/b12173/llama-b12173-bin-ubuntu-x64.tar.gz',
                    '9016289854f5a589029f964c7d5821f8e3482df7290ceaf4ae88abdfaf8e90bd'),
    'model.gguf': ('https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/resolve/91cad51170dc346986eccefdc2dd33a9da36ead9/qwen2.5-1.5b-instruct-q4_k_m.gguf',
                   '6a1a2eb6d15622bf3c96857206351ba97e1af16c30d7a74ee38970e434e9407e'),
}


def install(destination):
    root = Path(destination)
    root.mkdir(parents=True, exist_ok=True)
    for name, (url, expected) in ARTIFACTS.items():
        target = root / name
        digest = hashlib.sha256()
        with urllib.request.urlopen(url, timeout=120) as response, target.open('wb') as output:
            while chunk := response.read(1024 * 1024):
                digest.update(chunk)
                output.write(chunk)
        if digest.hexdigest() != expected:
            target.unlink()
            raise ValueError('Artifact checksum mismatch: ' + name)
    with tarfile.open(root / 'llama.tar.gz') as archive:
        archive.extractall(root, filter='data')
    (root / 'llama.tar.gz').unlink()


if __name__ == '__main__':
    import sys
    install(sys.argv[1])

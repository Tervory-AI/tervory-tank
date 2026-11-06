"""Fetch immutable, checksum-verified CPU inference artifacts; no credentials."""
import hashlib
from pathlib import Path
import tarfile
import urllib.request
from urllib.parse import urlsplit
import shutil

ARTIFACTS = {
    'large.gguf': ('https://huggingface.co/unsloth/Qwen3-4B-Instruct-2507-GGUF/resolve/a06e946bb6b655725eafa393f4a9745d460374c9/Qwen3-4B-Instruct-2507-Q4_K_M.gguf',
                   '3605803b982cb64aead44f6c1b2ae36e3acdb41d8e46c8a94c6533bc4c67e597'),
    'llama.tar.gz': ('https://github.com/ggml-org/llama.cpp/releases/download/b12173/llama-b12173-bin-ubuntu-x64.tar.gz',
                    '9016289854f5a589029f964c7d5821f8e3482df7290ceaf4ae88abdfaf8e90bd'),
    'model.gguf': ('https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/resolve/91cad51170dc346986eccefdc2dd33a9da36ead9/qwen2.5-1.5b-instruct-q4_k_m.gguf',
                   '6a1a2eb6d15622bf3c96857206351ba97e1af16c30d7a74ee38970e434e9407e'),
}


class HTTPSRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        address = urlsplit(newurl)
        trusted = ('github.com', 'githubusercontent.com', 'huggingface.co', 'hf.co')
        host = address.hostname or ''
        if (address.scheme != 'https' or address.username or address.port not in (None, 443)
                or not any(host == name or host.endswith('.' + name) for name in trusted)):
            raise ValueError('Artifact redirects must remain HTTPS')
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def extract_runtime(archive, root):
    """Copy regular bytes only; archive links never become filesystem links."""
    root = root.resolve()
    for member in archive.getmembers():
        target = (root / member.name).resolve()
        if not target.is_relative_to(root) or '..' in Path(member.name).parts:
            raise ValueError('Unsafe runtime archive path')
        if member.isdir():
            target.mkdir(parents=True, exist_ok=True)
        elif member.isfile() or member.issym() or member.islnk():
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.extractfile(member) as source, target.open('wb') as output:
                shutil.copyfileobj(source, output)
            target.chmod(0o755 if member.mode & 0o111 else 0o644)
        else:
            raise ValueError('Unsupported runtime archive entry')


def install(destination):
    root = Path(destination)
    root.mkdir(parents=True, exist_ok=True)
    downloader = urllib.request.build_opener(HTTPSRedirect())
    for name, (url, expected) in ARTIFACTS.items():
        target = root / name
        digest = hashlib.sha256()
        with downloader.open(url, timeout=120) as response, target.open('wb') as output:
            while chunk := response.read(1024 * 1024):
                digest.update(chunk)
                output.write(chunk)
        if digest.hexdigest() != expected:
            target.unlink()
            raise ValueError('Artifact checksum mismatch: ' + name)
    with tarfile.open(root / 'llama.tar.gz') as archive:
        extract_runtime(archive, root)
    (root / 'llama.tar.gz').unlink()


if __name__ == '__main__':
    import sys
    install(sys.argv[1])

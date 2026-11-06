"""Read the applied Skala sources named by the unchanged patch manifests."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCES = {}
for patch in ('finish.patch', 'gate4.patch', 'gate5.patch'):
    for line in (ROOT/'tank-patches/skala'/patch).read_text().splitlines():
        if line.startswith('+++ b/'):
            name = line[6:]
            if '..' in Path(name).parts or not name.startswith(('tank/', 'workspace/')):
                raise ValueError('Unsafe Skala source path')
            path = ROOT/name
            SOURCES[str(path)] = path.read_text()

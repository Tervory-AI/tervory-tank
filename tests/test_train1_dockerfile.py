"""Every local module imported by Tank must be present in its image."""
import ast
import shlex
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_tank_dockerfile_copies_every_main_local_import():
    tank = ROOT / "tank"
    tree = ast.parse((tank / "main.py").read_text())
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module.split(".")[0])
        elif isinstance(node, ast.Call) and node.args and isinstance(node.args[0], ast.Constant):
            if isinstance(node.func, ast.Name) and node.func.id == "__import__":
                imports.add(str(node.args[0].value).split(".")[0])
            elif isinstance(node.func, ast.Attribute) and node.func.attr == "import_module":
                imports.add(str(node.args[0].value).split(".")[0])
    required = {f"{name}.py" for name in imports if (tank / f"{name}.py").is_file()}
    copy = next(line for line in (tank / "Dockerfile").read_text().splitlines()
                if line.startswith("COPY ") and "*.py" in shlex.split(line))
    # COPY *.py copies every module in tank/, so the copied set is every .py file there.
    copied = {path.name for path in tank.glob("*.py")} if "*.py" in shlex.split(copy) else set()
    assert required <= copied, f"Local Tank imports missing from COPY: {sorted(required - copied)}"
    assert {"gold.py", "training.py"} <= copied

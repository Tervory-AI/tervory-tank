"""Cheap guard: a /v1/ route that takes tenant_id must mention it in every SQL string it runs.

This parses tank/main.py. It is not a proof that a query is correctly scoped.
"""
import ast
import pathlib

MAIN = pathlib.Path(__file__).resolve().parents[1] / "tank" / "main.py"
_SQL_METHODS = {"execute", "executemany"}


def _route_path(decorator: ast.AST) -> str | None:
    if not isinstance(decorator, ast.Call):
        return None
    func = decorator.func
    if not isinstance(func, ast.Attribute):
        return None
    if not isinstance(func.value, ast.Name) or func.value.id != "app":
        return None
    if func.attr not in {"get", "post", "put"}:
        return None
    if not decorator.args:
        return None
    path = decorator.args[0]
    if isinstance(path, ast.Constant) and isinstance(path.value, str):
        return path.value
    return None


def _takes_tenant_id(fn: ast.AST) -> bool:
    assert isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef))
    args = [*fn.args.posonlyargs, *fn.args.args, *fn.args.kwonlyargs]
    return any(arg.arg == "tenant_id" for arg in args)


def _string_constants(tree: ast.AST) -> dict[str, str]:
    found: dict[str, str] = {}
    for node in tree.body:  # type: ignore[attr-defined]
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if isinstance(target, ast.Name) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            found[target.id] = node.value.value
    return found


def _sql_text(node: ast.AST | None, constants: dict[str, str]) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        parts: list[str] = []
        for value in node.values:
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                parts.append(value.value)
            elif isinstance(value, ast.FormattedValue):
                piece = _sql_text(value.value, constants)
                if piece is None:
                    return None
                parts.append(piece)
            else:
                return None
        return "".join(parts)
    if isinstance(node, ast.Name):
        return constants.get(node.id)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left = _sql_text(node.left, constants)
        right = _sql_text(node.right, constants)
        if left is None or right is None:
            return None
        return left + right
    return None


def _is_sql_call(node: ast.AST) -> bool:
    if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
        return False
    name = node.func.attr
    if name not in _SQL_METHODS and not name.startswith("fetch"):
        return False
    receiver = node.func.value
    return isinstance(receiver, ast.Name) and receiver.id == "conn"


def _sql_arg(call: ast.Call) -> ast.AST | None:
    if call.args:
        return call.args[0]
    for keyword in call.keywords:
        if keyword.arg in {"query", "sql"}:
            return keyword.value
    return None


def test_v1_routes_with_tenant_id_scope_their_sql() -> None:
    tree = ast.parse(MAIN.read_text(encoding="utf-8"), filename=str(MAIN))
    constants = _string_constants(tree)
    guarded: list[str] = []
    problems: list[str] = []
    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        path = next((p for dec in node.decorator_list if (p := _route_path(dec)) and p.startswith("/v1/")), None)
        if path is None or not _takes_tenant_id(node):
            continue
        guarded.append(f"{node.name} {path}")
        saw_sql = False
        for child in ast.walk(node):
            if not _is_sql_call(child):
                continue
            assert isinstance(child, ast.Call)
            saw_sql = True
            text = _sql_text(_sql_arg(child), constants)
            if text is None:
                problems.append(f"{node.name}: SQL passed to conn.{child.func.attr} is not a readable string")  # type: ignore[union-attr]
            elif "tenant_id" not in text:
                problems.append(f"{node.name}: SQL missing tenant_id:\n{text.strip()[:240]}")
        if not saw_sql:
            problems.append(f"{node.name}: takes tenant_id but runs no SQL the guard can see")
    assert guarded, "expected at least one /v1/ route with a tenant_id parameter"
    assert not problems, "\n".join(problems)

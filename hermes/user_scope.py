"""Product-owned type declarations; request metadata cannot grant shared scope."""

# DECISION explicit kind allowlists, never a caller-provided scope flag or prefix.
TENANT_WIDE_KINDS: dict[str, frozenset[str]] = {
    "opli": frozenset({"opli.repo_map", "opli.convention"}),
    "trigger": frozenset(),
    "workspace": frozenset({"workspace.project"}),
    # Autumbra standing blocks are tenant-shared facts, never a personal row.
    "ghost": frozenset({"blocked_address"}),
    "tisan": frozenset({"heartbeat", "tisan.brand"}),
    **{agent: frozenset({"heartbeat"}) for agent in ("template", "base", "tiger", "market_lab", "zenas", "radix", "rig")},
    "market_lab": frozenset({"heartbeat", "warning_pattern"}),
    "rig": frozenset({"heartbeat", "rig.store_preference"}),
    "tank": frozenset(),
}
# Internal maintenance can inspect rows without impersonating an end user.
# HTTP routes always pass user_id explicitly, including None (shared rows only).
INTERNAL = object()


def wide_kinds(agent: str) -> list[str]:
    return sorted(TENANT_WIDE_KINDS.get(agent, ()))


def visible(n: int) -> str:
    """Parameters n and n+1: user and trusted product-wide kinds."""
    return (f"((jsonb_typeof(meta->'user_id') = 'string' AND meta->>'user_id' = ${n}::text)"
            f" OR (COALESCE(meta->>'user_id','') = '' AND kind = ANY(${n+1}::text[])))")


def write_meta(agent: str, kind: str, meta: dict, user_id: str | None = None) -> dict:
    value = dict(meta)
    owner = value.get("user_id")
    if user_id is not None:
        if owner is not None and owner != user_id:
            raise ValueError("Conflicting memory owner")
        owner = user_id
    if owner is not None:
        if not isinstance(owner, str) or not owner.strip() or len(owner) > 200:
            raise ValueError("Invalid memory user_id")
        value["user_id"] = owner
    elif kind not in wide_kinds(agent):
        raise ValueError("Personal memory requires meta.user_id")
    return value

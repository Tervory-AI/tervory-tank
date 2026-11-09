"""A fixture restart must not replace argument classes in the shared registry."""
from gates78.products.workspace_fixture import fresh_workspace_module


def test_workspace_restart_preserves_existing_registry(monkeypatch):
    import command
    import command_tools as registry
    from command_tools import workspace

    before = dict(command.ADAPTERS)
    for _ in range(2):
        restarted = fresh_workspace_module(monkeypatch)
        assert restarted is not workspace
        assert restarted.Chat is not workspace.Chat
        assert registry.build_adapters(vars(command)) == before
        assert command.ADAPTERS == before

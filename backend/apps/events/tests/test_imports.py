"""Tests for event services imports and basic functionality."""


class TestEventHandlerImports:
    """Test event_handler module imports."""

    def test_event_handler_function_exists(self):
        """event_handler function can be imported."""
        from apps.events.services.event_handler import event_handler

        assert callable(event_handler)

    def test_event_cooldown_active_exception_exists(self):
        """EventCooldownActive exception can be imported."""
        from apps.events.services.event_handler import EventCooldownActive

        assert issubclass(EventCooldownActive, Exception)

    def test_get_template_function_exists(self):
        """get_template function can be imported."""
        from apps.events.services.event_handler import get_template

        assert callable(get_template)


class TestActionsImports:
    """Test actions module imports."""

    def test_action_dispatch_function_exists(self):
        """action_dispatch function can be imported."""
        from apps.events.services.actions import action_dispatch

        assert callable(action_dispatch)

    def test_dispatch_msg_function_exists(self):
        """dispatch_msg function can be imported."""
        from apps.events.services.actions import dispatch_msg

        assert callable(dispatch_msg)

    def test_stop_machine_function_exists(self):
        """stop_machine function can be imported."""
        from apps.events.services.actions import stop_machine

        assert callable(stop_machine)


class TestActionsModuleStructure:
    """Test actions module has expected structure."""

    def test_action_dispatch_accepts_three_arguments(self):
        """action_dispatch function signature."""
        from apps.events.services.actions import action_dispatch
        import inspect

        sig = inspect.signature(action_dispatch)
        params = list(sig.parameters.keys())
        assert len(params) == 3
        assert "action_config" in params
        assert "rule" in params
        assert "aggregate" in params

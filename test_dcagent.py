"""
Simple functional self-test for dcagent.

This test verifies basic bot functionality without requiring a full Delta Chat environment.
"""


# Test 1: Verify module imports
def test_imports():
    """Check that required imports work."""
    from deltabot_cli import BotCli
    from deltachat2 import MsgData, events

    assert BotCli is not None
    assert MsgData is not None
    assert events is not None
    print("✓ Imports work correctly")


# Test 2: Verify DEFAULT_BOT_NAME constant
def test_default_bot_name():
    """Check that DEFAULT_BOT_NAME is set correctly."""
    from main import DEFAULT_BOT_NAME

    assert DEFAULT_BOT_NAME == "dcagent"
    print("✓ DEFAULT_BOT_NAME is correct")


# Test 3: Verify _dispatch routing
def test_dispatch_routing():
    """Test that _dispatch routes commands correctly."""

    from main import _dispatch

    # Mock the send_msg method
    class MockRpc:
        sent_messages = []

        def send_msg(self, accid, chat_id, msg):
            self.sent_messages.append((accid, chat_id, msg))

    class MockBot:
        rpc = MockRpc()

    class MockCli:
        _bot = MockBot()

    # Replace cli with mock
    import logging

    import main

    original_cli = main.cli
    main.cli = MockCli()

    try:
        # Test send command
        _dispatch({"cmd": "send", "chat_id": 12, "text": "test"}, 1, logging.getLogger("test"))
        assert len(main.cli._bot.rpc.sent_messages) == 1
        assert main.cli._bot.rpc.sent_messages[0] == (1, 12, main.cli._bot.rpc.sent_messages[0][2])
        print("✓ _dispatch routes send command correctly")
    finally:
        # Restore original cli
        main.cli = original_cli


def run_all_tests():
    """Run all tests."""
    print("=" * 50)
    print("Running dcagent self-tests")
    print("=" * 50)

    tests = [
        test_imports,
        test_default_bot_name,
        test_dispatch_routing,
    ]

    failed = 0
    for test in tests:
        try:
            test()
        except Exception as e:
            print(f"✗ {test.__name__} failed: {e}")
            failed += 1

    print("=" * 50)
    if failed == 0:
        print("All tests passed! ✓")
    else:
        print(f"{failed} test(s) failed")
    print("=" * 50)


if __name__ == "__main__":
    run_all_tests()

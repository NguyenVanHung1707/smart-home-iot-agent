from src.services.conversation import ConversationStore, PendingClarification


def test_sessions_are_isolated_and_expire_after_ttl():
    now = [0.0]
    store = ConversationStore(ttl_seconds=600, clock=lambda: now[0])
    store.add_turn("family-a", "bật đèn", "Bạn muốn phòng nào?")
    store.set_pending("family-a", PendingClarification("bật đèn", "device"))

    assert store.snapshot("family-a").pending is not None
    assert store.snapshot("family-b").messages == ()

    now[0] = 601.0

    assert store.snapshot("family-a").messages == ()
    assert store.snapshot("family-a").pending is None


def test_history_keeps_only_ten_turns():
    store = ConversationStore(max_turns=10)

    for index in range(12):
        store.add_turn("family", f"user-{index}", f"assistant-{index}")

    messages = store.snapshot("family").messages
    assert len(messages) == 20
    assert messages[0] == ("user", "user-2")
    assert messages[-1] == ("assistant", "assistant-11")


def test_conversation_clears_last_devices_when_mode_switches():
    store = ConversationStore()
    session_id = "session-mode-switch"

    store.set_last_devices(session_id, ("sim-light", "sim-tv"), mode="simulator")
    store.set_pending(session_id, PendingClarification("bật", "device"), mode="simulator")

    sim_snap = store.snapshot(session_id, mode="simulator")
    assert sim_snap.last_device_ids == ("sim-light", "sim-tv")
    assert sim_snap.pending is not None

    # Switch mode to "real"
    real_snap = store.snapshot(session_id, mode="real")
    assert real_snap.last_device_ids == ()
    assert real_snap.pending is None

    # Set new device in "real" mode
    store.set_last_devices(session_id, ("real-light",), mode="real")
    assert store.snapshot(session_id, mode="real").last_device_ids == ("real-light",)

    # Switch back to "simulator" mode
    sim_snap_again = store.snapshot(session_id, mode="simulator")
    assert sim_snap_again.last_device_ids == ()
    assert sim_snap_again.pending is None


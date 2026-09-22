from src.models.schemas import DeviceCommand
from src.services.approvals import ApprovalStore


def test_unlock_approval_can_be_approved_once():
    store = ApprovalStore()
    item = store.create("entry-lock", DeviceCommand(action="unlock"))

    assert store.decide(item.id, approved=True).status == "approved"
    assert store.decide(item.id, approved=True) is None


def test_approval_store_and_capability_mode():
    store = ApprovalStore()
    item_sim = store.create("entry-lock", DeviceCommand(action="unlock"))
    assert item_sim.mode == "simulator"
    cap_sim = store.approve(item_sim.id)
    assert cap_sim is not None
    assert cap_sim.mode == "simulator"

    item_real = store.create("entry-lock", DeviceCommand(action="unlock"), mode="real")
    assert item_real.mode == "real"
    cap_real = store.approve(item_real.id)
    assert cap_real is not None
    assert cap_real.mode == "real"

    issued = store.issue_capability("entry-lock", "unlock", mode="real")
    assert issued.mode == "real"


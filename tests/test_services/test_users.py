from src.services.users import UserStore, verify_password


def test_user_store_hashes_password_and_persists_public_user(tmp_path):
    store = UserStore(tmp_path / "store" / "users.json")

    created = store.create("Owner@Example.com", "owner-password", "Owner", "ADMIN")
    raw = store.get(created.id)

    assert created.email == "owner@example.com"
    assert raw["password_hash"] != "owner-password"
    assert verify_password("owner-password", raw["password_hash"])
    assert store.get_by_email("OWNER@example.com")["id"] == created.id

    reloaded = UserStore(tmp_path / "store" / "users.json")
    assert reloaded.get(created.id)["email"] == "owner@example.com"


def test_user_store_rejects_duplicate_email(tmp_path):
    store = UserStore(tmp_path / "store" / "users.json")
    store.create("member@example.com", "member-password", "Member", "MEMBER")

    try:
        store.create("MEMBER@example.com", "member-password", "Member 2", "MEMBER")
    except ValueError as exc:
        assert str(exc) == "email_exists"
    else:
        raise AssertionError("duplicate email should fail")


def test_user_store_bumps_token_version_for_security_updates(tmp_path):
    store = UserStore(tmp_path / "store" / "users.json")
    user = store.create("member@example.com", "member-password", "Member", "MEMBER")
    before = store.get(user.id)["token_version"]

    store.update(user.id, {"locked": True})

    after = store.get(user.id)
    assert after["locked"] is True
    assert after["token_version"] == before + 1

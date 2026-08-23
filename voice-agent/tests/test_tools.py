from assistant import tools


def test_every_tool_has_a_valid_schema():
    for schema in tools.schemas():
        assert schema["description"], f"{schema['name']} needs a description"
        assert schema["parameters"]["type"] == "object"
        properties = schema["parameters"]["properties"]
        for required in schema["parameters"]["required"]:
            assert required in properties, f"{schema['name']}: '{required}' missing from properties"


def test_unknown_tool_returns_error_instead_of_raising():
    assert tools.run("does_not_exist", {})["ok"] is False


def test_wrong_arguments_return_error_instead_of_raising():
    result = tools.run("create_booking", {"nonsense": 1})
    assert result["ok"] is False
    assert "Wrong arguments" in result["error"]


def test_create_then_list_then_cancel(temp_store):
    created = tools.run(
        "create_booking",
        {"business_name": "Mama Put Kitchen", "kind": "restaurant", "starts_at": "2026-09-04T19:00"},
    )
    assert created["ok"]
    booking_id = created["booking"]["id"]

    assert tools.run("list_bookings", {})["count"] == 1

    cancelled = tools.run("cancel_booking", {"booking_id": booking_id, "reason": "changed plans"})
    assert cancelled["booking"]["status"] == "cancelled"


def test_cancel_unknown_booking_is_reported(temp_store):
    assert tools.run("cancel_booking", {"booking_id": "bk_nope"})["ok"] is False


def test_check_availability_flags_a_clash(temp_store):
    tools.run(
        "create_booking",
        {"business_name": "A", "kind": "restaurant", "starts_at": "2026-09-04T19:00"},
    )
    assert tools.run("check_availability", {"starts_at": "2026-09-04T19:30"})["free"] is False
    assert tools.run("check_availability", {"starts_at": "2026-09-05T19:30"})["free"] is True


def test_double_booking_still_saves_but_warns(temp_store):
    args = {"business_name": "A", "kind": "restaurant", "starts_at": "2026-09-04T19:00"}
    tools.run("create_booking", args)
    second = tools.run("create_booking", args)
    assert second["ok"] and "Overlaps" in second["warning"]


def test_confirm_booking_sets_reference(temp_store):
    booking_id = tools.run(
        "create_booking",
        {"business_name": "A", "kind": "restaurant", "starts_at": "2026-09-04T19:00"},
    )["booking"]["id"]
    confirmed = tools.run("confirm_booking", {"booking_id": booking_id, "confirmation_ref": "XY9"})
    assert confirmed["booking"]["status"] == "confirmed"
    assert confirmed["booking"]["confirmation_ref"] == "XY9"


def test_find_business_hit_and_miss():
    assert tools.run("find_business", {"query": "sushi"})["ok"] is True
    assert tools.run("find_business", {"query": "submarine repair"})["ok"] is False


def test_calls_need_approval_before_dialling(temp_store, monkeypatch):
    from assistant.config import settings

    monkeypatch.setattr(settings, "require_call_approval", True)
    staged = tools.run(
        "place_phone_call",
        {"to_number": "+2348030000001", "business_name": "Mama Put", "objective": "Book 4 Friday"},
    )
    assert staged["status"] == "awaiting_approval"
    assert temp_store.calls.get(staged["call_id"])["status"] == "awaiting_approval"


def test_preferences_survive_a_round_trip(temp_store):
    tools.run("remember_preference", {"key": "diet", "value": "vegetarian"})
    assert tools.run("get_preferences", {})["preferences"]["diet"] == "vegetarian"

from assistant.store import Store


def test_booking_round_trip(temp_store):
    booking = temp_store.create_booking(
        business_name="Blue Fin Sushi", kind="restaurant", starts_at="2026-09-04T19:00", party_size=2
    )
    assert booking["status"] == "requested"
    assert temp_store.bookings.get(booking["id"])["business_name"] == "Blue Fin Sushi"


def test_overlapping_booking_is_a_conflict(temp_store):
    temp_store.create_booking(
        business_name="A", kind="restaurant", starts_at="2026-09-04T19:00", duration_minutes=90
    )
    assert len(temp_store.conflicts("2026-09-04T20:00", 60)) == 1
    assert temp_store.conflicts("2026-09-04T21:00", 60) == []


def test_cancelled_bookings_do_not_block_the_slot(temp_store):
    booking = temp_store.create_booking(
        business_name="A", kind="restaurant", starts_at="2026-09-04T19:00"
    )
    temp_store.bookings.update(booking["id"], status="cancelled")
    assert temp_store.conflicts("2026-09-04T19:00", 60) == []


def test_bad_datetime_never_crashes(temp_store):
    assert temp_store.conflicts("not-a-date") == []


def test_preferences_persist(tmp_path):
    Store(tmp_path).remember("diet", "vegetarian")
    assert Store(tmp_path).preferences()["diet"] == "vegetarian"


def test_corrupt_file_is_recovered_not_fatal(tmp_path):
    store = Store(tmp_path)
    store.bookings.path.write_text("{ this is not json")
    assert store.bookings.all() == []
    store.create_booking(business_name="A", kind="other", starts_at="2026-09-04T19:00")
    assert len(store.bookings.all()) == 1


def test_transcript_appends_in_order(temp_store):
    call = temp_store.stage_call(to_number="+100", business_name="A", objective="book")
    temp_store.append_turn(call["id"], "agent", "hello")
    temp_store.append_turn(call["id"], "human", "hi")
    assert [t["speaker"] for t in temp_store.calls.get(call["id"])["transcript"]] == ["agent", "human"]

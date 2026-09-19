from datetime import datetime, timedelta, timezone

import db


def setup_database(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "giveaway.db"))
    db.init()


def create_draw(draw_at=None):
    if draw_at is None:
        draw_at = datetime.now(timezone.utc) + timedelta(hours=1)
    return db.create_giveaway(123, "Giveaway", "Court time", draw_at)


def test_pick_winner_chooses_only_participants_with_screenshot(
    tmp_path, monkeypatch
):
    setup_database(tmp_path, monkeypatch)
    giveaway_id = create_draw()
    db.add_participant(giveaway_id, 1, "without_screenshot")
    db.add_participant(giveaway_id, 2, "verified")
    db.set_screenshot(2, "screenshot-2")

    winner = db.pick_winner(giveaway_id)

    assert winner is not None
    assert winner["user_id"] == 2
    assert winner["screenshot_file_id"] == "screenshot-2"


def test_pick_winner_returns_none_without_screenshots(tmp_path, monkeypatch):
    setup_database(tmp_path, monkeypatch)
    giveaway_id = create_draw()
    db.add_participant(giveaway_id, 1, "participant")

    assert db.pick_winner(giveaway_id) is None


def test_redraw_does_not_return_previous_winner(tmp_path, monkeypatch):
    setup_database(tmp_path, monkeypatch)
    giveaway_id = create_draw()
    db.add_participant(giveaway_id, 1, "first")
    db.set_screenshot(1, "screenshot-1")
    db.add_participant(giveaway_id, 2, "second")
    db.set_screenshot(2, "screenshot-2")

    first_winner = db.pick_winner(giveaway_id)
    new_winner = db.redraw(giveaway_id)

    assert first_winner is not None
    assert new_winner is not None
    assert new_winner["user_id"] != first_winner["user_id"]


def test_due_giveaways_excludes_drawn_giveaways(tmp_path, monkeypatch):
    setup_database(tmp_path, monkeypatch)
    now = datetime.now(timezone.utc)
    drawn_id = create_draw(now - timedelta(minutes=2))
    due_id = create_draw(now - timedelta(minutes=1))
    db.pick_winner(drawn_id)

    due_ids = [giveaway["id"] for giveaway in db.due_giveaways(now)]

    assert due_ids == [due_id]

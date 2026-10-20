import database


def test_feedback_round_trip(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "feedback.db")
    feedback_id = database.save_feedback(123, "tester", "Корисний звіт")
    items = database.get_recent_feedback()
    assert feedback_id == 1
    assert items[0]["telegram_user_id"] == 123
    assert items[0]["telegram_username"] == "tester"
    assert items[0]["text"] == "Корисний звіт"

def test_rating_upsert_and_stats(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "ratings.db")
    database.save_rating(1, "natal", 6)
    database.save_rating(1, "natal", 9)  # re-vote replaces
    database.save_rating(2, "natal", 8)
    database.save_rating(3, "year", 5)
    stats = database.get_rating_stats()
    assert stats["total"]["votes"] == 3
    assert stats["total"]["high"] == 2
    natal = next(r for r in stats["products"] if r["product"] == "natal")
    assert natal["votes"] == 2 and natal["avg_score"] == 8.5


def test_rating_rejects_out_of_range(tmp_path, monkeypatch):
    import pytest
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "ratings.db")
    with pytest.raises(ValueError):
        database.save_rating(1, "natal", 11)


def test_delete_user_removes_ratings(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "ratings.db")
    database.init_db()
    database.save_rating(7, "natal", 9)
    database.delete_user_data(7)
    assert database.get_rating_stats()["total"]["votes"] == 0

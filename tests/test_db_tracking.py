import sqlite3


def save(db, item_id=1, query_id=1, price=45.0, in_range=False, title="Wukong"):
    db.save_tracked_item(
        id=item_id,
        title=title,
        query_id=query_id,
        price=price,
        timestamp=1000,
        photo_url="https://img/1.webp",
        currency="EUR",
        in_range=in_range,
    )


def rows(db):
    conn = sqlite3.connect(db.DB_PATH)
    try:
        return conn.execute(
            "SELECT item, query_id, price, in_range FROM items ORDER BY query_id"
        ).fetchall()
    finally:
        conn.close()


def test_migration_bumps_version(fresh_db):
    assert fresh_db.get_parameter("version") == "1.0.5.5"


def test_migration_raises_items_per_query_to_api_maximum(fresh_db):
    assert fresh_db.get_parameter("items_per_query") == "96"


def test_unseen_item_has_no_tracking_record(fresh_db):
    fresh_db.add_query_to_db("https://www.vinted.it/catalog?search_text=wukong")
    assert fresh_db.get_tracked_item(1, 1) is None


def test_saved_item_is_returned_with_price_and_range_flag(fresh_db):
    fresh_db.add_query_to_db("https://www.vinted.it/catalog?search_text=wukong")
    save(fresh_db, price=45.0, in_range=False)
    assert fresh_db.get_tracked_item(1, 1) == {"price": 45.0, "in_range": False}


def test_saving_again_updates_price_without_duplicating(fresh_db):
    fresh_db.add_query_to_db("https://www.vinted.it/catalog?search_text=wukong")
    save(fresh_db, price=45.0, in_range=False)
    save(fresh_db, price=28.0, in_range=True)
    assert rows(fresh_db) == [(1, 1, 28.0, 1)]


def test_same_item_is_tracked_separately_per_query(fresh_db):
    fresh_db.add_query_to_db("https://www.vinted.it/catalog?search_text=wukong")
    fresh_db.add_query_to_db("https://www.vinted.it/catalog?search_text=black+myth")
    save(fresh_db, query_id=1, price=45.0, in_range=False)
    save(fresh_db, query_id=2, price=45.0, in_range=True)
    assert rows(fresh_db) == [(1, 1, 45.0, 0), (1, 2, 45.0, 1)]


def test_saving_marks_the_query_as_having_run(fresh_db):
    fresh_db.add_query_to_db("https://www.vinted.it/catalog?search_text=wukong")
    assert fresh_db.get_last_timestamp(1) is None
    save(fresh_db)
    assert fresh_db.get_last_timestamp(1) == 1000

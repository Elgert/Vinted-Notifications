import queue

import pytest

from pyVintedVN.items.item import Item

QUERY = (
    "https://www.vinted.it/catalog?search_text=wukong&catalog%5B%5D=3026"
    "&order=newest_first&price_from=20&price_to=30"
)


def item(item_id, price, title="Black Myth Wukong PS5"):
    return Item(
        {
            "id": item_id,
            "title": title,
            "price": {"amount": str(price), "currency_code": "EUR"},
            "photo": {"url": f"https://img/{item_id}.webp"},
            "url": f"/items/{item_id}-wukong",
            "item_box": {"first_line": title, "second_line": "Ottime"},
            "user": {"id": 7},
        },
        "www.vinted.it",
    )


@pytest.fixture
def core(fresh_db):
    import core

    fresh_db.add_query_to_db(QUERY)
    return core


def run(core, items):
    """Push one scrape for query 1 through clear_item_queue and return the messages."""
    items_queue, new_items_queue = queue.Queue(), queue.Queue()
    items_queue.put((items, 1, (20.0, 30.0)))
    core.clear_item_queue(items_queue, new_items_queue)
    messages = []
    while not new_items_queue.empty():
        messages.append(new_items_queue.get())
    return messages


def test_first_run_records_items_without_notifying(core, fresh_db):
    assert run(core, [item(1, 25), item(2, 45)]) == []
    assert fresh_db.get_tracked_item(1, 1) == {"price": 25.0, "in_range": True}
    assert fresh_db.get_tracked_item(2, 1) == {"price": 45.0, "in_range": False}


def test_new_item_in_range_notifies(core):
    run(core, [item(1, 45)])
    messages = run(core, [item(2, 25), item(1, 45)])
    assert [m[1] for m in messages] == ["https://www.vinted.it/items/2-wukong"]


def test_new_item_out_of_range_is_silent(core):
    run(core, [item(1, 45)])
    assert run(core, [item(2, 31), item(1, 45)]) == []


def test_known_item_dropping_into_range_notifies_with_old_and_new_price(core):
    run(core, [item(1, 45)])
    messages = run(core, [item(1, 28)])
    assert len(messages) == 1
    assert messages[0][0].startswith("📉 45.00 → 28.00 EUR\n")
    assert messages[0][1] == "https://www.vinted.it/items/1-wukong"


def test_known_item_staying_in_range_is_not_announced_twice(core):
    run(core, [item(1, 45)])
    run(core, [item(1, 28)])
    assert run(core, [item(1, 25)]) == []


def test_banned_words_are_skipped(core, fresh_db):
    fresh_db.set_parameter("banwords", "steelbook")
    run(core, [item(1, 45)])
    assert run(core, [item(2, 25, title="Wukong steelbook only")]) == []
    assert fresh_db.get_tracked_item(2, 1) is None


def test_seller_outside_allowlist_is_tracked_but_not_announced(core, fresh_db, monkeypatch):
    fresh_db.add_to_allowlist("IT")
    monkeypatch.setattr(core, "get_user_country", lambda profile_id: "FR")
    run(core, [item(1, 45)])
    assert run(core, [item(2, 25)]) == []
    assert fresh_db.get_tracked_item(2, 1) == {"price": 25.0, "in_range": True}


def test_notifications_are_capped_per_run(core):
    run(core, [item(1, 45)])
    fresh = [item(i, 25) for i in range(100, 100 + core.MAX_NOTIFICATIONS_PER_RUN + 5)]
    assert len(run(core, fresh)) == core.MAX_NOTIFICATIONS_PER_RUN

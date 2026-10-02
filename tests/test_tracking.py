import pytest

import tracking


class TestTitleMatches:
    def test_every_search_word_must_appear(self):
        assert tracking.title_matches("black myth wukong", "Black Myth: Wukong PS5")

    def test_missing_word_rejects(self):
        assert not tracking.title_matches("black myth wukong", "Black Myth PS5")

    def test_unrelated_filler_rejects(self):
        assert not tracking.title_matches("wukong", "Visions of Mana PS5 (Japanese Import)")

    def test_case_accents_and_punctuation_are_ignored(self):
        assert tracking.title_matches("pokemon epee", "POKÉMON Épée - Switch!")

    def test_words_match_whole_not_as_substrings(self):
        assert not tracking.title_matches("mana", "Mandragora PS5")

    def test_empty_search_text_matches_everything(self):
        assert tracking.title_matches("", "Anything at all")


class TestSearchText:
    def test_reads_search_text_from_url(self):
        url = "https://www.vinted.it/catalog?search_text=black+myth+wukong&order=newest_first"
        assert tracking.search_text(url) == "black myth wukong"

    def test_missing_search_text_is_empty(self):
        assert tracking.search_text("https://www.vinted.it/catalog?catalog%5B%5D=3026") == ""


class TestPriceRange:
    def test_reads_both_bounds(self):
        url = "https://www.vinted.it/catalog?search_text=x&price_from=20&price_to=30"
        assert tracking.price_range(url) == (20.0, 30.0)

    def test_missing_bounds_are_none(self):
        assert tracking.price_range("https://www.vinted.it/catalog?search_text=x") == (None, None)

    def test_only_upper_bound(self):
        assert tracking.price_range("https://www.vinted.it/catalog?price_to=45.5") == (None, 45.5)


class TestStripPriceParams:
    def test_removes_price_and_currency_but_keeps_other_filters(self):
        url = (
            "https://www.vinted.it/catalog?search_text=wukong&catalog%5B%5D=3026"
            "&order=newest_first&price_to=30&currency=EUR&price_from=20"
        )
        assert tracking.strip_price_params(url) == (
            "https://www.vinted.it/catalog?search_text=wukong&catalog%5B%5D=3026"
            "&order=newest_first"
        )


class TestInRange:
    @pytest.mark.parametrize(
        "price, low, high, expected",
        [
            (25, 20, 30, True),
            (20, 20, 30, True),
            (30, 20, 30, True),
            (31, 20, 30, False),
            (19, 20, 30, False),
            (500, None, None, True),
            (5, None, 30, True),
            (5, 10, None, False),
        ],
    )
    def test_bounds_are_inclusive_and_optional(self, price, low, high, expected):
        assert tracking.in_range(price, low, high) is expected


class TestDecide:
    def test_unseen_item_in_range_notifies(self):
        assert tracking.decide(None, 25, 20, 30) == ("new", True)

    def test_unseen_item_out_of_range_is_tracked_silently(self):
        assert tracking.decide(None, 45, 20, 30) == (None, False)

    def test_known_item_dropping_into_range_notifies(self):
        previous = {"price": 45.0, "in_range": False}
        assert tracking.decide(previous, 28, 20, 30) == ("drop", True)

    def test_known_item_entering_a_widened_range_at_same_price_is_new(self):
        previous = {"price": 45.0, "in_range": False}
        assert tracking.decide(previous, 45, 20, 50) == ("new", True)

    def test_known_item_staying_in_range_is_silent(self):
        previous = {"price": 29.0, "in_range": True}
        assert tracking.decide(previous, 25, 20, 30) == (None, True)

    def test_known_item_leaving_range_is_silent(self):
        previous = {"price": 25.0, "in_range": True}
        assert tracking.decide(previous, 40, 20, 30) == (None, False)

    def test_known_item_out_of_range_changing_price_is_silent(self):
        previous = {"price": 50.0, "in_range": False}
        assert tracking.decide(previous, 45, 20, 30) == (None, False)

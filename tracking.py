"""
Matching and price-tracking rules for scraped items.

Vinted pads a search with loosely related listings whenever the exact search comes
up empty, and that padding gets much worse once a price filter is applied. So the
price range is kept out of the API call and enforced here instead, alongside a
strict title match. Knowing every matching listing's price is also what makes it
possible to notice a listing whose price drops into range.
"""

import re
import unicodedata
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

PRICE_PARAMS = ("price_from", "price_to", "currency")


def _words(text):
    """Lowercase, strip accents and split on anything that is not a letter or digit."""
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(c for c in text if not unicodedata.combining(c)).lower()
    return re.findall(r"[a-z0-9]+", text)


def title_matches(search_text, title):
    """True when every word of the search text appears as a whole word in the title."""
    title_words = set(_words(title))
    return all(word in title_words for word in _words(search_text))


def search_text(url):
    """The search_text of a Vinted catalog URL, or an empty string."""
    return " ".join(v for k, v in parse_qsl(urlparse(url).query) if k == "search_text")


def price_range(url):
    """(price_from, price_to) of a Vinted catalog URL, each a float or None."""
    params = dict(parse_qsl(urlparse(url).query))

    def bound(key):
        try:
            return float(params[key])
        except (KeyError, ValueError):
            return None

    return bound("price_from"), bound("price_to")


def strip_price_params(url):
    """The URL without its price filters, which are applied locally instead."""
    parsed = urlparse(url)
    query = [(k, v) for k, v in parse_qsl(parsed.query) if k not in PRICE_PARAMS]
    return urlunparse(parsed._replace(query=urlencode(query)))


def in_range(price, low, high):
    """Inclusive range check where a missing bound means unbounded."""
    price = float(price)
    return (low is None or price >= low) and (high is None or price <= high)


def decide(previous, price, low, high):
    """
    Work out whether an item deserves a notification.

    Args:
        previous (dict | None): {"price", "in_range"} from the last time this query
            saw the item, or None if it never has.
        price: The item's current price.
        low, high: The query's price range.

    Returns:
        tuple: (reason, now_in_range) where reason is "new" for an unseen item in
        range or a known one a widened range now covers, "drop" for a known item
        whose price fell into range, else None.
    """
    now_in_range = in_range(price, low, high)
    if previous is None:
        return ("new" if now_in_range else None), now_in_range
    if now_in_range and not previous["in_range"]:
        # Same price but now in range means the query's range was edited, not
        # that the price dropped.
        return ("drop" if float(price) < previous["price"] else "new"), True
    return None, now_in_range

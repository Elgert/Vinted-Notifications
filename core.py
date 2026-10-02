import db
import requests
import tracking
from pyVintedVN import Vinted, requester
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
from logger import get_logger

# Get logger for this module
logger = get_logger(__name__)

# Vinted stopped publishing listing times in September 2026, so "is this item new?"
# is answered purely by "have we recorded its id before?". That makes a wiped or
# freshly seeded database the only real flood risk, and this caps the blast radius.
MAX_NOTIFICATIONS_PER_RUN = 10


def process_query(query, name=None):
    """
    Process a Vinted query URL by:
    1. Checking if the URL is a brand URL and converting it to standard format if needed
    2. Parsing the URL and extracting query parameters
    3. Ensuring the order flag is set to "newest_first"
    4. Removing time and search_id parameters
    5. Rebuilding the query string and URL
    6. Checking if the query already exists in the database
    7. Adding the query to the database if it doesn't exist

    Args:
        query (str): The Vinted query URL
        name (str, optional): A name for the query. If provided, it will be used as the query name.

    Returns:
        tuple: (message, is_new_query)
            - message (str): Status message
            - is_new_query (bool): True if query was added, False if it already existed
    """
    # Check if the URL is a brand URL (format: url/brand/id-name)
    parsed_url = urlparse(query)
    path_parts = parsed_url.path.strip("/").split("/")

    if len(path_parts) >= 2 and path_parts[0] == "brand":
        # Extract the brand ID from the format "id-name"
        brand_id_with_name = path_parts[1]
        brand_id = brand_id_with_name.split("-")[0]

        # Create a new URL with the standard format
        new_path = "/catalog"
        new_query_params = {"brand_ids[]": [brand_id]}
        new_query_string = urlencode(new_query_params, doseq=True)

        # Rebuild the URL
        query = urlunparse(
            (parsed_url.scheme, parsed_url.netloc, new_path, "", new_query_string, "")
        )
        logger.info(f"Converted brand URL to standard format: {query}")

        # Parse the URL and extract the query parameters
        parsed_url = urlparse(query)

    query_params = parse_qs(parsed_url.query)

    # Ensure the order flag is set to newest_first
    query_params["order"] = ["newest_first"]
    # Remove time and search_id if provided
    query_params.pop("time", None)
    query_params.pop("search_id", None)
    query_params.pop("disabled_personalization", None)
    query_params.pop("page", None)

    # Rebuild the query string and the entire URL
    new_query = urlencode(query_params, doseq=True)
    processed_query = urlunparse(
        (
            parsed_url.scheme,
            parsed_url.netloc,
            parsed_url.path,
            parsed_url.params,
            new_query,
            parsed_url.fragment,
        )
    )

    # Some queries are made with filters only, so we need to check if the search_text is present
    if db.is_query_in_db(processed_query) is True:
        return "Query already exists.", False
    else:
        # add the query to the db
        db.add_query_to_db(processed_query, name)
        return "Query added.", True


def get_formatted_query_list():
    """
    Get a formatted list of all queries in the database.

    Returns:
        str: A formatted string with all queries, numbered
    """
    all_queries = db.get_queries()
    queries_keywords = []
    for query in all_queries:
        parsed_url = urlparse(query[1])
        query_params = parse_qs(parsed_url.query)

        # Get the name or Extract the value of 'search_text'
        query_name = (
            query[3]
            if query[3] is not None
            else query_params.get("search_text", [None])[0]
        )

        if query_name[0] is None:
            # Use query text instead of the whole query object
            queries_keywords.append([query[1]])
        else:
            queries_keywords.append(query_name)

    query_list = ("\n").join(
        [str(i + 1) + ". " + j for i, j in enumerate(queries_keywords)]
    )
    return query_list


def process_remove_query(number):
    """
    Process the removal of a query from the database.

    Args:
        number (str): The number of the query to remove or "all" to remove all queries

    Returns:
        tuple: (message, success)
            - message (str): Status message
            - success (bool): True if query was removed successfully
    """
    if number == "all":
        db.remove_all_queries_from_db()
        return "All queries removed.", True

    # Check if number is a valid digit
    if number.isdigit():
        # Remove the query from the database
        db.remove_query_from_db(number)
        return "Query removed.", True
    else:
        return "Invalid number.", False


def process_update_query(query_id, query, name):
    """
    Process the update of a query in the database.

    Args:
        query_id (int): The ID of the query to update
        query (str): The new Vinted query URL
        name (str, optional): A new name for the query. If provided, it will be used as the query name.

    Returns:
        tuple: (message, success)
            - message (str): Status message
            - success (bool): True if query was updated successfully
    """
    # Parse the URL and extract the query parameters
    parsed_url = urlparse(query)
    query_params = parse_qs(parsed_url.query)

    # Ensure the order flag is set to newest_first
    query_params["order"] = ["newest_first"]
    # Remove time and search_id if provided
    query_params.pop("time", None)
    query_params.pop("search_id", None)
    query_params.pop("disabled_personalization", None)
    query_params.pop("page", None)

    # Rebuild the query string and the entire URL
    new_query = urlencode(query_params, doseq=True)
    processed_query = urlunparse(
        (
            parsed_url.scheme,
            parsed_url.netloc,
            parsed_url.path,
            parsed_url.params,
            new_query,
            parsed_url.fragment,
        )
    )

    # Update the query in the database
    if db.update_query_in_db(query_id, processed_query, name):
        return "Query updated.", True
    else:
        return "Failed to update query.", False


def process_add_country(country):
    """
    Process the addition of a country to the allowlist.

    Args:
        country (str): The country code to add

    Returns:
        tuple: (message, country_list)
            - message (str): Status message
            - country_list (list): Current list of allowed countries
    """
    # Format the country code (remove spaces)
    country = country.replace(" ", "")
    country_list = db.get_allowlist()

    # Validate the country code (check if it's 2 characters long)
    if len(country) != 2:
        return "Invalid country code", country_list

    # Check if the country is already in the allowlist
    # If country_list is 0, it means the allowlist is empty
    if country_list != 0 and country.upper() in country_list:
        return f'Country "{country.upper()}" already in allowlist.', country_list

    # Add the country to the allowlist
    db.add_to_allowlist(country.upper())
    return "Country added.", db.get_allowlist()


def process_remove_country(country):
    """
    Process the removal of a country from the allowlist.

    Args:
        country (str): The country code to remove

    Returns:
        tuple: (message, country_list)
            - message (str): Status message
            - country_list (list): Current list of allowed countries
    """
    # Format the country code (remove spaces)
    country = country.replace(" ", "")

    # Validate the country code (check if it's 2 characters long)
    if len(country) != 2:
        return "Invalid country code", db.get_allowlist()

    # Remove the country from the allowlist
    db.remove_from_allowlist(country.upper())
    return "Country removed.", db.get_allowlist()


def get_user_country(profile_id):
    """
    Get the country code for a Vinted user.

    Makes an API request to retrieve the user's country code.
    Handles rate limiting by trying an alternative endpoint.

    Args:
        profile_id (str): The Vinted user's profile ID

    Returns:
        str: The user's country code (2-letter ISO code) or "XX" if it can't be determined
    """
    # Users are shared between all Vinted platforms, so we can use whatever locale we want
    url = f"https://www.vinted.fr/api/v2/users/{profile_id}?localize=false"
    response = requester.get(url)
    # That's a LOT of requests, so if we get a 429 we wait a bit before retrying once
    if response.status_code == 429:
        # In case of rate limit, we're switching the endpoint. This one is slower, but it doesn't RL as soon.
        # We're limiting the items per page to 1 to grab as little data as possible
        url = f"https://www.vinted.fr/api/v2/users/{profile_id}/items?page=1&per_page=1"
        response = requester.get(url)
        try:
            user_country = response.json()["items"][0]["user"]["country_iso_code"]
        except KeyError:
            logger.warning(
                "Couldn't get the country due to too many requests. Returning default value."
            )
            user_country = "XX"
    else:
        user_country = response.json()["user"]["country_iso_code"]
    return user_country


def process_items(queue):
    """
    Process all queries from the database, search for items, and put them in the queue.
    Uses the global items_queue by default, but can accept a custom queue for backward compatibility.

    The price filter is left out of the API call: with one applied, Vinted pads an
    empty search with unrelated listings, and the price of a listing outside the
    range is exactly what is needed to notice it dropping into range later. Both
    the title match and the price range are enforced locally instead.

    Args:
        queue (Queue, optional): The queue to put the items in. Defaults to the global items_queue.

    Returns:
        None
    """

    all_queries = db.get_queries()

    # Initialize Vinted
    vinted = Vinted()

    # Get the number of items per query from the database
    items_per_query = int(db.get_parameter("items_per_query"))

    # for each keyword we parse data
    for query in all_queries:
        url = query[1]
        all_items = vinted.items.search(
            tracking.strip_price_params(url), nbr_items=items_per_query
        )
        text = tracking.search_text(url)
        data = [item for item in all_items if tracking.title_matches(text, item.title)]
        queue.put((data, query[0], tracking.price_range(url)))
        logger.info(
            f"Scraped {len(all_items)} items, {len(data)} matching the title, for query: {url}"
        )


def clear_item_queue(items_queue, new_items_queue):
    """
    Process items from the items_queue.
    This function is scheduled to run frequently.

    Every matching item is recorded per query with its current price. An item is
    announced when it is first seen inside the query's price range, or when a
    price change moves an already known item into it.
    """
    if not items_queue.empty():
        data, query_id, (price_from, price_to) = items_queue.get()
        banwords_str = db.get_parameter("banwords")

        # Read this once, before the loop: saving the first item below marks the
        # query as having run, which would cut a first-run priming pass short.
        is_first_run = db.get_last_timestamp(query_id) is None
        if is_first_run:
            logger.info(
                f"First run for query {query_id}: recording {len(data)} item(s) "
                f"without notifying, so the existing catalogue is not replayed."
            )

        to_notify = []
        for item in reversed(data):
            # Check if the item title contains any banwords
            if banwords_str and contains_banwords(item.title, banwords_str):
                continue

            previous = db.get_tracked_item(item.id, query_id)
            reason, now_in_range = tracking.decide(
                previous, item.price, price_from, price_to
            )

            # Only look the seller up for items we would otherwise announce: it
            # costs a request per item.
            allowlist = db.get_allowlist()
            if (
                reason
                and allowlist != 0
                and get_user_country(item.raw_data["user"]["id"]) not in allowlist + ["XX"]
            ):
                reason = None

            # Recording the price is what lets a later drop into range be noticed,
            # so every item is saved whether or not it ends up being announced.
            db.save_tracked_item(
                id=item.id,
                title=item.title,
                query_id=query_id,
                price=item.price,
                timestamp=item.raw_timestamp,
                photo_url=item.photo,
                currency=item.currency,
                in_range=now_in_range,
            )
            if reason:
                to_notify.append((item, reason, previous))

        if is_first_run:
            return

        # data arrives newest first and is walked in reverse, so to_notify runs
        # oldest to newest. Trim from the front: a backlog is worth dropping, the
        # listings that just appeared are not.
        if len(to_notify) > MAX_NOTIFICATIONS_PER_RUN:
            logger.warning(
                f"{len(to_notify)} items to announce for query {query_id}; notifying the "
                f"{MAX_NOTIFICATIONS_PER_RUN} most recent and recording the rest silently."
            )
            to_notify = to_notify[-MAX_NOTIFICATIONS_PER_RUN:]

        message_template = db.get_parameter("message_template")
        for item, reason, previous in to_notify:
            # We create the message
            content = message_template.format(
                title=item.title,
                price=str(item.price) + " " + item.currency,
                brand=item.brand_title,
                image=None if item.photo is None else item.photo,
            )
            if reason == "drop":
                content = (
                    f"📉 {previous['price']:.2f} → {float(item.price):.2f} {item.currency}\n"
                    + content
                )
            # add the item to the queue
            new_items_queue.put((content, item.url, "Open Vinted", None, None))
            # new_items_queue.put((content, item.url, "Open Vinted", item.buy_url, "Open buy page"))


def contains_banwords(title, banwords_str):
    """
    Check if a title contains any banwords.

    Args:
        title (str): The title to check
        banwords_str (str): List of banwords separated by 3 pipe character
    Returns:
        bool: True if the title contains any banwords, False otherwise
    """

    # Split the banwords string into a list using pipe as delimiter
    banwords = [
        word.strip().lower() for word in banwords_str.split("|||") if word.strip()
    ]

    # If the list is empty, return False
    if not banwords:
        return False

    # Check if any banword is in the title (case-insensitive)
    title_lower = title.lower()
    for word in banwords:
        if word in title_lower:
            return True

    return False


def check_version():
    """
    Check if the application is up to date
    """
    try:
        # Get URL from the database
        github_url = db.get_parameter("github_url")
        # Get version from the database
        ver = db.get_parameter("version")
        # Get latest version from the repository
        url = f"{github_url}/releases/latest"
        response = requests.get(url)

        if response.status_code == 200:
            latest_version = response.url.split("/")[-1]
            is_up_to_date = ver == latest_version
            return is_up_to_date, ver, latest_version, github_url
        else:
            # If we can't check, assume it's up to date
            return True, ver, ver, github_url
    except Exception as e:
        logger.error(f"Error checking for new version: {str(e)}", exc_info=True)
        # If we can't check, assume it's up to date
        return True, ver, ver, github_url

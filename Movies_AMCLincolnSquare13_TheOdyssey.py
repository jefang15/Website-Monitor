from playwright.sync_api import sync_playwright
from datetime import datetime
import time
import re
import smtplib
from email.message import EmailMessage


##################################################################################################################################
""" Overview """
##################################################################################################################################

"""
AMC Lincoln Square Seat Monitor

Monitors one or more AMC showtimes and alerts whenever there are newly available seats.

Features:
- Checks each configured showtime at a fixed interval.
- Detects only seats that became available since the previous check.
- Separates adjacent seat pairs from individual seats.
- Sends Gmail notifications when new seats appear.
- Automatically retries after temporary network failures.
- Runs headlessly using Playwright.
"""


##################################################################################################################################
""" Parameters """
##################################################################################################################################


EMAIL_FROM = "jeffreyfang035@gmail.com"
EMAIL_TO = "jeffreyfang035@gmail.com"
EMAIL_PASSWORD = "vfzh guaf imfp omey"
EMAIL_SUBJECT = "🎟 AMC Lincoln Square 13 - The Odyssey"

CHECK_INTERVAL_SECONDS = 30

MAX_RETRIES = 5
# RATE_LIMIT_SLEEP_SECONDS = 86400  # 24 hours
RATE_LIMIT_SLEEP_SECONDS = 28800  # 8 hours
RETRY_DELAY_SECONDS = 30


SHOWTIMES = [

    # Fri July 17, 2026
    # {
    #     "name": "Fri, Jul 17, 2026 11:00 PM",
    #     "url": "https://www.amctheatres.com/showtimes/143822253/seats"
    # },

    # Sat July 18, 2026
    # {
    #     "name": "Sat, Jul 18 7:00 AM",
    #     "url": "https://www.amctheatres.com/showtimes/144060333/seats"
    # },
    {
        "name": "Sat, Jul 18 @ 11:00 AM",
        "url": "https://www.amctheatres.com/showtimes/143822251/seats"
    },
    {
        "name": "Sat, Jul 18 @ 3:00 PM",
        "url": "https://www.amctheatres.com/showtimes/143822252/seats"
    },
    {
        "name": "Sat, Jul 18 @ 7:00 PM (EVENT)",
        "url": "https://www.amctheatres.com/showtimes/134717193/seats"
    },
    # {
    #     "name": "Sat, Jul 18 @ 11:00 PM",
    #     "url": "https://www.amctheatres.com/showtimes/143822250/seats"
    # },

    # Sun July 19, 2026
    {
        "name": "Sun, Jul 19 @ 7:00 AM",
        "url": "https://www.amctheatres.com/showtimes/144062400/seats"
    }
    # {
    #     "name": "Sun, Jul 19 @ 11:00 AM",
    #     "url": "https://www.amctheatres.com/showtimes/143822248/seats"
    # }

    # # Fri August 7, 2026
    # {
    #     "name": "Fri, Aug 7 @ 2:00 PM",
    #     "url": "https://www.amctheatres.com/showtimes/144696889/seats"
    # },
    # {
    #     "name": "Fri, Aug 7 @ 6:00 PM",
    #     "url": "https://www.amctheatres.com/showtimes/144696890/seats"
    # },
    #
    # # Sat August 8, 2026
    # {
    #     "name": "Sat, Aug 8 @ 10:00 AM",
    #     "url": "https://www.amctheatres.com/showtimes/144696892/seats"
    # },
    # {
    #     "name": "Sat, Aug 8 @ 2:00 PM",
    #     "url": "https://www.amctheatres.com/showtimes/144696893/seats"
    # },
    # {
    #     "name": "Sat, Aug 8 @ 6:00 PM",
    #     "url": "https://www.amctheatres.com/showtimes/144696894/seats"
    # }
]



##################################################################################################################################
""" Functions """
##################################################################################################################################


""" Seats """


def get_available_seats(_page):
    """
    Reads the current AMC seating page and returns a set containing the seat IDs (e.g. "A25") for every seat that is currently
    available. Occupied or unavailable seats are ignored.

    :param _page:
    :return:
    """

    _seats = _page.locator(
        'input[type="checkbox"]'
    )

    _set_available = set()

    for _i in range(_seats.count()):

        _seat = _seats.nth(_i)

        if not _seat.is_disabled():

            _name = _seat.get_attribute("name")

            if _name:
                _set_available.add(_name)

    return _set_available


def format_seat(_seat):
    """
    Converts a seat ID from the compact AMC format into a more human-readable format.

    Example: A25 -> Row A Seat 25 (optional)

    Used when referencing seats in email notifications.

    :param _seat:
    :return:
    """

    _match = re.match(
        r"([A-Z]+)(\d+)",
        _seat
    )

    if _match:

        _row = _match.group(1)
        _number = _match.group(2)

        # return f"Row {_row} Seat {_number}"
        return f"{_row}{_number}"

    return _seat


def parse_seat(_seat):
    """
    Splits a seat ID into its row and seat number.

    Example: A25 -> ("A", 25)

    Returns (None, None) if the seat string cannot be parsed.

    :param _seat:
    :return:
    """

    _match = re.match(
        r"([A-Z]+)(\d+)",
        _seat
    )

    if _match:

        return (
            _match.group(1),
            int(_match.group(2))
        )

    return None, None


def find_seat_pairs(_seats):
    """
    Finds newly available adjacent seat pairs.

    Input: {"A24", "A25", "B10"}

    Returns: [("A", 24, 25)]

    Used to separate adjacent seat pairs from individual seats in the email notification.

    :param _seats:
    :return:
    """

    _parsed = []

    for _seat in _seats:

        _row, _number = parse_seat(_seat)

        if _row:
            _parsed.append(
                (_row, _number)
            )

    _pairs = []

    for _i in range(len(_parsed)):

        _row1, _seat1 = _parsed[_i]

        for _j in range(_i + 1, len(_parsed)):

            _row2, _seat2 = _parsed[_j]

            if (
                _row1 == _row2
                and abs(_seat1 - _seat2) == 1
            ):

                _pairs.append(
                    (
                        _row1,
                        min(_seat1, _seat2),
                        max(_seat1, _seat2)
                    )
                )

    return _pairs


""" Email  """


def send_email(_subject, _body):
    """
    Sends an email using Gmail's SMTP server whenever newly available seats are detected.

    Parameters:
        subject - Email subject line.
        body    - Plain text email body.

    :param _subject:
    :param _body:
    :return:
    """

    _msg = EmailMessage()

    _msg["From"] = EMAIL_FROM
    _msg["To"] = EMAIL_TO
    _msg["Subject"] = _subject

    _msg.set_content(_body)

    with smtplib.SMTP_SSL(
        "smtp.gmail.com",
        465
    ) as _smtp:

        _smtp.login(
            EMAIL_FROM,
            EMAIL_PASSWORD
        )

        _smtp.send_message(_msg)

    # print("Email sent!")


def build_email_body(_show_name, _seats):
    """
    Creates the email body for a single showtime.

    The email is organized into:
        - Newly available adjacent seat pairs
        - Newly available single seats

    Returns the completed email body as a formatted string.

    :param _show_name:
    :param _seats:
    :return:
    """

    _body = []

    # _body.append(
    #     "New Seats Available"
    # )
    #
    # _body.append(
    #     ""
    # )

    _body.append(
        _show_name
    )

    # _body.append(
    #     "=" * 40
    # )

    _pairs = find_seat_pairs(_seats)

    _paired_seats = set()

    if _pairs:

        _body.append(
            ""
        )

        _body.append(
            "New Seat Pair(s):"
        )

        for _row, _seat1, _seat2 in _pairs:

            _body.append(
                f"{_row}{_seat1}-{_seat2}"
            )

            _paired_seats.add(
                f"{_row}{_seat1}"
            )

            _paired_seats.add(
                f"{_row}{_seat2}"
            )

    _singles = _seats - _paired_seats

    if _singles:

        _body.append(
            ""
        )

        _body.append(
            "New Single Seat(s):"
        )

        for _seat in sorted(_singles):

            _body.append(
                format_seat(_seat)
            )

    return "\n".join(_body)


""" Network Resilience """


class RateLimitError(Exception):
    pass


def safe_reload(_page):
    """
    Reloads an existing Playwright page while handling temporary network failures. If a reload fails, the function retries
    several times before giving up.

    Returns:
        True  - Reload succeeded.
        False - All retry attempts failed.

    :param _page:
    :return:
    """

    for _attempt in range(1, MAX_RETRIES + 1):

        try:

            _page.reload(
                wait_until="domcontentloaded",
                timeout=60000
            )

            _page.wait_for_selector(
                'input[type="checkbox"]',
                state="attached",
                timeout=60000
            )

            return True


        except Exception as _e:

            if "checkbox" in str(_e):

                raise RateLimitError(

                    "AMC rate limit detected"

                )

            print(

                f"Opening page failed ({_attempt}/{MAX_RETRIES})"

            )

            print(_e)

            time.sleep(

                RETRY_DELAY_SECONDS

            )

    return False


def open_page(_browser, _url):
    """
    Opens a new browser tab for a showtime URL and waits until the seat map has loaded. If the page fails to load, the function retries several times.

    Returns:
        Playwright Page object on success.
        None if all attempts fail.

    :param _browser:
    :param _url:
    :return:
    """

    for _attempt in range(1, MAX_RETRIES + 1):

        try:

            _page = _browser.new_page()

            _page.goto(
                _url,
                wait_until="domcontentloaded",
                timeout=60000
            )

            _page.wait_for_selector(
                'input[type="checkbox"]',
                state="attached",
                timeout=60000
            )

            return _page



        except Exception as _e:

            if "checkbox" in str(_e):

                raise RateLimitError(

                    "AMC rate limit detected"

                )

            print(

                f"Opening page failed ({_attempt}/{MAX_RETRIES})"

            )

            print(_e)

            time.sleep(

                RETRY_DELAY_SECONDS

            )

    return None



##################################################################################################################################
""" Run Functions """
##################################################################################################################################


with sync_playwright() as p:

    browser = p.chromium.launch(
        headless=True
    )

    pages = {}

    previous_seats = {}

    # print("Loading showtimes...")

    try:

        for show in SHOWTIMES:

            page = open_page(
                browser,
                show["url"]
            )

            if page is None:

                print("Could not open showtime. Skipping.")

                continue

            available = get_available_seats(
                page
            )

            pages[show["name"]] = page

            previous_seats[show["name"]] = available


    except RateLimitError:

        print(
            "AMC rate limit detected."
        )

        print(
            f"Sleeping for {RATE_LIMIT_SLEEP_SECONDS / 3600:.0f} hours."
        )

        time.sleep(
            RATE_LIMIT_SLEEP_SECONDS
        )

        # print(
        #     "Initial available seats:",
        #     sorted(available)
        # )

    # print("\n==========================")
    # print("Monitoring started")
    # print("==========================")

    while True:

        print(
            "Run:",
            datetime.now().strftime("%Y-%m-%d %I:%M:%S %p")
        )

        try:

            # print("\nChecking seats...")

            for show in SHOWTIMES:

                name = show["name"]

                if name not in pages:

                    continue

                page = pages[name]

                success = safe_reload(
                    page
                )

                if not success:

                    print(
                        "Skipping this showtime"
                    )

                    continue

                try:

                    current_available = get_available_seats(
                        page
                    )

                except Exception as e:

                    print(
                        "Seat reading failed:",
                        e
                    )

                    continue

                new_seats = (
                    current_available
                    -
                    previous_seats[name]
                )

                if new_seats:

                    print(f"\n{name}")

                    pairs = find_seat_pairs(new_seats)

                    if pairs:
                        print("New seat pair(s):")

                        for row, seat1, seat2 in pairs:
                            print(f"  {row}{seat1}-{seat2}")

                    paired = {
                        f"{row}{seat}"
                        for row, s1, s2 in pairs
                        for seat in (s1, s2)
                    }

                    singles = sorted(new_seats - paired)

                    if singles:
                        print("New single seat(s):")

                        for seat in singles:
                            print(f"  {format_seat(seat)}")

                    body = build_email_body(
                        name,
                        new_seats
                    )

                    send_email(
                        EMAIL_SUBJECT,
                        body
                    )

                else:

                    pass

                    # print(
                    #     "No new seats"
                    # )

                previous_seats[name] = current_available

            # print(
            #     f"\nSleeping {CHECK_INTERVAL_MINUTES} minutes..."
            # )

            if CHECK_INTERVAL_SECONDS > 0:
                time.sleep(CHECK_INTERVAL_SECONDS)


        except RateLimitError as e:

            print(

                "AMC rate limit detected."

            )

            print(

                f"Sleeping for {RATE_LIMIT_SLEEP_SECONDS / 3600:.0f} hours."

            )

            time.sleep(

                RATE_LIMIT_SLEEP_SECONDS

            )


        except Exception as e:

            print(

                "Unexpected error:"

            )

            print(e)

            print(

                "Continuing in 60 seconds..."

            )

            time.sleep(60)


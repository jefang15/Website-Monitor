"""
Scrapes the Glacier National Park lodging website for rooms available and alerts me when a new room at one of the lodges is
available.
Prevents needing to frequently visit and check the page for each lodge and each night for new availability.

https://secure.glaciernationalparklodges.com/booking/lodging
"""


import os
from bs4 import BeautifulSoup
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from password import email, email_password
import time
import json
from datetime import datetime, timedelta
from selenium import webdriver
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.firefox.options import Options


def _scrape_html(_date):
    """
    Scrapes URL for the specified date and creates a list of key information from the website (including lodge name, room type,
    and price).

    :return:
    """

    # Path to GeckoDriver
    _gecko_service = Service('Output - Lodging - Glacier National Park/geckodriver')

    # Setup Firefox WebDriver options (needed due to JavaScript)
    _firefox_options = Options()
    _firefox_options.add_argument('--headless')  # Run headless for performance

    # Start the WebDriver for Firefox
    _driver = webdriver.Firefox(service=_gecko_service, options=_firefox_options)

    # Load the Glacier lodging website
    _driver.get(
        f'https://secure.glaciernationalparklodges.com/booking/lodging-search?destination=ALL&adults=2&children=0&rateCode&rateType=&dateFrom={_date}&nights=1')

    time.sleep(5)  # Wait for the page to load

    # Example scraping logic
    _page_source = _driver.page_source
    _soup = BeautifulSoup(_page_source, 'html.parser')
    _driver.quit()

    # Parse the availability information
    _availability = []

    _lodge_cards = _soup.find_all('div', class_='product-card__info')

    for _card in _lodge_cards:
        # Extract lodge name
        _lodge_name = _card.find('div', class_='product-card__title').find('span').text.strip()

        # Extract price
        _price_container = _card.find_next('div', class_='product-card__price-value')

        if _price_container is not None:
            _price_symbol = _price_container.find('sup').text.strip()
            _price_value = _price_container.find('span').text.strip()
            _price = f'{_price_symbol}{_price_value}'

            # Append lodge info with its price
            _availability.append({
                'Lodge': _lodge_name,
                'Room Type': 'Standard',  # Adjust as necessary; you may need to extract this if available
                'Price': _price
            })
        else:
            # If no price is found, mark as not available
            _availability.append({
                'Lodge': _lodge_name,
                'Room Type': 'Standard',  # Adjust as necessary; you may need to extract this if available
                'Price': 'Not available'
            })

    # Aggregate minimum prices for lodges that have multiple rooms available
    aggregated_availability = {}
    for room in _availability:
        lodge = room['Lodge']
        price = room['Price']

        if lodge not in aggregated_availability:
            aggregated_availability[lodge] = {'Room Type': room['Room Type'], 'prices': []}

        if price != 'Not available':
            aggregated_availability[lodge]['prices'].append(price)

    final_availability = []
    for lodge, data in aggregated_availability.items():
        if data['prices']:
            # Find minimum price
            min_price = min(float(p.replace('$', '').replace(',', '')) for p in data['prices'])
            final_availability.append({
                'Lodge': lodge,
                'Room Type': data['Room Type'],
                'Price': f'${min_price:.2f}'  # Format to currency
            })
        else:
            # No available rooms
            final_availability.append({
                'Lodge': lodge,
                'Room Type': data['Room Type'],
                'Price': 'Not available'
            })

    return final_availability


def _load_previous_data():
    """
    Load previous JSON data from file.

    :return: JSON file containing the previous period's availability.
    """
    try:
        with open('Output - Lodging - Glacier National Park/previous_availability.json', 'r') as _file:
            return json.load(_file)
    except FileNotFoundError:
        return {}


def _save_current_data(_data):
    """
    Save the current scrape data over the previous availability JSON file.

    :param _data:
    :return:
    """
    with open('Output - Lodging - Glacier National Park/previous_availability.json', 'w') as _file:
        json.dump(_data, _file, indent=4)  # Set indent for pretty printing


def _save_historical_data(_new_data):
    """
    Save all historical data to a separate archive file.

    :param _new_data:
    :return:
    """

    _archive_file = 'Output - Lodging - Glacier National Park/historical_availability.json'

    # Load existing historical data if the file exists
    if os.path.exists(_archive_file):
        with open(_archive_file, 'r') as _file:
            _historical_data = json.load(_file)
    else:
        _historical_data = []

    # Append new data with a timestamp to the historical archive
    _timestamped_data = {
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'data': _new_data
    }
    _historical_data.append(_timestamped_data)

    # Save the updated historical data back to the file with pretty printing
    with open(_archive_file, 'w') as _file:
        json.dump(_historical_data, _file, indent=4)


def _send_email(_email, _email_password, _changes):
    """
    Configure Email.

    :param _email:
    :param _email_password:
    :param _changes:
    :return:
    """

    # Form Email Parameters
    _msg = MIMEMultipart('multipart')  # To support mix of content types
    _msg['From'] = email
    _msg['To'] = email
    _msg['Subject'] = 'Glacier Lodging Availability and Price Changes!'

    # Static itinerary
    _static_text = (
        'Itinerary:<br>'
        '-Fri, Aug 29, 2025: Kalispell/Lake McDonald/Apgar<br>'
        '-Sat, Aug 30, 2025: Lake McDonald<br>'
        '-Sun, Aug 31, 2025: Lake McDonald<br>'
        '-Mon, Sep 1, 2025: Waterton<br>'
        '-Tue, Sep 2, 2025: Many Glacier<br>'
        '-Wed, Sep 3, 2025: Many Glacier<br>'
        '-Thu, Sep 4, 2025: Many Glacier<br>'
        '-Fri, Sep 5, 2025: Kalispell/Lake McDonald/Apgar<br>'
        '<br><br>')

    # Group changes by date
    grouped_changes = {}
    for _change in _changes:
        _date = _change['date']
        if _date not in grouped_changes:
            grouped_changes[_date] = []
        grouped_changes[_date].append({
            'Lodge': _change['Lodge'],
            'Room Type': _change['Room Type'],
            'Price': _change['Price'],
            'change_type': _change['change_type']
        })

    # Build the email body with all changes
    _text = _static_text  # Start with the static text
    current_date = None  # To keep track of the current date for grouping

    for _change in _changes:
        if _change['date'] != current_date:  # Check if the date has changed
            if current_date is not None:  # Add a line break between different dates
                _text += '<br>'
            current_date = _change['date']  # Update the current date
            _text += f'<strong>{current_date}</strong><br>'  # Bold the date
        # Append lodge information
        _text += f"Lodge: {_change['Lodge']}<br>Room Type: {_change['Room Type']}<br>Price: {_change['Price']}<br><br>"

    _part = MIMEText(_text, "html")  # Change to "html"
    _msg.attach(_part)

    with smtplib.SMTP('smtp.outlook.com', 587) as smtp:
        smtp.ehlo()
        smtp.starttls()
        smtp.login(email, email_password)
        smtp.send_message(_msg)


def _compare_and_notify(_email, _email_password, _new_data, _old_data):
    """
    Compare new data with old data and send emails for new availability or price decreases of existing availability for each
    lodge.

    :param _new_data:
    :param _old_data:
    :return:
    """

    _changes = []  # List to accumulate all changes

    for _date, _rooms in _new_data.items():
        if _date not in _old_data:
            _old_data[_date] = []

        # Find new rooms (not in old data)
        for _new_room in _rooms:
            if _new_room not in _old_data[_date]:
                _changes.append({
                    'Lodge': _new_room['Lodge'],
                    'date': _date,
                    'Room Type': _new_room['Room Type'],
                    'Price': _new_room['Price'],
                    'change_type': 'New availability'
                })

        # Check for price decreases in existing rooms
        for _new_room in _rooms:
            for _old_room in _old_data[_date]:
                if (_new_room['Lodge'] == _old_room['Lodge'] and
                        _new_room['Room Type'] == _old_room['Room Type']):

                    # Check if the prices are available for both rooms
                    if _new_room['Price'] != 'Not available' and _old_room['Price'] != 'Not available':
                        # Strip the '$' sign and convert prices to compare numerically
                        _new_price = float(_new_room['Price'].replace('$', '').replace(',', ''))
                        _old_price = float(_old_room['Price'].replace('$', '').replace(',', ''))

                        if _new_price < _old_price:  # Price decrease detected
                            _changes.append({
                                'Lodge': _new_room['Lodge'],
                                'date': _date,
                                'Room Type': _new_room['Room Type'],
                                'Price': _new_room['Price'],
                                'change_type': 'Price decrease'
                            })

    # Send one email for all changes (if any)
    if _changes:
        _send_email(_email, _email_password, _changes)


def _check_availability(_email, _email_password):
    """
    Main function to scrape all dates and send notification as needed.

    :return:
    """
    _old_data = _load_previous_data()
    _new_data = {}

    _start_date = datetime(2025, 8, 29)
    _end_date = datetime(2025, 9, 5)
    _delta = timedelta(days=1)

    while _start_date <= _end_date:
        print(f"Scraping availability for {_start_date.strftime('%m-%d-%Y')}...", flush=True)
        _availability = _scrape_html(_start_date.strftime('%m-%d-%Y'))
        _new_data[_start_date.strftime('%Y-%m-%d')] = _availability
        _start_date += _delta

    _compare_and_notify(_email, _email_password, _new_data, _old_data)

    # Save both the current and historical data
    _save_current_data(_new_data)
    _save_historical_data(_new_data)


if __name__ == '__main__':
    while True:
        print('Checking availability...')
        _check_availability(email, email_password)

        print('Sleeping...')
        time.sleep(60*60*1)  # Sleep for 30 minutes (1800 seconds)


"""
Scrapes the Glacier National Park lodging website for rooms available and alerts me when a new room at one of the lodges is
available.
Prevents needing to frequently visit and check the page for each lodge and each night for new availability.

https://secure.glaciernationalparklodges.com/booking/lodging
"""


import os
from bs4 import BeautifulSoup
from email.mime.multipart import MIMEMultipart
import time
import json
from datetime import datetime, timedelta
from selenium import webdriver
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.firefox.options import Options
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import os.path
import base64
from email.mime.text import MIMEText


def scrape_html(_website_url):
    """
    Scrapes URL for the specified date and creates a list of key information from the website (including lodge name, room type,
    and price).

    :_website_url: Website for Glacier lodging for a date (specified in an outer loop outside function)
    :return:
    """

    # Path to GeckoDriver
    _gecko_service = Service(
        '/Users/jeff/Documents/Programming/Projects/Website-Monitor/geckodriver',
        log_output=None)

    # Setup Firefox WebDriver options (needed due to JavaScript)
    _firefox_options = Options()
    _firefox_options.add_argument('--headless')  # Run headless for performance

    # Start the WebDriver for Firefox
    _driver = webdriver.Firefox(service=_gecko_service, options=_firefox_options)

    # Load the Glacier lodging website
    _driver.get(_website_url)

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
    _aggregated_availability = {}
    for _room in _availability:
        _price = _room['Price']
        _lodge = _room['Lodge']

        if _lodge not in _aggregated_availability:
            _aggregated_availability[_lodge] = {'Room Type': _room['Room Type'], 'Prices': []}

        if _price != 'Not available':
            _aggregated_availability[_lodge]['Prices'].append(_price)

    _final_availability = []
    for _lodge, _data in _aggregated_availability.items():
        if _data['Prices']:
            # Find minimum price
            min_price = min(float(p.replace('$', '').replace(',', '')) for p in _data['Prices'])
            _final_availability.append({
                'Lodge': _lodge,
                'Room Type': _data['Room Type'],
                'Price': f'${min_price:.2f}'  # Format to currency
            })
        else:
            # No available rooms
            _final_availability.append({
                'Lodge': _lodge,
                'Room Type': _data['Room Type'],
                'Price': 'Not available'
            })

    return _final_availability


def load_previous_data():
    """
    Load previous JSON data from file.

    :return: JSON file containing the previous period's availability.
    """
    try:
        with open('Output - Lodging - Glacier National Park/Glacier_Previous_Availability.json', 'r') as _file:
            return json.load(_file)
    except FileNotFoundError:
        return {}


def save_current_data(_data):
    """
    Save the current scrape data over the previous availability JSON file.

    :param _data:
    :return:
    """
    with open('Output - Lodging - Glacier National Park/Glacier_Previous_Availability.json', 'w') as _file:
        json.dump(_data, _file, indent=4)  # Set indent for pretty printing


def save_historical_data(_new_data):
    """
    Save all historical data to a separate archive file.

    :param _new_data:
    :return:
    """

    _archive_file = 'Output - Lodging - Glacier National Park/Glacier_Historical_Availability.json'

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


def authenticate_gmail():
    """
    Handles OAuth 2.0 authentication (allows Python script to securely access a Gmail account without requiring the password)

    :return: Credentials (information like the access token, refresh token, and token expiry time) used to authenticate API
    requests to Google services/the Gmail API
    """

    _scopes = ['https://www.googleapis.com/auth/gmail.send']

    creds = None

    # The token.json file stores the user's access and refresh tokens (prevents manual authentication on subsequent runs)
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', _scopes)
    # If no valid credentials are available, request new ones
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                '/Users/jeff/Documents/Programming/Projects/Website-Monitor/credentials.json',
                _scopes)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    return creds


def compare_and_notify(_from_email, _to_email, _creds, _new_data, _old_data):
    """
    Compare new data with old data and returns a list of lodges with changes from the last scrape.

    :param _from_email: Gmail
    :param _to_email: Outlook, etc.
    :param _creds: Credentials for Gmail API access
    :param _new_data: Current availability
    :param _old_data: Previous availability
    :return: List of changes in lodge availability.
    """

    _changes = []  # List to accumulate all changes

    for _date, _rooms in _new_data.items():
        # print(_date, _rooms)
        if _date not in _old_data:
            _old_data[_date] = []
            # type(_old_data)  # Dict of list
            # print(_old_data)

        # New rooms (not in old data) are automatically added to the change list (if their price is $400 or less)
        for _new_room in _rooms:
            if _new_room not in _old_data[_date] and _new_room['Price'] != 'Not available':
                # print(_new_room)

                # Use this: to add all new rooms to the change list
                _changes.append({
                    'Lodge': _new_room['Lodge'],
                    'Date': _date,
                    'Room Type': _new_room['Room Type'],
                    'Price': _new_room['Price'],
                    'Change Type': 'New'
                })

                # Use this: to only add new rooms to the change list if its price is $400 or less
                # _new_price = float(_new_room['Price'].replace('$', '').replace(',', ''))
                # if _new_price <= 400:
                #     _changes.append({
                #         'Lodge': _new_room['Lodge'],
                #         'Date': _date,
                #         'Room Type': _new_room['Room Type'],
                #         'Price': _new_room['Price'],
                #         'Change Type': 'New'
                #     })

        # For rooms that were previously available, check if the price decreased
        for _new_room in _rooms:
            for _old_room in _old_data[_date]:
                if _new_room['Lodge'] == _old_room['Lodge'] and _new_room['Room Type'] == _old_room['Room Type']:

                    # Check if the prices are available for both rooms
                    if _new_room['Price'] != 'Not available' and _old_room['Price'] != 'Not available':
                        # Strip the '$' sign and convert prices to compare numerically
                        _new_price = float(_new_room['Price'].replace('$', '').replace(',', ''))
                        _old_price = float(_old_room['Price'].replace('$', '').replace(',', ''))

                        # Use this: to add rooms with price decreases
                        if _new_price < _old_price:  # Price decrease detected
                            _changes.append({
                                'Lodge': _new_room['Lodge'],
                                'Date': _date,
                                'Room Type': _new_room['Room Type'],
                                'Price': _new_room['Price'],
                                'Change Type': f'Price decreased ${round(_old_price - _new_price, 2)}'
                            })

                        # Use this: to add rooms with price decreases to $400 or below
                        # if _new_price < _old_price and _new_price <= 400:
                        #     _changes.append({
                        #         'Lodge': _new_room['Lodge'],
                        #         'Date': _date,
                        #         'Room Type': _new_room['Room Type'],
                        #         'Price': _new_room['Price'],
                        #         'Change Type': f'Price decreased ${_old_price - _new_price}'
                        #     })

    return _changes


def send_email(_from_email, _to_email, _creds, _changes):
    """
    Configure Email.

    Emojis at: https://emojipedia.org

    :param _from_email: Gmail
    :param _to_email: Outlook, etc.
    :param _creds: Credentials for Gmail API access
    :param _changes: Changes in availability  (new rooms, and price decreases of existing rooms)
    :return:
    """

    # Form Email Parameters
    _msg = MIMEMultipart('multipart')  # To support mix of content types
    _msg['From'] = _from_email
    _msg['To'] = _to_email
    _msg['Subject'] = '🛏️ Glacier Lodging Update!'

    # Build the email body
    _html_content = "<html><body style='background-color: transparent;'>"

    # Static itinerary
    _summary_text = '<h1>Itinerary</h1>'

    _summary_text += (
        '-Fri, Aug 29, 2025: Lake McDonald/Apgar<br>'
        '-Sat, Aug 30, 2025: Lake McDonald<br>'
        '-Sun, Aug 31, 2025: Lake McDonald<br>'
        '-Mon, Sep 1, 2025: Waterton<br>'
        '-Tue, Sep 2, 2025: Many Glacier<br>'
        '-Wed, Sep 3, 2025: Many Glacier<br>'
        '-Thu, Sep 4, 2025: Many Glacier<br>'
        '-Fri, Sep 5, 2025: Lake McDonald/Apgar<br>'
        '<br><br>')
    _html_content += _summary_text

    # Group changes by date
    grouped_changes = {}

    for _change in _changes:
        _date = _change['Date']
        if _date not in grouped_changes:
            grouped_changes[_date] = []
        grouped_changes[_date].append({
            'Lodge': _change['Lodge'],
            'Room Type': _change['Room Type'],
            'Price': _change['Price'],
            'Change Type': _change['Change Type']
        })

    # Build the email body with all changes
    _current_date = None  # To keep track of the current date for grouping

    for _change in _changes:
        if _change['Date'] != _current_date:  # Check if the date has changed
            if _current_date is not None:  # Add a line break between different dates
                _html_content += ''
            _current_date = _change['Date']  # Update the current date
            _current_datetime = datetime.strptime(_current_date, '%Y-%m-%d')
            _html_content += f"<h1>{_current_datetime.strftime('%a, %b %d, %Y')}</h1>"
        # Append lodge information
        _html_content += (
            f"<strong>{_change['Lodge']}</strong><br>"  # Bold lodge name
            # f"Room Type: {_change['Room Type']}<br>"
            f"Price: {_change['Price']}<br>"
            f"Change: {_change['Change Type']}<br><br>"
        )

    _website_url = 'https://secure.glaciernationalparklodges.com/booking/lodging?_gl=1%2axa24f8%2a_gcl_aw%2aR0NMLjE3Mjg3MDYwOTAuQ2p3S0NBandtYU80QmhBaEVpd0E1cDRZTDFONkVtVWdUSFdZSVZpQjIzWVY0aVhTeVhTa1lWNkFwcjVNdHc1Wjk1OWRFUW9JaTdtS1ZSb0NqTEVRQXZEX0J3RQ..%2a_gcl_au%2aMjE0MzkyMzY5NC4xNzI2MzY3MzIy%2a_ga%2aMTY5MzM0OTM3My4xNzI2MzY3MzIy%2a_ga_GCMW2T3P1D%2aMTcyODcwNjA4NS43OS4xLjE3Mjg3MDYwOTAuNTUuMC4w'
    _lodge_name = 'Glacier National Park Lodges'
    _html_content += f"<p>More details at <a href='{_website_url}'>{_lodge_name}</a></p>"

    _part = MIMEText(_html_content, 'html')  # Change to "html"
    _msg.attach(_part)

    # Convert the message to a format that Gmail API can accept (base64 encoding)
    raw_message = base64.urlsafe_b64encode(_msg.as_bytes()).decode()

    # Build the Gmail service
    _service = build('gmail', 'v1', credentials=_creds)

    # Send the email using the Gmail API
    try:
        message = {
            'raw': raw_message
        }
        send_result = _service.users().messages().send(userId='me', body=message).execute()
        print(f"Email sent successfully with ID: {send_result['id']}")
    except Exception as error:
        print(f"An error occurred: {error}")


def main():
    """
    Main function to scrape all dates and send notification as needed.

    :return: Sends email if there are changes in availability
    """

    # Define inputs
    _from_email = 'nanookgolightly@gmail.com'
    _to_email = 'jeffreyfang@msn.com'

    _old_data = load_previous_data()
    _new_data = {}

    _start_date = datetime(2025, 8, 29)
    _end_date = datetime(2025, 9, 5)
    _delta = timedelta(days=1)

    while _start_date <= _end_date:
        
        _website_url = (f"https://secure.glaciernationalparklodges.com/booking/lodging-search?destination=ALL&adults=2&children"
                        f"=0&rateCode&rateType=&dateFrom={_start_date.strftime('%m-%d-%Y')}&nights=1")
        
        print(f"Checking availability for {_start_date.strftime('%m-%d-%Y')}...", flush=True)
        _availability = scrape_html(_website_url)
        _new_data[_start_date.strftime('%Y-%m-%d')] = _availability
        _start_date += _delta

    _creds = authenticate_gmail()

    _changes = compare_and_notify(_from_email, _to_email, _creds, _new_data, _old_data)

    if _changes:
        send_email(_from_email, _to_email, _creds, _changes)
    else:
        print('No new availability or price decreases')

        save_historical_data(_new_data)

    save_current_data(_new_data)

    # Sleep for X minutes before the next check
    sleep_time = 5  # Minutes
    print(f"Sleeping for {sleep_time} minutes...\n")
    time.sleep(sleep_time * 60)  # Convert minutes to seconds


if __name__ == '__main__':
    while True:
        main()


##################################################################################################################################
""" Troubleshoot """
##################################################################################################################################


# <editor-fold desc="Description">


# from_email = 'nanookgolightly@gmail.com'
# to_email = 'jeffreyfang@msn.com'
#
# old_data = load_previous_data()
# type(old_data)  # Dict
# print(old_data)
# # {'2025-08-29': [{'Lodge': 'Cedar Creek Lodge (Columbia Falls, MT)', 'Room Type': 'Standard', 'Price': '$479.99'}, ...
#
# new_data = {}
# type(new_data)  # Dict
# print(new_data)
# # {}
#
# start_date = datetime(2025, 8, 29)
# end_date = datetime(2025, 9, 5)
# delta = timedelta(days=1)
#
# while start_date <= end_date:
#     print(start_date)
#     availability = scrape_html(start_date.strftime('%m-%d-%Y'))
#     new_data[start_date.strftime('%Y-%m-%d')] = availability
#     start_date += delta
#
#
# # Temp info to append to each date in new_data dictionary
# type(availability)  # List
# print(availability)
#
# type(new_data)  # Dict
# print(new_data)
# # {'2025-08-29': [
# #     {'Lodge': 'Cedar Creek Lodge (Columbia Falls, MT)', 'Room Type': 'Standard', 'Price': '$479.99'},
# #     {'Lodge': 'Lake McDonald', 'Room Type': 'Standard', 'Price': 'Not available'},
# #     {'Lodge': 'Many Glacier Hotel', 'Room Type': 'Standard', 'Price': 'Not available'},
# #     {'Lodge': 'Rising Sun Motor Inn & Cabins', 'Room Type': 'Standard', 'Price': 'Not available'},
# #     {'Lodge': 'Swiftcurrent Motor Inn & Cabins', 'Room Type': 'Standard', 'Price': 'Not available'},
# #     {'Lodge': 'Village Inn at Apgar', 'Room Type': 'Standard', 'Price': 'Not available'}],
# #  '2025-08-30': [
# #      {'Lodge': 'Cedar Creek Lodge (Columbia Falls, MT)', 'Room Type': 'Standard', 'Price': '$489.99'},
# #     ...]
#
# creds = authenticate_gmail()
#
# changes = compare_and_notify(from_email, to_email, creds, new_data, old_data)
# type(changes)  # List
# print(changes)
#
#
# # save_current_data(new_data)
# # save_historical_data(new_data)
#
# send_email(from_email, to_email, creds, changes)


# </editor-fold>


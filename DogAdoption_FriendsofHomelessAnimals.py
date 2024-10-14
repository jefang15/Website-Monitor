"""
Scrapes the Friends of Homeless Animals site (24petconnect.com) for dogs available for adoption and alerts me when a new dog is
available or was adopted. Prevents needing to frequently refresh the page and manually identifying changes.

https://foha.org/pet-adoption/find-a-dog/
"""


import os
import json
import time
import requests
import base64
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.firefox.options import Options
from bs4 import BeautifulSoup
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
import math


def check_pages(_website_url):
    _gecko_service = Service(
        '/Users/jeff/Documents/Programming/Projects/Website-Monitor/geckodriver',
        log_output=os.devnull)
    _firefox_options = Options()
    _firefox_options.add_argument('--headless')

    _driver = webdriver.Firefox(service=_gecko_service, options=_firefox_options)
    _driver.get(_website_url)

    time.sleep(5)

    _page_source = _driver.page_source
    _soup = BeautifulSoup(_page_source, 'html.parser')
    _driver.quit()

    # Check number of pages
    _animal_count_header = _soup.find('h3', id='AnimalCountHeader')

    if _animal_count_header:
        _animal_count_text = _animal_count_header.text.strip()
        _animal_count_str = _animal_count_text.split(' of ', 1)[1]
        _animal_count_int = int(_animal_count_str)

        return _animal_count_int
    else:
        _animal_count_int = 30
        return _animal_count_int


def scrape_html(_website_url):
    """
    Scrapes URL for dogs available for adoption.

    :param _website_url: Dog adoption website to monitor and scrape.
    :return: List of dictionaries containing dog availability information.
    """

    # Connect to webite
    _gecko_service = Service(
        '/Users/jeff/Documents/Programming/Projects/Website-Monitor/geckodriver',
        log_output=os.devnull)
    _firefox_options = Options()
    _firefox_options.add_argument('--headless')

    _driver = webdriver.Firefox(service=_gecko_service, options=_firefox_options)
    _driver.get(_website_url)

    time.sleep(5)

    _page_source = _driver.page_source
    _soup = BeautifulSoup(_page_source, 'html.parser')
    _driver.quit()

    # Scrape dog information
    _availability = []
    _dog_cards = _soup.find_all('div', class_='gridResult')

    for _card in _dog_cards:
        _picture_tag = _card.find('img')
        _picture_url = _picture_tag['src'].strip() if _picture_tag else None

        _name_tag = _card.find('div', class_='line_Name').find('span', class_='text_Name')
        _name_full = _name_tag.text.strip() if _name_tag else None

        if _name_full:
            _name = _name_full.split(' (', 1)[0]
            _id = _name_full.split(' (', 1)[1].split(')')[0]

        _gender_tag = _card.find('div', class_='line_Gender').find('span', class_='text_Gender')
        _gender = _gender_tag.text.strip() if _gender_tag else None

        _breed_tag = _card.find('div', class_='line_Breed').find('span', class_='text_Breed')
        _breed = _breed_tag.text.strip() if _breed_tag else None

        _age_tag = _card.find('div', class_='line_Age').find('span', class_='text_Age')
        _age = _age_tag.text.strip() if _age_tag else None

        _availability.append({
            'Name': _name,
            'ID': _id,
            'Gender': _gender,
            'Breed': _breed,
            'Age': _age,
            'Picture': _picture_url
        })

    return _availability


def load_previous_data(_directory_previous_availability):
    """
    Load previous JSON data from file.

    :_directory_previous_availability: File path to folder containing the Previous_Availability.json file.
    :return: JSON file containing the dog availability from the previous scrape.
    """
    try:
        with open(_directory_previous_availability, 'r') as _file:
            data = json.load(_file)
            return data.get('data', [])  # Assuming the data is wrapped in a 'data' key
    except FileNotFoundError:
        return []  # Return an empty list if the file does not exist


def save_current_data(_current_availability, _directory_previous_availability):
    """
    Save the current availability over the Previous_Availability.json file (so that the current availability will be "old" for
    the next time the script runs).

    :param _current_availability: Current availability (output of _scrape_html function)
    :param _directory_previous_availability: File path to folder containing the Previous_Availability.json file.
    :return:
    """

    _current_availability2 = sorted(_current_availability, key=lambda x: x['Name'])

    # Create a timestamp for when the scrape was performed
    timestamped_data = {
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'data': _current_availability2
    }

    with open(_directory_previous_availability, 'w') as _file:
        json.dump(timestamped_data, _file, indent=4)  # Set indent for pretty printing


def save_historical_data(_current_availability, _directory_historical_availability):
    """
    Save and append all current availability to a separate archival file.

    :param _current_availability: Current availability (output of _scrape_html function)
    :param _directory_historical_availability: File path to folder containing the Previous_Availability.json file.
    :return:
    """

    if os.path.exists(_directory_historical_availability):
        with open(_directory_historical_availability, 'r') as _file:
            _historical_data = json.load(_file)
    else:
        _historical_data = []

    _current_availability2 = sorted(_current_availability, key=lambda x: x['Name'])

    _timestamped_data = {
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'data': _current_availability2
    }
    _historical_data.append(_timestamped_data)

    # _historical_data2 = [{k: v for k, v in dog.items() if k != 'Photo_Path'} for dog in _historical_data]

    with open(_directory_historical_availability, 'w') as _file:
        json.dump(_historical_data, _file, indent=4)


def compare_dogs(_current_dogs, _previous_dogs):
    """
    Compare the current list of dogs with the previous list based on stable attributes. Identifies new dogs and adopted dogs.

    :param _current_dogs: List of current dog availability (output of scrape_html function)
    :param _previous_dogs: List of previous dog availability (output of load_previous_data function)
    :return: Lists of new dogs and adopted dogs
    """

    # Create sets for IDs of current and previous dogs
    _current_dog_ids = {dog['ID'] for dog in _current_dogs}
    _previous_dog_ids = {dog['ID'] for dog in _previous_dogs}

    # Find IDs of new and adopted dogs
    _new_dog_ids = _current_dog_ids - _previous_dog_ids
    _adopted_dog_ids = _previous_dog_ids - _current_dog_ids

    # Get new and adopted dogs based on ID matches
    _new_dogs = [dog for dog in _current_dogs if dog['ID'] in _new_dog_ids]
    _adopted_dogs = [dog for dog in _previous_dogs if dog['ID'] in _adopted_dog_ids]

    return _new_dogs, _adopted_dogs


def download_new_dog_photos(_new_dogs, _photo_directory):
    """
    Saves photos of new dogs available for adoption to a local folder.

    :param _new_dogs: New dogs, if any.
    :param _photo_directory: File path to folder containing saved dog photos.
    :return:
    """

    os.makedirs(_photo_directory, exist_ok=True)

    _headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/85.0.4183.83 Safari/537.36'
    }

    for _dog in _new_dogs:
        if _dog['Picture']:
            _response = requests.get(_dog['Picture'], headers=_headers)
            if _response.status_code == 200:
                _file_path = os.path.join(_photo_directory, f"{_dog['Name']} ({_dog['ID']}).png")
                with open(_file_path, 'wb') as file:
                    file.write(_response.content)
            else:
                print(f"Failed to download image for {_dog['Name']}.")
        else:
            print(f"No image found for {_dog['Name']}.")


def authenticate_gmail(_directory_credentials):
    """
    Handles OAuth 2.0 authentication (allows Python script to securely access a Gmail account without requiring the password)

    :param _directory_credentials: File path to credentials.json file.
    :return: Credentials (information like the access token, refresh token, and token expiry time) used to authenticate API
    requests to Google services/the Gmail API
    """
    _scopes = ['https://www.googleapis.com/auth/gmail.send']

    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', _scopes)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(_directory_credentials, _scopes)
            creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    return creds


def send_email(_from_email, _to_email, _email_subject, _creds, _new_dogs, _adopted_dogs, _directory_photos, _website_url,
               _shelter_name):
    """
    Sends an email with information on new and adopted dogs.

    :param _from_email: Sender email (@gmail.com).
    :param _to_email: Recipient email.
    :param _email_subject: Subject of the email.
    :param _creds: Gmail API credentials.
    :param _new_dogs: List of new dogs.
    :param _adopted_dogs: List of adopted dogs.
    :param _directory_photos: File path to folder containing dog photos.
    :param _website_url: The URL of the scraped website
    :param _shelter_name: Name of dog adoption shelter.
    :return:
    """

    # Form Email Parameters
    _msg = MIMEMultipart('related')  # Use 'related' to embed images
    _msg['From'] = _from_email
    _msg['To'] = _to_email
    _msg['Subject'] = _email_subject

    # Build the email body
    _html_content = "<html><body style='background-color: transparent;'>"

    # Add summary intro
    _summary_text = '<h1>Summary</h1><ul>'
    if _new_dogs:
        _summary_text += f"<li>{len(_new_dogs)} new dog(s) available for adoption</li>"
    if _adopted_dogs:
        _summary_text += f"<li>{len(_adopted_dogs)} dog(s) adopted</li>"
    _summary_text += "</ul>"

    _html_content += _summary_text

    # Add section for new dogs if there are any
    if _new_dogs:
        _html_content += '<h1>New Dogs</h1>'
        for _dog in _new_dogs:
            _html_content += f"""
                        <p>
                            <b>{_dog['Name']}</b> <br>
                            {_dog['Gender']}<br>
                            {_dog['Breed']}<br>
                            {_dog['Age']}<br>
                            {'<img src="cid:' + _dog['Name'] + ' (' + _dog['ID'] + ')' + '"><br>'}
                        </p>
                    """

    # Add section for adopted dogs if there are any
    if _adopted_dogs:
        _html_content += "<h1>Adopted Dogs</h1>"
        for _dog in _adopted_dogs:
            _html_content += f"""
                        <p>
                            <b>{_dog['Name']}</b> <br>
                            {_dog['Gender']}<br>
                            {_dog['Breed']}<br>
                            {_dog['Age']}<br>
                            {'<img src="cid:' + _dog['Name'] + ' (' + _dog['ID'] + ')' + '"><br>'}
                        </p>
                    """

    _html_content += f"<p>More details at <a href='{_website_url}'>{_shelter_name}</a></p>"
    _html_content += "</body></html>"

    _msg.attach(MIMEText(_html_content, 'html'))

    # Attach images for new and adopted dogs
    for _dog in _new_dogs + _adopted_dogs:  # Combine both lists to attach images
        _photo_path = os.path.join(_directory_photos, f"{_dog['Name']} ({_dog['ID']}).png")
        if os.path.exists(_photo_path):
            with open(_photo_path, 'rb') as _img_file:
                _img = MIMEImage(_img_file.read())
                _img.add_header('Content-ID', f"<{_dog['Name']} ({_dog['ID']})>")
                _msg.attach(_img)

    # Try sending the email and handle potential errors
    try:
        service = build('gmail', 'v1', credentials=_creds)
        service.users().messages().send(userId='me', body={'raw': base64.urlsafe_b64encode(_msg.as_bytes()).decode()}).execute()

        print(f"Email sent at {datetime.now()}")
        return True  # Indicate success
    except Exception as e:
        print(f"Failed to send email: {e}")
        return False  # Indicate failure


def main():
    """
    Logic to orchestrate scraping, comparing availability, downloading new dog photos, and sending an email of changes.

    :return:
    """

    " Set Up Parameters "

    _website_url = 'https://24petconnect.com/13168/?at=DOG'
    _directory_previous_availability = 'Output - Dog Adoption - FOHA/FOHA_Previous_Availability.json'
    _directory_historical_availability = 'Output - Dog Adoption - FOHA/FOHA_Historical_Availability.json'
    _directory_photos = 'Output - Dog Adoption - FOHA/Photos'
    _directory_credentials = '/Users/jeff/Documents/Programming/Projects/Website-Monitor/credentials.json'
    _from_email = 'nanookgolightly@gmail.com'
    _to_email = 'jeffreyfang@msn.com'
    _shelter_name = 'FOHA Animal Shelter'
    _email_subject = '🐶 {} Update!'.format(_shelter_name)

    " Run All Functions "

    while True:
        # Get the current local time
        current_time = datetime.now()

        # Define the restricted hours (midnight to 8 AM)
        if current_time.hour < 8:
            # Calculate the time until 8 AM
            next_run_time = current_time.replace(hour=8, minute=0, second=0, microsecond=0)
            if current_time.hour == 0:  # If it's midnight, wait until 8 AM
                wait_duration = (next_run_time - current_time).total_seconds()
                print(f"Current time is {current_time.strftime('%Y-%m-%d %H:%M')}. Sleeping until 8 AM...")
                time.sleep(wait_duration)  # Sleep until 8 AM
            else:  # If it's between midnight and 8 AM
                print(f"Current time is {current_time.strftime('%Y-%m-%d %H:%M')}. Sleeping until 8 AM...")
                time.sleep((next_run_time - current_time).total_seconds())  # Sleep until 8 AM
            continue  # Skip to the next iteration of the loop

        # Check pages
        _animal_count = check_pages(_website_url)
        _pages = math.floor(_animal_count / 30)

        _current_availability = []
        for _page in range(_pages + 1):
            if _page == 0:
                _current_availability += scrape_html(_website_url)
            else:
                _count = 30 * _pages
                _website_url_page_n = f'https://24petconnect.com/13168?index={_count}&at=DOG'
                _current_availability += scrape_html(_website_url_page_n)

        _previous_availability = load_previous_data(_directory_previous_availability)

        _new_dogs, _adopted_dogs = compare_dogs(_current_availability, _previous_availability)

        if _new_dogs or _adopted_dogs:
            # Save the current availability
            save_current_data(_current_availability, _directory_previous_availability)

            # Save to historical if there are new or adopted dogs
            save_historical_data(_current_availability, _directory_historical_availability)

            # Download photos for new dogs
            download_new_dog_photos(_new_dogs, _directory_photos)

            # Send email
            _creds = authenticate_gmail(_directory_credentials)
            send_email(
                _from_email, _to_email, _email_subject, _creds, _new_dogs, _adopted_dogs, _directory_photos, _website_url,
                _shelter_name)
        else:
            print(f'{datetime.now()}')
            print('No changes in availability')

        # Sleep for X minutes before the next check
        sleep_time = 30  # Minutes
        print(f"Sleeping for {sleep_time} minutes...\n")
        time.sleep(sleep_time * 60)  # Convert minutes to seconds


if __name__ == "__main__":
    # Call and execute the main() function, when you the script is run directly.
    main()


##################################################################################################################################
""" Test Area """
##################################################################################################################################


# <editor-fold desc="Description">


# # Set parameters
# website_url = 'https://24petconnect.com/13168/?at=DOG'
# directory_previous_availability = 'Output - Dog Adoption - FOHA/FOHA_Previous_Availability.json'
# directory_historical_availability = 'Output - Dog Adoption - FOHA/FOHA_Historical_Availability.json'
# directory_photos = 'Output - Dog Adoption - FOHA/Photos'
# directory_credentials = '/Users/jeff/Documents/Programming/Projects/Website-Monitor/credentials.json'
# from_email = 'nanookgolightly@gmail.com'
# to_email = 'jeffreyfang@msn.com'
# shelter_name = 'FOHA Animal Shelter'
# email_subject = '🐶 {} Update!'.format(shelter_name)
#
# # Check pages
# animal_count = check_pages('https://24petconnect.com/13168?at=DOG')
# pages = math.floor(animal_count / 30)
# type(pages)  # Int
#
# # Scrape dog information for each page
# current_availability = []
# for page in range(pages + 1):
#     if page == 0:
#         current_availability += scrape_html(website_url)
#     else:
#         count = 30 * page
#         # Website URL for additional pages
#         website_url_page_n = f'https://24petconnect.com/13168?index={count}&at=DOG'
#         current_availability += scrape_html(website_url_page_n)
#
# type(current_availability)  # List
# # print(current_availability)
#
# previous_availability = load_previous_data(directory_previous_availability)
# type(previous_availability)  # List
# # print(previous_availability)
#
# new_dogs, adopted_dogs = compare_dogs(current_availability, previous_availability)
#
# type(new_dogs)  # List
# print(new_dogs)
#
# type(adopted_dogs)  # List
# print(adopted_dogs)
#
# if new_dogs:
#     download_new_dog_photos(new_dogs, directory_photos)
#
# save_current_data(current_availability, directory_previous_availability)
# save_historical_data(current_availability, directory_historical_availability)
#
# creds = authenticate_gmail(directory_credentials)
# type(creds)  # google.oauth2.credentials.Credentials
#
# send_email(from_email, to_email, email_subject, creds, new_dogs, adopted_dogs, directory_photos, website_url, shelter_name)


# </editor-fold>


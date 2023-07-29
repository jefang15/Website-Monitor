"""
July 28, 2023

Scrapes the Fairfax County Animal Shelter site (24petconnect.com) for dogs available for adoption and alerts me when a new dog is
available or was adopted. Prevents needing to frequently and manually visit and refresh the page and being able to identify
what has changed.
"""


import requests
from datetime import datetime
from bs4 import BeautifulSoup
from lxml.html.clean import Cleaner
import pandas as pd
# from tabulate import tabulate
import glob
# from twilio.rest import Client
import smtplib
from email.message import EmailMessage
from password import email, email_password
import time



""" Current Dog Availability """


def scrape_html(url):
    """

    Scrapes URL with dogs available for adoption, and creates a cleaned string with HTML content that can be used to create a DF
    in the next step. This also subsets the HTML content to start where the dogs available for adoption are listed.

    An HTML version (BeautifulSoup object) can be returned as well, if desired.

    :param url: URL for dog adoption site on 24petconnect.com for Fairfax County Animal Shelter
    :return: a string of HTML content
    """

    columns = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.95 Safari/537.36',
        'Pragma': 'no-cache', 'Cache-Control': 'no-cache'}

    # Send HTTP GET request to URL
    response = requests.get(url, headers=columns)

    def process_html(string):

        soup = BeautifulSoup(string, features='lxml')
        soup.prettify()

        # Remove script tags
        for s in soup.select('script'):
            s.extract()

        # Remove meta tags
        for s in soup.select('meta'):
            s.extract()

        # convert to a string, remove '\r', and return
        return str(soup).replace('\r', '')

    html_processed = process_html(response.text)
    # type(html_processed)  # Str
    # len(html_processed)  # 144,615

    def sanitize(dirty_html):
        cleaner = Cleaner(
            page_structure=True,
            scripts=True,
            meta=True,
            embedded=True,
            links=True,
            style=True,
            processing_instructions=True,
            inline_style=True,
            javascript=True,
            comments=True,
            frames=True,
            forms=True,
            annoying_tags=True,
            remove_unknown_tags=True,
            safe_attrs_only=True,
            safe_attrs=frozenset(['src', 'color', 'href', 'title', 'class', 'name', 'id']),
            remove_tags=('html', 'body', 'p', 'span', 'font', 'div', 'br')
            )

        return cleaner.clean_html(dirty_html)

    html_sanitized = sanitize(html_processed)
    # type(html_sanitized)  # Str
    # len(html_sanitized)  # 42,273

    # Truncate beginning of HTML
    index_start = html_sanitized.find('Animals: ')
    html_text = html_sanitized[index_start:]
    # print(html_text)
    # type(html_text)  # Str
    # len(html_text)  # 10,850

    # Turn HTML to BS4 object (only use this if you want to save text)
    # html_bs = BeautifulSoup(html_text, 'lxml')
    # print(html_bs)
    # type(html_bs)  # BS4
    # print(html_bs)

    return html_text


def create_dataframe_from_html(html, current_time):
    """

    Creates a DataFrame from the HTML content with each attribute as a separate column for each dog.

    :param html: HTML string output from the scrape_html function
    :param current_time: Current datetime
    :return: count of number of dogs available (proxy for number of webpages that need scraping, and cleaned DF of dog attributes)
    """

    # Create list from HTML string
    list_text = [i.strip() for i in html.splitlines()]
    # type(list_text)  # List
    # len(list_text)  # 1,224

    # Create DataFrame from list
    df = pd.DataFrame(list_text, columns=['Text'])
    # len(df)  # 1,224

    # Drop NAN rows
    df2 = df[df['Text'] != ''].copy()
    # len(df2)  # 479

    df2.reset_index()

    # Determine number of dogs available (if more than 30 dogs, there are two pages to scrape)
    text_animals_available = df2['Text'][0]
    animals_available = int(text_animals_available.split(' - ')[1].split('</h3>')[0].split(' of ')[1])

    for index, row in df2.iterrows():

        # Store a single index to write all attributes to that belong to the same dog
        if row['Text'] == 'Name:':
            index_save = index

        # Fill in Name
        if row['Text'] == 'Name:':
            df2.loc[index_save, 'Name'] = df2.loc[index + 1, 'Text']

        # Fill in Gender
        if row['Text'] == 'Gender:':
            df2.loc[index_save, 'Gender'] = df2.loc[index + 1, 'Text']

        # Fill in Breed
        if row['Text'] == 'Breed:':
            df2.loc[index_save, 'Breed'] = df2.loc[index + 1, 'Text']

        # Fill in Animal Type
        if row['Text'] == 'Animal type:':
            df2.loc[index_save, 'Animal Type'] = df2.loc[index + 1, 'Text']

        # Fill in Age
        if row['Text'] == 'Age:':
            df2.loc[index_save, 'Age'] = df2.loc[index + 1, 'Text']

        # Fill in Brought to the Shelter
        if row['Text'] == 'Brought to the shelter:':
            df2.loc[index_save, 'Brought to Shelter'] = df2.loc[index + 1, 'Text']

        # Fill in Located At
        if row['Text'] == 'Located at:':
            df2.loc[index_save, 'Location'] = df2.loc[index + 1, 'Text']

    # Fill in Image (done separately, since this attribute appears after the index associated with the dog's name)
    df2.loc[df2['Text'].str.contains('<img id="AnimalImage_'), 'Image'] = df2['Text']
    df2['Image'].ffill(inplace=True)

    # Drop rows where Name is NAN
    df3 = df2[df2['Name'].notna()].copy()
    # len(df3)  # 30

    # Finish cleaning URLs in Image column (doesn't work until NANs are taken care of)
    df3.loc[df3['Image'].str.contains(' src="'), 'Image'] = df3['Image'].str.split(' src="').str[1].str.split('">').str[0]
    df3.reset_index(drop=True, inplace=True)
    # print(tabulate(df3.head(10), tablefmt='psql', numalign='right', headers='keys', showindex=False))

    # Create ID column from latter part of Name
    df3['ID'] = df3['Name'].str.extract('(\d*\.?\d+)', expand=True)

    # Clean and remove ID from Name column
    df3.loc[df3['Name'].str.contains(' \\([0-9]'), 'Name'] = df3['Name'].str.split(' \\([0-9]').str[0]
    df4 = df3.applymap(lambda x: str(x).replace('&amp;', '&'))

    # Set Date Types
    # print(df4.dtypes)
    df4['Brought to Shelter'] = pd.to_datetime(df4['Brought to Shelter'])
    df4['ID'] = df4['ID'].astype('int32')

    # Add scraped DateTime to DF
    df4['Scrape Datetime'] = current_time

    # print(df4.columns)
    df5 = df4[['ID', 'Name', 'Gender', 'Breed', 'Age', 'Brought to Shelter', 'Location', 'Image', 'Scrape Datetime']].copy()
    # print(df5.dtypes)
    # print(tabulate(df5, tablefmt='psql', numalign='right', headers='keys', showindex=True))

    return animals_available, df5


def concat_additional_pages(availability, url2, df1, current_time):
    """

    Scrapes the second page of the dog adoption site, if there is one, using the scrape_html function, creates a separate
    cleaned DF, and then concatenates the two cleaned DFs/pages together. If there is only one page, this function has no effect.

    :param availability: number of dogs available on the first page, if there are more than 30 dogs then there are at least 2
    pages of content
    :param url2: URL of second page of dogs on 24petconnect.com for Fairfax County Animal Shelter
    :param df1: cleaned DF (output from create_dataframe_from_html function) to be concatenated as needed
    :param current_time: Current datetime to label and export results
    :return:
    """

    if availability > 30:

        # Scrape second page
        html_text2 = scrape_html(url2)

        # Turn second page to DF
        _, df2 = create_dataframe_from_html(html_text2, current_time)

        # Concatenate each DataFrame representing each page
        df_concat = pd.concat([df1, df2])

        # Create counter
        df_concat['Counter'] = range(1, len(df_concat) + 1)

        # Keep only columns needed to save and to compare with previous iterations
        df_concat2 = df_concat[[
            'Counter',
            'ID',
            'Name',
            # 'Gender',
            # 'Breed',
            # 'Age',
            # 'Brought to Shelter',
            # 'Location',
            'Image',
            'Scrape Datetime']].copy()

        return df_concat2


""" Compare Availability """


def compare_availability(df_current):
    """

    Identifies how many, and which, dogs are either newly available for adoption or were adopted since the last check.

    :param df_current: List and information of dogs in the latest scrape of adoption site
    :return: Tells whether there are any changes in availability or not, and how many
    """

    # Reference most recent dog availability spreadsheet
    list_past_files = glob.glob('Output - Spreadsheets/*.xlsx')
    list_past_files.sort(reverse=False)
    latest_file = list_past_files[-1]
    df_previous = pd.read_excel(latest_file)

    list_current_dogs = df_current['ID'].to_list()
    list_previous_dogs = df_previous['ID'].to_list()

    set_current_dogs = set(list_current_dogs)
    set_previous_dogs = set(list_previous_dogs)

    # Determine if there is a change in availability
    if set_current_dogs == set_previous_dogs:
        diff = 0
        list_content = []
        return diff, list_content

    else:
        # Blank list to document any new and/or adopted dogs. This content will end up in the email or text message body.
        list_content = []

        # New dogs' IDs
        set_dogs_new = set_current_dogs - set_previous_dogs  # New dogs

        list_content.append(str(len(set_dogs_new)) + ' New Dogs')
        list_content.append('')

        # Gather information about new dogs
        df_new_dogs = df_current[df_current['ID'].isin(set_dogs_new)].copy()

        for index_new, row_new in df_new_dogs.iterrows():
            list_content.append(row_new['Name'])
            list_content.append(row_new['Image'])
            list_content.append('')

        # Adopted dogs' IDs
        set_dogs_adopted = set_previous_dogs - set_current_dogs  # Dogs that were adopted

        list_content.append(str(len(set_dogs_adopted)) + ' Adopted Dogs')
        list_content.append('')

        # Gather information about adopted dogs
        df_adopted_dogs = df_previous[df_previous['ID'].isin(set_dogs_adopted)].copy()

        for index_adopted, row_adopted in df_adopted_dogs.iterrows():
            list_content.append(row_adopted['Name'])
            list_content.append(row_adopted['Image'])
            list_content.append('')

        diff = len(set_dogs_new) + len(df_adopted_dogs)

        return diff, list_content


""" Send Notification """


# <editor-fold desc="Text Message Notification">
""" Text Results """

# TWILIO_ACCOUNT_SID = 'ACfde007403d9289a8f9d137a4707ea369'
# TWILIO_AUTH_TOKEN = '241e6a037f158d7cd2073836a8d9d5e7'
# TWILIO_PHONE_SENDER = '+18664481495'
# TWILIO_PHONE_RECIPIENT = '+12068980303'
#
# alert_str = 'test'
#
#
# def send_text_alert(alert_str):
#
#     client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
#
#     message = client.messages.create(
#         to=TWILIO_PHONE_RECIPIENT,
#         from_=TWILIO_PHONE_SENDER,
#         body=alert_str)
#
#
# send_text_alert(alert_str)
# print('Sent Text')


# TODO: This notification method needs a new phone number from Twilio every 30 days? or trial expires after 30 days?
# </editor-fold>


def send_email(list_content):
    """

    Only sends an email if there is change in adoptable dog availability. Email and password are stored as variables in a
    separate password.py file (and imported a la a package at the top) in the same directory that is not version controlled.

    :param list_content: List of text from compare_availability function to include in notification message
    :return: If there's a change in availability, email me that change
    """

    # Form message
    msg = EmailMessage()
    msg['Subject'] = 'Fairfax County Animal Shelter Update!'
    msg['From'] = email
    msg['To'] = email
    msg.set_content('\r\n'.join(list_content))

    with smtplib.SMTP('smtp.outlook.com', 587) as server:
        server.ehlo()
        server.starttls()
        server.login(email, email_password)
        server.send_message(msg)
        # print('Email sent')



""" Run Infinite Loop """


# Set URL
url_page1 = 'https://24petconnect.com/PP4352?at=DOG'
url_page2 = 'https://24petconnect.com/PP4352?index=30&at=DOG'


# Set frequency to run script
minutes = 5
seconds = 60
delay_seconds = minutes * seconds  # Runs every 10 minutes


def main(url1, url2, delay):

    while True:

        try:

            # Current DateTime for exporting and naming files with current timestamp
            now = datetime.now()

            html_text_clean = scrape_html(url1)
            dog_availability, df_dog = create_dataframe_from_html(html_text_clean, now)
            df_current_dogs = concat_additional_pages(dog_availability, url2, df_dog, now)

            num_changes, list_to_message = compare_availability(df_current_dogs)
            # for i in list_to_message:
            #     print(i)

            now_text = now.strftime('%Y-%m-%d %H-%M-%S')
            df_current_dogs.to_excel('Output - Spreadsheets/Fairfax County Animal Shelter {}.xlsx'.format(now_text), index=False)

            if num_changes == 0:
                print(
                    str(now.strftime('%Y-%m-%d %I:%M %p')) +
                    ' - No Change (To break loop, press Ctrl + C in Console or Cmd + F2 in Terminal)')
                pass
            else:
                print(
                    str(now.strftime('%Y-%m-%d %I:%M %p')) +
                    ' - Change in Availability!')
                send_email(list_to_message)

        except:
            print('Error')

        time.sleep(delay)


main(url_page1, url_page2, delay_seconds)

# Guide: https://medium.com/swlh/tutorial-creating-a-webpage-monitor-using-python-and-running-it-on-a-raspberry-pi-df763c142dac

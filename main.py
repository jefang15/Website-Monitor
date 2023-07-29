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


# Set URL
url_page1 = 'https://24petconnect.com/PP4352?at=DOG'
url_page2 = 'https://24petconnect.com/PP4352?index=30&at=DOG'

# Current DateTime for exporting and naming files with current timestamp
now = datetime.now()


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


html_text_clean = scrape_html(url_page1)


def create_dataframe_from_html(html):
    """

    Creates a DataFrame from the HTML content with each attribute as a separate column for each dog.

    :param html: HTML string output from the scrape_html function
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
    # print(tabulate(df2.head(20), tablefmt='psql', numalign='right', headers='keys', showindex=False))
    # print(tabulate(df2.tail(20), tablefmt='psql', numalign='right', headers='keys', showindex=False))

    # Determine number of dogs available (if more than 30 dogs, there are two pages to scrape)
    text_animals_available = df2['Text'][0]
    animals_available = int(text_animals_available.split(' - ')[1].split('</h3>')[0].split(' of ')[1])
    # print(animals_available)

    # df2.loc[df2['Text'].str.contains('Animals: '), 'Availability on Page'] = df2['Text'].str.split(' - ').str[1].str.split(
    #     '</h3>').str[0].str.split(' of ').str[0]
    # df2.loc[df2['Text'].str.contains('Animals: '), 'Availability Total'] = df2['Text'].str.split(' - ').str[1].str.split(
    #     '</h3>').str[0].str.split(' of ').str[1]
    # print(tabulate(df2.head(10), tablefmt='psql', numalign='right', headers='keys', showindex=False))

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

    # print(tabulate(df2.head(10), tablefmt='psql', numalign='right', headers='keys', showindex=False))

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

    # Current DateTime for exporting and naming files with current timestamp
    df4['Scrape Datetime'] = now

    # print(df4.columns)
    df5 = df4[['ID', 'Name', 'Gender', 'Breed', 'Age', 'Brought to Shelter', 'Location', 'Image', 'Scrape Datetime']].copy()
    # print(df5.dtypes)
    # print(tabulate(df5, tablefmt='psql', numalign='right', headers='keys', showindex=True))

    return animals_available, df5


dog_availability, df_dog = create_dataframe_from_html(html_text_clean)


def concat_additional_pages(availability, url2, df1):
    """

    Scrapes the second page of the dog adoption site, if there is one, using the scrape_html function, creates a separate
    cleaned DF, and then concatenates the two cleaned DFs/pages together. If there is only one page, this function has no effect.

    :param availability: number of dogs available on the first page, if there are more than 30 dogs then there are at least 2
    pages of content
    :param url2: URL of second page of dogs on 24petconnect.com for Fairfax County Animal Shelter
    :param df1: cleaned DF (output from create_dataframe_from_html function) to be concatenated as needed
    :return:
    """

    if availability > 30:
        print('More than one page')

        # Scrape second page
        html_text2 = scrape_html(url2)

        # Turn second page to DF
        _, df2 = create_dataframe_from_html(html_text2)

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

    else:
        print('Just one page')


df_current_dogs = concat_additional_pages(dog_availability, url_page2, df_dog)

# Convert current datetime to custom string format
now_text = now.strftime('%Y-%m-%d %H-%M-%S')
# print(now_text)

# print(tabulate(df_current_dogs, tablefmt='psql', numalign='right', headers='keys', showindex=False))
df_current_dogs.to_excel('Output - Spreadsheets/Fairfax County Animal Shelter {}.xlsx'.format(now_text), index=False)


""" Compare Dog Availability """

# Reference most recent dog availability spreadsheet
list_past_files = glob.glob('Output - Spreadsheets/*.xlsx')
# len(list_past_files)
latest_file = list_past_files[-1]

df_previous_dogs = pd.read_excel(latest_file)

list_current_dogs = df_current_dogs['ID'].to_list()
list_previous_dogs = df_previous_dogs['ID'].to_list()


# Blank list whose contents will end up in the email/text message body
list_to_message = []


# Identify new dogs
count_new_dogs = 0
list_new_dogs = []

for dog in list_current_dogs:
    if dog in list_previous_dogs:
        pass
    else:
        list_new_dogs.append(dog)
        count_new_dogs += 1

if count_new_dogs != 0:

    # Number of new dogs for adoption
    list_to_message.append(str(count_new_dogs) + ' New Dogs')
    list_to_message.append('')

    df_new_dogs = df_current_dogs[df_current_dogs['ID'].isin(list_new_dogs)]

    # New dogs for adoption info
    for index_new, row_new in df_new_dogs.iterrows():
        list_to_message.append(row_new['Name'])
        list_to_message.append(row_new['Image'])
        list_to_message.append('')


# Identify adopted dogs
count_adopted_dogs = 0
list_adopted_dogs = []

for dog in list_previous_dogs:
    if dog in list_current_dogs:
        pass
    else:
        list_adopted_dogs.append(dog)
        count_adopted_dogs += 1

if count_adopted_dogs != 0:

    # Number of adopted dogs
    list_to_message.append('Adopted Dogs: ' + str(count_adopted_dogs))
    list_to_message.append('')

    df_adopted_dogs = df_previous_dogs[df_previous_dogs['ID'].isin(list_adopted_dogs)]

    # Adopted dogs info
    for index_adopted, row_adopted in df_adopted_dogs.iterrows():
        list_to_message.append(row_adopted['Name'])
        list_to_message.append(row_adopted['Image'])
        list_to_message.append('')


# for i in list_to_message:
#     print(i)


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


""" Email Results - SMTP """


def send_email(count_new, count_removed):
    """
    Only sends an email if there is change in adoptable dog availability. Email and password are stored as variables in a
    separate password.py file (and imported a la a package at the top) in the same directory that is not version controlled.
    :param count_new: Number of new dogs available for adoption since last check
    :param count_removed: Number of dogs no longer available since last check
    :return: If new activity, send me an email
    """

    if count_new == 0 and count_removed == 0:
        pass
    else:
        # Form message
        msg = EmailMessage()
        msg['Subject'] = 'Fairfax County Animal Shelter Update!'
        msg['From'] = email
        msg['To'] = email
        msg.set_content('\r\n'.join(list_to_message))

        with smtplib.SMTP('smtp.outlook.com', 587) as server:
            server.ehlo()
            server.starttls()
            server.login(email, email_password)
            server.send_message(msg)
            print('Email sent')


send_email(count_new_dogs, count_adopted_dogs)


# Guide: https://medium.com/swlh/tutorial-creating-a-webpage-monitor-using-python-and-running-it-on-a-raspberry-pi-df763c142dac

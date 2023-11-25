"""
July 28, 2023

Scrapes the Fairfax County Animal Shelter site (24petconnect.com) for dogs available for adoption and alerts me when a new dog is
available or was adopted. Prevents needing to frequently refresh the page and manually identifying changes.
"""


import requests
from datetime import datetime
from bs4 import BeautifulSoup
from lxml.html.clean import Cleaner
import pandas as pd
import glob
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from password import email, email_password
import time
import logging
import sys
from tabulate import tabulate


def scrape_html(url: str):
    """
    Scrapes URL with dogs available for adoption, and creates a cleaned string with HTML content that can be used to create a DF
    in the next step. This also subsets the HTML content to start where the dogs available for adoption are listed.

    An HTML version (BeautifulSoup object) can be returned as well, if desired.

    :param url: URL for dog adoption site on 24petconnect.com for Fairfax County Animal Shelter
    :return: a string of HTML content
    """

    # Connect to URL
    columns = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.95 Safari/537.36',
        'Pragma': 'no-cache', 'Cache-Control': 'no-cache'}

    # Send HTTP GET request to URL
    response = requests.get(url, headers=columns)

    # Clean HTML content
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

    # Truncate beginning of HTML
    index_start = html_sanitized.find('<li>') + 4  # Gets rid of the 4 characters in <li>
    html_text = html_sanitized[index_start:]
    type(html_text)  # Str

    return html_text


def create_dataframe_from_html(html: str, current_time: datetime):
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

    df2.reset_index(inplace=True, drop=True)

    # Create new columns for each data point and initialize them with None
    df2['Image'] = None
    df2['ID'] = None
    df2['Name'] = None
    df2['Gender'] = None
    df2['Breed'] = None
    df2['Age'] = None
    df2['Brought to Shelter'] = None
    df2['Location'] = None

    for index, row in df2.iterrows():
        # Store one index per dog and write all attributes associated with that dog to the index in question
        if ' src="' in row['Text']:
            index_save = index

        # Save information based on row distance from ' src="'

        # Fill in Image
        df2.loc[index_save, 'Image'] = df2.loc[index_save, 'Text']

        # Fill in Name
        if index == index_save + 1:
            df2.loc[index_save, 'Name'] = df2.loc[index, 'Text']

        # Fill in ID
        if index == index_save + 2:
            df2.loc[index_save, 'ID'] = df2.loc[index, 'Text']

        # Fill in Gender
        if index == index_save + 4:
            df2.loc[index_save, 'Gender'] = df2.loc[index, 'Text']

        # Fill in Breed
        if index == index_save + 5:
            df2.loc[index_save, 'Breed'] = df2.loc[index, 'Text']

        # Fill in Age
        if index == index_save + 6:
            df2.loc[index_save, 'Age'] = df2.loc[index, 'Text']

    df3 = df2[~df2['Image'].isna()].copy()

    # Clean text
    df3.loc[df3['Image'].str.contains(' src="'), 'Image'] = df3['Image'].str.split(' src="').str[1].str.split('"></a>').str[0]
    df3.loc[df3['Name'].str.contains('spv8bws1svbei2rr8u3h6cg32yx4eywg4il3e3rk8wcjghn2pg">'), 'Name'] = df3['Name'].str.split(
        'spv8bws1svbei2rr8u3h6cg32yx4eywg4il3e3rk8wcjghn2pg">').str[1].str.split('</a>').str[0]

    # # Drop rows where Gender is NAN (proxy for when a row doesn't actually represent a unique dog and is just HTML filler)
    df4 = df3[df3['Gender'].notna()].copy()

    del df4['Text']

    # Create counter
    df4['Counter'] = range(1, len(df4) + 1)

    # Set Date Types
    # print(df4.dtypes)
    df4['ID'] = df4['ID'].astype('int32')
    df4['Counter'] = df4['Counter'].astype('int8')

    # Add scraped DateTime to DF
    df4['Scrape Datetime'] = current_time

    # print(df4.columns)
    df5 = df4[[
        'Counter', 'ID', 'Name', 'Gender', 'Breed', 'Age', 'Brought to Shelter', 'Location', 'Image', 'Scrape Datetime']].copy()
    # print(df5.dtypes)

    return df5


def compare_availability(folder_spreadsheets: str, folder_photos: str, df_current):
    """
    Identifies how many, and which, dogs are either newly available for adoption or were adopted since the last check.

    :param folder_spreadsheets: Folder path to location where spreadsheets are saved
    :param folder_photos: Folder path to location where images are saved
    :param df_current: List and information of dogs in the latest scrape of adoption site
    :return: 2 separate DataFrames, one for new dogs and one for adopted dogs, if applicable
    """

    # Previous Availability
    list_past_files = glob.glob('{}/*.xlsx'.format(folder_spreadsheets))
    list_past_files.sort(reverse=False)
    latest_file = list_past_files[-1]
    df_previous = pd.read_excel(latest_file)

    list_current_dogs = df_current['ID'].to_list()
    list_previous_dogs = df_previous['ID'].to_list()

    set_current_dogs = set(list_current_dogs)
    set_previous_dogs = set(list_previous_dogs)

    # Compare Current and Previous Availability
    if set_current_dogs == set_previous_dogs:  # If no change
        df_new = pd.DataFrame()
        df_adopted = pd.DataFrame()
        return df_new, df_adopted

    else:  # If change

        # Compile Information About New Dogs
        # Flag new dogs' IDs
        set_new = set_current_dogs - set_previous_dogs  # New dogs

        # Gather information about new dogs
        df_new = df_current[df_current['ID'].isin(set_new)].copy()

        for index_new, row_new in df_new.iterrows():
            # Save new dog photos
            image_url_new = row_new['Image']
            r = requests.get(image_url_new, allow_redirects=True)
            with open('{}/{}.png'.format(folder_photos, row_new['ID']), 'wb') as f:
                f.write(r.content)

        # Compile Information About Adopted Dogs
        # Flag adopted dogs' IDs
        set_adopted = set_previous_dogs - set_current_dogs  # Dogs that were adopted

        # Gather information about adopted dogs
        df_adopted = df_previous[df_previous['ID'].isin(set_adopted)].copy()

        for index_adopted, row_adopted in df_adopted.iterrows():
            # Save adopted dogs' photos locally
            image_url_adopted = row_adopted['Image']
            r = requests.get(image_url_adopted, allow_redirects=True)
            with open('{}/{}.png'.format(folder_photos, row_adopted['ID']), 'wb') as f:
                f.write(r.content)

        return df_new, df_adopted


def send_email(shelter_name: str, folder_photos: str, df_new, df_adopted, current_time: datetime):
    """
    Only sends an email if there is change in adoptable dog availability. Email and password are stored as variables in a
    separate password.py file (and imported á la a package at the top) in the same directory that is not version controlled.

    Emojis at: https://emojipedia.org

    :param shelter_name: Name of dog shelter
    :param folder_photos: DF of newly available dogs
    :param df_new: DF of newly available dogs
    :param df_adopted: DF of adopted dogs
    :param current_time: Time that website was scraped, to include as text at end of email body
    :return: If there's a change in availability, email me that change
    """

    # Form Email Parameters
    msg = MIMEMultipart('multipart')  # To support mix of content types
    msg['From'] = email
    msg['To'] = email
    msg['Subject'] = '🐶 {} Update!'.format(shelter_name)

    if len(df_new) > 0 and len(df_adopted) > 0:
        msg.attach(MIMEText('<b>Summary: new and adopted dogs</b><br></br>', 'html'))
    else:
        pass

    # Form Email Body - New Dogs
    if len(df_new) > 0:

        # Count of new dogs
        if len(df_new) == 1:  # Only difference in this if/else is whether to print dog (singular) vs dogs (plural)
            new_dog_count = '<b>' + '{} New Dog'.format(len(df_new)) + '</b></font>' + '<br></br>'  # Bold and line break (HTML)
            # text = '<font face="Courier New, Courier, monospace">' + 'text' + '</font>'  # Sample font change
            msg.attach(MIMEText(new_dog_count, 'html'))
        else:
            new_dog_count = '<b>' + '{} New Dogs'.format(len(df_new)) + '</b></font>' + '<br></br>'
            msg.attach(MIMEText(new_dog_count, 'html'))

        # Fill email body with content
        for index_new, row_new in df_new.iterrows():

            # Name
            msg.attach(MIMEText('<b>{}</b>'.format(row_new['Name']), 'html'))

            # Age
            msg.attach(MIMEText('  |  {}'.format(row_new['Age']), 'plain'))

            # Gender
            msg.attach(MIMEText('  |  {}'.format(row_new['Gender']), 'plain'))

            # Breed
            msg.attach(MIMEText('  |  {}'.format(row_new['Breed']), 'plain'))

            # Photo
            with open('{}/{}.png'.format(folder_photos, row_new['ID']), 'rb') as f:
                image_data = MIMEImage(f.read(), _subtype='png')
                msg.attach(image_data)
                msg.attach(MIMEText('<br></br>', 'html'))

    # Form Email Body - Adopted Dogs
    if len(df_adopted) > 0:

        # Count of adopted dogs
        if len(df_adopted) == 1:
            adopted_dog_count = '<b>' + '{} Adopted Dog'.format(len(df_adopted)) + '</b></font>' + '<br></br>'
            msg.attach(MIMEText(adopted_dog_count, 'html'))
        else:
            adopted_dog_count = '<b>' + '{} Adopted Dogs'.format(len(df_adopted)) + '</b></font>' + '<br></br>'
            msg.attach(MIMEText(adopted_dog_count, 'html'))

        # Fill email body with content
        for index_adopted, row_adopted in df_adopted.iterrows():

            # Name
            msg.attach(MIMEText('<b>{}</b>'.format(row_adopted['Name']), 'html'))

            # Age
            msg.attach(MIMEText('  |  {}'.format(row_adopted['Age']), 'plain'))

            # Gender
            msg.attach(MIMEText('  |  {}'.format(row_adopted['Gender']), 'plain'))

            # Breed
            msg.attach(MIMEText('  |  {}'.format(row_adopted['Breed']), 'plain'))

            # Photo
            with open('{}/{}.png'.format(folder_photos, row_adopted['ID']), 'rb') as f:
                image_data = MIMEImage(f.read())
                msg.attach(image_data)
                msg.attach(MIMEText('<br></br>', 'html'))

    # Add Time to Body
    time_for_email = current_time.strftime('%Y-%m-%d %H:%M %p')
    msg.attach(MIMEText(time_for_email + '<br>', 'html'))

    # Add Website Link to Body
    homepage = MIMEText('https://ws.petango.com/webservices/adoptablesearch/wsAdoptableAnimals2.aspx?species=Dog&gender=A&agegroup=All&location=&site=&onhold=A&orderby=Name&colnum=3&css=&authkey=spv8bws1svbei2rr8u3h6cg32yx4eywg4il3e3rk8wcjghn2pg&recAmount=&detailsInPopup=No&featuredPet=Include&stageID=', 'html')
    msg.attach(homepage)

    # Send Email
    with smtplib.SMTP('smtp.outlook.com', 587) as smtp:
        smtp.ehlo()
        smtp.starttls()
        smtp.login(email, email_password)
        smtp.send_message(msg)


def main(shelter_name: str, folder_spreadsheets: str, folder_photos: str, file_name: str, url: str):
    """
    Scrapes dog adoption site every 5 minutes during the day and emails any changes.

    :param shelter_name: Name of dog shelter
    :param folder_spreadsheets: Folder path to location where spreadsheets are saved
    :param folder_photos: Folder path to location where images are saved
    :param file_name: Name of Python script (without any file types)
    :param url: Webpage of dog adoption site
    :return: Sends email when there is new or adopted dog and includes notable information.
    """

    # Write to log
    logging.basicConfig(
        filename='Logs/' + file_name + '.log',
        format='%(asctime)s   %(module)s   %(levelname)s   %(message)s',
        datefmt='%Y-%m-%d %I:%M:%S %p',
        filemode='a',  # Append to log (rather than, 'w', over-wright)
        level=logging.INFO)  # Set minimum level to INFO and above

    # Print log in console
    formatter = logging.Formatter(
        fmt='%(asctime)s  %(module)s  %(levelname)s  %(message)s',
        datefmt='%Y-%m-%d %I:%M:%S %p')
    screen_handler = logging.StreamHandler(stream=sys.stdout)  # stream=sys.stdout is similar to normal print
    screen_handler.setFormatter(formatter)
    logging.getLogger().addHandler(screen_handler)

    logging.info('Started running script')

    while True:  # Only runs after 8 AM and before 10 PM (shelter's hours are roughly 11 AM - 7 PM, depending on day)

        # Current DateTime for exporting and naming files with current timestamp
        now = datetime.now()

        try:  # Accounts for potential network connectivity issues?

            html_text_clean = scrape_html(url)
            df_dog = create_dataframe_from_html(html_text_clean, now)

            df_dogs_new, df_dogs_adopted = compare_availability(folder_spreadsheets, folder_photos, df_dog)

            if df_dogs_new.empty & df_dogs_adopted.empty:
                print(str(
                    now.strftime('%Y-%m-%d %I:%M:%S %p'))
                      + '  {}  INFO  No Change'.format(file_name))

                # logging.info('No change')

                pass
            else:
                # print(str(now.strftime('%Y-%m-%d %I:%M %p')) + ' - Change in Availability!')

                # logging.info('Change in availability!')

                if df_dogs_new.empty is False:
                    for _, row in df_dogs_new.iterrows():
                        logging.info('New dog: %s (ID %s)', row['Name'], row['ID'])

                if df_dogs_adopted.empty is False:
                    for _, row in df_dogs_adopted.iterrows():
                        logging.info('Adopted dog: %s (ID %s)', row['Name'], row['ID'])

                # Save to Excel
                now_text = now.strftime('%Y-%m-%d %H-%M-%S')
                df_dog.to_excel(
                    '{}/{} {}.xlsx'.format(folder_spreadsheets, shelter_name, now_text), index=False)

                send_email(shelter_name, folder_photos, df_dogs_new, df_dogs_adopted, now)
        except:
            print(str(now.strftime('%Y-%m-%d %I:%M:%S %p')) + ' - Unable to connect to or scrape website')

            logging.error('Unable to connect to or scrape website')

        # Time delay
        # Having this after the main code makes sure that the code runs at least once for testing even if it's during off hours
        hour_start = 8  # 8 AM - Time of day to start running script (script stops at midnight)

        if int(now.strftime('%H')) >= hour_start:  # If it's after 8 AM and before midnight, loop and run code every minute
            delay_sec = 60 * 10  # Run every 10 minutes
        else:  # If it's after midnight and before 8 AM, calculate the number of seconds until 8 AM and set that as the delay
            diff_hour = hour_start - int(now.strftime('%H')) - 1
            diff_min = 60 - int(now.strftime('%M'))
            delay_sec = 60 * (diff_min + (diff_hour * 60))

        time.sleep(delay_sec)


""" ########################################################################################################################## """
""" Scrape Website """
""" ########################################################################################################################## """


# <editor-fold desc="Troubleshoot">
# _now = datetime.now()
#
# _html = scrape_html('https://ws.petango.com/webservices/adoptablesearch/wsAdoptableAnimals2.aspx?species=Dog&gender=A&agegroup=All&location=&site=&onhold=A&orderby=Name&colnum=3&css=&authkey=spv8bws1svbei2rr8u3h6cg32yx4eywg4il3e3rk8wcjghn2pg&recAmount=&detailsInPopup=No&featuredPet=Include&stageID=')
# print(_html)
#
# _df_html = create_dataframe_from_html(_html, _now)
# # print(_count)
# print(tabulate(_df_html, tablefmt='psql', numalign='right', headers='keys', showindex=False))
#
# _df_new, _df_adopted = compare_availability(
#     'Output - Fairfax Shelter Spreadsheets', 'Output - Fairfax Shelter Photos', _df_html)
# print(tabulate(_df_new, tablefmt='psql', numalign='right', headers='keys', showindex=False))
# print(tabulate(_df_adopted, tablefmt='psql', numalign='right', headers='keys', showindex=False))
#
# send_email(
#     'Fairfax County Animal Shelter', 'Output - Fairfax Shelter Photos', _df_new, _df_adopted, _now)
# </editor-fold>


# Set URL
url_page = 'https://ws.petango.com/webservices/adoptablesearch/wsAdoptableAnimals2.aspx?species=Dog&gender=A&agegroup=All&location=&site=&onhold=A&orderby=Name&colnum=3&css=&authkey=spv8bws1svbei2rr8u3h6cg32yx4eywg4il3e3rk8wcjghn2pg&recAmount=&detailsInPopup=No&featuredPet=Include&stageID='


main(
    'Fairfax County Animal Shelter',
    'Output - Fairfax Shelter Spreadsheets',
    'Output - Fairfax Shelter Photos',
    'DogAdoption_FairfaxCountyAnimalShelter',
    url_page)


# Guide: https://medium.com/swlh/tutorial-creating-a-webpage-monitor-using-python-and-running-it-on-a-raspberry-pi-df763c142dac

"""
August 1, 2023

Scrapes the Vyne Apartment site (https://livevyne.com) for unit availability alerts me when there is a new unit, leased unit,
or a change in price. Prevents needing to frequently and manually visit and refresh the page.
"""


from selenium.webdriver.chrome.options import Options
from selenium import webdriver
from bs4 import BeautifulSoup
import pandas as pd
from tabulate import tabulate
from datetime import datetime
import glob
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from password import email, email_password
import smtplib
import time
import logging
import sys


def scrape_html_selenium(url: str):
    """
    Scrapes HTML content from a given floor plan's URL

    :param url: URL
    :return: Cleaned HTML string containing key floor plan and unit information (such as units available, price, etc.)
    """

    # Set the options for the Chromium browser
    chromium_options = Options()
    chromium_options.add_argument('--headless=new')

    # Set the driver for the Chromium browser
    chrome_driver = webdriver.Chrome(options=chromium_options)

    # Navigate to your website
    chrome_driver.get(url)

    # Get HTML from URL
    html = chrome_driver.page_source

    # chrome_driver.quit()  # Don't run until HTML is created

    # Clean HTML
    html_soup = BeautifulSoup(html, features='lxml').text  # String
    # len(html_soup)  # 7,822

    # Truncate beginning and end of HTML string
    index_start = html_soup.find('Available Units')
    html_soup = html_soup[index_start:]
    # len(html_soup)  # 4,054

    index_end = html_soup.find('Have a question?')
    html_soup = html_soup[:index_end]
    # len(html_soup)  # 274

    return html_soup


def create_dataframe_from_html(floor_plan, html_str: str, current_time):
    """
    Converts the HTML string of key unit information to a DF.

    :param floor_plan: Floor plan type to add to DF column
    :param html_str: Cleaned HTML of floor plan website
    :param current_time: Scraped datetime to include in DataFrame
    :return: DataFrame containing Unit, Price, Date Available columns
    """

    # Create list from HTML string
    list_html_text = [i.strip() for i in html_str.splitlines()]
    # type(list_text)  # List
    # len(list_text)  # 63

    # Create DataFrame from list
    df = pd.DataFrame(list_html_text, columns=['Unit'])
    # len(df)  # 63

    # Drop NAN rows
    df2 = df[df['Unit'] != ''].copy()
    # len(df2)  # 12

    df2.reset_index(drop=True, inplace=True)

    # Build wide DF
    for index, row in df2.iterrows():

        # Store one index per unit and write all attributes associated with that unit to the index in question
        if 'Apartment: ' in row['Unit']:
            index_save = index

        # Fill in Price
        if 'Starting at:' in row['Unit']:
            df2.loc[index_save, 'Price'] = df2.loc[index, 'Unit']

        # Fill in Date Available (HTML changes if available now vs future date)
        if 'Date Available:' in row['Unit']:
            df2.loc[index_save, 'Date Available'] = df2.loc[index, 'Unit']
        if 'Available Now' in row['Unit']:
            df2.loc[index_save, 'Date Available'] = df2.loc[index, 'Unit']

    # Drop rows that contain NAN in any column
    df3 = df2[~df2.isnull().any(axis=1)].copy()
    # len(df3)  # 2

    # Clean column values
    df3.loc[df3['Unit'].str.contains('Apartment: '), 'Unit'] = df3['Unit'].str.split('Apartment: # ').str[1]
    df3.loc[df3['Date Available'].str.contains(
        'Date Available: '), 'Date Available'] = df3['Date Available'].str.split('Date Available:  ').str[1]
    df3.loc[df3['Price'].str.contains('Starting at: '), 'Price'] = df3['Price'].str.split('Starting at: ').str[1]

    # Turn Price string to integer
    df3['Price'] = df3['Price'].str.replace('$', '')
    df3['Price'] = df3['Price'].str.replace(',', '')
    df3['Price'] = df3['Price'].astype('int16')

    # Change availability string
    df3.loc[df3['Date Available'].str.contains('Available Now'), 'Date Available'] = 'Now'

    # Add floor plan to DF
    df3['Floor Plan'] = floor_plan

    # Add scraped DateTime to DF
    df3['Scrape Datetime'] = current_time

    df4 = df3[['Floor Plan', 'Unit', 'Price', 'Date Available', 'Scrape Datetime']].copy()

    df4.reset_index(drop=True, inplace=True)

    return df4


def compare_availability(floor_plan: str, df_scraped):
    """
    Identifies how many and which apartment units are either newly available on the market, were leased, or had a price change
    since the last check.

    :param floor_plan: Indicating which floor plan is being scraped. For file naming and differentiating between floor plans.
    :param df_scraped: Cleaned DataFrame containing current unit availability and prices from the website
    :return: 1 DF for current status with all potential changes, only new units, only leased units, and only units with prices
    changes
    """

    # Previous Availability (need to have an existing spreadsheet to compare to; create a blank one if it doesn't exist)
    list_past_files = glob.glob('Output - Vyne Spreadsheets/Vyne {}*.xlsx'.format(floor_plan))
    list_past_files.sort(reverse=False)
    latest_file = list_past_files[-1]
    df_previous = pd.read_excel(latest_file)

    # Outer merge tells if a unit is new, leased, or still available. Upon merge, _x is current _y is previous.
    df_merged = pd.merge(
        df_scraped,
        df_previous,
        how='outer',
        on=['Floor Plan', 'Unit'])

    df_merged2 = df_merged.rename(
        {
            'Price_x': 'Price Current',  # TODO: eventually can delete (change column name convention for prices)
            'Price_y': 'Price Previous',  # TODO: eventually can delete (change column name convention for prices)

            'Price Current_x': 'Price Current',
            'Price Current_y': 'Price Previous',
            'Date Available_x': 'Date Available',
            'Scrape Datetime_x': 'Scrape Datetime'
        }, axis=1)

    df_merged2.loc[(df_merged2['Price Previous'].isna()), 'Change Status'] = 'New Unit'
    df_merged2.loc[(df_merged2['Price Current'].isna()), 'Change Status'] = 'Leased Unit'
    df_merged2.loc[(df_merged2['Change Status'].isna()), 'Change Status'] = 'Still Available'

    # Calculate price change, if applicable
    df_merged2['Price Change'] = df_merged2['Price Current'] - df_merged2['Price Previous']
    df_merged2['Price Change'].fillna(0, inplace=True)

    # Create separate DF for each change status, which will inform if and what to send in email
    df_new = df_merged2[df_merged2['Change Status'] == 'New Unit'].copy()
    df_leased = df_merged2[df_merged2['Change Status'] == 'Leased Unit'].copy()
    df_change = df_merged2[
        (df_merged2['Change Status'] == 'Still Available') &
        (df_merged2['Price Change'] != 0)].copy()

    df_all = df_merged2[[
        'Floor Plan', 'Unit', 'Price Current', 'Price Previous', 'Price Change', 'Change Status', 'Date Available',
        'Scrape Datetime']].copy()

    return df_all, df_new, df_leased, df_change


def send_email(floor_plan, df_new, df_leased, df_change, current_time, url):
    """
    Only sends an email if there is change in apartment unit availability. Email and password are stored as variables in a
    separate password.py file (and imported á la a package at the top) in the same directory that is not version controlled.

    _x columns are current, _y columns are previous

    Emojis at: https://emojipedia.org

    :param floor_plan: Unit floor plan type
    :param df_new: DF of new apartment units
    :param df_leased: DF of leased apartment units
    :param df_change: DF of changes in existing apartment units
    :param current_time: Time that website was scraped, to include as text at end of email body
    :param url: Floor plan URL, to include at end of email body
    :return: If there's a change in availability, email me that change
    """

    # Form Email Parameters
    msg = MIMEMultipart('multipart')  # To support mix of content types
    msg['From'] = email
    msg['To'] = email
    msg['Subject'] = '🏠 Vyne Apt {} Update!'.format(floor_plan)

    # Form Email Body - New Units
    # <editor-fold desc="New">
    if df_new.empty:
        pass
    else:
        # Count of new units
        if len(df_new) == 1:  # Only difference in this if/else is whether to print 'Unit' (singular) vs 'Units' (plural)
            new_unit_count = '<b>' + '{} New {} Unit'.format(len(df_new), floor_plan) + '</b></font>' + '<br></br>'
            # text = '<font face="Courier New, Courier, monospace">' + 'text' + '</font>'  # Sample font change
            msg.attach(MIMEText(new_unit_count, 'html'))
        else:
            new_unit_count = '<b>' + '{} New {} Units'.format(len(df_new), floor_plan) + '</b></font>' + '<br></br>'
            msg.attach(MIMEText(new_unit_count, 'html'))

        # Fill email body with content
        for index_new, row_new in df_new.iterrows():

            # Unit
            msg.attach(MIMEText('<b>{}</b>'.format(row_new['Unit']), 'html'))

            # Price
            msg.attach(MIMEText('  |  ${}'.format(row_new['Price Current']), 'plain'))

            # Date Available
            msg.attach(MIMEText('  |  Available: {}'.format(row_new['Date Available']), 'plain'))

            # Photo
            with open('Output - Vyne Floor Plans/{}.png'.format(str(floor_plan)), 'rb') as f:
                image_data = MIMEImage(f.read(), _subtype='png')
                msg.attach(image_data)
                msg.attach(MIMEText('<br></br>', 'html'))
    # </editor-fold>

    # Form Email Body - Leased Units
    # <editor-fold desc="Leased">
    if df_leased.empty:
        pass
    else:
        # Count of leased units
        if len(df_leased) == 1:  # Only difference in this if/else is whether to print 'Unit' (singular) vs 'Units' (plural)
            leased_unit_count = '<b>' + '{} Leased {} Unit'.format(len(df_leased), floor_plan) + '</b></font>' + '<br></br>'
            # text = '<font face="Courier New, Courier, monospace">' + 'text' + '</font>'  # Sample font change
            msg.attach(MIMEText(leased_unit_count, 'html'))
        else:
            leased_unit_count = '<b>' + '{} Leased {} Units'.format(len(df_leased), floor_plan) + '</b></font>' + '<br></br>'
            msg.attach(MIMEText(leased_unit_count, 'html'))

        # Fill email body with content
        for index_leased, row_leased in df_leased.iterrows():

            # Unit
            msg.attach(MIMEText('<b>{}</b>'.format(row_leased['Unit']), 'html'))

            # Price
            msg.attach(MIMEText('  |  ${}'.format(row_leased['Price Previous']), 'plain'))

            # Date Available
            msg.attach(MIMEText('  |  Available: {}'.format(row_leased['Date Available']), 'plain'))

            # Photo
            with open('Output - Vyne Floor Plans/{}.png'.format(floor_plan), 'rb') as f:
                image_data = MIMEImage(f.read(), _subtype='png')
                msg.attach(image_data)
                msg.attach(MIMEText('<br></br>', 'html'))
    # </editor-fold>

    # Form Email Body - Change in Unit Price
    # <editor-fold desc="Changed">
    if df_change.empty:
        pass
    else:
        # Count of leased units
        if len(df_change) == 1:  # Only difference in this if/else is whether to print 'Change' (singular) vs 'Changes' (plural)
            change_unit_count = '<b>' + '{} {} Price Change'.format(len(df_change), floor_plan) + '</b></font>' + '<br></br>'
            # text = '<font face="Courier New, Courier, monospace">' + 'text' + '</font>'  # Sample font change
            msg.attach(MIMEText(change_unit_count, 'html'))
        else:
            change_unit_count = '<b>' + '{} {} Price Changes'.format(len(df_change), floor_plan) + '</b></font>' + '<br></br>'
            msg.attach(MIMEText(change_unit_count, 'html'))

        # Fill email body with content
        for index_change, row_change in df_change.iterrows():

            # Unit
            msg.attach(MIMEText('<b>{}</b>'.format(row_change['Unit']), 'html'))

            # Price
            msg.attach(MIMEText('  |  ${}'.format(row_change['Price Current']), 'plain'))

            # Price Change
            if row_change['Price Change'] > 0:
                msg.attach(MIMEText(' (+{})'.format(row_change['Price Change']), 'plain'))
            elif row_change['Price Change'] < 0:
                msg.attach(MIMEText(' ({})'.format(row_change['Price Change']), 'plain'))
            else:
                pass

            # Date Available
            msg.attach(MIMEText('  |  Available: {}'.format(row_change['Date Available']), 'plain'))

            # Photo
            with open('Output - Vyne Floor Plans/{}.png'.format(floor_plan), 'rb') as f:
                image_data = MIMEImage(f.read(), _subtype='png')
                msg.attach(image_data)
                msg.attach(MIMEText('<br></br>', 'html'))
    # </editor-fold>

    # Add Time to Email Body
    time_for_email = current_time.strftime('%Y-%m-%d %-I:%M %p')
    msg.attach(MIMEText(time_for_email + '<br>', 'html'))

    # Add Website Link to Email Body
    homepage = MIMEText(url, 'html')
    msg.attach(homepage)

    # Send Email
    with smtplib.SMTP('smtp.outlook.com', 587) as smtp:
        smtp.ehlo()
        smtp.starttls()
        smtp.login(email, email_password)
        smtp.send_message(msg)


def main(list_dicts):
    """
    Runs all previous functions to scrape website and compare unit availability.

    :param list_dicts: List of dictionaries; each dictionary contains floor plan name as the Key and floor plan URL as the Value.
    :return: Sends email if there is a change in availability or price.
    """

    # Write to log
    logging.basicConfig(
        filename='Apartments_OneLoudoun_Vyne.log',
        format='%(asctime)s   %(module)s, Line %(lineno)d   %(levelname)s   %(message)s',
        datefmt='%Y-%m-%d %I:%M:%S %p',
        filemode='a',  # Append to log (rather than, 'w', over-wright)
        level=logging.INFO)  # Set minimum level to INFO and above

    # Print log in console
    formatter = logging.Formatter(
        fmt='%(asctime)s  %(module)s, Line %(lineno)d  %(levelname)s  %(message)s',
        datefmt='%Y-%m-%d %I:%M:%S %p')
    screen_handler = logging.StreamHandler(stream=sys.stdout)  # stream=sys.stdout is similar to normal print
    screen_handler.setFormatter(formatter)
    logging.getLogger().addHandler(screen_handler)

    logging.info('Started running script')

    while True:
        # Loop through each Dictionary in the list
        for dict_floor_plan in list_dicts:
            now = datetime.now()
            try:
                # For each floor plan, scrape website, compare availability, and send notification
                for k_floor_plan, v_floor_plan_url in dict_floor_plan.items():

                    html = scrape_html_selenium(v_floor_plan_url)
                    # print(html)

                    df_current = create_dataframe_from_html(k_floor_plan, html, now)
                    # print(tabulate(df_current, tablefmt='psql', numalign='right', headers='keys', showindex=False))

                    df_all, df_units_new, df_units_leased, df_units_change = compare_availability(k_floor_plan, df_current)

                    if df_units_new.empty & df_units_leased.empty & df_units_change.empty:
                        # print(str(now.strftime('%Y-%m-%d %I:%M %p')) + ' - No Change ({})'.format(k_floor_plan))
                        logging.info('No change (%s)', k_floor_plan)
                        pass

                    else:
                        # print(str(now.strftime('%Y-%m-%d %I:%M %p')) + ' - Change in Availability! ({})'.format(k_floor_plan))
                        logging.info('Change in availability! (%s)', k_floor_plan)

                        (logging.info(
                            '{}'.format(k_floor_plan)
                            + '\n\n'
                            + df_all.to_string(index=False)
                            + '\n'))

                        # Save changes locally
                        today = datetime.today().strftime('%Y-%m-%d %H%M%S')
                        df_all.to_excel(
                            'Output - Vyne Spreadsheets/Vyne {} {}.xlsx'.format(k_floor_plan, today), index=False)

                        send_email(k_floor_plan, df_units_new, df_units_leased, df_units_change, now, v_floor_plan_url)
            except:
                # print(
                #     str(now.strftime('%Y-%m-%d %I:%M %p'))
                #     + ' - Unable to connect to or scrape website ({})'.format(k_floor_plan))
                logging.error(
                    'Unable to connect to or scrape website (%s)', k_floor_plan)  # , exc_info=True (shows full error)

        delay_sec = 60 * 60  # Run every hour
        time.sleep(delay_sec)


def troubleshoot(list_dicts):
    """
    Same as main function, but prints statements to help pinpoint where errors occur and does not write to log

    :param list_dicts: List of dictionaries; each dictionary contains floor plan name as the Key and floor plan URL as the Value.
    :return: Sends email if there is a change in availability or price.
    """

    while True:
        # Loop through each Dictionary in the list
        for dict_floor_plan in list_dicts:
            now = datetime.now()
            try:
                # For each floor plan, scrape website, compare availability, and send notification
                for k_floor_plan, v_floor_plan_url in dict_floor_plan.items():
                    print(k_floor_plan)

                    html = scrape_html_selenium(v_floor_plan_url)
                    print('Scraped website and cleaned HTML')
                    # print(html)

                    df_current = create_dataframe_from_html(k_floor_plan, html, now)
                    print('Created DataFrame of current availability from HTML')
                    print(tabulate(df_current, tablefmt='psql', numalign='right', headers='keys', showindex=False))

                    df_all, df_units_new, df_units_leased, df_units_change = compare_availability(k_floor_plan, df_current)
                    print('Created DataFrames for each change status')
                    print('DF new length: ' + str(len(df_units_new)))
                    print('DF leased length: ' + str(len(df_units_leased)))
                    print('DF changed length: ' + str(len(df_units_change)))

                    if df_units_new.empty & df_units_leased.empty & df_units_change.empty:
                        print(str(now.strftime('%Y-%m-%d %I:%M %p')) + ' - No Change ({})'.format(k_floor_plan))
                        pass

                    else:
                        print(str(now.strftime('%Y-%m-%d %I:%M %p')) + ' - Change in Availability! ({})'.format(k_floor_plan))

                        send_email(k_floor_plan, df_units_new, df_units_leased, df_units_change, now, v_floor_plan_url)
                    print('')
            except:
                print(
                    str(now.strftime('%Y-%m-%d %I:%M %p'))
                    + ' - Unable to connect to or scrape website ({})'.format(k_floor_plan))

        delay_sec = 60 * 15
        time.sleep(delay_sec)


""" ########################################################################################################################## """
""" Scrape Website """
""" ########################################################################################################################## """


dict_a1a = {'A1A': 'https://www.vyneapts.com/floorplans/a1a'}  # 1 bed 1 bath
dict_a2a = {'A2A': 'https://www.vyneapts.com/floorplans/a2a'}  # 1 bed 1 bath
dict_a6d = {'A6D': 'https://www.vyneapts.com/floorplans/a6d'}  # 1 bed 1 bath
dict_b1b = {'B1B': 'https://www.vyneapts.com/floorplans/b1b'}  # 2 bed 2 bath
dict_b2b = {'B2B': 'https://www.vyneapts.com/floorplans/b2b'}  # 2 bed 2 bath
dict_b3b = {'B3B': 'https://www.vyneapts.com/floorplans/b3b'}  # 2 bed 2 bath
dict_b10b = {'B10B': 'https://www.vyneapts.com/floorplans/b10b'}  # 2 bed 2 bath
dict_b12b = {'B12B': 'https://www.vyneapts.com/floorplans/b12b'}  # 2 bed 2 bath
dict_s3a = {'S3A': 'https://www.vyneapts.com/floorplans/s3a'}  # Studio

list_of_dicts = [dict_a1a, dict_a2a, dict_a6d, dict_b1b, dict_b2b, dict_b3b, dict_b10b, dict_b12b, dict_s3a]


main(list_of_dicts)
# troubleshoot(list_of_dicts)


# TODO: If and when S3A is first scraped, delete the blank spreadsheet saved in folder

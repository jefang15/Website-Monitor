"""
August 1, 2023

Scrapes the Vyne apartment website (https://livevyne.com) for unit availability alerts me when there is a new unit, leased unit,
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


def create_blank_spreadsheets(floor_plan: str):
    """
    Creates empty Excel files with the correct column headers for each floor plan. Only need to run this once when scraping the
    webpages for the first time. compare_availability function needs an existing spreadsheet to compare to, even if empty.

    :param floor_plan:
    :return:
    """

    df = pd.DataFrame(columns=[
        'Floor Plan', 'Unit', 'Price Current', 'Price Previous', 'Price Change', 'Change Status', 'Date Available',
        'Scrape Datetime'])

    df.to_excel('Output - Vyne Spreadsheets/Vyne {} 0000-00-00 000000.xlsx'.format(floor_plan), index=False)


def create_dataframe_from_html(floor_plan: str, html_str: str, current_time: datetime):
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
            df2.loc[index_save, 'Price Current'] = df2.loc[index, 'Unit']

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
    df3.loc[df3['Price Current'].str.contains('Starting at: '), 'Price Current'] = df3['Price Current'].str.split(
        'Starting at: ').str[1]

    # Turn Price string to integer
    df3['Price Current'] = df3['Price Current'].str.replace('$', '')
    df3['Price Current'] = df3['Price Current'].str.replace(',', '')
    df3['Price Current'] = df3['Price Current'].astype('int16')

    # Change availability string
    df3.loc[df3['Date Available'].str.contains('Available Now'), 'Date Available'] = 'Now'

    # Add floor plan to DF
    df3['Floor Plan'] = floor_plan

    # Add scraped DateTime to DF
    df3['Scrape Datetime'] = current_time

    df4 = df3[['Floor Plan', 'Unit', 'Price Current', 'Date Available', 'Scrape Datetime']].copy()

    df4.reset_index(drop=True, inplace=True)

    return df4


def compare_availability(apartment_name: str, folder_spreadsheets: str, floor_plan: str, df_scraped):
    """
    Identifies how many and which apartment units are either newly available on the market, were leased, or had a price change
    since the last check.

    :param apartment_name: Name of apartment, to help build directory
    :param folder_spreadsheets: Folder path to location where spreadsheets are saved
    :param floor_plan: Indicates which floor plan is being scraped. For file naming and differentiating between floor plans.
    :param df_scraped: Cleaned DataFrame containing current unit availability and prices from the website
    :return: 1 DF for current status with all potential changes, only new units, only leased units, and only units with prices
    changes
    """

    # Previous Availability (need to have an existing spreadsheet to compare to; create a blank one if it doesn't exist)
    list_past_files = glob.glob('{}/{} {}*.xlsx'.format(folder_spreadsheets, apartment_name, floor_plan))
    list_past_files.sort(reverse=False)
    latest_file = list_past_files[-1]
    df_previous = pd.read_excel(latest_file)

    # Outer merge tells if a unit is new, leased, or still available. Upon merge, _x is current _y is previous.
    df_merged = pd.merge(
        df_scraped,
        df_previous,
        how='outer',
        on=['Floor Plan', 'Unit'])

    # Drop columns from saved spreadsheet whose column names we will reuse and recreate
    df_merged = df_merged.drop('Price Previous', axis=1)
    df_merged = df_merged.drop('Price Change', axis=1)
    df_merged = df_merged.drop('Change Status', axis=1)

    df_merged2 = df_merged.rename(
        {
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

    df_all = df_merged2[[
        'Floor Plan', 'Unit', 'Price Current', 'Price Previous', 'Price Change', 'Change Status', 'Date Available',
        'Scrape Datetime']].copy()

    df_all.sort_values(by=['Floor Plan', 'Unit'], inplace=True)

    df_all['Price Current'] = df_all['Price Current'].astype('int', errors='ignore')
    df_all['Price Previous'] = df_all['Price Previous'].astype('int', errors='ignore')
    df_all['Price Change'] = df_all['Price Change'].astype('int', errors='ignore')

    # Create separate DF for each change status, which will inform if and what to send in email
    df_new = df_all[df_all['Change Status'] == 'New Unit'].copy()
    df_leased = df_all[df_all['Change Status'] == 'Leased Unit'].copy()
    df_change = df_all[
        (df_all['Change Status'] == 'Still Available') &
        (df_all['Price Change'] != 0)].copy()
    df_all = df_all[(df_all['Change Status'] == 'New Unit') | (df_all['Change Status'] == 'Still Available')].copy()

    return df_all, df_new, df_leased, df_change


def send_email(apartment_name: str, folder_photos: str, floor_plan: str, building_floor_plan: str, df_new, df_leased, df_change,
               current_time: datetime, url: str):
    """
    Only sends an email if there is change in apartment unit availability. Email and password are stored as variables in a
    separate password.py file (and imported á la a package at the top) in the same directory that is not version controlled.

    Emojis at: https://emojipedia.org

    :param apartment_name: Name of apartment, to help build directory
    :param folder_photos: Folder path to location where floorplans are saved
    :param floor_plan: Unit floor plan type
    :param building_floor_plan: Image file name for the building's floor plan
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
    msg['Subject'] = '🏠 {} Apt {} Update!'.format(apartment_name, floor_plan)

    if len(df_new) > 0 and len(df_leased) > 0:
        msg.attach(MIMEText('<b>Summary: new and leased units</b><br></br>', 'html'))
    elif len(df_new) > 0 and len(df_change) > 0:
        msg.attach(MIMEText('<b>Summary: new and changed units</b><br></br>', 'html'))
    elif len(df_leased) > 0 and len(df_change) > 0:
        msg.attach(MIMEText('<b>Summary: leased and changed units</b><br></br>', 'html'))
    elif len(df_new) > 0 and len(df_leased) > 0 and len(df_change) > 0:
        msg.attach(MIMEText('<b>Summary: new, leased, and changed units</b><br></br>', 'html'))
    else:
        pass

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
            with open('{}/{}.png'.format(folder_photos, floor_plan), 'rb') as f:
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
            with open('{}/{}.png'.format(folder_photos, floor_plan), 'rb') as f:
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
            with open('{}/{}.png'.format(folder_photos, floor_plan), 'rb') as f:
                image_data = MIMEImage(f.read(), _subtype='png')
                msg.attach(image_data)
                msg.attach(MIMEText('<br></br>', 'html'))
    # </editor-fold>

    # Photo
    with open('{}/{}.png'.format(folder_photos, building_floor_plan), 'rb') as f:
        image_data2 = MIMEImage(f.read(), _subtype='png')
        msg.attach(image_data2)
        msg.attach(MIMEText('<br></br>', 'html'))

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


def main(apartment_name: str, file_name: str, folder_spreadsheets: str, folder_photos: str, list_dicts: list,
         building_floor_plan: str):
    """
    Runs all previous functions to scrape website and compare unit availability.

    :param apartment_name: Name of apartment, for output files
    :param file_name: Name for log file (without '.log' at the end); same as Python script
    :param folder_spreadsheets: Folder path in which spreadsheets are saved
    :param folder_photos: Folder path to location where images are saved
    :param list_dicts: List of dictionaries; each dictionary contains floor plan name as the Key and floor plan URL as the Value.
    :param building_floor_plan: Image file name for the building's floor plan
    :return: Sends email if there is a change in availability or price.
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

    while True:
        # Loop through each Dictionary in the list
        for dict_floor_plan in list_dicts:
            now = datetime.now()
            try:
                # For each floor plan, scrape website, compare availability, and send notification
                for k_floor_plan, v_floor_plan_url in dict_floor_plan.items():

                    html = scrape_html_selenium(v_floor_plan_url)
                    # print(html)

                    if html:

                        df_current = create_dataframe_from_html(k_floor_plan, html, now)
                        # print(tabulate(df_current, tablefmt='psql', numalign='right', headers='keys', showindex=False))

                        df_all, df_units_new, df_units_leased, df_units_changed = compare_availability(
                            apartment_name, folder_spreadsheets, k_floor_plan, df_current)

                        if df_units_new.empty & df_units_leased.empty & df_units_changed.empty:
                            print(str(
                                now.strftime('%Y-%m-%d %I:%M:%S %p'))
                                  + '  {}  INFO  No Change ({})'.format(file_name, k_floor_plan))
                            # logging.info('No change (%s)', k_floor_plan)
                            pass

                        else:
                            # print(str(now.strftime('%Y-%m-%d %I:%M %p')) + ' - Change in Availability! ({})'.format(k_floor_plan))

                            # logging.info('Change in availability! (%s)', k_floor_plan)
                            # (logging.info(
                            #     '\n\n'
                            #     + df_all.to_string(index=False)
                            #     + '\n'))

                            # <editor-fold desc="New">
                            if df_units_new.empty is False:
                                for _, row in df_units_new.iterrows():
                                    logging.info(
                                        'New %s unit: %s ($%s)',
                                        row['Floor Plan'], row['Unit'], row['Price Current'])

                                logging.info(
                                    '\n\n'
                                    + df_units_new.to_string(index=False)
                                    + '\n')
                            # </editor-fold>

                            # <editor-fold desc="Leased">
                            if df_units_leased.empty is False:
                                for _, row in df_units_leased.iterrows():
                                    logging.info(
                                        'Leased %s unit: %s ($%s)',
                                        row['Floor Plan'], row['Unit'], row['Price Previous'])

                                logging.info(
                                    '\n\n'
                                    + df_units_leased.to_string(index=False)
                                    + '\n')
                            # </editor-fold>

                            # <editor-fold desc="Price change">
                            if df_units_changed.empty is False:
                                for _, row in df_units_changed.iterrows():

                                    # Price Change
                                    if row['Price Change'] > 0:
                                        logging.info('%s price change: %s +%s ($%s)',
                                                     row['Floor Plan'], row['Unit'], row['Price Change'], row['Price Current'])
                                    elif row['Price Change'] < 0:
                                        logging.info('%s price change: %s %s ($%s)',
                                                     row['Floor Plan'], row['Unit'], row['Price Change'], row['Price Current'])
                                    else:
                                        pass

                                logging.info(
                                    '\n\n'
                                    + df_units_changed.to_string(index=False)
                                    + '\n')
                            # </editor-fold>

                            # Save changes locally
                            today = datetime.today().strftime('%Y-%m-%d %H%M%S')
                            df_all.to_excel(
                                '{}/{} {} {}.xlsx'.format(
                                    folder_spreadsheets, apartment_name, k_floor_plan, today), index=False)

                            # send_email(apartment_name, folder_photos, k_floor_plan, building_floor_plan, df_units_new,
                            #            df_units_leased, df_units_changed, now, v_floor_plan_url)
                            pass
                    else:
                        print(str(
                            now.strftime('%Y-%m-%d %I:%M:%S %p'))
                              + '  {}  INFO  No {} units'.format(file_name, k_floor_plan))

                        # logging.info('No {} units'.format(k_floor_plan))

                        break
            except:
                # print(
                #     str(now.strftime('%Y-%m-%d %I:%M %p'))
                #     + ' - Unable to connect to or scrape website ({})'.format(k_floor_plan))
                logging.error(
                    'Unable to connect to or scrape website (%s)', k_floor_plan)  # , exc_info=True (shows full error)

        delay_sec = 60 * 60 * 6
        time.sleep(delay_sec)


""" ########################################################################################################################## """
""" Scrape Website """
""" ########################################################################################################################## """


# # Troubleshoot
# _html = scrape_html_selenium('https://www.vyneapts.com/floorplans/b3b')
# _df = create_dataframe_from_html('B3B', _html, datetime.now())
# _df1, _df2, _df3, _df4 = compare_availability(
#     'Vyne', 'Output - Vyne Spreadsheets', 'B3B', _df)
# print(tabulate(_df1, tablefmt='psql', numalign='right', headers='keys', showindex=False))
# print(tabulate(_df2, tablefmt='psql', numalign='right', headers='keys', showindex=False))
# print(tabulate(_df3, tablefmt='psql', numalign='right', headers='keys', showindex=False))
# print(tabulate(_df4, tablefmt='psql', numalign='right', headers='keys', showindex=False))


# list_floor_plans = ['A1A', 'A2A', 'A6D', 'B1B', 'B2B', 'B3B', 'B10B', 'B12B', 'S3A']
# for plan in list_floor_plans:
#     create_blank_spreadsheets(plan)
# TODO: If and when S3A is first scraped, delete the blank spreadsheet saved in folder


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


main(
    'Vyne',
    'Apartments_OneLoudoun_Vyne',
    'Output - Vyne Spreadsheets',
    'Output - Vyne Floor Plans',
    list_of_dicts,
    'Building Floor Plan')

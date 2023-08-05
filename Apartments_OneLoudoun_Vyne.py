"""
August 1, 2023


"""
import numpy as np
from selenium.webdriver.chrome.options import Options
from selenium import webdriver
from bs4 import BeautifulSoup
import pandas as pd
from tabulate import tabulate
from datetime import datetime
import glob


def scrape_html_selenium(url: str):
    """
    Scrapes HTML content from a given floorplan's URL

    :param url: URL
    :return: Cleaned HTML string containing key floorplan and unit information (such as units available, price, etc.)
    """

    # Set the options for the Chromium browser
    chromium_options = Options()
    chromium_options.add_argument('--disable-extensions')
    # chromium_options.add_argument('--headless')

    # Set the driver for the Chromium browser
    chrome_driver = webdriver.Chrome(options=chromium_options)

    # Navigate to your website and close browser
    chrome_driver.get(url)

    # Get HTML from URL
    html = chrome_driver.page_source
    chrome_driver.quit()  # Don't run until HTML is created

    # Clean HTML
    html_soup = BeautifulSoup(html, features='lxml').text  # String
    len(html_soup)  # 7,822

    # Truncate beginning and end of HTML string
    index_start = html_soup.find('Available Units')
    html_soup = html_soup[index_start:]
    len(html_soup)  # 4,054

    index_end = html_soup.find('Have a question?')
    html_soup = html_soup[:index_end]
    len(html_soup)  # 274

    return html_soup


def create_dataframe_from_html(html_str: str):
    """
    Converts the HTML string of key unit information to a DF

    :param html_str:
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

        # Fill in Date Available
        if 'Date Available:' in row['Unit']:
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

    # Add scraped DateTime to DF
    now = datetime.now()

    df3['Scrape Datetime'] = now

    df4 = df3[['Unit', 'Price', 'Date Available', 'Scrape Datetime']].copy()

    return df4


def compare_availability(floorplan: str, df_scraped):
    """
    Identifies how many and which apartment units are either newly available on the market, were leased, or had a price change
    since the last check.

    :param floorplan: Indicating which floorplan is being scraped. For file naming and differentiating between floorplans.
    :param df_scraped: Cleaned DataFrame containing current unit availability and prices from the website
    :return: 1 DF for new units, leased units, and units with prices changes
    """

    # Previous Availability
    list_past_files = glob.glob('Output - Vyne Spreadsheets/Vyne {}*.xlsx'.format(floorplan))
    list_past_files.sort(reverse=False)
    latest_file = list_past_files[-1]
    df_previous = pd.read_excel(latest_file)

    # Outer merge tells if a unit is new, leased, or still available. Upon merge, _x is current _y is previous.
    df_merged = pd.merge(
        df_scraped,
        df_previous,
        how='outer',
        on='Unit')

    df_merged.loc[(df_merged['Price_y'].isna()), 'Change Status'] = 'New Unit'
    df_merged.loc[(df_merged['Price_x'].isna()), 'Change Status'] = 'Unit Leased'
    df_merged.loc[(df_merged['Change Status'].isna()), 'Change Status'] = 'Same Availability'

    # Calculate price change, if applicable
    df_merged['Price Change'] = df_merged['Price_x'] - df_merged['Price_y']
    df_merged['Price Change'].fillna(0, inplace=True)

    # Create separate DF for each change status, which will inform if and what to send in email
    df_new = df_merged[df_merged['Change Status'] == 'New Unit'].copy()
    df_leased = df_merged[df_merged['Change Status'] == 'Unit Leased'].copy()
    df_change = df_merged[
        (df_merged['Change Status'] == 'Same Availability') &
        (df_merged['Price Change'] != 0)].copy()

    return df_new, df_leased, df_change


""" ########################################################################################################################## """
""" Scrape Website """
""" ########################################################################################################################## """


vyne_dict = {'A1A': 'https://www.vyneapts.com/floorplans/a1a'}


for k_floorplan, v_floorplan_url in vyne_dict.items():

    html = scrape_html_selenium(v_floorplan_url)
    print(html)

    df_current = create_dataframe_from_html(html)
    print(tabulate(df_current, tablefmt='psql', numalign='right', headers='keys', showindex=False))

    df_units_new, df_units_leased, df_units_change = compare_availability(k_floorplan, df_current)

    if df_units_new.empty is True & df_units_leased.empty is True & df_units_change.empty is True:
        now = datetime.now()
        print(str(now.strftime('%Y-%m-%d %I:%M %p')) + ' - No Change')
        pass
    else:
        # Save to Excel only if there is some change (either new unit, leased unit, or change in price)
        today = datetime.today().strftime('%Y-%m-%d %H%m%S')
        df_current.to_excel('Output - Vyne Spreadsheets/Vyne {} {}.xlsx'.format(k_floorplan, today), index=False)

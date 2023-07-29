"""
July 28, 2023

Scrapes the Fairfax County Animal Shelter site (24petconnect.com) for available dogs and alerts me when a new dog is available
for adoption or a dog was adopted.
"""


import requests
from lxml.html.clean import Cleaner
from bs4 import BeautifulSoup
from datetime import datetime
import pandas as pd
from tabulate import tabulate


# Set URL
url_page1 = 'https://24petconnect.com/PP4352?at=DOG'
url_page2 = 'https://24petconnect.com/PP4352?index=30&at=DOG'

# Current DateTime for exporting and naming files with current timestamp
now = datetime.now()


def scrape_html(url):

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
    # print(html_sanitized2)
    # type(html_sanitized2)  # Str
    # len(html_sanitized2)  # 10,850

    # Turn HTML to BS4 object (only use this if you want to save text)
    # html_bs = BeautifulSoup(html_text, 'lxml')
    # print(html_bs)
    # type(html_bs)  # BS4
    # print(html_bs)

    return html_text


html_text_clean = scrape_html(url_page1)


def create_dataframe_from_html(html):

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


def scrape_additional_pages(availability, url2, df1):

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
            # 'Counter'
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


df_dog_concat = scrape_additional_pages(dog_availability, url_page2, df_dog)
print(tabulate(df_dog_concat, tablefmt='psql', numalign='right', headers='keys', showindex=False))

# Convert current datetime to custom string format
now_text = now.strftime('%Y-%m-%d %H-%M-%S')
print(now_text)

df_dog_concat.to_excel('Output - Spreadsheets/Fairfax County Animal Shelter {}.xlsx'.format(now_text), index=False)


# Website Monitor

import requests
import os
from lxml.html.clean import Cleaner
from bs4 import BeautifulSoup
from datetime import datetime
import glob
import pandas as pd
from tabulate import tabulate


# https://medium.com/swlh/tutorial-creating-a-webpage-monitor-using-python-and-running-it-on-a-raspberry-pi-df763c142dac


""" Scrape URL """

# Set URL
URL_TO_MONITOR = 'https://24petconnect.com/PP4352?at=DOG'
URL_TO_MONITOR2 = 'https://24petconnect.com/PP4352?index=30&at=DOG'  # TODO: need to account for multiple pages, if there are

Columns = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.95 Safari/537.36',
    'Pragma': 'no-cache', 'Cache-Control': 'no-cache'}

# Send HTTP GET request to URL
response = requests.get(URL_TO_MONITOR, headers=Columns)


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
type(html_processed)  # Str
len(html_processed)  # 144,615


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
type(html_sanitized)  # Str
len(html_sanitized)  # 42,273


# Truncate beginning of HTML
index_start = html_sanitized.find('Animals: ')
html_sanitized2 = html_sanitized[index_start:]
# print(html_sanitized2)
type(html_sanitized2)  # Str
len(html_sanitized2)  # 10,850

# Turn HTML to BS4 object
html_bs = BeautifulSoup(html_sanitized2, 'lxml')
# print(html_bs)
type(html_bs)  # BS4
print(html_bs)

# Current DateTime for exporting and naming files with current timestamp
now = datetime.now()
now_text = now.strftime('%Y-%m-%d %H-%M-%S')
print(now_text)

# Export bs4 HTML as txt file
with open('Output - Text/Fairfax County Animal Shelter {}.txt'.format(now_text), 'w+', encoding='utf-8') as f_out:
    f_out.write(html_bs.prettify())


""" Create DataFrame from HTML Text """

# Create list from HTML string
list_text = [i.strip() for i in html_sanitized2.splitlines()]
type(list_text)  # List
len(list_text)  # 1,224

# Create DataFrame from list
df = pd.DataFrame(list_text, columns=['Text'])
len(df)  # 1,224
print(tabulate(df.head(10), tablefmt='psql', numalign='right', headers='keys', showindex=False))

# Drop NAN rows
df2 = df[df['Text'] != ''].copy()
len(df2)  # 479

df2.reset_index()
# print(tabulate(df2.head(20), tablefmt='psql', numalign='right', headers='keys', showindex=False))
# print(tabulate(df2.tail(20), tablefmt='psql', numalign='right', headers='keys', showindex=False))

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

print(tabulate(df2.head(10), tablefmt='psql', numalign='right', headers='keys', showindex=False))

# Fill in Image (done separately, since this attribute appears after the index associated with the dog's name)
df2.loc[df2['Text'].str.contains('<img id="AnimalImage_'), 'Image'] = df2['Text']
df2['Image'].ffill(inplace=True)

# Drop rows where Name is NAN
df3 = df2[df2['Name'].notna()].copy()
len(df3)  # 30

# Finish cleaning URLs in Image column (doesn't work until NANs are taken care of)
df3.loc[df3['Image'].str.contains(' src="'), 'Image'] = df3['Image'].str.split(' src="').str[1].str.split('">').str[0]
df3.reset_index(drop=True, inplace=True)
print(tabulate(df3.head(10), tablefmt='psql', numalign='right', headers='keys', showindex=False))

# Create ID column from latter part of Name
df3['ID'] = df3['Name'].str.extract('(\d*\.?\d+)', expand=True)

# Clean and remove ID from Name column
df3.loc[df3['Name'].str.contains(' \\([0-9]'), 'Name'] = df3['Name'].str.split(' \\([0-9]').str[0]
df4 = df3.applymap(lambda x: str(x).replace('&amp;', '&'))

# Set Date Types
print(df4.dtypes)
df4['Brought to Shelter'] = pd.to_datetime(df4['Brought to Shelter'])
df4['ID'] = df4['ID'].astype('int32')


# print(df4.columns)
df5 = df4[['ID', 'Name', 'Gender', 'Breed', 'Age', 'Brought to Shelter', 'Location', 'Image']].copy()
# print(df5.dtypes)
print(tabulate(df5, tablefmt='psql', numalign='right', headers='keys', showindex=True))
df5.to_excel('Output - Spreadsheets/Fairfax County Animal Shelter {}.xlsx'.format(now_text), index=False)

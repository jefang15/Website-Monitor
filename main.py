
# Website Monitor

import requests
import os
from lxml.html.clean import Cleaner
from bs4 import BeautifulSoup
from datetime import datetime
import glob
import re
import pandas as pd
from tabulate import tabulate



# https://medium.com/swlh/tutorial-creating-a-webpage-monitor-using-python-and-running-it-on-a-raspberry-pi-df763c142dac


# Set URL to track
URL_TO_MONITOR = 'https://24petconnect.com/PP4352?at=DOG'

today = datetime.today()
print(today)


def process_html(string):

    soup = BeautifulSoup(string, features="lxml")
    # using features='lxml' gives error:
    # bs4.FeatureNotFound: Couldn't find a tree builder with the features you requested: lxml. Do you need to install a parser
    # library?

    # make the html look good
    soup.prettify()

    # remove script tags
    for s in soup.select('script'):
        s.extract()

    # remove meta tags
    for s in soup.select('meta'):
        s.extract()

    # convert to a string, remove '\r', and return
    return str(soup).replace('\r', '')


def webpage_was_changed(url):

    # Informs GET request (prevents caching)
    Columns = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.95 Safari/537.36',
        'Pragma': 'no-cache', 'Cache-Control': 'no-cache'}

    # Send an HTTP GET request to a specified URL
    response = requests.get(url, Columns=Columns)

    # Create current HTML text file
    if not os.path.exists('/Users/jeff/Documents/Programming/Projects/Website-Monitor/Output/previous_content_{}.txt'.format(
            today)):
        open('/Users/jeff/Documents/Programming/Projects/Website-Monitor/Output/previous_content_{}.txt'.format(
            today), 'w+').close()

    # Open previous HTML text file
    # glob.glob()
    # filehandle = open('/Users/jeff/Documents/Programming/Projects/Website-Monitor/Output/previous_content_{}.txt'.format(
    #         today), 'r')
    # previous_response_html = filehandle.read()
    # print(previous_response_html)
    # filehandle.close()
    #
    # processed_response_html = process_html(response.text)
    #
    # print(processed_response_html)

    test = glob.glob('/Users/jeff/Documents/Programming/Projects/Website-Monitor/Output/*.txt')
    latest_saved_txt = test[-1]

    filehandle = open(latest_saved_txt, 'r')
    previous_response_html = filehandle.read()
    print(previous_response_html)
    filehandle.close()

    processed_response_html = process_html(response.text)

    print(processed_response_html)


    if processed_response_html == previous_response_html:
        return False
    else:
        filehandle = open('/Users/jeff/Documents/Programming/Projects/Website-Monitor/Output/previous_content_{}.txt'.format(
            today), 'w')
        filehandle.write(processed_response_html)
        filehandle.close()
        return True


webpage_was_changed(URL_TO_MONITOR)



""" Code line by line before putting in function """


URL_TO_MONITOR = 'https://24petconnect.com/PP4352?at=DOG'


Columns = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.95 Safari/537.36',
    'Pragma': 'no-cache', 'Cache-Control': 'no-cache'}

# Send an HTTP GET request to a specified URL
response = requests.get(URL_TO_MONITOR, Columns=Columns)
type(response)

# Process HTML as text
new = process_html(response.text)
type(new)  # str


# Start string at actual contents/gets rids of all fluff leading up to dogs available for adoption
index_start = new.find('Animals: ')
print(index_start)

text = new[index_start:]
print(text)
type(text)  # str

# Turn subset str to bs4 object
soup = BeautifulSoup(text, "lxml")
print(soup)
type(soup)  # bs4


# Export bs4 HTML as txt file
with open('Output/previous_content1.txt', 'w+', encoding='utf-8') as f_out:
    f_out.write(soup.prettify())


" Clean all tags "

# Clean HTML / Replace <tags> with blanks
clean = re.compile('<.*?>')
text2 = re.sub(clean, '', text)
type(text2)  # str

# Turn subset str to bs4 object
soup2 = BeautifulSoup(text2, "lxml")
print(soup2)

# Export bs4 HTML as txt file
with open('Output/previous_content2 - truncate remove tags.txt', 'w+', encoding='utf-8') as f_out:
    f_out.write(soup2.prettify())


" Keep URLs "


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


text3 = sanitize(text)
type(text3)

soup3 = BeautifulSoup(text3, "lxml")

# Export bs4 HTML as txt file
with open('Output/previous_content5 - truncate auto clean3.txt', 'w+', encoding='utf-8') as f_out:
    f_out.write(soup3.prettify())
# TODO: keep, this is best one so far (gets rid of tags, but keeps link to dog photo)


# Create DF from HTML
type(soup3)
lst = [i.get_text(strip=True, separator="~") for i in soup3.find("div", class_="gridResultsContinerInner").find_all("div")]
final_lst = [i.split("~") for i in lst]

column = [i.next for i in soup.find_all('div', {'class': 'gridResultsContinerInner'})]
row = [i.next.next.text for i in soup.find_all('div', {'class': 'gridResultsContinerInner'})]

df = pd.DataFrame(columns=column)
df = df._append(pd.Series(row, index=column), ignore_index=True)
print(tabulate(df.head(10), tablefmt='psql', numalign='right', headers='keys', showindex=False))


# Create DF from string
soup3

len(text3)  # 8812
text_for_df = [i.strip() for i in text3.splitlines()]  # create a list of lines
len(text_for_df)  # 983
text_for_df

df = pd.DataFrame(text_for_df, columns=['Column'])
print(tabulate(df.head(10), tablefmt='psql', numalign='right', headers='keys', showindex=False))

len(df)  # 983


# Drop blank lines

df2 = df[df['Column'] != ''].copy()
len(df2)

df2.reset_index()

print(tabulate(df2.head(20), tablefmt='psql', numalign='right', headers='keys', showindex=False))


for index, row in df2.iterrows():
    # print(index)
    # print(row['Column'])

    # Set single index to write all new columns to
    if row['Column'] == 'Name:':
        index_save = index

    # Fill in Image
    if row['Column'].contains('<img id="AnimalImage_'):
        print(index)

    # Fill in Name
    if row['Column'] == 'Name:':
        df2.loc[index_save, 'Name'] = df2.loc[index + 1, 'Column']

    # Fill in Gender
    if row['Column'] == 'Gender:':
        df2.loc[index_save, 'Gender'] = df2.loc[index + 1, 'Column']

    # Fill in Breed
    if row['Column'] == 'Breed:':
        df2.loc[index_save, 'Breed'] = df2.loc[index + 1, 'Column']

    # Fill in Animal Type
    if row['Column'] == 'Animal type:':
        df2.loc[index_save, 'Animal Type'] = df2.loc[index + 1, 'Column']

    # Fill in Age
    if row['Column'] == 'Age:':
        df2.loc[index_save, 'Age'] = df2.loc[index + 1, 'Column']

    # Fill in Brought to the Shelter
    if row['Column'] == 'Brought to the shelter:':
        df2.loc[index_save, 'Brought to Shelter'] = df2.loc[index + 1, 'Column']

    # Fill in Located At
    if row['Column'] == 'Located at:':
        df2.loc[index_save, 'Location'] = df2.loc[index + 1, 'Column']


print(tabulate(df2.head(10), tablefmt='psql', numalign='right', headers='keys', showindex=False))


# Fill in Image Link
df2.loc[df2['Column'].str.contains('<img id="AnimalImage_'), 'Image'] = df2['Column']
df2['Image'].ffill(inplace=True)
print(tabulate(df2.head(20), tablefmt='psql', numalign='right', headers='keys', showindex=False))


# Drop rows where Name is NAN
df3 = df2[df2['Name'].notna()].copy()
len(df3)
print(tabulate(df3.head(30), tablefmt='psql', numalign='right', headers='keys', showindex=False))

# Clean up values
df3.loc[df3['Image'].str.contains(' src="'), 'Image'] = df3['Image'].str.split(' src="').str[1].str.split('">').str[0]

print(tabulate(df3.head(10), tablefmt='psql', numalign='right', headers='keys', showindex=False))

df3.reset_index(drop=True, inplace=True)

# Create ID column
df3['ID'] = df3['Name'].str.extract('(\d*\.?\d+)', expand=True)
print(tabulate(df3.head(10), tablefmt='psql', numalign='right', headers='keys', showindex=False))

# Clean and remove ID from Name column
df3.loc[df3['Name'].str.contains(' \\([0-9]'), 'Name'] = df3['Name'].str.split(' \\([0-9]').str[0]
df4 = df3.applymap(lambda x: str(x).replace('&amp;', '&'))
print(tabulate(df4.head(10), tablefmt='psql', numalign='right', headers='keys', showindex=False))

# Date Types
df4['Brought to Shelter'] = pd.to_datetime(df4['Brought to Shelter'])
df4['ID'] = df4['ID'].astype('int32')


df4.columns
df5 = df4[['ID', 'Name', 'Gender', 'Breed', 'Age', 'Brought to Shelter', 'Location', 'Image']].copy()
df5.dtypes
print(tabulate(df5.head(10), tablefmt='psql', numalign='right', headers='keys', showindex=False))


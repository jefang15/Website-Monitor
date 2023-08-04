"""
August 1, 2023


"""



from selenium import webdriver
from selenium.webdriver.chrome.options import Options


import re



from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
from lxml.html.clean import Cleaner
import pandas as pd


def scrape_html_javascript(url):

    " Connect to URL "

    # V1
    options = Options()
    options.add_argument('--headless')

    driver = webdriver.Chrome(options=options)
    driver.get(url)

    # Or  # TODO: use this instead? or try the above V1 after some time (website looks out for robots)
    # driver = webdriver.Chrome()
    # driver.get(url)
    # driver.quit()

    " Clean HTML Content "
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

    html_processed = process_html(driver.page_source)
    # type(html_processed)  # Str

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

    # Truncate beginning and end of HTML string
    index_start = html_sanitized.find('Available Units')
    html_text = html_sanitized[index_start:]

    index_end = html_text.find('Have a question?')
    html_text2 = html_text[:index_end]

    return html_text2



" Connect to URL "


url = 'https://www.vyneapts.com/floorplans/a1a'


# V1
options = Options()
options.add_argument('--headless')  # TODO: code somewhat works without this argument

driver = webdriver.Chrome(options=options)
driver.get(url)


# V2  # TODO: use this instead? or try the above V1 after some time (website looks out for robots)
driver = webdriver.Chrome()
driver.get(url)
html = driver.page_source
soup=BeautifulSoup(html,'html.parser')
soup2 = soup.prettify()
# driver.quit()


# V7


def scrape_html_selenium(url):

    # Set the options for the Chromium browser
    chromium_options = Options()
    chromium_options.add_argument('--disable-extensions')

    # Set the driver for the Chromium browser
    chrome_driver = webdriver.Chrome(options=chromium_options)

    # Navigate to your website and close browser
    chrome_driver.get(url)
    chrome_driver.quit()  # Don't run until HTML is created

    # Get HTML from URL
    html = chrome_driver.page_source

    cleaner = re.compile('<.*?>')

# Set the options for the Chromium browser
chrome_options = Options()
chrome_options.add_argument('--disable-extensions')

# Set the driver for the Chromium browser
chrome_driver = webdriver.Chrome(options=chrome_options)

# Navigate to your website and close browser
chrome_driver.get(url)
chrome_driver.quit()  # Don't run until HTML is created

html = chrome_driver.page_source
print(html)
soup=BeautifulSoup(html, features='lxml').text
print(soup)
type(soup)

html_processed = process_html(html)
print(html_processed)

html_sanitized = sanitize(html_processed)
print(html_sanitized)

# TODO: V7 works



CLEANR = re.compile('<.*?>')

def cleanhtml(raw_html):
  cleantext = re.sub(CLEANR, '', raw_html)
  return cleantext

html_clean = cleanhtml(html)
soup = BeautifulSoup(html_clean, features='lxml')
print(soup)

# Truncate beginning of HTML
index_start = html_clean.find('Available Units')
index_start
html_text = html_clean[index_start:]
len(html_text)  # 7,335
print(html_text)

index_end = html_text.find('Have a question?')
index_end
html_text2 = html_text[:index_end]
print(html_text2)



" Clean HTML Content "


def process_html(string):
    # soup = BeautifulSoup(string, features='lxml')
    soup=BeautifulSoup(html,'html.parser')
    soup.prettify()

    # Remove script tags
    for s in soup.select('script'):
        s.extract()

    # Remove meta tags
    for s in soup.select('meta'):
        s.extract()

    # Remove section tags
    for s in soup.select('section'):
        s.extract()

    # Remove class tags
    for s in soup.select('class'):
        s.extract()

    # convert to a string, remove '\r', and return
    return str(soup).replace('\r', '')


html_processed = process_html(html)
print(html_processed)
type(html_processed)  # Str
len(html_processed)  # 101,030


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
print(html_sanitized)
type(html_sanitized)  # Str
len(html_sanitized)  # 15,776

# Truncate beginning of HTML
html_sanitized = soup
index_start = html_sanitized.find('Available Units')
index_start
html_text = html_sanitized[index_start:]
len(html_text)  # 7,335
print(html_text)


index_end = html_text.find('Have a question?')
index_end
html_text2 = html_text[:index_end]
# type(html_text2)
# len(html_text2)
print(html_text2)
# type(html_text)  # Str
# len(html_text)  # 10,850


""" ########################################################################################################################## """
""" Convert HTML to DataFrame """
""" ########################################################################################################################## """


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

    df2.reset_index(inplace=True)

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


# Create list from HTML string
list_text = [i.strip() for i in html_text2.splitlines()]
# type(list_text)  # List
# len(list_text)  # 1,224

# Create DataFrame from list
df = pd.DataFrame(list_text, columns=['Text'])
# len(df)  # 1,224

# Drop NAN rows
df2 = df[df['Text'] != ''].copy()
# len(df2)  # 479

df2.reset_index(inplace=True)


df2.head()

for index, row in df2.iterrows():
    print(index)
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



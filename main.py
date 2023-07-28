
# Website Monitor

import requests
import os
from bs4 import BeautifulSoup


# Set URL to track
URL_TO_MONITOR = 'https://24petconnect.com/PP4352?at=DOG'


headers = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.95 Safari/537.36',
    'Pragma': 'no-cache',
    'Cache-Control': 'no-cache'}


# Pull HTML
response = requests.get(URL_TO_MONITOR, headers=headers)
response2 = response.text
print(response.text)
type(response.text)


# Clean up HTML
soup = BeautifulSoup(response2, "lxml")
print(soup)


# Create then write HTML contents to text file
with open('Output/previous_content2.txt', 'w+', encoding='utf-8') as f_out:
    f_out.write(soup.prettify())


# ALt new HTML


def process_html(string):
    soup = BeautifulSoup(string, features="lxml")

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


processed_response_html = process_html(response.text)
print(processed_response_html)
type(processed_response_html)




# Open previous file
with open('Output/previous_content2.txt') as f:
    text = f.read()
soup_old = BeautifulSoup(text, 'lxml')
print(soup_old)
type(soup_old)

# Open previous file as string
filehandle = open('Output/previous_content2.txt', 'r')
previous_response_html = filehandle.read()
type(previous_response_html)
print(previous_response_html)


type(soup)
type(soup_old)


# Compare old and new file
if soup == soup_old:
    print(True)
else:
    print(False)






if not os.path.exists('Output/previous_content2.txt'):
    open('Output/previous_content2.txt', 'w+').close()

filehandle = open('Output/previous_content2.txt', 'r')
previous_response_html = filehandle.read()
previous_response_html
type(previous_response_html)
filehandle.close()

type(processed_response_html)
type(previous_response_html)

if response == previous_response_html:
    print(True)
else:
    print(False)



# https://medium.com/swlh/tutorial-creating-a-webpage-monitor-using-python-and-running-it-on-a-raspberry-pi-df763c142dac


URL_TO_MONITOR = 'https://24petconnect.com/PP4352?at=DOG'



def process_html(string):
    soup = BeautifulSoup(string, features="lxml")

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


def webpage_was_changed(URL):
    """Returns true if the webpage was changed, otherwise false."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.95 Safari/537.36',
        'Pragma': 'no-cache', 'Cache-Control': 'no-cache'}
    response = requests.get(URL, headers=headers)

    # create the previous_content.txt if it doesn't exist
    if not os.path.exists("/Users/jeff/Documents/Programming/Projects/Website-Monitor/Output/previous_content2.txt"):
        open("/Users/jeff/Documents/Programming/Projects/Website-Monitor/Output/previous_content2.txt", 'w+').close()

    filehandle = open("/Users/jeff/Documents/Programming/Projects/Website-Monitor/Output/previous_content2.txt", 'r')
    previous_response_html = filehandle.read()
    print(previous_response_html)
    filehandle.close()

    processed_response_html = process_html(response.text)

    print(processed_response_html)

    if processed_response_html == previous_response_html:
        return False
    else:
        filehandle = open("/Users/jeff/Documents/Programming/Projects/Website-Monitor/Output/previous_content2.txt", 'w')
        filehandle.write(processed_response_html)
        filehandle.close()
        return True


webpage_was_changed(URL_TO_MONITOR)
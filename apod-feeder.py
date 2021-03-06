import feedparser
import os
import re
import requests
import pytz
import time

from bs4 import BeautifulSoup
from datetime import datetime
from feedformatter import Feed

from flask import Flask
from flask import make_response

app = Flask(__name__)

FEED_URL = 'http://apod.nasa.gov/apod.rss'
DAILY_LINK = 'http://antwrp.gsfc.nasa.gov/apod/astropix.html'


@app.route("/apod.rss", methods=['GET'])
def feed():

    # Create the feed
    feed = Feed()
    of = feedparser.parse(FEED_URL)

    # Set the feed/channel level properties
    feed.feed["title"] = of['feed']['title']
    feed.feed["link"] = of['feed']['link']
    feed.feed["description"] = of['feed']['description']
    feed.feed["language"] = of['feed']['language']
    feed.feed["image"] = {
        "title": of['feed']['image']['title'],
        "url": of['feed']['image']['url'],
        "link": of['feed']['image']['link'],
    }

    # Set up the timezone
    central = pytz.timezone('US/Central')

    # Build the entries
    for entry in of['entries']:
        item = {}
        # check for the bad one here, alter this link
        link = entry['link']
        if link == DAILY_LINK:
            link = "http://antwrp.gsfc.nasa.gov/apod/ap{}.html".format(datetime.now().strftime("%y%m%d"))
        # get a better date
        date_string = re.search('ap(\d+).html', link).group(1)  # "141226" ap(\d+).html
        date = datetime.strptime(date_string, "%y%m%d")

        # Get the date into a better format for feedformatter
        localized_date = central.localize(date)
        tuple_time = time.strptime(localized_date.strftime("%a, %d %b %Y %H:%M:%S"), "%a, %d %b %Y %H:%M:%S")

        # Check for an image to provide a better one (APOD provides a small thumbnail only)
        # Grab the html of the current page
        r = requests.get(link)
        linked_page = r.text

        # Some feeds return 404 (put up too early?)
        if r.status_code == 404:
            continue

        body = u''

        # Locate an image (if there is one)
        soup = BeautifulSoup(linked_page)
        # Loop through the children elements to get the <p> we need
        for idx, child in enumerate(soup.body.children):
            if idx == 5:
                # The <p> tag with the text is the 5th element
                # Need to add a closing <p> since the source is missing it
                body = unicode(child).split("<p> <center>")[0] + "</p>"

        try:
            # Check for the main image source url
            img = soup.center.img['src']
            if img:
                # An image exists, get the best formatted version
                feed_soup = BeautifulSoup(entry['summary'])
                feed_soup.p.a.img['src'] = 'http://apod.nasa.gov/apod/' + img
                # Prepend the right tag to the front of the desciption
                body = unicode(feed_soup.p.a.img) + body
        except TypeError:
            pass

        # Complete the feed item
        item["title"] = entry['title']
        item["link"] = link
        item["description"] = body
        item["pubDate"] = tuple_time
        item["guid"] = link

        feed.items.append(item)

    response = make_response(feed.format_rss2_string())
    response.headers["Content-Type"] = 'application/rss+xml'
    response.mimetype = 'application/rss+xml'
    return response


@app.route("/")
def home():
    raise Exception("Test Exception")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    # Dumb hack to properly set debug state
    debug = {'True': True, 'False': False}.get(os.environ.get("DEBUG", 'False'), False)
    app.run(host='0.0.0.0', port=port, debug=debug)

# gym_scraper.py
from playwright.sync_api import sync_playwright
from urllib.parse import urlencode, quote
from ics import Calendar, Event
from datetime import datetime
import os
import re
from collections import defaultdict
import pytz
from datetime import datetime, timedelta
from google_calendar import upload_to_google_calendars


sbp_constants = {
    "locations": {
        "Seattle Poplar": 1,
        "Seattle Fremont": 2,
        "Seattle Upper Walls": 3,
        "Seattle University District": 4,
    },
    "categories": {"Events": 2, "Climbing Classes": 4, "Yoga": 5, "Fitness": 6},
}

base_url = "https://boulderingproject.portal.approach.app/schedule/embed"


def create_url(date, categories, locations):
    # Convert category and location names to IDs
    category_ids = [
        sbp_constants["categories"][cat]
        for cat in categories
        if cat in sbp_constants["categories"]
    ]
    location_ids = [
        sbp_constants["locations"][loc]
        for loc in locations
        if loc in sbp_constants["locations"]
    ]

    # Create query parameters
    params = {
        "scheduleView": "week",
        "date": date,
        "categoryIds": ",".join(map(str, category_ids)),
        "locationIds": ",".join(map(str, location_ids)),
    }

    return f"{base_url}?{urlencode(params, quote_via=quote)}"


# Rows looks like this. First element is a picture
# ['', '6:15 AM – 7:15 AM\n1 hour', 'Power Flow w/ Emma', 'Seattle Poplar', '4 Pricing Options Available\n35/36 left']
def parse_row(row):
    # Skip the picture/empty field (row[0])
    time_range = row[1].split("–")
    start_str = time_range[0].strip()
    end_str = time_range[1].split("\n")[0].strip() if len(time_range) > 1 else None

    # Parse times into 24-hour format (optional)
    start_time = datetime.strptime(start_str, "%I:%M %p").strftime("%H:%M")
    end_time = (
        datetime.strptime(end_str, "%I:%M %p").strftime("%H:%M") if end_str else None
    )

    # Extract number of spots available using regex
    match = re.search(r"(\d+)/\d+ left", row[4])
    available_spots = int(match.group(1)) if match else None

    return {
        "startTime": start_time,
        "endTime": end_time,
        "eventName": row[2].strip(),
        "eventLocation": row[3].strip(),
        "availableSpots": available_spots,
    }


def getEventsForDate(page, date):
    # Select the date on the page and wait for the table to load events
    url = create_url(
        date,
        categories=["Events", "Climbing Classes", "Yoga", "Fitness"],
        locations=["Seattle Poplar", "Seattle University District", "Seattle Fremont"],
    )
    page.goto(url, timeout=3000)
    print("Navigating to " + date)
    page.wait_for_selector("td:has-text('Seattle Poplar')")
    print("Page loaded")

    #  Select all the rows inside the table
    rows = page.query_selector_all("table.MuiTable-root tr.MuiTableRow-root")

    events = []

    for row in rows:
        cells = row.query_selector_all("td")
        values = [cell.inner_text().strip() for cell in cells]
        parsedData = parse_row(values)
        events.append(parsedData)

    return events


def scrape_with_playwright():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, channel="chromium")

        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800},
            device_scale_factor=1,
            is_mobile=False,
            has_touch=False,
        )

        print("Opening browser")
        page = context.new_page()
        page.goto(base_url, timeout=5000)

        # Select default location and save
        poplarButton = page.locator('p:has-text("Seattle Poplar")')
        poplarButton.wait_for(timeout=3000)
        poplarButton.click()
        saveButtom = page.locator('button:has-text("Save")')
        saveButtom.wait_for(timeout=3000)
        saveButtom.click()
        print("Location selected")

        today = datetime.today()
        all_events = {}

        # Including today
        days_to_load = 5

        for i in range(days_to_load):
            date = today + timedelta(days=i)
            date_str = date.strftime("%Y-%m-%d")
            events = getEventsForDate(page, date_str)
            all_events[date_str] = events

        print("Starting calendar upload")
        upload_to_google_calendars(all_events)

        browser.close()


if __name__ == "__main__":
    scrape_with_playwright()

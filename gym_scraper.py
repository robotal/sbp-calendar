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
    page.wait_for_selector("td:has-text('Seattle Poplar')")

    #  Select all the rows inside the table
    rows = page.query_selector_all("table.MuiTable-root tr.MuiTableRow-root")

    events = []

    for row in rows:
        cells = row.query_selector_all("td")
        values = [cell.inner_text().strip() for cell in cells]
        parsedData = parse_row(values)
        events.append(parsedData)

    return events


def generate_ics_per_location(
    events_by_date, output_dir="ics_output", timezone="America/Los_Angeles"
):
    os.makedirs(output_dir, exist_ok=True)
    local_tz = pytz.timezone(timezone)

    # Group events by location
    location_events = defaultdict(list)

    for date_str, events in events_by_date.items():
        for event in events:
            start_dt = datetime.strptime(
                f"{date_str} {event['startTime']}", "%Y-%m-%d %H:%M"
            )
            end_dt = datetime.strptime(
                f"{date_str} {event['endTime']}", "%Y-%m-%d %H:%M"
            )

            event_copy = event.copy()
            event_copy["begin"] = local_tz.localize(start_dt)
            event_copy["end"] = local_tz.localize(end_dt)

            location_events[event["eventLocation"]].append(event_copy)

    # Create one calendar per location
    for location, events in location_events.items():
        cal = Calendar()
        for e_data in events:
            e = Event()
            e.name = e_data["eventName"]
            e.begin = e_data["begin"]
            e.end = e_data["end"]
            e.location = e_data["eventLocation"]
            e.description = f"Available Spots: {e_data['availableSpots']}"
            cal.events.add(e)

        safe_location = location.lower().replace(" ", "_")
        output_path = os.path.join(output_dir, f"{safe_location}.ics")

        with open(output_path, "w") as f:
            f.writelines(cal)

        print(f"Written: {output_path}")


def scrape_with_playwright():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        page.goto(base_url, timeout=3000)
        # page.wait_for_selector(".event")  # Wait for content to load

        # Select default location and save
        page.locator('p:has-text("Seattle Poplar")').click()
        page.locator('button:has-text("Save")').click()

        today = datetime.today()
        all_events = {}

        for i in range(1, 3):
            date = today + timedelta(days=i)
            date_str = date.strftime("%Y-%m-%d")
            events = getEventsForDate(page, date_str)
            all_events[date_str] = (
                events  # or store in a dict if you want to group by day
            )

        generate_ics_per_location(all_events)

        page.wait_for_timeout(1000 * 1800)

        # browser.close()


if __name__ == "__main__":
    scrape_with_playwright()

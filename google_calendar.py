from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
import os
import datetime
import pytz
from collections import defaultdict

SCOPES = ["https://www.googleapis.com/auth/calendar"]
TIMEZONE = "America/Los_Angeles"
CALENDAR_EVENT_PREFIX = "SBP –"  # em dash for pretty titles
CALENDAR_COLD_PLUNGE_PREFIX = "SBP Cold Plunge –"  # em dash for pretty titles
CREDENTIAL_FILE = "secrets/credential.json"
TOKEN_FILE = "secrets/token.json"

GITHUB_OUTPUT = os.getenv("GITHUB_OUTPUT")


def get_calendar_service():
    creds = None
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

    refreshed = False
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            refreshed = True
        else:
            raise Exception("Token invalid or expired and can't be refreshed.")

        with open(TOKEN_FILE, "w") as token:
            token.write(creds.to_json())

    if GITHUB_OUTPUT:
        with open(GITHUB_OUTPUT, "a") as fh:
            fh.write(f"refreshed={'true' if refreshed else 'false'}\n")
            if refreshed:
                fh.write(f"refreshed_token={creds.to_json()}\n")

    return build("calendar", "v3", credentials=creds)


def get_or_create_calendar(service, location_name, prefix):
    calendar_summary = f"{prefix} {location_name}"
    existing = service.calendarList().list().execute()
    for c in existing.get("items", []):
        if c["summary"] == calendar_summary:
            return c["id"]

    new_cal = {
        "summary": calendar_summary,
        "timeZone": TIMEZONE,
    }
    created = service.calendars().insert(body=new_cal).execute()
    print(f"Created calendar for {location_name}")
    return created["id"]


def make_calendar_public(service, calendar_id):
    try:
        rule = {"scope": {"type": "default"}, "role": "reader"}
        service.acl().insert(calendarId=calendar_id, body=rule).execute()
    except Exception as e:
        print(f"Warning: couldn't make calendar public: {e}")


def sync_calendar_events(service, calendar_id, events):
    now = datetime.datetime.utcnow().isoformat() + "Z"
    tz = pytz.timezone(TIMEZONE)

    # Convert new events into a comparable key set
    new_event_map = {}
    for event in events:
        start_dt = tz.localize(
            datetime.datetime.strptime(
                f"{event['date']} {event['startTime']}", "%Y-%m-%d %H:%M"
            )
        )
        end_dt = tz.localize(
            datetime.datetime.strptime(
                f"{event['date']} {event['endTime']}", "%Y-%m-%d %H:%M"
            )
        )
        key = (event["eventName"], start_dt.isoformat(), end_dt.isoformat())
        new_event_map[key] = {
            "summary": event["eventName"],
            "location": event["eventLocation"],
            "description": f"""Available Spots: {event['availableSpots']}"""
            + (f"\nRegister here: {event['url']}" if event.get("url") else ""),
            "start": {"dateTime": start_dt.isoformat(), "timeZone": TIMEZONE},
            "end": {"dateTime": end_dt.isoformat(), "timeZone": TIMEZONE},
        }

    # Fetch existing events
    existing_event_keys = {}
    page_token = None
    while True:
        result = (
            service.events()
            .list(calendarId=calendar_id, timeMin=now, pageToken=page_token)
            .execute()
        )
        for item in result.get("items", []):
            key = (
                item.get("summary"),
                item.get("start", {}).get("dateTime"),
                item.get("end", {}).get("dateTime"),
            )
            existing_event_keys[key] = item.get("id")
        page_token = result.get("nextPageToken")
        if not page_token:
            break

    # Events to delete
    to_delete = set(existing_event_keys) - set(new_event_map)
    for key in to_delete:
        service.events().delete(
            calendarId=calendar_id, eventId=existing_event_keys[key]
        ).execute()

    # Events to insert
    to_add = set(new_event_map) - set(existing_event_keys)
    for key in to_add:
        service.events().insert(
            calendarId=calendar_id, body=new_event_map[key]
        ).execute()


def upload_to_google_calendars(events_by_date):
    service = get_calendar_service()

    # Flatten and group by location
    location_events = defaultdict(list)
    for date_str, events in events_by_date.items():
        for event in events:
            event["date"] = date_str  # add date into event dict
            location_events[event["eventLocation"]].append(event)

    public_links = {}

    for location, events in location_events.items():
        cal_id = get_or_create_calendar(service, location, CALENDAR_EVENT_PREFIX)
        sync_calendar_events(service, cal_id, events)
        make_calendar_public(service, cal_id)

        public_url = f"https://calendar.google.com/calendar/embed?src={cal_id}"
        public_links[location] = public_url
        print(f"✅ Calendar for {location}: {public_url}")

    return public_links


def upload_cold_plunges(events_by_date):
    service = get_calendar_service()

    # Flatten and group by location
    location_events = defaultdict(list)
    for date_str, events in events_by_date.items():
        for event in events:
            event["date"] = date_str  # add date into event dict
            location_events[event["eventLocation"]].append(event)

    public_links = {}

    for location, events in location_events.items():
        cal_id = get_or_create_calendar(service, location, CALENDAR_COLD_PLUNGE_PREFIX)
        sync_calendar_events(service, cal_id, events)
        make_calendar_public(service, cal_id)

        public_url = f"https://calendar.google.com/calendar/embed?src={cal_id}"
        public_links[location] = public_url
        print(f"✅ Cold Plunge Calendar for {location}: {public_url}")

    return public_links

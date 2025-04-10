from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
import os
import datetime
import pytz
from collections import defaultdict

SCOPES = ["https://www.googleapis.com/auth/calendar"]
TIMEZONE = "America/Los_Angeles"
CALENDAR_PREFIX = "SBP –"  # em dash for pretty titles
credential_file = "/Users/tdavidi/Documents/code/secrets/credential.json"
token_file = "/Users/tdavidi/Documents/code/secrets/token.json"


def get_calendar_service():
    creds = None
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file(token_file, SCOPES)
    if not creds or not creds.valid:
        flow = InstalledAppFlow.from_client_secrets_file(credential_file, SCOPES)
        creds = flow.run_local_server(port=0)
        with open(token_file, "w") as token:
            token.write(creds.to_json())
    return build("calendar", "v3", credentials=creds)


def get_or_create_calendar(service, location_name):
    calendar_summary = f"{CALENDAR_PREFIX} {location_name}"
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


def clear_calendar(service, calendar_id):
    now = datetime.datetime.utcnow().isoformat() + "Z"
    events = service.events().list(calendarId=calendar_id, timeMin=now).execute()
    for event in events.get("items", []):
        service.events().delete(calendarId=calendar_id, eventId=event["id"]).execute()


def upload_events(service, calendar_id, events):
    tz = pytz.timezone(TIMEZONE)
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

        event_body = {
            "summary": event["eventName"],
            "location": event["eventLocation"],
            "description": f"Available Spots: {event['availableSpots']}",
            "start": {
                "dateTime": start_dt.isoformat(),
                "timeZone": TIMEZONE,
            },
            "end": {
                "dateTime": end_dt.isoformat(),
                "timeZone": TIMEZONE,
            },
        }

        service.events().insert(calendarId=calendar_id, body=event_body).execute()


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
        cal_id = get_or_create_calendar(service, location)
        clear_calendar(service, cal_id)
        upload_events(service, cal_id, events)
        make_calendar_public(service, cal_id)

        public_url = f"https://calendar.google.com/calendar/embed?src={cal_id}"
        public_links[location] = public_url
        print(f"✅ Calendar for {location}: {public_url}")

    return public_links

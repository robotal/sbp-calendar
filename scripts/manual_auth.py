from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
import os
from google.oauth2.credentials import Credentials

SCOPES = ["https://www.googleapis.com/auth/calendar"]
CREDENTIAL_FILE = "secrets/credential.json"
TOKEN_FILE = "secrets/token.json"

flow = InstalledAppFlow.from_client_secrets_file(CREDENTIAL_FILE, SCOPES)
creds = flow.run_local_server(port=0)

with open(TOKEN_FILE, "w") as token:
    token.write(creds.to_json())

print("\nCopy this token and update your GitHub secret `CREDENTIAL_JSON`:\n")
with open(TOKEN_FILE) as f:
    print(f.read())

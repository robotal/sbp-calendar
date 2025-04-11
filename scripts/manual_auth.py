from google_auth_oauthlib.flow import InstalledAppFlow
import os

SCOPES = ["https://www.googleapis.com/auth/calendar"]
CREDENTIAL_FILE = "secrets/credential.json"
TOKEN_FILE = "secrets/token.json"
GITHUB_OUTPUT = os.getenv("GITHUB_OUTPUT")

flow = InstalledAppFlow.from_client_secrets_file(CREDENTIAL_FILE, SCOPES)
# Set redirect URI to "urn:ietf:wg:oauth:2.0:oob" for manual/paste auth
flow.redirect_uri = "urn:ietf:wg:oauth:2.0:oob"
auth_url, _ = flow.authorization_url(prompt="consent")

print(f"Please go to this URL and authorize the app:\n{auth_url}")

# Now prompt the user to paste the authorization code
code = input("Enter the authorization code here: ")

flow.fetch_token(code=code)
creds = flow.credentials

with open(TOKEN_FILE, "w") as token:
    token.write(creds.to_json())

print("✅ Token created and stored.")

# Write token to GitHub Actions output (safe for secrets update)
if GITHUB_OUTPUT:
    with open(GITHUB_OUTPUT, "a") as fh:
        fh.write(f"refreshed=true\n")
        fh.write(f"refreshed_token={creds.to_json()}\n")

import os
import json
from flask import Flask, request, redirect, session, url_for
from dotenv import load_dotenv
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from datetime import datetime, timedelta

# ── Load environment vars from .env ───────────────────────────────────────────
load_dotenv()

# ── Flask setup ──────────────────────────────────────────────────────────────
app = Flask(__name__)
app.secret_key = os.urandom(24)   # needed for secure session storage

# ── Load your Google client config ────────────────────────────────────────────
# credentials.json is the file you downloaded from Google Cloud Console
with open('credentials.json', 'r') as f:
    CLIENT_CONFIG = json.load(f)

SCOPES = ['https://www.googleapis.com/auth/calendar.events']
REDIRECT_URI = os.getenv('REDIRECT_URI')  # from your .env

# ── Root health‐check route ───────────────────────────────────────────────────
@app.route('/')
def home():
    return '🚀 WhatsApp–Calendar Bot is up and running!'

# ── 1) Authorize endpoint ─────────────────────────────────────────────────────
@app.route('/authorize')
def authorize():
    flow = Flow.from_client_config(
        CLIENT_CONFIG,
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI
    )
    auth_url, _ = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true'
    )
    return redirect(auth_url)

# ── 2) OAuth2 callback endpoint ────────────────────────────────────────────────
@app.route('/oauth2callback')
def oauth2callback():
    flow = Flow.from_client_config(
        CLIENT_CONFIG,
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI
    )
    flow.fetch_token(code=request.args.get('code'))
    creds = flow.credentials

    # Save the credentials into the session (or store in a DB)
    session['credentials'] = {
        'token': creds.token,
        'refresh_token': creds.refresh_token,
        'token_uri': creds.token_uri,
        'client_id': creds.client_id,
        'client_secret': creds.client_secret,
        'scopes': creds.scopes
    }

    return '✅ Authorization complete! You can now create calendar events.'

# ── Helper to build a calendar client ─────────────────────────────────────────
def build_calendar_service():
    creds_info = session.get('credentials')
    if not creds_info:
        return None
    creds = Credentials(**creds_info)
    return build('calendar', 'v3', credentials=creds)

# ── 3) Test route to create a dummy event ────────────────────────────────────
@app.route('/create_test_event')
def create_test_event():
    service = build_calendar_service()
    if not service:
        return redirect(url_for('authorize'))

    start_time = datetime.utcnow()
    end_time   = start_time + timedelta(hours=1)
    event = {
        'summary': '🚀 Test Event from WhatsApp Bot',
        'start':   {'dateTime': start_time.isoformat() + 'Z'},
        'end':     {'dateTime': end_time.isoformat()   + 'Z'},
    }
    created = service.events().insert(calendarId='primary', body=event).execute()
    return (
        f"✅ Event created! "
        f"<a href='{created.get('htmlLink')}' target='_blank'>View in Google Calendar</a>"
    )


# ── Run server ────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    app.run(debug=True) 
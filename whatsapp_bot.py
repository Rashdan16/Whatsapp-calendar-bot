import os
import json
from flask import Flask, request, redirect, session, url_for
from dotenv import load_dotenv
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from datetime import datetime, timedelta
from twilio.twiml.messaging_response import MessagingResponse
from pyngrok import ngrok

def parse_event(text):
    """
    Very naïve parser:
    - Uses the entire incoming message as the event title.
    - Schedules it to start NOW (UTC) and last 1 hour.
    Returns: (title, start_iso, end_iso)
    """
    title = text
    start = datetime.utcnow()
    end   = start + timedelta(hours=1)
    # Format as ISO strings with Z to indicate UTC
    start_iso = start.isoformat() + 'Z'
    end_iso   = end.isoformat()   + 'Z'
    return title, start_iso, end_iso


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
    flow = Flow.from_client_config(CLIENT_CONFIG, scopes=SCOPES, redirect_uri=REDIRECT_URI)
    flow.fetch_token(code=request.args.get('code'))
    creds = flow.credentials

    # Persist to a file
    with open('token.json', 'w') as token_file:
        token_file.write(creds.to_json())

    return '✅ Authorization complete! You can now create calendar events.'


# ── Helper to build a calendar client ─────────────────────────────────────────
def build_calendar_service():
    if not os.path.exists('token.json'):
        return None
    creds = Credentials.from_authorized_user_file('token.json', SCOPES)
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

# ── 4) WhatsApp webhook ─────────────────────────────────────────────────────
@app.route('/webhook', methods=['POST'])
def whatsapp_webhook():
    incoming_msg = request.values.get('Body', '').strip()

    service = build_calendar_service()
    if not service:
        auth_url = url_for('authorize', _external=True)
        resp = MessagingResponse()
        resp.message(f"👋 Hi there! To link your Google Calendar, tap here:\n{auth_url}")
        return str(resp)

 


    # 2) Parse message → (title, start_iso, end_iso)
    title, start_iso, end_iso = parse_event(incoming_msg)

    # 3) Create the Calendar event
    service = build_calendar_service()
    event = {
        'summary': title,
        'start': {'dateTime': start_iso, 'timeZone': 'Asia/Dhaka'},
        'end':   {'dateTime': end_iso,   'timeZone': 'Asia/Dhaka'},
    }
    service.events().insert(calendarId='primary', body=event).execute()

    # 4) Reply via WhatsApp
    resp = MessagingResponse()
    resp.message(f"✅ Booked “{title}” on {start_iso.replace('T',' ').split('+')[0]}")
    return str(resp)

# ── Run server ────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    # Only kill/connect in the child process (not the initial parent)
    if os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        ngrok.kill()
        tunnel = ngrok.connect(5000, bind_tls=True)
        print(f" * ngrok tunnel running at: {tunnel.public_url}/webhook")

    # Now start Flask
    app.run(debug=True) 
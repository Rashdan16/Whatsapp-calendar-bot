import os
import json
import re
from flask import Flask, request, redirect, session, url_for
from dotenv import load_dotenv
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from datetime import datetime, timedelta
from twilio.twiml.messaging_response import MessagingResponse
from pyngrok import ngrok
import openai
from googleapiclient.errors import HttpError
from openai import OpenAI
# ── Load environment vars from .env ───────────────────────────────────────────
load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
MODEL  = "gpt-4o-mini"   # alias for “4.1-nano” in the SDK

def parse_event(text: str):
    """Use GPT-4.1 Nano to extract title, start, end, attendees."""
    prompt = f"""
Extract from this message a calendar event.  
Return ONLY valid JSON with keys: title (string), start (ISO datetime), end (ISO datetime), attendees (array of emails, may be empty).

Message:
\"\"\" 
{text}
\"\"\" 
"""

    resp = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": "You are a helpful calendar assistant."},
            {"role": "user", "content": prompt}
        ],
        temperature=0
    )

    raw = resp.choices[0].message.content.strip()
    print("🔍 raw LLM output:", repr(raw))

    # Clean up any formatting like ```json or triple quotes
    cleaned = re.sub(r"^```json|```$", "", raw.strip(), flags=re.MULTILINE)

    # Try to parse JSON safely
    return json.loads(cleaned)







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

    # 1) Ensure we have calendar creds
    service = build_calendar_service()
    if not service:
        auth_url = url_for('authorize', _external=True)
        resp    = MessagingResponse()
        resp.message(f"👋 Hi there! To link your Google Calendar, tap here:\n{auth_url}")
        return str(resp)

    # 2) Parse via AI
    data      = parse_event(incoming_msg)
    title     = data['title']
    start_iso = data['start']
    end_iso   = data['end']
    attendees = data.get('attendees', [])

    # 3) Build the event
    event = {
      'summary':   title,
      'start':   {'dateTime': start_iso, 'timeZone': 'Asia/Dhaka'},
      'end':     {'dateTime': end_iso,   'timeZone': 'Asia/Dhaka'},
      'attendees': [{'email': e} for e in attendees],
    }

    # 4) Try inserting — catch failures
    try:
        created = service.events().insert(calendarId='primary', body=event).execute()
    except HttpError as e:
        resp = MessagingResponse()
        resp.message("❌ Oops! I wasn’t able to create your event. Please try again later.")
        return str(resp)

    # 5) Success reply
    resp = MessagingResponse()
    resp.message(f"✅ Booked “{title}” on {start_iso.replace('T',' ').split('Z')[0]}")
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
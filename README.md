# Whatsapp-calendar-bot
Ask a ai bot in whatapp to schedule an event

# WhatsApp–Calendar Bot

**Overview:**  
A WhatsApp chatbot that parses event requests and schedules them in Google Calendar.

## Tech Stack
- Python 3.10+
- Flask
- Twilio (or Meta) WhatsApp API
- OpenAI GPT API
- Google Calendar API

## Local Setup
1. Clone repo & `cd` into it  
2. `python3 -m venv venv && source venv/bin/activate`  
3. `pip install -r requirements.txt`  
4. Copy `.env.example` → `.env`, then fill in your keys  
5. `flask run`

## Branching Strategy
- `main`: stable prototype  
- `feature/...`: new features  

Reminder: Once you add more routes or callbacks, use the Flask CLI instead of python whatsapp_bot.py—set FLASK_APP=whatsapp_bot.py and run flask run for auto-reload and better error pages.


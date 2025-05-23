import os
import re
import requests
import datetime
import pytz
from dateutil import parser

# === Azure App Details ===
TENANT_ID = '89cf11d4-079d-47a6-af93-e6ae64ceb42c'
CLIENT_ID = '570470dd-be0d-4dd2-aac7-9a3a66b57e6e'
CLIENT_SECRET = 'RLr8Q~TzOS2j1ASxnZbplZdJhpgYCvL1rXqs3bqb'
USER_EMAIL = 'data.aianalytics@intelliswift.com'

# === GROQ API ===
GROQ_API_KEY = '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'
GROQ_API_URL = 'https://api.groq.com/openai/v1/chat/completions'
MODEL_NAME = 'llama3-8b-8192'

# === Internal Team Email ===
INTERNAL_EMAIL = 'rohit.jagdale@intelliswift.com'

# === Get latest file from chat_logs ===
def get_latest_file(directory='chat_logs') -> str:
    files = [f for f in os.listdir(directory)
             if f.startswith("all_chat_history_sr_") and f.endswith(".txt")]
    if not files:
        raise FileNotFoundError(f"No transcript files in {directory}")
    files.sort(key=lambda x: int(re.findall(r'\d+', x)[-1]))
    return os.path.join(directory, files[-1])

# === Safe extract using regex ===
def safe_extract(pattern: str, text: str, field_name: str) -> str | None:
    match = re.search(pattern, text, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    print(f"⚠️ Could not extract {field_name}")
    return None

# === Call Groq API to extract info from text ===
def extract_info_from_text(file_path: str) -> str:
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    system_prompt = (
        "You are an assistant. Extract the name, email, date, time, and interested product from the given text."
    )
    user_prompt = f"""This is a communication between a chatbot and human:
{content}
Extract and return the following:
- Name
- Email
- Date
- Time
- Interested Product"""

    payload = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_prompt}
        ],
        "temperature": 0.2
    }
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    resp = requests.post(GROQ_API_URL, json=payload, headers=headers)
    resp.raise_for_status()
    return resp.json()['choices'][0]['message']['content']

# === Microsoft Graph API: Get Access Token ===
def get_access_token() -> str:
    url = f'https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/token'
    data = {
        'grant_type': 'client_credentials',
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET,
        'scope': 'https://graph.microsoft.com/.default'
    }
    resp = requests.post(url, data=data)
    resp.raise_for_status()
    return resp.json()['access_token']

# === Microsoft Teams Meeting (IST, DD/MM/YYYY) ===
def create_teams_meeting(token: str, name: str, email: str, date_raw: str, time_raw: str, product: str) -> dict:
    """
    Creates a Teams meeting and returns meeting details, including join URL.
    """
    # Parse date & time
    naive_dt = parser.parse(f"{date_raw} {time_raw}", dayfirst=True)
    ist = pytz.timezone("Asia/Kolkata")
    meeting_start = ist.localize(naive_dt)
    meeting_end = meeting_start + datetime.timedelta(minutes=30)

    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    meeting_payload = {
        "subject": f"📅 {product} Demo with {name}",
        "body": {"contentType": "HTML", "content": f"Let's connect to discuss {product}."},
        "start": {"dateTime": meeting_start.isoformat(), "timeZone": "Asia/Kolkata"},
        "end":   {"dateTime": meeting_end.isoformat(),   "timeZone": "Asia/Kolkata"},
        "location": {"displayName": "Microsoft Teams Meeting"},
        "attendees": [
            {"emailAddress": {"address": email, "name": name},            "type": "required"},
            {"emailAddress": {"address": INTERNAL_EMAIL, "name": "Sales Team"}, "type": "required"}
        ],
        "isOnlineMeeting": True,
        "onlineMeetingProvider": "teamsForBusiness"
    }

    url = f"https://graph.microsoft.com/v1.0/users/{USER_EMAIL}/events?sendInvites=true"
    resp = requests.post(url, headers=headers, json=meeting_payload)
    resp.raise_for_status()
    evt = resp.json()

    return {
        'join_url': evt.get('onlineMeeting', {}).get('joinUrl'),
        'start': meeting_start.isoformat(),
        'end': meeting_end.isoformat(),
        'subject': meeting_payload['subject']
    }

# === LangGraph node ===
def schedule_meeting(state: dict) -> dict:
    """
    Graph node: extracts info from transcript and schedules a Teams meeting.
    Updates state with meeting details.
    """
    # Locate transcript
    transcript_path = state.get('transcript_path') or get_latest_file()

    # Extract raw info
    extracted = extract_info_from_text(transcript_path)

    # Safe extraction
    name = safe_extract(r'name[:\- ]+(.*)', extracted, 'name')
    email = safe_extract(r'email[:\- ]+(.*)', extracted, 'email')
    date_raw = safe_extract(r'date[:\- ]+([0-9/\-]+)', extracted, 'date')
    time_raw = safe_extract(r'time[:\- ]+([0-9: ]+[APMapm]+)', extracted, 'time')
    product = safe_extract(r'product[:\- ]+(.*)', extracted, 'product')

    # Validate
    if not all([name, email, date_raw, time_raw, product]):
        raise ValueError(f"Missing meeting info: {name}, {email}, {date_raw}, {time_raw}, {product}")

    # Get token and create meeting
    token = get_access_token()
    meet_info = create_teams_meeting(token, name, email, date_raw, time_raw, product)

    # Update state
    state['meeting_details'] = meet_info
    print(f"[scheduling_agent] Meeting scheduled, invite sent to {email}")
    return state

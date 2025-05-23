from dotenv import load_dotenv
load_dotenv()

import os
import re
import requests
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

def summarize_and_send_email(state):
    """Summarize chat transcript via Groq API and send email via SMTP."""
    transcript_path = state["transcript_path"]
    with open(transcript_path, "r", encoding="utf-8") as f:
        conversation = f.read()

    groq_key = os.getenv("GROQ_API_KEY")
    groq_url = os.getenv("GROQ_API_URL")
    model_name = os.getenv("GROQ_MODEL_NAME")

    prompt = f"""Extract the lead information from the following AI chat conversation and format it as a professional summary email to the sales team. Follow this format exactly:

Dear Sales Team,

Following a recent interaction with our AI agent, a new high-potential lead has been identified and is ready for follow-up. Please find the lead details below:

Lead Information
Name: <Name>
Email Address: <Email>
Interested Product: <Product Name>
Online Demo Interest: <Yes/No> – customer <confirmed/declined> readiness for an online demo

Please reach out to the lead at your earliest convenience to continue the conversation and explore potential opportunities.

Best regards,
AI Agent
AI Lead Management System

Chat Transcript:
{conversation}
"""

    payload = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": "You are an AI assistant that summarizes chat transcripts into structured emails."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.3
    }

    headers = {"Authorization": f"Bearer {groq_key}", "Content-Type": "application/json"}
    resp = requests.post(groq_url, json=payload, headers=headers)
    resp.raise_for_status()
    content = resp.json()["choices"][0]["message"]["content"]

    lines = content.strip().splitlines()
    filtered = [l for l in lines if not l.lower().startswith("subject:") and "draft" not in l.lower()]
    body = "\n".join(filtered).strip()

    name_match = re.search(r"Name:\s*(.+)", body)
    name = name_match.group(1).strip() if name_match else "New Lead"
    subject = f"New Lead Identified – {name}"

    sender = os.getenv("SENDER_EMAIL")
    password = os.getenv("SENDER_PASSWORD")
    receiver = os.getenv("RECEIVER_EMAIL")

    message = MIMEMultipart()
    message["From"] = sender
    message["To"] = receiver
    message["Subject"] = subject
    message.attach(MIMEText(body, "plain"))

    server = smtplib.SMTP("smtp.gmail.com", 587)
    server.starttls()
    server.login(sender, password)
    server.sendmail(sender, receiver, message.as_string())
    server.quit()

    state["email_status"] = f"Sent summary email with subject: {subject}"
    print(f"[email_agent] {state['email_status']}")
    return state

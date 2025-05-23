# ProductEmail.py

import os
import re
import json
import requests
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

def get_latest_serial_file(directory: str) -> str:
    """Return the path to the latest all_chat_history_sr_*.txt in `directory`."""
    files = [
        f for f in os.listdir(directory)
        if f.startswith("all_chat_history_sr_") and f.endswith(".txt")
    ]
    if not files:
        raise FileNotFoundError(f"No transcript files in {directory}")
    def serial(fn):
        m = re.search(r"all_chat_history_sr_(\d+)\.txt", fn)
        return int(m.group(1)) if m else -1
    latest = max(files, key=serial)
    return os.path.join(directory, latest)

def summarize_and_send_email(state: dict) -> dict:
    """
    1) Reads the transcript specified by state['transcript_path'],
    2) extracts the customer email,
    3) calls the LLM for product recommendations,
    4) emails the customer.
    """
    # 1. locate transcript from state or fallback
    transcript_path = state.get("transcript_path")
    if not transcript_path or not os.path.isfile(transcript_path):
        transcript_dir = os.getenv("TRANSCRIPT_DIR", ".")
        transcript_path = get_latest_serial_file(transcript_dir)

    with open(transcript_path, "r", encoding="utf-8") as f:
        conversation = f.read()

    # 2. extract customer email
    email_match = re.search(r"[\w\.-]+@[\w\.-]+\.\w+", conversation)
    if not email_match:
        raise ValueError("No customer email found in the transcript.")
    customer_email = email_match.group(0)

    # 3. call the LLM to get recommendations
    groq_key   = os.getenv("GROQ_API_KEY")
    groq_url   = os.getenv("GROQ_API_URL")
    model_name = os.getenv("GROQ_MODEL_NAME")

    llm_prompt = (
        "Based on this conversation, recommend the single best product for the lead. "
        "Respond in JSON with keys: product_name, video_link, document_link.\n\n"
        f"Conversation:\n{conversation}"
    )
    payload = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": "You are an assistant that suggests product resources."},
            {"role": "user",   "content": llm_prompt}
        ],
        "temperature": 0.2
    }
    headers = {"Authorization": f"Bearer {groq_key}", "Content-Type": "application/json"}
    resp = requests.post(groq_url, json=payload, headers=headers)
    resp.raise_for_status()
    content = resp.json()["choices"][0]["message"]["content"].strip()

    # Extract JSON block from response
    match = re.search(r"\{.*\}", content, flags=re.DOTALL)
    if not match:
        raise ValueError(f"LLM did not return a JSON block:\n{content}")
    json_str = match.group(0)
    try:
        recs = json.loads(json_str)
    except json.JSONDecodeError:
        raise ValueError(f"Error parsing JSON from LLM response:\n{json_str}")

    product_name = recs.get("product_name", "Your Product")
    video_link   = recs.get("video_link", "")
    doc_link     = recs.get("document_link", "")

    # 4. compose & send email to the customer
    sender   = os.getenv("SENDER_EMAIL")
    password = os.getenv("SENDER_PASSWORD")
    subject  = f"Resources for {product_name}"

    body = f"""Hello,

Thank you for chatting with our AI assistant. Based on your interests, we recommend **{product_name}**.

▶️ Watch the product overview video:
{video_link}

📄 Read the detailed documentation:
{doc_link}

If you have any further questions, feel free to reply to this email.

Best regards,
AI Support Team
"""

    msg = MIMEMultipart()
    msg["From"]    = sender
    msg["To"]      = customer_email
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login(sender, password)
        server.send_message(msg)

    # update and return state
    state.update({
        "transcript_path": transcript_path,
        "customer_email":  customer_email,
        "product_name":    product_name,
        "video_link":      video_link,
        "document_link":   doc_link,
        "email_status":    f"Sent recommendations to {customer_email}"
    })
    print(f"[product_email_agent] {state['email_status']}")
    return state

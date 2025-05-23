import os
import openai
from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential

import logging
 
# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Azure credentials
try:
    credential = DefaultAzureCredential()
    logger.info("Successfully initialized Azure credentials")
except Exception as e:
    logger.error(f"Failed to initialize Azure credentials: {str(e)}")
    credential = None

# ... [config and other imports as before] ...

# === LLM Configuration ===
llm_config = {
    "config_list": [{
        "model": "gpt-4o",
        "api_key": "YOUR_API_KEY",
        "base_url": "https://data-mahx4ixq-westeurope.services.ai.azure.com/",
        "api_type": "azure",
        "api_version": "2024-02-15-preview"
    }]
}
config = llm_config["config_list"][0]
openai.api_type    = config["api_type"]
openai.api_base    = config["base_url"]
openai.api_version = config["api_version"]
openai.api_key     = config["api_key"]
INTENT_DEPLOYMENT = config["model"]

'''project_client = AIProjectClient.from_connection_string()
project_client = AIProjectClient.from_connection_string(
    credential=DefaultAzureCredential(),
    conn_str="eastus2.api.azureml.ms;2c33e03c-3b25-4174-8086-feed9ee27475;Customer_service_Agent;customer_service_agent1"
)'''
#project_client = AIProjectClient(endpoint="https://customerservic4873468061.services.ai.azure.com/models",subscription_id="2c33e03c-3b25-4174-8086-feed9ee27475",resource_group_name="Customer_service_Agent",project_name="customer_service_Agent1", credential=DefaultAzureCredential())
project_client = AIProjectClient(endpoint="https://customerservic4873468061.openai.azure.com/",credential=DefaultAzureCredential())
agent = project_client.agents.get_agent("asst_wEEJsqIqJFwu6G8KOGn65EUk")

# === GLOBAL THREAD, created ONCE per app run ===
thread = project_client.agents.create_thread()
thread_id = thread.id

MAX_TURNS = 20
TIMEOUT_SEC = 800

def has_provided_required_details(user_message: str) -> bool:
    # [no changes]
    prompt = (
        "You are collecting user info (name, email, product, demo time). "
        f"User said: \"{user_message}\". "
        "Has the user provided all required details? Answer \"yes\" or \"no\"."
    )
    try:
        resp = openai.ChatCompletion.create(
            engine=INTENT_DEPLOYMENT,
            messages=[
                {"role": "system", "content": "Answer with yes or no only."},
                {"role": "user",   "content": prompt}
            ],
            temperature=0.0,
            max_tokens=1
        )
        ans = resp.choices[0].message.content.strip().lower()
        return ans.startswith("yes")
    except Exception:
        return False

def save_chat_history(history) -> str:
    # [same as before]
    base_dir = "chat_logs"
    os.makedirs(base_dir, exist_ok=True)
    existing = [
        f for f in os.listdir(base_dir)
        if f.startswith("all_chat_history_sr_") and f.endswith(".txt")
    ]
    nums = [
        int(f.split("_")[-1].split(".")[0]) for f in existing
        if f.split("_")[-1].split(".")[0].isdigit()
    ]
    sr = max(nums, default=0) + 1
    path = os.path.join(base_dir, f"all_chat_history_sr_{sr}.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"Serial Number: {sr}\n\n")
        for msg in history:
            f.write(f"User: {msg['user']}\nBot: {msg['bot']}\n")
            f.write("\n" + "-"*40 + "\n\n")
    print(f"💾 Chat history saved as {path}")
    return path

# === Use GLOBAL thread_id ===
def send_message_to_bot(user_message: str) -> str:
    project_client.agents.create_message(
        thread_id=thread_id,
        role="user",
        content=user_message
    )
    project_client.agents.create_and_process_run(
        thread_id=thread_id,
        agent_id=agent.id
    )
    msgs = project_client.agents.list_messages(thread_id=thread_id)
    for m in msgs.text_messages:
        return m.text['value']
    return "Sorry, I didn't understand that."

def run_chatbot(turn_limit=MAX_TURNS, inactivity_timeout=TIMEOUT_SEC) -> dict:
    print("run_chatbot called (dummy implementation).")
    return {"transcript_path": None}

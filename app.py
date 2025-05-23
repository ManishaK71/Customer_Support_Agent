from flask import Flask, render_template, request, jsonify
from time import time
from ChatAgent import (
    send_message_to_bot,
    has_provided_required_details,
    save_chat_history,
    MAX_TURNS,
    TIMEOUT_SEC
)
from SummaryEmail import summarize_and_send_email as send_sales_summary
from ProductEmail import summarize_and_send_email as send_product_recommendations
from MeetingAgent import schedule_meeting
from langgraph.graph import StateGraph, START, END
from ChatAgent import run_chatbot
from graph_workflow import main

app = Flask(__name__, static_folder='static', template_folder='templates')

chat_history = []
chat_meta = {"turn_count": 0, "last_activity": time()}

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/chat', methods=['POST'])
def chat():
    now = time()
    exit_flag = False

    if now - chat_meta["last_activity"] >= TIMEOUT_SEC:
        exit_flag = True
    else:
        chat_meta["last_activity"] = now

    data = request.json or {}
    user_msg = data.get('message', '').strip()
    if not user_msg:
        return jsonify({'bot': 'Please say something.', 'exit': False})

    chat_meta["turn_count"] += 1
    print(f"[DEBUG] Turn count: {chat_meta['turn_count']}, Last activity: {chat_meta['last_activity']}")
    if chat_meta["turn_count"] >= MAX_TURNS:
        exit_flag = True

    chat_history.append({'sender': 'user', 'text': user_msg})
    bot_reply = send_message_to_bot(user_msg)
    chat_history.append({'sender': 'bot', 'text': bot_reply})

    if exit_flag or has_provided_required_details(user_msg):
        convo_pairs = []
        for i in range(0, len(chat_history), 2):
            user_entry = chat_history[i]['text']
            bot_entry = chat_history[i+1]['text'] if i+1 < len(chat_history) else ''
            convo_pairs.append({'user': user_entry, 'bot': bot_entry})

        transcript_path = save_chat_history(convo_pairs)
        state = {"transcript_path": transcript_path}

        send_sales_summary(state)
        send_product_recommendations(state)
        schedule_meeting(state)

        chat_history.clear()
        chat_meta["turn_count"] = 0
        chat_meta["last_activity"] = now

        return jsonify({'bot': bot_reply, 'exit': True})

    return jsonify({'bot': bot_reply, 'exit': False})

@app.route('/status', methods=['GET'])
def status():
    now = time()
    timed_out = (now - chat_meta["last_activity"]) >= TIMEOUT_SEC
    turns_exceeded = chat_meta["turn_count"] >= MAX_TURNS
    return jsonify({
        "timed_out": timed_out,
        "turns_exceeded": turns_exceeded,
        "turn_count": chat_meta["turn_count"],
        "seconds_since_last": now - chat_meta["last_activity"]
    })

@app.route('/force_exit', methods=['POST'])
def force_exit():
    now = time()
    convo_pairs = []
    for i in range(0, len(chat_history), 2):
        user_entry = chat_history[i]['text']
        bot_entry = chat_history[i+1]['text'] if i+1 < len(chat_history) else ''
        convo_pairs.append({'user': user_entry, 'bot': bot_entry})

    transcript_path = save_chat_history(convo_pairs) if convo_pairs else None
    state = {"transcript_path": transcript_path} if transcript_path else {}

    if transcript_path:
        send_sales_summary(state)
        send_product_recommendations(state)
        schedule_meeting(state)

    chat_history.clear()
    chat_meta["turn_count"] = 0
    chat_meta["last_activity"] = now

    return jsonify({'status': 'followup triggered'})

def langgraph_workflow():

    graph = StateGraph(dict)

    # 1) Customer chat node: collects details and returns {'transcript_path': ...}
    graph.add_node(
        "cust_agent",
        lambda state: run_chatbot(
            turn_limit=MAX_TURNS,
            inactivity_timeout=TIMEOUT_SEC
        )
    )

    # 2) Summary email node: send a structured summary email to sales team
    graph.add_node("email_agent", send_sales_summary)

    # 3) Product email node: send product recommendations to customer
    graph.add_node("product_email_agent", send_product_recommendations)

    # 4) Scheduling node: schedule a meeting if needed
    graph.add_node("scheduling_agent", schedule_meeting)

    # --- Workflow sequence as per requirements ---
    graph.add_edge(START, "cust_agent")
    graph.add_edge("cust_agent", "email_agent")
    graph.add_edge("email_agent", "product_email_agent")
    graph.add_edge("product_email_agent", "scheduling_agent")
    graph.add_edge("scheduling_agent", END)

    # Compile and run the workflow
    workflow_app = graph.compile()
    workflow_app.invoke({})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)

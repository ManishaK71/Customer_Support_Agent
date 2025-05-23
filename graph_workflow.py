# graph_workflow.py
from dotenv import load_dotenv

load_dotenv()

from langgraph.graph import StateGraph
from langgraph.graph.state import START, END

from ChatAgent import run_chatbot, MAX_TURNS, TIMEOUT_SEC
from SummaryEmail import summarize_and_send_email as send_sales_summary
from ProductEmail import summarize_and_send_email as send_product_recommendations
from MeetingAgent import schedule_meeting


def main():
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

    # Define workflow sequence
    graph.add_edge(START, "cust_agent")
    graph.add_edge("cust_agent", "email_agent")
    graph.add_edge("email_agent", "product_email_agent")
    graph.add_edge("product_email_agent", "scheduling_agent")
    graph.add_edge("scheduling_agent", END)

    # Compile and run the workflow
    app = graph.compile()
    print("Starting LangGraph customer service workflow…")
    app.invoke({})


if __name__ == "__main__":
    main()

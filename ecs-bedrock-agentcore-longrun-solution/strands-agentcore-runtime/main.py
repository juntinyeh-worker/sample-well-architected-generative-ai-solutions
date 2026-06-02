"""Strands Agent as AgentCore Runtime with async task management."""
import json
import threading
import logging
from aws_api_agent import create_supervisor_agent
from bedrock_agentcore.runtime import BedrockAgentCoreApp

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = BedrockAgentCoreApp()
results = {}


@app.entrypoint
def main(payload):
    """Handle incoming requests with async task support."""
    user_input = payload.get("input", payload.get("prompt", ""))

    # Poll for completed task
    check_task = payload.get("check_task")
    if check_task:
        if check_task in results:
            return {"status": "complete", "task_id": check_task, "response": results.pop(check_task)}
        return {"status": "processing", "task_id": check_task}

    if not user_input:
        return {"status": "error", "response": "No input provided."}

    # Create agent per-request so SSM model override takes effect in realtime
    agent = create_supervisor_agent()

    # Start async task
    task_id = app.add_async_task("strands_prompt")

    def run():
        try:
            response = agent(user_input)
            results[task_id] = response.message['content'][0]['text']
        except Exception as e:
            results[task_id] = f"Error: {e}"
        finally:
            app.complete_async_task(task_id)

    threading.Thread(target=run, daemon=True).start()
    return {"status": "accepted", "task_id": task_id, "response": "Working on your request..."}


if __name__ == "__main__":
    logger.info("Starting Strands AgentCore Runtime")
    app.run()

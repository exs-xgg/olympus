import asyncio
import os
import sys

# Ensure backend directory is in path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from config import get_settings
from orchestrator.graph import compile_graph

print("Settings API Key:", "SET" if get_settings().openai_api_key else "NOT SET")

async def test():
    try:
        print("Compiling graph...")
        graph = compile_graph()
        print("Graph compiled successfully")
        
        # Test basic invocation
        print("Testing invocation...")
        config = {"configurable": {"thread_id": "test-1"}}
        result = await asyncio.to_thread(
            graph.invoke,
            {"messages": [("user", "Hello")], "task_id": "test", "task_description": "test", "current_agent": "supervisor", "status": "running"},
            config
        )
        print("Invocation successful:", result.get("status"))
        
    except Exception as e:
        import traceback
        print(f"FAILED: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test())

import asyncio
from backend.config import get_settings
from backend.orchestrator.graph import get_graph

print("Settings:", get_settings())

try:
    print("Compiling graph...")
    graph = get_graph()
    print("Graph compiled successfully")
except Exception as e:
    print(f"FAILED TO COMPILE GRAPH: {e}")

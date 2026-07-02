import asyncio
from src.client import MuseScoreClient
from src.tools.analysis import setup_analysis_tools

class MockMCP:
    def __init__(self):
        self.tools = {}
        
    def tool(self):
        def decorator(func):
            self.tools[func.__name__] = func
            return func
        return decorator

async def main():
    print("Connecting to MuseScore websocket...")
    client = MuseScoreClient()
    
    mcp = MockMCP()
    setup_analysis_tools(mcp, client)
    
    print("Running harmony check...")
    result = await mcp.tools["check_harmony_rules"]()
    print("Result:")
    print(result)
    
if __name__ == "__main__":
    asyncio.run(main())

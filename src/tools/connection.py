"""Connection and utility tools for MuseScore MCP."""

from ..client import MuseScoreClient
from ..utils.response_formatter import run_and_format_response


def setup_connection_tools(mcp, client: MuseScoreClient):
    """Setup connection and utility tools."""
    
    @mcp.tool()
    async def connect_to_musescore():
        """Connect to the MuseScore WebSocket API."""
        result = await client.connect()
        return {"success": result}

    @mcp.tool()
    async def ping_musescore():
        """Ping the MuseScore WebSocket API to check connection."""
        return await run_and_format_response(client, "ping")

    @mcp.tool()
    async def get_score():
        """Get information about the current score."""
        return await run_and_format_response(client, "getScore")
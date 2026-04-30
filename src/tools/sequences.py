"""Sequence processing tools for MuseScore MCP."""

from ..client import MuseScoreClient
from ..types import ActionSequence
from ..utils.response_formatter import run_and_format_response


def setup_sequence_tools(mcp, client: MuseScoreClient):
    """Setup sequence processing tools."""
    
    @mcp.tool()
    async def processSequence(sequence: ActionSequence):
        """Process a sequence of commands."""
        return await run_and_format_response(client, "processSequence", {"sequence": sequence})
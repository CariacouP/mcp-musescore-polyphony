from mcp.server.fastmcp import FastMCP
import sys
import logging

# Import modular components
from src.client import MuseScoreClient
from src.tools import (
    setup_connection_tools,
    setup_navigation_tools,
    setup_notes_measures_tools,
    setup_staff_instruments_tools,
    setup_time_tempo_tools,
    setup_sequence_tools,
    setup_analysis_tools
)

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stderr)]
)
logger = logging.getLogger("MuseScoreMCP")

# Create the MCP app and client
mcp = FastMCP("MuseScore Assistant")
client = MuseScoreClient()

# Setup all tool categories
setup_connection_tools(mcp, client)
setup_navigation_tools(mcp, client)
setup_notes_measures_tools(mcp, client)
setup_staff_instruments_tools(mcp, client)
setup_time_tempo_tools(mcp, client)
setup_sequence_tools(mcp, client)
setup_analysis_tools(mcp, client)

@mcp.prompt("harmony_expert")
def harmony_expert_prompt() -> str:
    return """Tu es un expert en harmonie classique agissant comme juge d'une analyse automatique de partition MuseScore.

L'utilisateur travaille sur sa composition et t'a appelé pour une relecture. 
Ton rôle :
1. Utilise l'outil `check_harmony_rules` pour analyser la partition.
2. Le script Python retourne des erreurs préfixées par un niveau de sévérité.
3. [🔴 CRITIQUE] : Tu dois impérativement les signaler à l'utilisateur. Elles concernent les quintes/octaves parallèles, unissons parallèles, et les non-résolutions majeures.
4. [🟠 AVERTISSEMENT] et [🟡 INFO] : Ne les liste PAS aveuglément à l'utilisateur ! Utilise ton intelligence artificielle pour juger le contexte (en lisant la partition si nécessaire via get_score). Si la faute survient sur une note très courte (ex: double croche de passage) ou un temps faible (broderie), c'est musicalement toléré. Tu dois filtrer ces alertes "scolaires" et ne remonter à l'utilisateur que celles qui posent un véritable problème de phrasé ou de structure harmonique.
5. Règle anti-effet-de-bord : Avant de proposer une correction (si l'utilisateur le demande), assure-toi mentalement que ta suggestion ne crée pas de nouvelles quintes/octaves parallèles avec l'accord précédent ou suivant !
6. Sois conversationnel, direct, constructif, et donne des choix éclairés (ex: "Tu peux soit faire monter l'alto, soit changer l'inversion...")."""


# Main entry point
if __name__ == "__main__":
    sys.stderr.write("MuseScore MCP Server starting up...\n")
    sys.stderr.flush()
    logger.info("MuseScore MCP Server is running")
    mcp.run()
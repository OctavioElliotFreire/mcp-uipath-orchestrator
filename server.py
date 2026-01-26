# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "mcp>=1.0.0",
#     "httpx>=0.27.0",
#     "python-dotenv>=1.0.0",
# ]
# ///

from mcp.server.fastmcp import FastMCP
from src.service import OrchestratorClient
import json
import asyncio

orchestrator_client = None



async def get_client():
    """Get or create the Orchestrator client"""
    global orchestrator_client
    if orchestrator_client is None:
        orchestrator_client = OrchestratorClient()
        await orchestrator_client.authenticate()
    return orchestrator_client

# Initialize FastMCP server
mcp = FastMCP("uipath-orchestrator")


@mcp.tool()
async def list_folders() -> str:
    """Get all folders from UiPath Orchestrator."""
    client = await get_client()
    folders = await client.get_folders()
    return json.dumps(folders, indent=2)


#@mcp.tool()
#async def list_assets(folder_id: int = None) -> str:
#    """Get all assets from UiPath Orchestrator, optionally filtered by folder ID."""
#   client = await get_client()
#    assets = await client.get_assets(folder_id=folder_id)
#    return json.dumps(assets, indent=2)


@mcp.tool()
async def list_triggers(folder_id: int) -> str:
    """Get all triggers (time and queue) from UiPath Orchestrator for a specific folder."""
    client = await get_client()
    triggers = await client.get_triggers(folder_id)
    return json.dumps(triggers, indent=2)


#if __name__ == "__main__":
  #  asyncio.run(mcp.run())

if __name__ == "__main__":
    mcp.run(transport="stdio")

# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "mcp[cli]>=1.12.3",
#     "pydantic>=2.11.7",
#     "python-dotenv>=1.1.1",
#     "requests>=2.32.4",
#    # ]
# ///


from mcp.server.fastmcp import FastMCP
from src.service import OrchestratorClient


mcp = FastMCP(
    name="YouTube",
    stateless_http=True,
)


@mcp.tool()
async def list_folders(
    filter: str = None,
) -> str:
    """Get all folders from UiPath Orchestrator."""
    client = OrchestratorClient()
    try:
        folders = await client.get_folders(filter_query=filter)
        # Convert to JSON string for the response
        import json
        return json.dumps(folders, indent=2)
    finally:
        await client.close()



if __name__ == "__main__":
    mcp.run(transport="stdio")

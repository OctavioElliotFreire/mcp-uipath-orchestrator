# 🤖 UiPath Orchestrator MCP Server

This is an MCP (Model Context Protocol) server that connects to the [UiPath Orchestrator API](https://docs.uipath.com/orchestrator/reference) and exposes tools that an LLM can use to manage folders, resources, packages, queues, and releases across UiPath tenants and accounts.

It uses the [FastMCP](https://github.com/jlowin/fastmcp) library and the UiPath Cloud API to interact with Orchestrator programmatically through a standardized protocol that works seamlessly with LLMs and AI agents.

---

## 🚀 Features

- List accounts, tenants, and folder trees
- Ensure folder paths exist (idempotent)
- Manage resources inside folders (assets, queues, processes, triggers, storage buckets)
- Link shared resources across folders
- Upload, download, and manage process packages and libraries
- Retrieve and filter queue items
- Ensure releases exist for processes

---

## 🛠️ Available Tools

| Tool | Description |
|------|-------------|
| `list_accounts` | List all configured UiPath Orchestrator accounts |
| `list_tenants` | List all tenants under an account |
| `list_folders` | Retrieve the full nested folder tree for a tenant |
| `ensure_folder_path` | Idempotently ensure a nested folder path exists |
| `get_folder_resources` | Fetch resources (assets, queues, processes, triggers, storage buckets) from a folder |
| `ensure_resource_in_folder` | Create a resource in a folder if it doesn't already exist |
| `link_resource_to_folder` | Link an existing shared resource into a target folder |
| `get_queue_items` | Retrieve and filter items from a queue |
| `upload_package` | Upload a `.nupkg` process package to a folder |
| `download_package_with_dependencies` | Download a process and all its internal library dependencies |
| `download_library_version` | Download a specific version of a UiPath library |
| `list_libraries` | List all library package IDs in a tenant |
| `list_library_versions` | List all available versions for a library package |
| `ensure_release` | Idempotently ensure a release exists for a process in a folder |

---

## 📦 Requirements

- Python 3.12+
- Node.js (required by some LLM hosts like Claude Desktop)
- [`uv`](https://docs.astral.sh/uv/getting-started/installation/)
- A UiPath Cloud account with Orchestrator access
- UiPath API credentials (Client ID & Client Secret)

---

## ⚙️ Installation

```bash
# Clone the repo
git clone https://github.com/OctavioElliotFreire/mcp-uipath-orchestrator
cd mcp-uipath-orchestrator

# Create virtual environment and activate it
uv venv
.venv\Scripts\activate     # On Windows
# source .venv/bin/activate  # On macOS/Linux

# Install dependencies from pyproject.toml
uv sync

# Before running, make sure to configure your credentials
# See the 🔐 Configuration section below

# Run the server
mcp dev server.py

# Connect and test tools
# Click to connect on the MCP inspector, select Tools tab and click list tools
```

---

## 🔐 Configuration

Create a `config/config.json` using your UiPath account logical name(s) as top-level keys. The config supports **multiple Orchestrator accounts** — just add additional entries at the top level.

```json
{
  "<account_logical_name_1>": {
    "base_url": "https://cloud.uipath.com/",
    "auth": {
      "client_id": "YOUR_CLIENT_ID",
      "client_secret": "YOUR_CLIENT_SECRET"
    },
    "download_dir": "/path/to/download/dir",
    "tenants": {
      "DEV": {
        "libraries_feed_id": "YOUR_FEED_ID"
      },
      "PROD": {
        "libraries_feed_id": "YOUR_FEED_ID"
      },
      "DefaultTenant": {
        "libraries_feed_id": "YOUR_FEED_ID"
      }
    }
  },

  "<account_logical_name_2>": {
    "base_url": "https://cloud.uipath.com/",
    "auth": {
      "client_id": "YOUR_CLIENT_ID",
      "client_secret": "YOUR_CLIENT_SECRET"
    },
    "download_dir": "/path/to/download/dir",
    "tenants": {
      "DefaultTenant": {
        "libraries_feed_id": "YOUR_FEED_ID"
      }
    }
  }
}
```

| Field | Description |
|-------|-------------|
| `<account_logical_name>` | Top-level key — your UiPath account logical name (found in the Cloud portal URL) |
| `base_url` | UiPath Cloud base URL, typically `https://cloud.uipath.com/` |
| `auth.client_id` | OAuth2 Client ID from an External Application |
| `auth.client_secret` | OAuth2 Client Secret from an External Application |
| `download_dir` | Local directory where packages and libraries will be downloaded |
| `tenants` | Map of tenant names to their configuration |
| `tenants.<name>.libraries_feed_id` | The feed ID used to resolve library packages for that tenant |

> You can generate a Client ID and Client Secret from the [UiPath Automation Cloud portal](https://cloud.uipath.com) under **Admin > External Applications**.
>
> To connect to **multiple Orchestrator accounts**, simply add more top-level entries to the config — each with their own credentials, download directory, and tenants.

### 🔍 How to find your `libraries_feed_id`

Each tenant has its own libraries feed. To retrieve it:

1. Open **UiPath Studio**
2. Go to **Manage Packages** → **Settings**
3. Under **Orchestrator Tenant**, look for the feed source URL — it follows this pattern:

```
https://cloud.uipath.com/{AccountName}/{TenantName}/orchestrator_/nuget/v3/{libraries_feed_id}
```

4. Copy the last segment of the URL — that is your `libraries_feed_id`

> Each tenant has its own unique feed ID, so repeat this step for every tenant you want to configure.

---

## 🔌 Connecting to Claude Desktop

To use this MCP server with Claude Desktop, add the following to your `claude_desktop_config.json`. You can register **multiple instances** of the server — one per environment or account — by giving each entry a unique name:

```json
{
  "mcpServers": {
    "prod-uipath-orchestrator": {
      "command": "uv",
      "args": [
        "--directory",
        "C:/MCP/Prod/mcp-uipath-orchestrator/",
        "run",
        "python",
        "server.py"
      ]
    },
    "dev-uipath-orchestrator": {
      "command": "uv",
      "args": [
        "--directory",
        "C:/MCP/Dev/mcp-uipath-orchestrator/",
        "run",
        "python",
        "server.py"
      ]
    }
  }
}
```

> **Tip:** You can open the config directly from Claude Desktop via **Settings** → **Developer** → **Edit Config**.
>
> Or navigate to the file manually:
> - **Windows:** `%APPDATA%\Claude\claude_desktop_config.json`
> - **macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`

---

## 💬 Example Prompts

Once connected to an LLM, you can ask things like:

- *"List all tenants under my account."*
- *"Make sure the folder path `Finance/Prod/Invoices` exists."*
- *"What processes are available in the `Shared` folder?"*
- *"Upload the package at `./MyProcess_1.0.0.nupkg` to the Production folder."*
- *"Show me all failed queue items from the last 7 days in queue ID 42."*
- *"Ensure a release exists for `MyProcess` version `1.2.3` in folder 15."*

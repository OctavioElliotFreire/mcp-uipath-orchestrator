# Cross-Orchestrator Deployment via MCP (UiPath)

## Overview

I am building a Python-based MCP server that connects to multiple UiPath Orchestrator instances (Cloud or On-Prem) via REST APIs.

The goal is to enable an LLM-powered assistant to perform cross-Orchestrator queries and deployments in a deterministic and reliable way.

API Documentation:
https://docs.uipath.com/orchestrator/automation-cloud/latest/api-Guide/assets-requests

---

## Objective

Design an MCP tool architecture that:

- Handles natural language requests
- Supports cross-Orchestrator deployments (e.g., Dev → Prod)
- Minimizes the number of tools
- Keeps tools deterministic
- Prevents hallucination by relying only on API responses

Balance required:
- Few generic tools  
vs  
- Explicit, deterministic tools  

---

## Environment Model

Each Orchestrator instance may contain:

- Tenants
- Nested folders
- Processes
- Assets
- Queues
- Triggers

Each instance is independent (authentication, structure, resources).

---

## Example Requests

### Cross-Orchestrator Deployment
"Deploy Process A from Dev to Prod"

May require:
- Resolving tenants and folders
- Retrieving process package/version
- Identifying linked assets, queues, triggers
- Creating missing dependencies in target
- Publishing process in correct folder

### Resource Queries
- "Which assets exist in folder X in Dev?"
- "List all disabled triggers in Prod."

---

## LLM Requirements

The LLM must:

- Understand Orchestrator boundaries
- Handle folder hierarchies
- Reason about dependencies
- Decompose multi-step workflows
- Avoid assuming state
- Always rely on tool responses

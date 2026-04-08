To implement the n8n MCP server into your LibreChat deployment, you can use the following document. You can paste this directly into **Claude Code** (or your preferred terminal-based agent) to guide the implementation.

***

# Technical Task: Integrate n8n MCP Server into LibreChat

## Objective
Configure LibreChat to use the `@n8n/mcp-server-n8n` MCP server to enable agentic automation workflows.

## Configuration Details
*   **MCP Server Package:** `@n8n/mcp-server-n8n`
*   **Host:** `https://automation.nikivs.com`
*   **Authentication:** Requires an API key (to be sourced from environment variables for security).

## Implementation Steps

### 1. Update/Create `mcp-config.json`
Please ensure the `mcp-config.json` file in the LibreChat configuration directory includes the following block. Note: Do not hardcode the API key here; use an environment variable reference if the implementation supports it, or place a placeholder that I will replace with the actual secret.

```json
{
  "mcpServers": {
    "n8n": {
      "type": "command",
      "command": "npx",
      "args": [
        "-y",
        "@n8n/mcp-server-n8n",
        "--host",
        "https://automation.nikivs.com",
        "--api-key",
        "${N8N_API_KEY}"
      ]
    }
  }
}
```

### 2. Environment Configuration
Update the LibreChat `docker-compose.yml` (or `.env` file) to include the necessary secret:
*   Add `N8N_API_KEY` to the `environment` section of the `librechat` service.

### 3. Verification & Runtime Requirements
*   **Node.js/NPM:** Confirm that the LibreChat container has `nodejs` and `npm` installed. If the base image lacks them, we may need to use a custom `Dockerfile` or modify the container startup script to install these dependencies before the app starts.
*   **Connectivity:** Ensure the LibreChat container has network access to `automation.nikivs.com`.
*   **Restart:** After applying these changes, perform a `docker-compose up -d` to restart the container and initialize the MCP server.

## Deliverables
1.  Updated `mcp-config.json`.
2.  Updated `docker-compose.yml` with the new environment variable.
3.  Confirmation of `npx` availability within the container environment.

***

**Pro-tip for Claude Code:** You can tell Claude: *"I have an existing LibreChat deployment. Please use this document to integrate the n8n MCP server. Check if my current image supports npx and help me set up the environment variable securely."*
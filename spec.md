# Technical Specification: `brain-mcp`

## Project Overview
**Project Name:** `brain-mcp`
**Target Deployment Domain:** `brain.nikivs.com/mcp`
**Description:** A personalized "Second Brain" AI memory system. It allows AI agents and LLMs to push thoughts, facts, and memories to a vector database, and retrieve them contextually over time. 
**Architecture:** It utilizes the Model Context Protocol (MCP) to standardize tool discovery, exposed over HTTP via Server-Sent Events (SSE) using FastAPI, backed by Qdrant as the vector database.

## Technology Stack
*   **Vector Database:** Qdrant (Running via Docker to utilize the built-in web dashboard).
*   **Protocol:** Model Context Protocol (MCP) using the official `mcp` Python SDK.
*   **Logic Framework:** `FastMCP` (for defining AI tools).
*   **Transport Framework:** `FastAPI` (to expose the MCP server over SSE to the internet).
*   **Embeddings:** `sentence-transformers` (Local embeddings using `all-MiniLM-L6-v2` for privacy and zero API costs).

---

## Directory Structure
Please initialize the project with the following structure:

    brain-mcp/
    ├── src/
    │   ├── __init__.py
    │   ├── main.py           # FastAPI application and SSE routing
    │   ├── mcp_server.py     # FastMCP tool definitions (push/retrieve)
    │   ├── qdrant_client.py  # Qdrant DB connection and embedding logic
    │   └── config.py         # Environment variables (host, ports, auth)
    ├── docker-compose.yml    # Runs Qdrant and the FastAPI app
    ├── Dockerfile            # Builds the FastAPI/MCP application
    ├── requirements.txt      # Python dependencies
    └── .env                  # Environment variables

---

## Technical Implementation Requirements

### 1. Vector Database & Dashboard (Qdrant)
*   Use `docker-compose.yml` to spin up the official Qdrant image (`qdrant/qdrant:latest`).
*   Map port `6333:6333` (HTTP/REST) and `6334:6334` (gRPC).
*   Ensure the Qdrant Web UI is accessible at `http://localhost:6333/dashboard`. This is a critical requirement so the user can visually browse and manage their "thoughts."
*   Map a local volume `./qdrant_storage:/qdrant/storage` to ensure memories persist across container restarts.

### 2. The Embedding Layer
*   In `src/qdrant_client.py`, use `sentence-transformers` with the `all-MiniLM-L6-v2` model.
*   The embedding dimension for this model is `384`.
*   Initialize a Qdrant collection named `my_thoughts` with Cosine distance.
*   Each "thought" point should store a payload containing:
    *   `text` (the actual thought)
    *   `category` (string, default "general")
    *   `timestamp` (ISO 8601 string of when it was saved)

### 3. FastMCP Logic (The Tools)
In `src/mcp_server.py`, initialize an MCP server instance named "PersonalBrain" and define the following `@mcp.tool()` endpoints:

1.  `push_thought(thought: str, category: str = "general") -> str`
    *   Takes the text, generates the embedding, and upserts it into Qdrant.
    *   Generates a unique UUID for the point.
    *   Returns a success message with the ID.
2.  `retrieve_thoughts(query: str, limit: int = 5) -> str`
    *   Takes a query, embeds it, and performs a similarity search in Qdrant.
    *   Formats the returned results nicely (e.g., `[Timestamp] [Category]: Text`) so an LLM can easily read it.

### 4. Transport Layer (FastAPI & SSE)
Since this will eventually be deployed to `brain.nikivs.com/mcp`, we cannot use standard `stdio`. We must use **SSE (Server-Sent Events)**.
*   In `src/main.py`, initialize a FastAPI app.
*   Integrate the `mcp` instance with FastAPI using the pattern provided by the MCP Python SDK for SSE (`SseServerTransport`).
*   The endpoints should handle:
    *   `GET /mcp/sse` (Establishes the SSE connection)
    *   `POST /mcp/messages` (Receives the JSON-RPC messages from the client)
*   **Security Note:** Add a basic placeholder for API Key authentication via FastAPI dependencies (e.g., checking an `X-API-Key` header), so the public internet cannot overwrite the brain.

### 5. Dockerization of the API
*   Include a `Dockerfile` for the FastAPI application.
*   Update `docker-compose.yml` to build and run the FastAPI app alongside Qdrant.
*   The FastAPI app should communicate with Qdrant via the internal Docker network (e.g., `http://qdrant:6333`).

---

## Instructions for Claude Code (Agent)
1. Read this specification carefully.
2. Create the `requirements.txt` containing `mcp`, `fastapi`, `uvicorn`, `qdrant-client`, `sentence-transformers`, `pydantic-settings`.
3. Scaffold the directory structure.
4. Implement the Python files as described.
5. Create the `docker-compose.yml` and `Dockerfile`.
6. Ensure the logic gracefully handles the scenario where the Qdrant collection doesn't exist yet by creating it on startup.
7. Once complete, explain to the user how to start the stack and how to access the Qdrant visual dashboard.
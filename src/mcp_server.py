from mcp.server.fastmcp import FastMCP

from . import qdrant_client as db

mcp = FastMCP("PersonalBrain")


@mcp.tool()
def push_thought(thought: str, category: str = "general") -> str:
    """Save a thought, fact, or memory to the personal brain."""
    point_id = db.push_thought(thought, category)
    return f"Thought saved successfully with ID: {point_id}"


@mcp.tool()
def retrieve_thoughts(query: str, limit: int = 5) -> str:
    """Retrieve relevant thoughts from the personal brain using semantic search."""
    results = db.retrieve_thoughts(query, limit)
    if not results:
        return "No relevant thoughts found."
    lines = []
    for r in results:
        lines.append(f"[{r['timestamp']}] [{r['category']}]: {r['text']}  (score: {r['score']:.3f})")
    return "\n".join(lines)

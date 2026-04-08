from mcp.server.fastmcp import FastMCP

from . import qdrant_client as db
from . import obsidian_client as obsidian

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


@mcp.tool()
def list_notes() -> str:
    """List all notes in the Obsidian vault."""
    paths = obsidian.list_notes()
    if not paths:
        return "No notes found in the vault."
    return "\n".join(paths)


@mcp.tool()
def read_note(path: str) -> str:
    """Read the content of an Obsidian note by its vault path (e.g. 'folder/note.md')."""
    try:
        return obsidian.read_note(path)
    except Exception as e:
        return f"Error reading note: {e}"


@mcp.tool()
def write_note(path: str, content: str) -> str:
    """Create or update an Obsidian note. Path is relative to vault root (e.g. 'folder/note.md')."""
    try:
        obsidian.write_note(path, content)
        return f"Note '{path}' saved successfully."
    except Exception as e:
        return f"Error writing note: {e}"

import time
import requests
from .config import settings


def _session() -> requests.Session:
    s = requests.Session()
    s.auth = (settings.couchdb_user, settings.couchdb_password)
    return s


def _base() -> str:
    return f"{settings.couchdb_url}/{settings.couchdb_db}"


def list_notes() -> list[str]:
    """Return all note paths stored in the Obsidian vault."""
    s = _session()
    resp = s.get(f"{_base()}/_all_docs", params={"include_docs": "false"})
    resp.raise_for_status()
    rows = resp.json().get("rows", [])
    # Filter out CouchDB internal docs and LiveSync metadata
    return [
        r["id"] for r in rows
        if not r["id"].startswith("_") and not r["id"].startswith("h:")
    ]


def read_note(path: str) -> str:
    """Return the markdown content of a note by its vault path."""
    s = _session()
    resp = s.get(f"{_base()}/{requests.utils.quote(path, safe='')}")
    resp.raise_for_status()
    doc = resp.json()

    if doc.get("deleted"):
        raise FileNotFoundError(f"Note '{path}' has been deleted.")

    # Handle chunked documents
    if "children" in doc:
        chunks = []
        for child_id in doc["children"]:
            chunk_resp = s.get(f"{_base()}/{requests.utils.quote(child_id, safe='')}")
            chunk_resp.raise_for_status()
            chunks.append(chunk_resp.json().get("data", ""))
        return "".join(chunks)

    return doc.get("data", "")


def write_note(path: str, content: str) -> None:
    """Create or update a note at the given vault path."""
    s = _session()
    url = f"{_base()}/{requests.utils.quote(path, safe='')}"
    now = int(time.time() * 1000)

    # Fetch existing rev if the doc already exists
    existing = s.get(url)
    doc: dict = {
        "_id": path,
        "data": content,
        "type": "plain",
        "mtime": now,
        "ctime": now,
        "size": len(content.encode()),
        "deleted": False,
    }
    if existing.status_code == 200:
        doc["_rev"] = existing.json()["_rev"]
        doc["ctime"] = existing.json().get("ctime", now)

    resp = s.put(url, json=doc)
    resp.raise_for_status()

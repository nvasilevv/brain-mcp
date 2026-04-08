import base64
import json
import time

import requests
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from .config import settings

IV_LENGTH = 12
HKDF_SALT_LENGTH = 32
PBKDF2_ITERATIONS = 310_000
ENCRYPTED_PREFIX = "%="
ENCRYPTED_META_PREFIX = "/\\:"
SYNC_PARAMS_ID = "_local/obsidian_livesync_sync_parameters"

# Caches
_pbkdf2salt_cache: bytes | None = None
_master_key_cache: bytes | None = None
# path → (doc_id, children) index, populated on first list/read
_path_index: dict[str, tuple[str, list]] | None = None


def _session() -> requests.Session:
    s = requests.Session()
    s.auth = (settings.couchdb_user, settings.couchdb_password)
    return s


def _base() -> str:
    return f"{settings.couchdb_url}/{settings.couchdb_db}"


def _b64decode(s: str) -> bytes:
    s += "=" * (-len(s) % 4)
    return base64.b64decode(s)


def _get_pbkdf2salt() -> bytes:
    global _pbkdf2salt_cache
    if _pbkdf2salt_cache is None:
        s = _session()
        resp = s.get(f"{_base()}/{SYNC_PARAMS_ID}")
        resp.raise_for_status()
        _pbkdf2salt_cache = _b64decode(resp.json()["pbkdf2salt"])
    return _pbkdf2salt_cache


def _get_master_key() -> bytes:
    """Derive master key from passphrase + pbkdf2salt. Cached — runs PBKDF2 only once."""
    global _master_key_cache
    if _master_key_cache is None:
        _master_key_cache = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=_get_pbkdf2salt(),
            iterations=PBKDF2_ITERATIONS,
        ).derive(settings.obsidian_passphrase.encode())
    return _master_key_cache


def _decrypt(encrypted: str) -> str:
    """Decrypt a LiveSync HKDF-encrypted string (%=...). Uses cached master key."""
    assert encrypted.startswith(ENCRYPTED_PREFIX), f"Unexpected prefix: {encrypted[:4]}"
    data = _b64decode(encrypted[len(ENCRYPTED_PREFIX):])

    iv = data[:IV_LENGTH]
    hkdf_salt = data[IV_LENGTH:IV_LENGTH + HKDF_SALT_LENGTH]
    ciphertext = data[IV_LENGTH + HKDF_SALT_LENGTH:]

    chunk_key = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=hkdf_salt,
        info=b"",
    ).derive(_get_master_key())

    plaintext = AESGCM(chunk_key).decrypt(iv, ciphertext, None)
    return plaintext.decode("utf-8")


def _decrypt_meta(path_field: str) -> dict:
    """Decrypt an encrypted path field (/\\:...) and return the full metadata dict.
    Contains: path, mtime, ctime, size, children (the real chunk IDs).
    """
    assert path_field.startswith(ENCRYPTED_META_PREFIX)
    decrypted = _decrypt(path_field[len(ENCRYPTED_META_PREFIX):])
    try:
        return json.loads(decrypted)
    except json.JSONDecodeError:
        return {"path": decrypted, "children": []}


def _build_path_index(refresh: bool = False) -> dict[str, tuple[str, list]]:
    """Build and cache a mapping of path → (doc_id, children) for all f: documents.
    children comes from the encrypted metadata (not the plaintext placeholder).
    """
    global _path_index
    if _path_index is not None and not refresh:
        return _path_index

    s = _session()
    resp = s.get(f"{_base()}/_all_docs", params={"include_docs": "true"})
    resp.raise_for_status()

    index: dict[str, tuple[str, list]] = {}
    for row in resp.json().get("rows", []):
        doc = row["doc"]
        doc_id = doc.get("_id", "")
        if not doc_id.startswith("f:"):
            continue
        if doc.get("deleted"):
            continue
        path_field = doc.get("path", "")
        if not path_field.startswith(ENCRYPTED_META_PREFIX):
            continue
        try:
            meta = _decrypt_meta(path_field)
            note_path = meta.get("path", "")
            children = meta.get("children") or []
            if note_path:
                index[note_path] = (doc_id, children)
        except Exception:
            pass

    _path_index = index
    return _path_index


def list_notes() -> list[str]:
    """Return all note paths stored in the Obsidian vault."""
    return sorted(_build_path_index().keys())


def read_note(path: str) -> str:
    """Return the markdown content of a note by its vault path."""
    index = _build_path_index()
    entry = index.get(path)
    if entry is None:
        index = _build_path_index(refresh=True)
        entry = index.get(path)
    if entry is None:
        raise FileNotFoundError(f"Note '{path}' not found.")

    doc_id, children = entry

    if not children:
        return ""

    s = _session()
    parts = []
    for chunk_id in children:
        chunk_resp = s.get(f"{_base()}/{requests.utils.quote(chunk_id, safe='')}")
        chunk_resp.raise_for_status()
        chunk_data = chunk_resp.json().get("data", "")
        parts.append(_decrypt(chunk_data) if chunk_data.startswith(ENCRYPTED_PREFIX) else chunk_data)

    return "".join(parts)


def write_note(path: str, content: str) -> None:
    """Create or update a note at the given vault path."""
    import hashlib

    index = _build_path_index()
    s = _session()
    now = int(time.time() * 1000)

    if path in index:
        doc_id, _ = index[path]
        existing_resp = s.get(f"{_base()}/{requests.utils.quote(doc_id, safe='')}")
        existing_resp.raise_for_status()
        existing = existing_resp.json()
        doc: dict = {
            **existing,
            "data": content,
            "mtime": now,
            "size": len(content.encode()),
            "deleted": False,
            "children": [],
        }
    else:
        doc_id = "f:" + hashlib.sha256(path.encode()).hexdigest()
        doc = {
            "_id": doc_id,
            "path": path,
            "data": content,
            "type": "plain",
            "mtime": now,
            "ctime": now,
            "size": len(content.encode()),
            "deleted": False,
            "children": [],
        }

    s.put(f"{_base()}/{requests.utils.quote(doc_id, safe='')}", json=doc).raise_for_status()
    # Update cache so the new note shows up on next list
    _path_index[path] = (doc_id, [])

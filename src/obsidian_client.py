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

_pbkdf2salt_cache: bytes | None = None


def _session() -> requests.Session:
    s = requests.Session()
    s.auth = (settings.couchdb_user, settings.couchdb_password)
    return s


def _base() -> str:
    return f"{settings.couchdb_url}/{settings.couchdb_db}"


def _b64decode(s: str) -> bytes:
    # Add padding if needed
    s += "=" * (-len(s) % 4)
    return base64.b64decode(s)


def _get_pbkdf2salt() -> bytes:
    global _pbkdf2salt_cache
    if _pbkdf2salt_cache is None:
        s = _session()
        resp = s.get(f"{_base()}/{SYNC_PARAMS_ID}")
        resp.raise_for_status()
        raw = resp.json()["pbkdf2salt"]
        _pbkdf2salt_cache = _b64decode(raw)
    return _pbkdf2salt_cache


def _decrypt(encrypted: str) -> str:
    """Decrypt a LiveSync HKDF-encrypted string (%=...)."""
    assert encrypted.startswith(ENCRYPTED_PREFIX), f"Unexpected prefix: {encrypted[:4]}"
    data = _b64decode(encrypted[len(ENCRYPTED_PREFIX):])

    iv = data[:IV_LENGTH]
    hkdf_salt = data[IV_LENGTH:IV_LENGTH + HKDF_SALT_LENGTH]
    ciphertext = data[IV_LENGTH + HKDF_SALT_LENGTH:]

    pbkdf2salt = _get_pbkdf2salt()
    passphrase = settings.obsidian_passphrase.encode()

    # PBKDF2: passphrase + pbkdf2salt → master key
    master_key = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=pbkdf2salt,
        iterations=PBKDF2_ITERATIONS,
    ).derive(passphrase)

    # HKDF: master key + hkdf_salt → chunk key
    chunk_key = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=hkdf_salt,
        info=b"",
    ).derive(master_key)

    plaintext = AESGCM(chunk_key).decrypt(iv, ciphertext, None)
    return plaintext.decode("utf-8")


def _decrypt_path(path_field: str) -> str:
    """Decrypt an encrypted path field (/\\:...) and return just the file path."""
    assert path_field.startswith(ENCRYPTED_META_PREFIX)
    decrypted = _decrypt(path_field[len(ENCRYPTED_META_PREFIX):])
    # Decrypted value is a JSON object: {"path": "...", "mtime": ..., ...}
    try:
        return json.loads(decrypted)["path"]
    except (json.JSONDecodeError, KeyError):
        return decrypted  # fallback: raw string


def list_notes() -> list[str]:
    """Return all note paths stored in the Obsidian vault."""
    s = _session()
    resp = s.get(f"{_base()}/_all_docs", params={"include_docs": "true"})
    resp.raise_for_status()

    paths = []
    for row in resp.json().get("rows", []):
        doc = row["doc"]
        doc_id = doc.get("_id", "")
        path_field = doc.get("path", "")
        if not doc_id.startswith("f:") or not path_field.startswith(ENCRYPTED_META_PREFIX):
            continue
        if doc.get("deleted"):
            continue
        try:
            paths.append(_decrypt_path(path_field))
        except Exception:
            pass

    return sorted(paths)


def read_note(path: str) -> str:
    """Return the markdown content of a note by its vault path."""
    s = _session()
    resp = s.get(f"{_base()}/_all_docs", params={"include_docs": "true"})
    resp.raise_for_status()

    target_doc = None
    for row in resp.json().get("rows", []):
        doc = row["doc"]
        if not doc.get("_id", "").startswith("f:"):
            continue
        if doc.get("deleted"):
            continue
        path_field = doc.get("path", "")
        if not path_field.startswith(ENCRYPTED_META_PREFIX):
            continue
        try:
            if _decrypt_path(path_field) == path:
                target_doc = doc
                break
        except Exception:
            continue

    if target_doc is None:
        raise FileNotFoundError(f"Note '{path}' not found.")

    children = target_doc.get("children", [])
    if not children:
        # Content may be inline
        data = target_doc.get("data", "")
        if data.startswith(ENCRYPTED_PREFIX):
            return _decrypt(data)
        return data

    # Fetch and decrypt each chunk
    parts = []
    for chunk_id in children:
        chunk_resp = s.get(f"{_base()}/{requests.utils.quote(chunk_id, safe='')}")
        chunk_resp.raise_for_status()
        chunk_data = chunk_resp.json().get("data", "")
        if chunk_data.startswith(ENCRYPTED_PREFIX):
            parts.append(_decrypt(chunk_data))
        else:
            parts.append(chunk_data)

    return "".join(parts)


def write_note(path: str, content: str) -> None:
    """Create or update a note at the given vault path (stores unencrypted for LiveSync to pick up)."""
    s = _session()
    now = int(time.time() * 1000)

    # Find existing doc by path
    existing_doc = None
    resp = s.get(f"{_base()}/_all_docs", params={"include_docs": "true"})
    resp.raise_for_status()
    for row in resp.json().get("rows", []):
        doc = row["doc"]
        if not doc.get("_id", "").startswith("f:"):
            continue
        path_field = doc.get("path", "")
        if not path_field.startswith(ENCRYPTED_META_PREFIX):
            continue
        try:
            if _decrypt_path(path_field) == path:
                existing_doc = doc
                break
        except Exception:
            continue

    if existing_doc:
        doc_id = existing_doc["_id"]
        url = f"{_base()}/{requests.utils.quote(doc_id, safe='')}"
        doc: dict = {
            **existing_doc,
            "data": content,
            "mtime": now,
            "size": len(content.encode()),
            "deleted": False,
            "children": [],
        }
    else:
        import hashlib
        doc_id = "f:" + hashlib.sha256(path.encode()).hexdigest()
        url = f"{_base()}/{requests.utils.quote(doc_id, safe='')}"
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

    resp = s.put(url, json=doc)
    resp.raise_for_status()

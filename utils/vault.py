#!/usr/bin/env python3
"""
Command Center // Encrypted Security Vault
Provides zero-dependency authenticated encryption (PBKDF2-HMAC-SHA256 + CTR Keystream + HMAC-SHA256)
for exporting and importing credentials, config, and state backups into .ccvault archives.
"""

import os
import sys
import json
import time
import base64
import hashlib
import hmac
import secrets

VAULT_MAGIC = "CC_VAULT_V1"
PBKDF2_ITERATIONS = 150000

def _derive_keys(password: str, salt: bytes) -> tuple:
    """Derives 32-byte encryption key and 32-byte MAC key using PBKDF2-HMAC-SHA256."""
    derived = hashlib.pbkdf2_hmac(
        'sha256',
        password.encode('utf-8'),
        salt,
        PBKDF2_ITERATIONS,
        dklen=64
    )
    k_enc = derived[:32]
    k_mac = derived[32:64]
    return k_enc, k_mac

def _ctr_crypt(data: bytes, key: bytes, nonce: bytes) -> bytes:
    """
    Encrypts/decrypts data using SHA-256 in Counter (CTR) mode keystream.
    CTR mode is symmetric: crypt(crypt(data)) == data.
    """
    out = bytearray(len(data))
    block_size = 32
    num_blocks = (len(data) + block_size - 1) // block_size

    for counter in range(num_blocks):
        counter_bytes = counter.to_bytes(4, byteorder='big')
        keystream_block = hashlib.sha256(key + nonce + counter_bytes).digest()
        start = counter * block_size
        end = min(start + block_size, len(data))
        chunk_len = end - start
        for i in range(chunk_len):
            out[start + i] = data[start + i] ^ keystream_block[i]

    return bytes(out)

def encrypt_data(data: bytes, password: str, metadata: dict = None) -> dict:
    """
    Encrypts arbitrary bytes using password-derived keys and Authenticated Encrypt-then-MAC.
    Returns a serializable dictionary envelope.
    """
    if not password:
        raise ValueError("Password cannot be empty")

    salt = secrets.token_bytes(16)
    nonce = secrets.token_bytes(16)
    k_enc, k_mac = _derive_keys(password, salt)

    ciphertext = _ctr_crypt(data, k_enc, nonce)
    
    # Compute HMAC over format + nonce + ciphertext
    mac = hmac.new(k_mac, VAULT_MAGIC.encode('utf-8') + nonce + ciphertext, hashlib.sha256).hexdigest()
    raw_checksum = hashlib.sha256(data).hexdigest()

    vault_payload = {
        "magic": VAULT_MAGIC,
        "version": 1,
        "timestamp": int(time.time()),
        "created_at_iso": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
        "salt": base64.b64encode(salt).decode('ascii'),
        "nonce": base64.b64encode(nonce).decode('ascii'),
        "iterations": PBKDF2_ITERATIONS,
        "kdf": "PBKDF2-HMAC-SHA256",
        "cipher": "CTR-SHA256-STREAM",
        "mac": mac,
        "raw_checksum": raw_checksum,
        "raw_size": len(data),
        "metadata": metadata or {},
        "ciphertext": base64.b64encode(ciphertext).decode('ascii')
    }

    return vault_payload

def decrypt_data(envelope: dict, password: str) -> bytes:
    """
    Authenticates and decrypts a vault envelope dictionary.
    Raises ValueError on password mismatch, corruption, or tampered payload.
    """
    if not password:
        raise ValueError("Password cannot be empty")

    if envelope.get("magic") != VAULT_MAGIC:
        raise ValueError("Invalid vault format or unsupported archive version")

    try:
        salt = base64.b64decode(envelope["salt"])
        nonce = base64.b64decode(envelope["nonce"])
        ciphertext = base64.b64decode(envelope["ciphertext"])
        expected_mac = envelope["mac"]
        expected_checksum = envelope.get("raw_checksum")
    except Exception as e:
        raise ValueError(f"Corrupted vault structure: {e}")

    k_enc, k_mac = _derive_keys(password, salt)

    # 1. Timing-safe MAC verification before touching ciphertext
    computed_mac = hmac.new(k_mac, VAULT_MAGIC.encode('utf-8') + nonce + ciphertext, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(computed_mac, expected_mac):
        raise ValueError("Decryption failed: Incorrect password or tampered vault archive")

    # 2. Decrypt ciphertext
    plaintext = _ctr_crypt(ciphertext, k_enc, nonce)

    # 3. Verify plaintext integrity
    if expected_checksum and hashlib.sha256(plaintext).hexdigest() != expected_checksum:
        raise ValueError("Integrity check failed: Plaintext checksum mismatch")

    return plaintext

def export_vault_file(source_config_path: str, output_vault_path: str, password: str, note: str = "") -> dict:
    """
    Reads source config file, encrypts it, and saves to destination .ccvault file.
    """
    if not os.path.exists(source_config_path):
        raise FileNotFoundError(f"Source configuration file not found: {source_config_path}")

    with open(source_config_path, "rb") as f:
        data = f.read()

    meta = {
        "source_file": os.path.basename(source_config_path),
        "export_host": "macOS-Localhost",
        "note": note or "Manual Security Vault Export"
    }

    envelope = encrypt_data(data, password, metadata=meta)

    # Ensure parent dir exists
    os.makedirs(os.path.dirname(os.path.abspath(output_vault_path)), exist_ok=True)
    with open(output_vault_path, "w", encoding="utf-8") as f:
        json.dump(envelope, f, indent=2)

    return {
        "success": True,
        "vault_path": output_vault_path,
        "timestamp": envelope["timestamp"],
        "size_bytes": os.path.getsize(output_vault_path),
        "raw_checksum": envelope["raw_checksum"]
    }

def import_vault_file(vault_path: str, destination_config_path: str, password: str) -> dict:
    """
    Reads .ccvault file, decrypts, and updates target config file.
    """
    if not os.path.exists(vault_path):
        raise FileNotFoundError(f"Vault archive file not found: {vault_path}")

    with open(vault_path, "r", encoding="utf-8") as f:
        envelope = json.load(f)

    plaintext = decrypt_data(envelope, password)

    # Validate JSON integrity
    try:
        config_obj = json.loads(plaintext.decode('utf-8'))
    except Exception as e:
        raise ValueError(f"Decrypted payload is not valid JSON: {e}")

    # Write atomically
    temp_target = destination_config_path + ".tmp"
    with open(temp_target, "wb") as f:
        f.write(plaintext)
    os.replace(temp_target, destination_config_path)

    return {
        "success": True,
        "imported_from": vault_path,
        "destination": destination_config_path,
        "vault_timestamp": envelope.get("timestamp"),
        "keys_restored": len(config_obj.get("integrations", {}))
    }

def inspect_vault_file(vault_path: str) -> dict:
    """
    Reads public headers of .ccvault file without requiring password.
    """
    if not os.path.exists(vault_path):
        raise FileNotFoundError(f"Vault file not found: {vault_path}")

    with open(vault_path, "r", encoding="utf-8") as f:
        envelope = json.load(f)

    return {
        "magic": envelope.get("magic"),
        "version": envelope.get("version"),
        "timestamp": envelope.get("timestamp"),
        "created_at": envelope.get("created_at_iso"),
        "kdf": envelope.get("kdf"),
        "cipher": envelope.get("cipher"),
        "raw_size": envelope.get("raw_size"),
        "metadata": envelope.get("metadata", {}),
        "archive_size": os.path.getsize(vault_path)
    }

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Command Center Security Vault")
    sub = parser.add_subparsers(dest="cmd", required=True)

    exp = sub.add_parser("export", help="Export encrypted vault")
    exp.add_argument("--config", default="config.json", help="Path to config.json")
    exp.add_argument("--out", default="backups/vault_export.ccvault", help="Output .ccvault path")
    exp.add_argument("--password", required=True, help="Vault encryption password")
    exp.add_argument("--note", default="CLI Export", help="Archive note")

    imp = sub.add_parser("import", help="Import encrypted vault")
    imp.add_argument("--vault", required=True, help="Path to .ccvault archive")
    imp.add_argument("--dest", default="config.json", help="Destination config.json path")
    imp.add_argument("--password", required=True, help="Vault decryption password")

    ins = sub.add_parser("inspect", help="Inspect vault header")
    ins.add_argument("--vault", required=True, help="Path to .ccvault archive")

    args = parser.parse_args()

    if args.cmd == "export":
        r = export_vault_file(args.config, args.out, args.password, args.note)
        print(json.dumps(r, indent=2))
    elif args.cmd == "import":
        r = import_vault_file(args.vault, args.dest, args.password)
        print(json.dumps(r, indent=2))
    elif args.cmd == "inspect":
        r = inspect_vault_file(args.vault)
        print(json.dumps(r, indent=2))

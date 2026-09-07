#!/usr/bin/env python3
"""
U1 OS — Zero-Dependency Base58 Utility
Pure-Python Base58 encoder and decoder for Solana addresses and private keys.
"""

ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
BASE = len(ALPHABET)
ALPHABET_MAP = {c: i for i, c in enumerate(ALPHABET)}

def b58encode(raw_bytes: bytes) -> bytes:
    """Encode bytes into base58 ASCII bytes."""
    if not raw_bytes:
        return b""
    origlen = len(raw_bytes)
    raw_bytes = raw_bytes.lstrip(b"\x00")
    newlen = len(raw_bytes)
    pad = origlen - newlen

    acc = int.from_bytes(raw_bytes, "big")
    res = []
    while acc > 0:
        acc, mod = divmod(acc, BASE)
        res.append(ALPHABET[mod])

    return (ALPHABET[0] * pad + "".join(reversed(res))).encode("ascii")

def b58decode(b58_val) -> bytes:
    """Decode base58 string or bytes into raw bytes."""
    if isinstance(b58_val, bytes):
        b58_val = b58_val.decode("ascii")
    if not b58_val:
        return b""
    pad = 0
    for c in b58_val:
        if c == ALPHABET[0]:
            pad += 1
        else:
            break
    acc = 0
    for c in b58_val[pad:]:
        if c not in ALPHABET_MAP:
            raise ValueError(f"Invalid base58 character: {c}")
        acc = acc * BASE + ALPHABET_MAP[c]
    
    res = []
    while acc > 0:
        acc, mod = divmod(acc, 256)
        res.append(mod)
    return (b"\x00" * pad) + bytes(reversed(res))

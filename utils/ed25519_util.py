#!/usr/bin/env python3
"""
U1 OS — Zero-Dependency Ed25519 Reference Implementation (RFC 8032)
Zero external C extensions, zero rust, 100% portable pure-Python ed25519 signer.
Derived from the official Python Ed25519 reference code (public domain).
"""

import hashlib

# Ed25519 curve parameters
q = 2**255 - 19
d = -121665 * pow(121666, q - 2, q) % q
I = pow(2, (q - 1) // 4, q)

def inv(x):
    return pow(x, q - 2, q)

def xrecover(y):
    xx = (y * y - 1) * inv(d * y * y + 1)
    x = pow(xx, (q + 3) // 8, q)
    if (x * x - xx) % q != 0:
        x = (x * I) % q
    if x % 2 != 0:
        x = q - x
    return x

By = 4 * inv(5) % q
Bx = xrecover(By)
B = (Bx % q, By % q)

def edwards(P, Q):
    x1, y1 = P
    x2, y2 = Q
    denom = d * x1 * x2 * y1 * y2
    x3 = (x1 * y2 + x2 * y1) * inv(1 + denom)
    y3 = (y1 * y2 + x1 * x2) * inv(1 - denom)
    return (x3 % q, y3 % q)

def scalarmult(P, e):
    if e == 0:
        return (0, 1)
    Q = scalarmult(P, e // 2)
    Q = edwards(Q, Q)
    if e & 1:
        Q = edwards(Q, P)
    return Q

def encodeint(y):
    bits = [(y >> i) & 1 for i in range(256)]
    return bytes(sum([bits[i * 8 + j] << j for j in range(8)]) for i in range(32))

def encodepoint(P):
    x, y = P
    bits = [(y >> i) & 1 for i in range(255)] + [x & 1]
    return bytes(sum([bits[i * 8 + j] << j for j in range(8)]) for i in range(32))

def bit(h, i):
    return (h[i // 8] >> (i % 8)) & 1

def public_key_from_seed(seed_bytes: bytes) -> bytes:
    """Derive 32-byte Ed25519 public key from 32-byte private seed."""
    h = hashlib.sha512(seed_bytes).digest()
    a = 2**254 + sum(2**i * bit(h, i) for i in range(3, 254))
    A = scalarmult(B, a)
    return encodepoint(A)

def sign(seed_bytes: bytes, message: bytes) -> bytes:
    """Sign message using 32-byte Ed25519 private seed. Returns 64-byte signature."""
    h = hashlib.sha512(seed_bytes).digest()
    a = 2**254 + sum(2**i * bit(h, i) for i in range(3, 254))
    A = scalarmult(B, a)
    pub_bytes = encodepoint(A)
    
    # r = H(h[32..64] || M)
    r_digest = hashlib.sha512(h[32:] + message).digest()
    r = sum(2**i * bit(r_digest, i) for i in range(512))
    R = scalarmult(B, r)
    R_bytes = encodepoint(R)
    
    # S = (r + H(R || A || M) * a) mod l
    l = 2**252 + 27742317777372353535851937790883648493
    k_digest = hashlib.sha512(R_bytes + pub_bytes + message).digest()
    k = sum(2**i * bit(k_digest, i) for i in range(512))
    S = (r + k * a) % l
    
    return R_bytes + encodeint(S)

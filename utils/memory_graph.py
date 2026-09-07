"""
Agentic Memory Graph & Local Vector Retrieval
Lightweight pure-Python associative memory graph and dense embedding similarity engine.
Indexes operator documents, meeting transcripts, and system events for instant semantic recall.
"""
import time
import math
import hashlib
import json

_MEMORY_GRAPH = [
    {
        "id": "mem_quant_mandate",
        "concept": "Capital Allocation & Kelly Bounds",
        "content": "Operator policy dictates max 15% Kelly fraction on prediction markets and mandatory atomic private mempools for flash arbitrage.",
        "tags": ["risk", "kelly", "finance"],
        "vector": [0.82, 0.15, 0.44, 0.91],
        "created_at": time.time() - 86400
    },
    {
        "id": "mem_security_gate",
        "concept": "Touch ID & YubiKey Hardware Interlocks",
        "content": "Lockdown release commands require both Touch ID biometric verification and physical FIDO2 YubiKey cryptographic assertions.",
        "tags": ["security", "auth", "hardware"],
        "vector": [0.12, 0.94, 0.78, 0.31],
        "created_at": time.time() - 43200
    },
    {
        "id": "mem_mesh_c2",
        "concept": "Nostr Sovereign P2P C2 Protocol",
        "content": "Emergency out-of-band communications broadcast via NIP-04 encrypted direct messages across 5 decentralized Nostr relays.",
        "tags": ["nostr", "p2p", "mesh"],
        "vector": [0.35, 0.45, 0.88, 0.67],
        "created_at": time.time() - 21600
    }
]

def _mock_embed(text):
    """Deterministic 4-element normalized vector projection."""
    h = hashlib.sha256(text.encode()).digest()
    raw = [float(h[i]) for i in range(4)]
    norm = math.sqrt(sum(x * x for x in raw)) or 1.0
    return [round(x / norm, 4) for x in raw]

def _cosine_similarity(v1, v2):
    """Computes cosine similarity between two dense vectors."""
    dot = sum(a * b for a, b in zip(v1, v2))
    n1 = math.sqrt(sum(a * a for a in v1)) or 1.0
    n2 = math.sqrt(sum(b * b for b in v2)) or 1.0
    return round(dot / (n1 * n2), 4)

def store_memory(concept, content, tags=None):
    """Indexes a new semantic memory node into the operator graph."""
    mid = f"mem_{hashlib.md5(concept.encode()).hexdigest()[:8]}"
    node = {
        "id": mid,
        "concept": concept,
        "content": content,
        "tags": tags or ["operator", "general"],
        "vector": _mock_embed(content),
        "created_at": time.time()
    }
    _MEMORY_GRAPH.append(node)
    return {"success": True, "node": node, "total_memories": len(_MEMORY_GRAPH)}

def query_memory_graph(query, top_k=3):
    """Performs semantic similarity retrieval against the memory graph."""
    q_vec = _mock_embed(query)
    scored = []
    for m in _MEMORY_GRAPH:
        score = _cosine_similarity(q_vec, m["vector"])
        scored.append({**m, "similarity_score": score})

    scored.sort(key=lambda x: x["similarity_score"], reverse=True)
    results = scored[:top_k]
    return {
        "success": True,
        "query": query,
        "results_count": len(results),
        "results": results,
        "top_concept": results[0]["concept"] if results else None
    }

def get_memory_stats():
    """Returns memory graph size and concept clusters."""
    return {
        "success": True,
        "total_nodes": len(_MEMORY_GRAPH),
        "nodes": list(_MEMORY_GRAPH),
        "clusters": ["Risk Governance", "Hardware Security", "P2P Mesh", "Quant Alpha"]
    }

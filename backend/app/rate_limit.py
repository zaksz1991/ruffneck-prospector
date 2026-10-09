"""
Simple in-memory rate limiter (per IP + route prefix).
Fine for single-node free deployments. Not distributed.
"""
from collections import defaultdict, deque
from time import time
from typing import Deque, Dict, Tuple
from fastapi import Request, HTTPException

# route_prefix -> max requests per window
LIMITS = {
    "/api/prospects/search": (10, 60),       # 10 / min
    "/api/discover": (15, 60),
    "/api/linkedin": (8, 60),
    "/api/sequences/process": (5, 60),
    "/api/replies/check": (10, 60),
    "/api/tech": (20, 60),
}

_hits: Dict[str, Deque[float]] = defaultdict(deque)


def _key(ip: str, prefix: str) -> str:
    return f"{ip}:{prefix}"


def check_rate_limit(request: Request) -> None:
    path = request.url.path
    matched = None
    for prefix, cfg in LIMITS.items():
        if path.startswith(prefix):
            matched = (prefix, cfg)
            break
    if not matched:
        return
    prefix, (max_req, window) = matched
    ip = request.client.host if request.client else "unknown"
    k = _key(ip, prefix)
    now = time()
    q = _hits[k]
    while q and q[0] < now - window:
        q.popleft()
    if len(q) >= max_req:
        raise HTTPException(429, f"Rate limit exceeded for {prefix}. Try again shortly.")
    q.append(now)

#!/usr/bin/env bash
# Lightweight API smoke test for RuffNeck Prospector
set -e
API="${1:-http://localhost:8000}"
echo "Smoke testing $API"

echo -n "GET / ... "
code=$(curl -s -o /tmp/rn_root.json -w "%{http_code}" "$API/")
echo "HTTP $code"
test "$code" = "200" -o "$code" = "404" -o "$code" = "307" || true

echo -n "GET /api/analytics ... "
code=$(curl -s -o /tmp/rn_an.json -w "%{http_code}" "$API/api/analytics")
echo "HTTP $code"

echo -n "GET /api/pipeline ... "
code=$(curl -s -o /tmp/rn_pipe.json -w "%{http_code}" "$API/api/pipeline")
echo "HTTP $code"

echo -n "GET /api/sequences ... "
code=$(curl -s -o /tmp/rn_seq.json -w "%{http_code}" "$API/api/sequences")
echo "HTTP $code"

echo -n "GET /api/notifications ... "
code=$(curl -s -o /tmp/rn_not.json -w "%{http_code}" "$API/api/notifications")
echo "HTTP $code"

echo -n "GET /api/replies/status ... "
code=$(curl -s -o /tmp/rn_rep.json -w "%{http_code}" "$API/api/replies/status")
echo "HTTP $code"

echo -n "GET /api/workspaces ... "
code=$(curl -s -o /tmp/rn_ws.json -w "%{http_code}" "$API/api/workspaces")
echo "HTTP $code"

echo -n "POST /api/tech/detect (example.com) ... "
code=$(curl -s -o /tmp/rn_tech.json -w "%{http_code}" -X POST "$API/api/tech/detect?url=https://example.com")
echo "HTTP $code"

echo ""
echo "Done. Non-200 on some routes may be OK if Supabase is not configured yet."
echo "Inspect /tmp/rn_*.json for bodies."

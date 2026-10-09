#!/usr/bin/env bash
# RuffNeck automation – cron recipes (alternative to Celery Beat)
# Requires: API running at API_URL, curl installed
API_URL="${API_URL:-http://localhost:8000}"

# Example crontab (crontab -e):
# */30 * * * * API_URL=http://localhost:8000 /path/to/scripts/cron_recipes.sh sequences
# */20 * * * * API_URL=http://localhost:8000 /path/to/scripts/cron_recipes.sh replies
# 0 8 * * *   API_URL=http://localhost:8000 /path/to/scripts/cron_recipes.sh daily

cmd="${1:-help}"
case "$cmd" in
  sequences)
    curl -s -X POST "$API_URL/api/sequences/process"
    echo
    ;;
  replies)
    curl -s -X POST "$API_URL/api/replies/check"
    echo
    ;;
  daily)
    curl -s -X POST "$API_URL/api/discover/daily" \
      -H "Content-Type: application/json" \
      -d '{"location":"","services":null}'
    echo
    ;;
  *)
    echo "Usage: $0 {sequences|replies|daily}"
    echo "Celery Beat alternative – see backend/app/celeryconfig.py"
    ;;
esac

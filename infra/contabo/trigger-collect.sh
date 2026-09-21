#!/usr/bin/env bash
# infra/contabo/trigger-collect.sh — hourly `workflow_dispatch` for .github/workflows/collect.yml.
#
# Why: GitHub's `schedule` fired the hourly collector about five times a day (2026-09-16: 23:06,
# 01:26, 07:39, 13:29 UTC; still ~5/day on 2026-09-18), so the public pages read "updated n hours
# ago" more often than "live". This runs from ney's crontab on Contabo every hour and asks GitHub
# to run the workflow now. Since 2026-09-21 it is the only clock: `schedule` was dropped from
# collect.yml after three days of proven cadence here, because both were firing and every hour ran
# twice. The daily steps still key off the 03:xx Bangkok run inside the collector; no input is
# passed here. `concurrency: collect` still covers a hand-run dispatch overlapping the hourly one.
#
# Token: a fine-grained PAT — resource owner neramitsingh, repository access ONLY tsntalks,
# permission Actions: read and write — in ~/.config/tsntalks/gh-token on Contabo (dir 700, file
# 600) and nowhere else. The laptop's broad git credential never leaves the laptop. No token file
# means disarmed: exit 0, one log line, no alert, no network.
#
# Alerts: one nav-event-bus post when a dispatch fails, one more when it recovers. BUS_TOKEN is read
# from nav-event-bus/.env (ney-readable on Contabo). The last outcome is kept in trigger.state so a
# dead token alerts once, not every hour.
#
# Install (as ney on Contabo; the repo is not in the VPS Syncthing subset, so this is a copy):
#   install -d -m 700 ~/.config/tsntalks
#   install -m 700 trigger-collect.sh ~/.config/tsntalks/trigger-collect.sh
#   crontab -e:  3 * * * * $HOME/.config/tsntalks/trigger-collect.sh
# Hand-over: remove the cron line and the token; Sunny's own scheduler, or GitHub's, takes over.
set -u

CFG="$HOME/.config/tsntalks"
TOKEN_FILE="${TSN_GH_TOKEN_FILE:-$CFG/gh-token}"
LOG="$CFG/trigger.log"
STATE="$CFG/trigger.state"
REPO="neramitsingh/tsntalks"
WORKFLOW="collect.yml"
REF="main"
BUS_URL="${BUS_URL:-http://127.0.0.1:8770}"
BUS_ENV="${BUS_ENV:-$HOME/Codes and Scripts/nav-event-bus/.env}"

ts() { date -u +%FT%TZ; }
log() { echo "$(ts) $*" >> "$LOG"; }
trim_log() {
  if [ -f "$LOG" ] && [ "$(wc -l < "$LOG")" -gt 2000 ]; then
    tail -n 1000 "$LOG" > "$LOG.tmp" && mv "$LOG.tmp" "$LOG"
  fi
}
# The bus payload is hand-built JSON: title and body pass through a character whitelist, as in
# personal-dashboard/ops/secwatch/secwatch.sh, so nothing can produce a quote or a backslash.
json_safe() { tr -cd 'A-Za-z0-9 !:;/.,()=_+@|#%?*-'; }
bus_post() { # bus_post <kind> <title> <severity> <event_uid> <body>
  local token=""
  if [ -r "$BUS_ENV" ]; then
    token="$(grep -m1 '^BUS_TOKEN=' "$BUS_ENV" | cut -d= -f2- | tr -d '\r"')"
  fi
  if [ -z "$token" ]; then
    log "bus: BUS_TOKEN unavailable, $1 not posted"
    return 1
  fi
  local code
  code="$(timeout 20 curl -s -o /dev/null -w '%{http_code}' -X POST \
    -H 'content-type: application/json' -H "X-Bus-Token: $token" \
    --data "$(printf '{"source":"tsn-trigger","kind":"%s","title":"%s","severity":"%s","event_uid":"%s","link":"/ops","body":"%s","meta":{"host":"contabo","repo":"%s"}}' \
      "$1" "$(printf '%s' "$2" | json_safe)" "$3" "$4" "$(printf '%s' "$5" | json_safe)" "$REPO")" \
    "$BUS_URL/events" 2>/dev/null)" || code="000"
  log "bus: $1 HTTP $code"
}

mkdir -p "$CFG"
chmod 700 "$CFG" 2>/dev/null || true
trim_log
prev="$(cat "$STATE" 2>/dev/null || echo ok)"

if [ ! -s "$TOKEN_FILE" ]; then
  log "disarmed: no token at $TOKEN_FILE"
  exit 0
fi

body="$(mktemp)"
code="$(timeout 30 curl -sS -o "$body" -w '%{http_code}' -X POST \
  -H 'Accept: application/vnd.github+json' \
  -H "Authorization: Bearer $(tr -d '[:space:]' < "$TOKEN_FILE")" \
  -H 'X-GitHub-Api-Version: 2022-11-28' \
  "https://api.github.com/repos/$REPO/actions/workflows/$WORKFLOW/dispatches" \
  --data "{\"ref\":\"$REF\"}" 2>/dev/null)" || code="000"

if [ "$code" = "204" ]; then
  log "dispatched"
  if [ "$prev" != "ok" ]; then
    bus_post "tsn-trigger-recovered" \
      "TSN Talks collector trigger is dispatching again (was HTTP $prev)" \
      "normal" "tsn-trigger-ok-$(date -u +%Y%m%d%H)" \
      "workflow_dispatch collect.yml returned 204 from contabo"
  fi
  echo ok > "$STATE"
  rm -f "$body"
  exit 0
fi

detail="$(head -c 200 "$body" | tr -d '\n')"
rm -f "$body"
log "FAILED http $code: $detail"
if [ "$prev" = "ok" ]; then
  bus_post "tsn-trigger-failed" \
    "TSN Talks collector trigger failed: HTTP $code from GitHub" \
    "high" "tsn-trigger-fail-$(date -u +%Y%m%d%H)" \
    "$detail (token expired or revoked? ~/.config/tsntalks/gh-token on contabo)"
fi
echo "$code" > "$STATE"
exit 1

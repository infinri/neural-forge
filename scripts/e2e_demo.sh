#!/usr/bin/env bash
set -euo pipefail
HOST=${HOST:-127.0.0.1}
PORT=${PORT:-8081}
TOKEN=${MCP_TOKEN:-dev}
BASE="http://$HOST:$PORT"

hdr=( -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" )

say() { echo -e "\n==== $* ====\n"; }

say "Capabilities"
curl -s "$BASE/get_capabilities" -H "Authorization: Bearer $TOKEN" | jq . || true

say "Governance: get_governance_policies"
curl -s -X POST "$BASE/tool/get_governance_policies" "${hdr[@]}" --data '{"projectId":"nf","scopes":["memory"]}' | jq . || true

say "Governance: get_active_tokens (security)"
curl -s -X POST "$BASE/tool/get_active_tokens" "${hdr[@]}" --data '{"projectId":"nf","kinds":["security"]}' | jq . || true

say "Governance: get_rules"
curl -s -X POST "$BASE/tool/get_rules" "${hdr[@]}" --data '{"projectId":"nf","scopes":["memory"]}' | jq . || true

say "Enqueue task"
ENQ=$(curl -s -X POST "${BASE}/tool/enqueue_task" "${hdr[@]}" --data '{"projectId":"neural-forge","payload":{"kind":"plan","note":"demo"}}')
echo "$ENQ" | jq .

say "Claim next task"
NEXT=$(curl -s -X POST "${BASE}/tool/get_next_task" "${hdr[@]}" --data '{"projectId":"neural-forge"}')
echo "$NEXT" | jq .
TASK_ID=$(echo "$NEXT" | jq -r '.task?.id // empty')

say "Save diff"
DIFF=$(cat <<'DIFF'
--- a/server/main.py
+++ b/server/main.py
@@
+# demo diff line
DIFF
)
SD=$(curl -s -X POST "${BASE}/tool/save_diff" "${hdr[@]}" --data @- <<JSON
{"projectId":"neural-forge","filePath":"server/main.py","diff":$(jq -Rn --arg d "$DIFF" '$d'),"author":"demo"}
JSON
)
echo "$SD" | jq .

say "Add memory"
AM=$(curl -s -X POST "${BASE}/tool/add_memory" "${hdr[@]}" --data '{"projectId":"neural-forge","content":"E2E demo memory token","metadata":{"tags":["demo","e2e"]}}')
echo "$AM" | jq .

say "Search memory"
SM=$(curl -s -X POST "${BASE}/tool/search_memory" "${hdr[@]}" --data '{"projectId":"neural-forge","query":"demo","limit":3}')
echo "$SM" | jq .

say "List recent diffs"
LR=$(curl -s -X POST "${BASE}/tool/list_recent" "${hdr[@]}" --data '{"projectId":"neural-forge","limit":5}')
echo "$LR" | jq .

if [[ -n "$TASK_ID" ]]; then
  say "Complete task $TASK_ID"
  FIN=$(curl -s -X POST "${BASE}/tool/update_task_status" "${hdr[@]}" --data @- <<JSON
{"id":"$TASK_ID","status":"done","result":{"ok":true,"note":"e2e complete"}}
JSON
)
  echo "$FIN" | jq .
else
  say "No task claimed"
fi

say "Log info"
LE=$(curl -s -X POST "${BASE}/tool/log_error" "${hdr[@]}" --data '{"level":"info","message":"E2E demo finished","projectId":"neural-forge"}')
echo "$LE" | jq .

echo -e "\nE2E demo finished successfully."

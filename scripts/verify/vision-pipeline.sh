#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
cd "${REPO_ROOT}"

if [[ ! -f "${REPO_ROOT}/backend/venv/bin/python" ]]; then
  echo "[FAIL] backend venv not found: ${REPO_ROOT}/backend/venv/bin/python"
  exit 20
fi

if [[ -f "${REPO_ROOT}/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "${REPO_ROOT}/.env"
  set +a
fi

BACKEND_API_TOKEN="${BACKEND_API_TOKEN:-}"
if [[ -z "${BACKEND_API_TOKEN}" ]]; then
  echo "[FAIL] BACKEND_API_TOKEN is required. Please set it in .env."
  exit 22
fi
export BACKEND_API_TOKEN

BACKEND_PORT="${BACKEND_PORT:-8000}"
BACKEND_HOST="${BACKEND_HOST:-127.0.0.1}"
VERIFY_API_BASE_URL="${VERIFY_API_BASE_URL:-http://${BACKEND_HOST}:${BACKEND_PORT}}"
export VERIFY_API_BASE_URL

echo "[INFO] Verifying vision pipeline against ${VERIFY_API_BASE_URL}"

"${REPO_ROOT}/backend/venv/bin/python" - <<'PY'
import asyncio
import base64
import json
import os
import time
from urllib.parse import urlencode

import httpx
import websockets

api_base = os.getenv("VERIFY_API_BASE_URL", "").rstrip("/")
if not api_base:
    raise SystemExit("[FAIL] VERIFY_API_BASE_URL is required.")

api_token = (os.getenv("BACKEND_API_TOKEN") or "").strip()
headers = {"Accept": "application/json"}
headers["X-API-Token"] = api_token

png_bytes = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO5nG9sAAAAASUVORK5CYII="
)

ws_base = api_base.replace("https://", "wss://").replace("http://", "ws://")
query = urlencode({"token": api_token})
ws_url = f"{ws_base}/api/ws/vision/tasks"
ws_url = f"{ws_url}?{query}"


async def main() -> None:
    async with httpx.AsyncClient(timeout=20.0, trust_env=False) as client:
        runtime_resp = await client.get(f"{api_base}/api/vision/runtime", headers=headers)
        if runtime_resp.status_code != 200:
            raise SystemExit(f"[FAIL] runtime check failed: {runtime_resp.status_code} {runtime_resp.text}")
        runtime = runtime_resp.json()
        print(f"[PASS] Runtime: engine={runtime.get('engine')} device={runtime.get('activeDevice')} storage={runtime.get('storageBackend')}")

        async with websockets.connect(ws_url, open_timeout=10) as websocket:
            connected_raw = await asyncio.wait_for(websocket.recv(), timeout=10)
            connected_payload = json.loads(connected_raw)
            if connected_payload.get("type") != "vision.connected":
                raise SystemExit(f"[FAIL] Unexpected websocket bootstrap payload: {connected_payload}")
            print("[PASS] WebSocket connected")

            files = {"file": ("verify_vision.png", png_bytes, "image/png")}
            submit_resp = await client.post(f"{api_base}/api/vision/tasks?source=MOBILE", headers=headers, files=files)
            if submit_resp.status_code != 202:
                raise SystemExit(f"[FAIL] submit task failed: {submit_resp.status_code} {submit_resp.text}")
            created = submit_resp.json()
            task_id = created.get("taskId")
            print(f"[PASS] Task accepted: {task_id}")

            accepted_seen = False
            final_payload = None
            deadline = time.monotonic() + 25
            while time.monotonic() < deadline:
                timeout = max(0.1, deadline - time.monotonic())
                message = await asyncio.wait_for(websocket.recv(), timeout=timeout)
                payload = json.loads(message)
                task = payload.get("task") or {}
                if task.get("taskId") != task_id:
                    continue
                if payload.get("type") == "vision.task.accepted":
                    accepted_seen = True
                if payload.get("type") == "vision.task.updated" and task.get("status") in {"DONE", "FAILED"}:
                    final_payload = payload
                    break

            if not accepted_seen:
                raise SystemExit("[FAIL] Did not receive vision.task.accepted event for submitted task.")
            if final_payload is None:
                raise SystemExit("[FAIL] Did not receive final vision.task.updated event within timeout.")

            status = final_payload["task"]["status"]
            engine = final_payload["task"].get("engine")
            device = final_payload["task"].get("device")
            print(f"[PASS] Real-time update: status={status} engine={engine} device={device}")

            final_resp = await client.get(f"{api_base}/api/vision/tasks/{task_id}", headers=headers)
            if final_resp.status_code != 200:
                raise SystemExit(f"[FAIL] fetch final task failed: {final_resp.status_code} {final_resp.text}")
            print("[PASS] Final task query available")

    print("[PASS] vision pipeline verification complete")


asyncio.run(main())
PY

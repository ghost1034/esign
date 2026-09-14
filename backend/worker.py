"""Private Cloud Run worker; invoke via Cloud Tasks/Scheduler OIDC."""
import os
from fastapi import FastAPI, Request, HTTPException
from google.auth.transport.requests import Request as GoogleRequest
from google.oauth2 import id_token
from core.runtime import is_explicitly_local, require_cloud_value
from services.esign.sealing_service import esign_sealing_service
from services.esign.ai_field_placement_service import esign_ai_field_placement_service
from services.esign.webhook_service import esign_webhook_service
from services.esign.maintenance_service import esign_maintenance_service

app = FastAPI(title="esign worker")

@app.post("/tasks/{kind}")
async def execute(kind: str, request: Request):
    if not is_explicitly_local():
        try:
            token = request.headers.get("authorization", "").removeprefix("Bearer ")
            claims = id_token.verify_oauth2_token(token, GoogleRequest(), require_cloud_value("ESIGN_WORKER_URL"))
            if claims.get("email") != require_cloud_value("TASK_SERVICE_ACCOUNT") or not claims.get("email_verified"):
                raise ValueError("Unauthorized task identity")
        except Exception as exc:
            raise HTTPException(401, "Invalid worker identity") from exc
    payload = await request.json()
    if kind == "seal": return await esign_sealing_service.process_envelope_seal(payload["envelope_id"])
    if kind == "placement": return await esign_ai_field_placement_service.process_run(payload["run_id"])
    if kind == "webhook": return await esign_webhook_service.deliver(payload["delivery_id"])
    if kind == "maintenance": return await esign_maintenance_service.run()
    raise HTTPException(404, "Unknown job")

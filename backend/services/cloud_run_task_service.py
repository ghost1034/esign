"""Dispatch only E-Signature jobs to the dedicated worker."""
import asyncio
import json
import os
import uuid
from datetime import datetime, timedelta, timezone
import httpx
from core.runtime import task_backend, require_cloud_value

class CloudRunTaskService:
    def __init__(self): self._local_tasks = set()
    async def _enqueue(self, kind, payload, delay_seconds=0):
        if task_backend() == "local":
            async def send():
                await asyncio.sleep(delay_seconds)
                async with httpx.AsyncClient(timeout=1800) as client:
                    worker = os.getenv("LOCAL_WORKER_BASE_URL", "http://127.0.0.1:8101").rstrip("/")
                    response = await client.post(worker + "/tasks/" + kind, json=payload)
                    response.raise_for_status()
            task = asyncio.create_task(send())
            self._local_tasks.add(task)
            def done(t):
                self._local_tasks.discard(t)
                if not t.cancelled() and t.exception():
                    import logging
                    logging.getLogger(__name__).error("Local task failed; maintenance will recover: %s", t.exception())
            task.add_done_callback(done)
            return "local/" + str(uuid.uuid4())
        from google.cloud import tasks_v2
        from google.protobuf.timestamp_pb2 import Timestamp
        from google.protobuf.duration_pb2 import Duration
        project = require_cloud_value("GOOGLE_CLOUD_PROJECT_ID")
        region = require_cloud_value("CLOUD_RUN_REGION")
        worker = require_cloud_value("ESIGN_WORKER_URL").rstrip("/")
        client = tasks_v2.CloudTasksClient()
        timestamp = Timestamp(); timestamp.FromDatetime(datetime.now(timezone.utc) + timedelta(seconds=delay_seconds))
        task = {"http_request": {"http_method": tasks_v2.HttpMethod.POST,
                "url": worker + "/tasks/" + kind, "headers": {"Content-Type": "application/json"},
                "body": json.dumps(payload).encode(), "oidc_token": {
                    "service_account_email": require_cloud_value("TASK_SERVICE_ACCOUNT"), "audience": worker}},
                "schedule_time": timestamp, "dispatch_deadline": Duration(seconds=1800)}
        result = await asyncio.to_thread(client.create_task, parent=client.queue_path(project, region, "esign-" + kind), task=task)
        return result.name
    async def enqueue_envelope_seal_task(self, envelope_id, delay_seconds=0):
        return await self._enqueue("seal", {"envelope_id": envelope_id}, delay_seconds)
    async def enqueue_esign_ai_field_placement_task(self, run_id, delay_seconds=0):
        return await self._enqueue("placement", {"run_id": run_id}, delay_seconds)
    async def enqueue_esign_webhook_task(self, delivery_id, delay_seconds=0):
        return await self._enqueue("webhook", {"delivery_id": delivery_id}, delay_seconds)
cloud_run_task_service = CloudRunTaskService()

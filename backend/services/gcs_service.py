"""Independent GCS adapter; development uses the filesystem adapter."""
import os
from datetime import timedelta
import asyncio
import google.auth
from google.auth.transport.requests import Request
from google.cloud import storage
from core.runtime import storage_backend, require_cloud_value

class GCSService:
    def __init__(self):
        self.bucket_name = require_cloud_value("GCS_BUCKET_NAME")
        self.client = storage.Client(project=require_cloud_value("GOOGLE_CLOUD_PROJECT_ID"))
        self.bucket = self.client.bucket(self.bucket_name)

    async def upload_file_content(self, content: bytes, object_name: str, content_type: str = "application/pdf"):
        await asyncio.to_thread(self.bucket.blob(object_name).upload_from_string, content, content_type=content_type)

    async def download_file_content(self, object_name: str) -> bytes:
        return await asyncio.to_thread(self.bucket.blob(object_name).download_as_bytes)

    async def download_file(self, object_name: str, local_path: str):
        await asyncio.to_thread(self.bucket.blob(object_name).download_to_filename, local_path)

    async def copy_object(self, source_object_name: str, destination_object_name: str):
        await asyncio.to_thread(self.bucket.copy_blob, self.bucket.blob(source_object_name), self.bucket, destination_object_name)

    async def delete_file(self, object_name: str):
        await asyncio.to_thread(self.bucket.blob(object_name).delete)

    async def list_objects(self, prefix: str):
        blobs = await asyncio.to_thread(lambda: list(self.client.list_blobs(self.bucket, prefix=prefix)))
        return [{"name": b.name, "size": b.size, "updated": b.updated} for b in blobs]

    async def generate_presigned_get_url(self, object_name: str, expiration_minutes: int = 15, **kwargs):
        def generate():
            credentials, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
            credentials.refresh(Request())
            return self.bucket.blob(object_name).generate_signed_url(
                version="v4", expiration=timedelta(minutes=expiration_minutes), method="GET",
                service_account_email=require_cloud_value("STORAGE_SIGNING_SERVICE_ACCOUNT"),
                access_token=credentials.token,
                response_disposition=("attachment; filename*=UTF-8\'\'" + __import__("urllib.parse", fromlist=["quote"]).quote(kwargs["download_filename"]) if kwargs.get("download_filename") else None),
                response_type=kwargs.get("response_type"),
            )
        return await asyncio.to_thread(generate)

_storage_service = None

def get_storage_service():
    global _storage_service
    if _storage_service is None:
        if storage_backend() == "local":
            from services.local_storage_service import LocalStorageService
            _storage_service = LocalStorageService()
        elif storage_backend() == "gcs":
            _storage_service = GCSService()
        else:
            raise RuntimeError("Unsupported STORAGE_BACKEND")
    return _storage_service

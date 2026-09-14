"""Independent esign API."""
from contextlib import asynccontextmanager
import os
from dotenv import load_dotenv
load_dotenv()
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from core.runtime import is_local, require_cloud_value, frontend_origins

@asynccontextmanager
async def lifespan(app):
    if not is_local():
        for name in ("ENVIRONMENT", "DATABASE_URL", "FIREBASE_PROJECT_ID", "GOOGLE_CLOUD_PROJECT_ID", "GCS_BUCKET_NAME", "APP_BASE_URL", "PUBLIC_API_BASE_URL", "ESIGN_WORKER_URL", "TASK_SERVICE_ACCOUNT", "STORAGE_SIGNING_SERVICE_ACCOUNT", "SMTP_HOST", "SMTP_FROM", "ESIGN_SIGNING_CERT_PEM", "ESIGN_KMS_SIGNING_KEY_VERSION"):
            require_cloud_value(name)
        if os.getenv("LOCAL_AUTH_BYPASS") == "true" or os.getenv("STORAGE_BACKEND") == "local" or os.getenv("TASK_BACKEND") == "local":
            raise RuntimeError("Development backends are prohibited outside local development")
    yield

app = FastAPI(title="esign API", version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=frontend_origins(), allow_methods=["*"], allow_headers=["*"])
from routes import esign, team, local_storage
app.include_router(esign.router, prefix="/api/esign", tags=["esign"])
app.include_router(team.router)
app.include_router(team.account_router)
if is_local(): app.include_router(local_storage.router, prefix="/api/local-storage")

@app.get("/health")
def health(): return {"status": "ok"}

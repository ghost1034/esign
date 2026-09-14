#!/usr/bin/env bash
set -euo pipefail
: "${GCP_PROJECT_ID:?Required}"
: "${GCP_REGION:?Required}"
: "${GCS_BUCKET_NAME:?Required}"
: "${APP_BASE_URL:?Set the standalone HTTPS frontend origin}"
: "${PUBLIC_API_BASE_URL:?Set the standalone HTTPS API origin}"
: "${SMTP_HOST:?Required}"
: "${SMTP_FROM:?Required}"
: "${SMTP_USERNAME:?Required}"
: "${NEXT_PUBLIC_FIREBASE_API_KEY:?Required}"
: "${NEXT_PUBLIC_FIREBASE_PROJECT_ID:?Required}"
: "${NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN:?Required}"
: "${NEXT_PUBLIC_FIREBASE_APP_ID:?Required}"
if [[ "$NEXT_PUBLIC_FIREBASE_PROJECT_ID" != "$GCP_PROJECT_ID" ]]; then echo 'Firebase must belong to the independent GCP project.' >&2; exit 1; fi
export RELEASE_ID="${RELEASE_ID:-$(git rev-parse --short HEAD)}"
export BACKEND_IMAGE="$GCP_REGION-docker.pkg.dev/$GCP_PROJECT_ID/esign/backend:$RELEASE_ID"
export FRONTEND_IMAGE="$GCP_REGION-docker.pkg.dev/$GCP_PROJECT_ID/esign/frontend:$RELEASE_ID"
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
export DEPLOY_WORK="$work"
python3 - <<'PY'
import json, os
from pathlib import Path
p = Path(os.environ['DEPLOY_WORK'])
project, region = os.environ['GCP_PROJECT_ID'], os.environ['GCP_REGION']
base = { 'ENVIRONMENT': 'production', 'STORAGE_BACKEND': 'gcs', 'TASK_BACKEND': 'cloud',
    'GOOGLE_CLOUD_PROJECT_ID': project, 'FIREBASE_PROJECT_ID': project, 'CLOUD_RUN_REGION': region,
    'GCS_BUCKET_NAME': os.environ['GCS_BUCKET_NAME'], 'APP_BASE_URL': os.environ['APP_BASE_URL'],
    'PUBLIC_API_BASE_URL': os.environ['PUBLIC_API_BASE_URL'], 'ESIGN_WORKER_URL': 'https://pending.invalid',
    'TASK_SERVICE_ACCOUNT': f'esign-tasks@{project}.iam.gserviceaccount.com',
    'SMTP_HOST': os.environ['SMTP_HOST'], 'SMTP_PORT': os.getenv('SMTP_PORT', '587'),
    'SMTP_SECURITY': os.getenv('SMTP_SECURITY', 'starttls'), 'SMTP_FROM': os.environ['SMTP_FROM'], 'SMTP_USERNAME': os.environ['SMTP_USERNAME'],
    'ESIGN_SIGNING_CERT_PEM': '',
    'ESIGN_KMS_SIGNING_KEY_VERSION': os.getenv('ESIGN_KMS_SIGNING_KEY_VERSION', f'projects/{project}/locations/{region}/keyRings/esign/cryptoKeys/esign-seal/cryptoKeyVersions/1'),
    'ESIGN_AI_FIELD_PLACEMENT_MODEL': os.getenv('ESIGN_AI_FIELD_PLACEMENT_MODEL', 'gemini-2.5-flash'),
    'ESIGN_AI_FIELD_PLACEMENT_LOCATION': os.getenv('ESIGN_AI_FIELD_PLACEMENT_LOCATION', 'global'),
    'ESIGN_WEBHOOK_DISPATCH_ENABLED': 'true' }
del base['ESIGN_SIGNING_CERT_PEM']
for kind in ['api', 'worker']:
    settings = {**base, 'APP_MODULE': 'main' if kind == 'api' else 'worker', 'STORAGE_SIGNING_SERVICE_ACCOUNT': f'esign-{kind}@{project}.iam.gserviceaccount.com'}
    (p / f'{kind}.json').write_text(json.dumps(settings))
args = ['build', '-t', os.environ['FRONTEND_IMAGE']]
for name in ['NEXT_PUBLIC_FIREBASE_API_KEY', 'NEXT_PUBLIC_FIREBASE_PROJECT_ID', 'NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN', 'NEXT_PUBLIC_FIREBASE_APP_ID']:
    args += ['--build-arg', name+'='+os.environ[name]]
args += ['.']
(p/'build.json').write_text(json.dumps({'steps':[{'name':'gcr.io/cloud-builders/docker','args':args}], 'images':[os.environ['FRONTEND_IMAGE']]}))
PY
gcloud builds submit backend --tag "$BACKEND_IMAGE" --project="$GCP_PROJECT_ID"
gcloud builds submit . --config "$work/build.json" --project="$GCP_PROJECT_ID"
connection="$GCP_PROJECT_ID:$GCP_REGION:esign-db"
secrets='DATABASE_URL=esign-database-url:latest,SMTP_PASSWORD=esign-smtp-password:latest,ESIGN_SIGNING_CERT_PEM=esign-signing-cert:latest'
# A separate job runs the baseline/forward migrations before API rollout.
gcloud run jobs deploy esign-migrate --image "$BACKEND_IMAGE" --command python --args=-m,alembic,upgrade,head --service-account="esign-api@$GCP_PROJECT_ID.iam.gserviceaccount.com" --set-cloudsql-instances="$connection" --set-secrets="DATABASE_URL=esign-database-url:latest" --set-env-vars=ENVIRONMENT=production --region="$GCP_REGION" --project="$GCP_PROJECT_ID"
gcloud run jobs execute esign-migrate --wait --region="$GCP_REGION" --project="$GCP_PROJECT_ID"
gcloud run deploy esign-worker --image "$BACKEND_IMAGE" --no-allow-unauthenticated --service-account="esign-worker@$GCP_PROJECT_ID.iam.gserviceaccount.com" --add-cloudsql-instances="$connection" --env-vars-file="$work/worker.json" --set-secrets="$secrets" --timeout=1800 --concurrency=4 --memory=4Gi --cpu=2 --region="$GCP_REGION" --project="$GCP_PROJECT_ID"
export ESIGN_WORKER_URL=$(gcloud run services describe esign-worker --region="$GCP_REGION" --project="$GCP_PROJECT_ID" --format='value(status.url)')
gcloud run services update esign-worker --update-env-vars="ESIGN_WORKER_URL=$ESIGN_WORKER_URL" --region="$GCP_REGION" --project="$GCP_PROJECT_ID"
gcloud run services add-iam-policy-binding esign-worker --member="serviceAccount:esign-tasks@$GCP_PROJECT_ID.iam.gserviceaccount.com" --role=roles/run.invoker --region="$GCP_REGION" --project="$GCP_PROJECT_ID"
python3 - <<'PY'
import json,os
from pathlib import Path
p=Path(os.environ['DEPLOY_WORK'])/'api.json'; data=json.loads(p.read_text());data['ESIGN_WORKER_URL']=os.environ['ESIGN_WORKER_URL'];p.write_text(json.dumps(data))
PY
gcloud run deploy esign-api --image "$BACKEND_IMAGE" --allow-unauthenticated --service-account="esign-api@$GCP_PROJECT_ID.iam.gserviceaccount.com" --add-cloudsql-instances="$connection" --env-vars-file="$work/api.json" --set-secrets="$secrets" --memory=2Gi --timeout=300 --region="$GCP_REGION" --project="$GCP_PROJECT_ID"
api_url=$(gcloud run services describe esign-api --region="$GCP_REGION" --project="$GCP_PROJECT_ID" --format='value(status.url)')
gcloud run deploy esign-web --service-account="esign-web@$GCP_PROJECT_ID.iam.gserviceaccount.com" --image "$FRONTEND_IMAGE" --allow-unauthenticated --set-env-vars="API_INTERNAL_URL=$api_url,NEXT_PUBLIC_APP_ENV=production" --memory=512Mi --region="$GCP_REGION" --project="$GCP_PROJECT_ID"
scheduler_command=create
if gcloud scheduler jobs describe esign-maintenance --location="$GCP_REGION" --project="$GCP_PROJECT_ID" >/dev/null 2>&1; then scheduler_command=update; fi
gcloud scheduler jobs "$scheduler_command" http esign-maintenance --schedule='* * * * *' --uri="$ESIGN_WORKER_URL/tasks/maintenance" --http-method=POST --message-body='{}' --headers=Content-Type=application/json --oidc-service-account-email="esign-tasks@$GCP_PROJECT_ID.iam.gserviceaccount.com" --oidc-token-audience="$ESIGN_WORKER_URL" --location="$GCP_REGION" --project="$GCP_PROJECT_ID"
echo 'Deployment submitted. Complete domain routing and the documented prelaunch smoke tests.'

#!/usr/bin/env bash
# Provision only when an operator explicitly runs this script.
set -euo pipefail
: "${GCP_PROJECT_ID:?Set an independent GCP project ID}"
: "${GCP_REGION:?Set a GCP region}"
: "${GCS_BUCKET_NAME:?Set a globally unique private bucket name}"
: "${DATABASE_PASSWORD_FILE:?Path to a password file for the new esign SQL user}"
: "${SMTP_PASSWORD_FILE:?Path to the independent SMTP password file}"
project="$GCP_PROJECT_ID"
region="$GCP_REGION"
if ! gcloud projects describe "$project" >/dev/null 2>&1; then
  : "${GCP_BILLING_ACCOUNT:?Required when creating a project}"
  gcloud projects create "$project" --name=esign
  gcloud billing projects link "$project" --billing-account="$GCP_BILLING_ACCOUNT"
fi
gcloud services enable run.googleapis.com sqladmin.googleapis.com cloudtasks.googleapis.com cloudscheduler.googleapis.com secretmanager.googleapis.com cloudkms.googleapis.com artifactregistry.googleapis.com cloudbuild.googleapis.com aiplatform.googleapis.com iamcredentials.googleapis.com firebase.googleapis.com identitytoolkit.googleapis.com --project="$project"
for name in esign-api esign-worker esign-tasks esign-web; do
  gcloud iam service-accounts describe "$name@$project.iam.gserviceaccount.com" --project="$project" >/dev/null 2>&1 || gcloud iam service-accounts create "$name" --project="$project"
done
gcloud artifacts repositories describe esign --location="$region" --project="$project" >/dev/null 2>&1 || gcloud artifacts repositories create esign --repository-format=docker --location="$region" --project="$project"
gcloud sql instances describe esign-db --project="$project" >/dev/null 2>&1 || gcloud sql instances create esign-db --database-version=POSTGRES_15 --tier=db-custom-1-3840 --region="$region" --storage-size=10 --backup-start-time=03:00 --enable-point-in-time-recovery --deletion-protection --project="$project"
gcloud sql databases describe esign --instance=esign-db --project="$project" >/dev/null 2>&1 || gcloud sql databases create esign --instance=esign-db --project="$project"
if gcloud sql users list --instance=esign-db --project="$project" --format='value(name)' | grep -qx esign; then
  echo 'SQL user already exists; preserving its password.'
else
  gcloud sql users create esign --instance=esign-db --password="$(cat "$DATABASE_PASSWORD_FILE")" --project="$project"
fi
gcloud storage buckets describe "gs://$GCS_BUCKET_NAME" --project="$project" >/dev/null 2>&1 || gcloud storage buckets create "gs://$GCS_BUCKET_NAME" --location="$region" --uniform-bucket-level-access --public-access-prevention --project="$project"
gcloud storage buckets update "gs://$GCS_BUCKET_NAME" --versioning --project="$project"
gcloud kms keyrings describe esign --location="$region" --project="$project" >/dev/null 2>&1 || gcloud kms keyrings create esign --location="$region" --project="$project"
gcloud kms keys describe esign-seal --keyring=esign --location="$region" --project="$project" >/dev/null 2>&1 || gcloud kms keys create esign-seal --keyring=esign --location="$region" --purpose=asymmetric-signing --default-algorithm=ec-sign-p256-sha256 --project="$project"
for kind in seal placement webhook maintenance; do
  gcloud tasks queues describe "esign-$kind" --location="$region" --project="$project" >/dev/null 2>&1 || gcloud tasks queues create "esign-$kind" --location="$region" --max-attempts=10 --max-concurrent-dispatches=5 --project="$project"
done
for identity in esign-api esign-worker; do
  sa="$identity@$project.iam.gserviceaccount.com"
  for role in roles/cloudsql.client roles/cloudtasks.enqueuer; do
    gcloud projects add-iam-policy-binding "$project" --member="serviceAccount:$sa" --role="$role" --condition=None --quiet >/dev/null
  done
  gcloud storage buckets add-iam-policy-binding "gs://$GCS_BUCKET_NAME" --member="serviceAccount:$sa" --role=roles/storage.objectAdmin --project="$project" >/dev/null
  gcloud iam service-accounts add-iam-policy-binding "esign-tasks@$project.iam.gserviceaccount.com" --member="serviceAccount:$sa" --role=roles/iam.serviceAccountUser --project="$project" >/dev/null
  gcloud iam service-accounts add-iam-policy-binding "$sa" --member="serviceAccount:$sa" --role=roles/iam.serviceAccountTokenCreator --project="$project" >/dev/null
done
for role in roles/cloudkms.signerVerifier roles/cloudkms.publicKeyViewer; do
  gcloud kms keys add-iam-policy-binding esign-seal --keyring=esign --location="$region" --member="serviceAccount:esign-worker@$project.iam.gserviceaccount.com" --role="$role" --project="$project" >/dev/null
done
gcloud projects add-iam-policy-binding "$project" --member="serviceAccount:esign-worker@$project.iam.gserviceaccount.com" --role=roles/aiplatform.user --condition=None --quiet >/dev/null
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
export ESIGN_SQL_CONNECTION="$project:$region:esign-db"
python3 - "$work/database-url" <<'PY'
import os, sys
from pathlib import Path
from urllib.parse import quote
password = Path(os.environ['DATABASE_PASSWORD_FILE']).read_text().strip()
Path(sys.argv[1]).write_text('postgresql://esign:' + quote(password, safe='') + '@/' + 'esign?host=/cloudsql/' + os.environ['ESIGN_SQL_CONNECTION'])
PY
key_version="projects/$project/locations/$region/keyRings/esign/cryptoKeys/esign-seal/cryptoKeyVersions/1"
backend/.venv/bin/python backend/scripts/setup_esign_signing_cert.py --key-version "$key_version" --out "$work/certificate.pem"
for mapping in "database-url:$work/database-url" "smtp-password:$SMTP_PASSWORD_FILE" "signing-cert:$work/certificate.pem"; do
  secret="esign-${mapping%%:*}"
  file="${mapping#*:}"
  if gcloud secrets describe "$secret" --project="$project" >/dev/null 2>&1; then
    echo "Preserving existing secret: $secret. Rotate explicitly when needed."
  else
    gcloud secrets create "$secret" --data-file="$file" --replication-policy=automatic --project="$project"
  fi
  for identity in esign-api esign-worker; do
    gcloud secrets add-iam-policy-binding "$secret" --member="serviceAccount:$identity@$project.iam.gserviceaccount.com" --role=roles/secretmanager.secretAccessor --project="$project" >/dev/null
  done
done
echo 'Infrastructure prepared. Register this project with Firebase, configure sign-in providers, and supply deployment settings as documented in docs/deployment.md.'

# Independent GCP deployment

The scripts are deployment tooling, not a record of a live deployment. Run from the repository root with a GCP operator account authorized to create the listed resources. Do not point them at an existing application project. Scripts always pass the explicit project; they do not change your gcloud default project.

## Provisioning inputs

Set `GCP_PROJECT_ID`, `GCP_REGION`, and a globally unique `GCS_BUCKET_NAME`. If the project does not exist, also set `GCP_BILLING_ACCOUNT`. Supply `DATABASE_PASSWORD_FILE` and `SMTP_PASSWORD_FILE` as paths to local secret files outside Git. The database password must be a strong random password; the example local password is not suitable for cloud deployment.

Run `bash scripts/provision-gcp.sh`. It creates/enables:

- Cloud Run, SQL, Tasks, Scheduler, Secret Manager, KMS, Artifact Registry, Cloud Build, Vertex AI, and Firebase/Identity Toolkit APIs.
- PostgreSQL 15 with backups, point-in-time recovery, deletion protection, application user/database, and no authorized public client networks; Cloud Run connects using its Cloud SQL integration.
- A private versioned storage bucket with uniform access and public-access prevention.
- Independent API, worker, and task-dispatch service accounts; object storage and database access, scoped secret access, and task dispatch permissions. Signing permissions belong to the worker; Vertex AI inference belongs to the worker.
- Four E-Signature queues, a P-256 asymmetric signing key, and a matching self-signed completion-seal certificate. The certificate is a tamper-evidence identity, not a publicly trusted certificate-authority credential.
- Database URL, SMTP password, and signing certificate secrets.

The operator needs KMS signing/public-key access to generate the initial certificate. Existing SQL users and secrets are preserved on reruns; changing local password files does not rotate deployed credentials. Use an explicit credential-rotation procedure instead. Record the pinned key version and certificate together.

## Firebase configuration

Register the independent GCP project in the Firebase console and add a web app. Enable email/password and Google providers, configure support email, and authorize the standalone app domain and localhost for development. Copy the web app's public values into the four `NEXT_PUBLIC_FIREBASE_*` inputs below. The Firebase project must equal `GCP_PROJECT_ID`; the backend verifies tokens against it.

For phone MFA, enable the Firebase/Identity Platform capabilities and billing required by that provider, configure allowed SMS regions and reCAPTCHA domains, and set test phone numbers for staging. Phone enrollment is optional in esign account settings; Firebase challenges accounts that have enrolled. Email verification precedes enrollment. MFA removal requires Firebase's recent-authentication checks; if prompted, sign out and back in before retrying. Do not describe an ordinary account signature as MFA-verified.

Authentication emails use the new Firebase project's templates/action URLs. Signing invitations, reminders, and completion emails use SMTP. Configure SMTP credentials and sender authorization in an independent mail service, and publish that service's required DNS records.

## Deployment inputs and command

Provide the provisioning inputs plus:

- `APP_BASE_URL`: standalone HTTPS frontend origin.
- `PUBLIC_API_BASE_URL`: standalone HTTPS API origin used in public links.
- `SMTP_HOST`, `SMTP_FROM`, `SMTP_USERNAME`; optional `SMTP_PORT` (587) and `SMTP_SECURITY` (`starttls`, or `ssl`). Production plaintext SMTP is prohibited.
- `NEXT_PUBLIC_FIREBASE_API_KEY`, `NEXT_PUBLIC_FIREBASE_PROJECT_ID`, `NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN`, `NEXT_PUBLIC_FIREBASE_APP_ID`.
- Optional `ESIGN_KMS_SIGNING_KEY_VERSION`, `ESIGN_AI_FIELD_PLACEMENT_MODEL`, and `ESIGN_AI_FIELD_PLACEMENT_LOCATION`. Defaults preserve the initial signing key version and current placement model configuration; confirm availability in the deployment project.
- Optional `RELEASE_ID`; otherwise the current Git commit supplies the image tag.

Run `bash scripts/deploy-gcp.sh`. It builds backend/frontend containers, runs database migrations as a separate Cloud Run job, deploys the private worker, configures its OIDC audience and task invoker, deploys the authenticated-domain API and public frontend, and schedules maintenance once per minute. The API is publicly reachable because guest endpoints need it; sender endpoints require Firebase authentication. The worker requires Cloud Run IAM plus application verification of the task account and audience.

The frontend passes `/api/*` through a runtime proxy to the standalone API, preserving authorization, guest cookies, response bodies, and download behavior. Firebase public settings are build inputs; changing them requires rebuilding the frontend. Secrets remain runtime inputs and never enter frontend build arguments.

Create domain routing for the supplied app/API origins using your approved HTTPS routing configuration, and configure Firebase's authorized domains before inviting users. The script does not purchase a domain or alter DNS. Use the emitted Cloud Run origins to establish routing; resource names are discoverable with `gcloud run services describe`.

The deploy operator must be able to act as the service accounts and run Cloud Build. Grant the project's selected Cloud Build identity Artifact Registry write access, following the project's build-identity policy. Do not give application service accounts deployment-administrator roles.

## Prelaunch checks (must run against the deployed environment)

1. Create a new Firebase account, verify email, create a team, invite a second account, and confirm member/admin boundaries and last-admin protection.
2. Sign in with Google and email/password. Enroll phone MFA, confirm the next login challenges it, remove it following recent-authentication verification, and confirm signing evidence distinguishes these paths.
3. Upload PDF and Office examples, author fields, send using real SMTP, sign through an incognito guest browser, and download the sealed PDF and certificate. Validate the seal and show that a modified PDF fails integrity checks.
4. Exercise typed/drawn signatures, sequential recipients, decline, correction, reassignment, PowerForms, a scheduled send, and a small bulk send. Confirm deep links stay on the new app origin.
5. Run one real Vertex placement request. Confirm the worker uses its own project and that failures remain visible/recoverable.
6. Verify Cloud Tasks duplicate delivery is harmless; inspect maintenance, email retries, and a controlled webhook receiver's signature verification. Confirm unauthenticated worker calls fail.
7. Verify GCS signed download URLs and tenant authorization. Check that guest cookies have the correct scoped path, HttpOnly, Secure, and SameSite flags in HTTPS.
8. Exercise backup restoration and confirm queue/certificate monitoring before opening general access.

Local, mocked, and CI checks do not substitute for these external-service checks. No live Firebase, SMTP, Vertex, KMS, or cloud rollout is claimed by the repository's local test results.

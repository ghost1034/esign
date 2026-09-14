# Operations

## Data and recovery

Cloud SQL holds identity/team membership, envelopes, recipients, fields, immutable evidence, templates, jobs, and delivery state. GCS holds source files, signature images, sealed PDFs, and certificates. Back up and restore them as one application: database recovery without matching object generations can leave broken evidence/downloads.

Use Cloud SQL automated backups and point-in-time recovery. Keep GCS object versioning enabled; define retention/lifecycle policy deliberately based on your organization's document retention requirements. Export database snapshots periodically to a separately permissioned backup destination. Test restoration into a separate project/bucket; never overwrite the active system as a rehearsal.

For recovery, pause scheduling/queue dispatch, restore SQL into a new instance, restore referenced object generations, and provide independent runtime configuration with the preserved signing certificates. Verify representative completed records and object hashes before directing traffic to restored services. Re-enable queues only after reconciling persistent work/delivery records to avoid sending obsolete invitations.

The initial schema intentionally has no destructive downgrade. Immutable evidence triggers, recipient-change history, published template versions, and administrative/webhook attempt history must survive forward migrations. Do not disable triggers to clean production data. The automated test runner uses a disposable database instead.

## Signing keys

KMS private keys never leave KMS. Pin a signing key version and its matching certificate in runtime configuration. To rotate, create a new key version, generate a matching certificate using `backend/scripts/setup_esign_signing_cert.py`, add a new certificate secret version, and deploy both values together. Confirm public-key correspondence before sending new envelopes. Keep historical certificates and key-version metadata so old records remain verifiable. Never destroy a key version without an approved retention/recovery review.

Development keys are created under `.local/`, ignored by Git, and prohibited outside explicit development/test environments. They are not production credentials or publicly trusted certificates.

## Jobs and delivery

Maintenance runs once per minute in GCP and every 30 seconds locally. It processes scheduled sends, bulk progress, reminders, expiration, persistent sealing work, pending email deliveries, AI recovery, and due webhook work. The database outbox is the recovery source; Cloud Tasks supplies delivery, not the only record of work.

Inspect structured Cloud Run logs and persisted job/delivery records when a task fails. Verify configuration and upstream availability first. Use the E-Signature management retry controls for failed seals/deliveries and the administrator webhook delivery views. Re-delivery must use the original job/envelope/delivery identity. AI inference attempts are reserved durably: a run that cannot safely repeat inference fails visibly rather than silently issuing a duplicate model request.

Monitor failed/old work items, aged email deliveries, webhook retries, AI failures, Cloud Tasks queue age, API error rate, SQL connections/storage, and KMS signing errors. Set Cloud Monitoring alerts for worker/API errors and queue age before launch. Current rate limiting is process-local and provides best-effort abuse protection; scale-out deployments should apply a managed edge/distributed rate-limit policy for strict global quotas.

SMTP success means acceptance by the configured SMTP server, not guaranteed inbox delivery. Monitor the mail provider for bounces and sender reputation. Do not reset a failed delivery to success manually. Mailpit captures development messages without external delivery.

## Releases and rollback

CI verifies the source, frontend, generated contracts, and PostgreSQL baseline/lifecycles before a release. Deploy migrations before application revisions. For subsequent releases use additive/backward-compatible schema changes so the previous API and worker revisions can run during rollout and rollback. Roll back Cloud Run traffic to an earlier compatible image if needed; do not automatically downgrade evidence-bearing databases. Keep frontend and API contract versions compatible when rolling back one tier.

The repository supplies provisioning and deployment commands but does not install project-specific alert destinations or DNS records automatically. Record those operational settings with the deployment inventory and complete the prelaunch checklist.

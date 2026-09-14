# esign

Independent electronic-signature application built with Next.js 15, React 19, FastAPI, and PostgreSQL 15. It owns its accounts, organizations, storage, background processing, and signing keys. There are no subscriptions or billing checks.

Prepare PDF and Office documents, place fields manually or with AI, create reusable versioned templates, route documents to signers and advanced recipients, and retain consent, audit evidence, sealed PDFs, and completion certificates. Includes guest signing, corrections, scheduled/bulk sends, PowerForms, branding, access profiles, custody management, reports, and outbound webhooks.

## Local development

Requirements: Node.js 22+, Python 3.13+, Docker Compose, LibreOffice, Tesseract, and Poppler. On macOS install the three document tools using your package manager. Linux dependencies are listed in `backend/Dockerfile`.

```sh
npm ci
cp .env.example .env
npm run dev
```

The launcher creates an isolated Python environment if needed, starts PostgreSQL and Mailpit, applies the baseline, creates a development signing certificate, and starts the API, worker, frontend, and maintenance timer.

- App: http://localhost:3100
- API/docs: http://127.0.0.1:8100/docs
- Private local worker: http://127.0.0.1:8101
- Captured email: http://localhost:8025
- PostgreSQL: localhost:55432 (`esign_dev`, local username/password `esign`)

The explicit local identity bypass signs in as a development account. Create an organization on first use. PostgreSQL and files under `.local/` persist across restarts. Ctrl-C stops the application processes; `docker compose stop` stops database/mail services. These ports are intentionally separate from typical development defaults.

AI placement requires credentials for **your independent** GCP project with Vertex AI enabled, even during local development. All other core signing workflows, conversion, sealing, and captured email run locally. No real email is sent by default. Development keys and all environment files are excluded from Git.

## Identity and teams

Set both local-auth bypass flags to `false` and configure the Firebase values in `.env` to use real email/password or Google sign-in. See [deployment setup](docs/deployment.md) for Firebase registration and optional phone MFA. Guests use scoped invitation/session tokens and do not need a team or an account.

Accounts belong to one organization. Its creator is administrator; invitation-code joins receive member/sender access. Organization administrators manage members, E-Signature permission profiles, and custody. Removing the final administrator is prohibited. Removing an owner requires a same-team custody successor. Account settings support profile changes, email verification, password reset, and optional phone MFA enrollment/removal.

## Verification

```sh
npm run lint
npm run type-check
npm run test:unit
npm run test:backend
npm run test:browser
npm run check:openapi
npm run check:independence
npm run build
```

Backend tests require the local PostgreSQL service. Their runner creates and drops a dedicated disposable database, applies the real baseline, and runs the PostgreSQL lifecycle and placement suites without skipping them. Browser tests launch the frontend and use controlled API responses to test UI contracts; they do not assert live Firebase/GCP behavior. Real signing/sealing/evidence semantics run in the backend PostgreSQL suite. Install the browser once with `npx playwright install chromium`.

`npm run generate-types` updates `backend/openapi.json` and `lib/api-types.ts`. CI checks both for drift. The independence check rejects external platform imports, URLs, branding, sibling-directory dependencies, and symlinks.

## Deployment and operations

[Deployment](docs/deployment.md) documents independent GCP provisioning, Firebase and SMTP setup, build inputs, deployment, and prelaunch checks. [Operations](docs/operations.md) covers backups, restoration, keys, failed jobs, and rollback. No cloud resources are provisioned by installation, tests, or local startup.

The repository includes a blank informed-consent example used only for deterministic placement regression tests; no customer envelopes, production data, or credentials are included. Signature font licenses remain alongside their font files.

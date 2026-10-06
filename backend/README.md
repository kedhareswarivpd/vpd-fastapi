# CoreFusion Technologies — FastAPI Backend

A production-ready Python/FastAPI + PostgreSQL backend powering the CoreFusion
Technologies website, Admin Panel, Client Portal, and Employee Portal — built
directly from the Website Master Content Pack (Version 1.0). This is the
Python/FastAPI counterpart of the Node.js/Express version, with equivalent
module coverage and architecture.

---

## 1. Tech Stack

| Layer | Technology |
|---|---|
| Runtime | Python 3.12, FastAPI |
| Database | PostgreSQL (SQLAlchemy 2.0 async ORM + asyncpg) — a local container in dev, optionally a Supabase-hosted Postgres in staging (database layer only) |
| Migrations | Alembic |
| Auth | **Fully CoreFusion-owned** (`app/services/auth_service.py`) — opaque, database-backed session tokens (not JWTs), Argon2id password hashing, refresh-token rotation with reuse detection, account lockout. No external identity provider is used in any environment. |
| Cache | Redis 7 — local container in dev, Upstash (managed) in staging |
| Validation | Pydantic v2 |
| File uploads | Local disk by default, or an S3-compatible bucket (`app/services/storage_service.py`) — MinIO locally, Supabase Storage in staging — when `STORAGE_BACKEND=s3` |
| Email | Brevo's transactional HTTP API (`app/services/email_service.py`) — contact-form notifications AND auth emails (password reset, verification, welcome, MFA) |
| Rate limiting | slowapi |
| Server | Uvicorn (dev) / Gunicorn + Uvicorn workers (prod) |
| Deployment | Docker, Docker Compose, Nginx, GitHub Actions |

---

## 2. Folder Structure

```
corefusion-fastapi/
├── app/
│   ├── core/               # config, database engine, password/token hashing, dependencies, logger, errors
│   ├── models/              # 35 SQLAlchemy models (async, UUID PKs, soft-delete-ready) + enums + associations
│   ├── schemas/              # Pydantic request/response models, grouped by domain
│   ├── crud/                 # CRUDBase — generic async list/get/create/update/delete
│   ├── routers/               # FastAPI routers, one per resource + aggregator (routers/__init__.py)
│   ├── services/               # email_service (reusable business logic)
│   ├── utils/                   # responses, pagination, router_factory, uploads
│   ├── seeders/                  # seed.py — creates super admin + reference data
│   └── main.py                    # FastAPI app: middleware, exception handlers, router mounting
├── alembic/                 # migration environment (async-aware env.py)
├── docker/
│   ├── Dockerfile
│   ├── docker-compose.yml   # api + postgres + redis + nginx
│   └── nginx.conf
├── tests/                    # pytest + httpx smoke tests
├── .github/workflows/deploy.yml   # CI: test → build image → deploy over SSH
├── uploads/                  # local file storage (gitignored, mounted volume in Docker)
├── logs/                      # rotating file logs (error.log, combined.log)
├── requirements.txt
├── alembic.ini
└── .env.example
```

### Why this shape
- **`CRUDBase`** (`app/crud/base.py`) is the async equivalent of a Node.js `crudFactory` —
  generic list/get/create/update/delete against any SQLAlchemy model, with pagination,
  sorting, search, and filters built in.
- **`build_crud_router`** (`app/utils/router_factory.py`) is the equivalent of a Node.js
  `routeFactory` — generates a full REST router (GET list/one, POST, PUT, DELETE) for simple
  CMS resources (Categories, Services, Industries, Technologies, Case Studies, Portfolio,
  Testimonials, Partners, Awards, FAQs, Gallery, Downloads, Events, Meetings, Roles,
  Permissions) so those 15+ modules share one audited implementation.
- **Custom routers** handle anything with real logic: Auth, Users, Employees (self-service
  portal: check-in/out, leave, timesheets, payslips), Clients (self-service portal: projects,
  invoices, tickets), Projects/Tasks, Finance (invoices/payments), Careers (public apply with
  resume upload), Contact, Blog (slug/publish workflow + comments), Tickets (support desk +
  reply thread), Dashboard analytics.
- **`app/models/__init__.py`** imports every model so SQLAlchemy's mapper registry and
  string-based `relationship()` references resolve correctly, and so Alembic sees the full
  schema when autogenerating migrations.

---

## 3. Authentication

Authentication is **100% CoreFusion-owned** — no external identity provider
(Supabase Auth, Auth0, Firebase, etc.) is consulted anywhere, in any
environment. `app/models/user.py` stores the Argon2id `password_hash`
directly; `app/services/auth_service.py` owns every session/account-security
decision.

- **Sessions** are opaque, random, database-backed tokens (`user_sessions`
  table) — not JWTs — set as httpOnly cookies (`cf_access_token` /
  `cf_refresh_token`) plus a non-httpOnly CSRF cookie (`cf_csrf_token`,
  enforced by `CSRFMiddleware` via the `X-CSRF-Token` header on
  state-changing requests). Tokens never appear in response bodies.
- **Passwords** are hashed with Argon2id (`app/core/password.py`).
- **Refresh-token rotation with reuse detection**: `POST /auth/refresh`
  rotates both tokens on a session row; presenting an already-rotated-away
  refresh token is treated as a theft signal and immediately revokes the
  whole session, rather than issuing new tokens.
- **Account lockout**: 5 failed login attempts locks the account for 15
  minutes (auto-expires; `is_account_locked()` in `auth_service.py`).
- **Login timing** is constant-time regardless of whether the email exists
  (a dummy Argon2id hash is always verified against), and forgot-password /
  resend-verification return an identical generic response either way —
  both defenses against account enumeration.
- **Email verification**, **password reset**, and **change password** all
  issue single-use, hashed, expiring tokens (`email_verification_tokens` /
  `password_reset_tokens` tables) — see the endpoint list below.
- **MFA/2FA (TOTP)** and **OAuth (Google, GitHub)** are both fully
  implemented — production-usable, not stubs — but **OFF by default**
  (`MFA_ENABLED=false` / `OAUTH_ENABLED=false`). Turning either on is a
  `.env`-only change (see `.env.example`); OAuth additionally needs each
  provider's own client credentials set before that provider's routes
  become active. See `docs/BACKEND_GAPS_AND_ISSUES.md` §4e for the full
  implementation/verification writeup.

### Where the database lives
The **database** (plain Postgres, no relation to auth) differs by
environment:
- **Local development** — a local Postgres container
  (`docker-compose.override.yml`).
- **Staging / production** — optionally a Supabase-hosted Postgres instance
  (`backend/.env.staging`'s `DB_HOST`), used purely as a hosted Postgres
  server. Supabase is never involved in authentication, sessions, or
  credential storage — swapping it for any other Postgres host requires no
  code change, only `DB_*` env vars.

### Setup
1. For **local dev**, `backend/.env`'s `DB_*` values just need to match
   `docker-compose.override.yml`'s local Postgres container — the defaults
   already do.
   For **staging** against a Supabase-hosted Postgres, `backend/.env.staging`'s
   `DB_HOST` / `DB_PORT` / `DB_PASS` come from **Project Settings → Database**
   in the Supabase dashboard (user is `postgres`, db name is `postgres` unless
   you changed it). Use the direct connection (port `5432`) for a
   long-running server like this one; behind a serverless platform, use the
   **Transaction pooler** host/port `6543` instead and set
   `DB_USE_PGBOUNCER=true`.
2. Run migrations with `bash scripts/migrate.sh local`, `staging`, or `both`
   (see "Getting Started" below) — this creates all of this app's tables,
   including `users`, `user_sessions`, `password_reset_tokens`,
   `email_verification_tokens`.
3. `python -m app.seeders.seed` creates the super admin and reference
   accounts directly in this app's own `users` table (Argon2id-hashed
   passwords) — no external provider involved.

---

## 4. Module Coverage (mapped from the Content Pack)

| Content Pack Section | Implementation |
|---|---|
| Services / Industries / Technologies / Portfolio / Case Studies / Projects | `services`, `industries`, `technologies`, `portfolio`, `case-studies`, `projects` routers |
| Careers | `careers` router (public listing + apply with resume upload, HR admin management) |
| Blog | `blogs` router (categories, comments, publish workflow) |
| Events / Gallery / Awards / Downloads / FAQ | dedicated CRUD routers, public-read |
| Contact | `contact` router (public form + SMTP notification + admin inbox) |
| Client Portal | `clients/me/*` — profile, projects, invoices, support tickets |
| Employee Portal | `employees/me/*` — profile, attendance, leave, timesheets, payslips |
| Admin Panel / Dashboard | `dashboard` router — KPIs, project status breakdown |
| User Roles / Database (Users, Roles, Permissions) | `users`, `access-control/roles`, `access-control/permissions` |
| Security (JWT, RBAC, rate limiting, audit logs) | `core/dependencies.py` (`require_roles`), slowapi, `audit-logs` |
| Performance (caching) | `core/redis` connection ready for use in services |
| Deployment (Docker, Nginx, GitHub Actions, PostgreSQL, Redis) | `docker/` + `.github/workflows/deploy.yml` |

---

## 5. Getting Started

The fastest path is Docker (below) — it brings up local Postgres + Redis for
you. To run the backend directly on the host instead:

```bash
# 1. Create a virtual environment and install dependencies
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 2. Configure environment
cp .env.example .env
# DB_* defaults already match docker-compose.override.yml's local Postgres.
# BREVO_API_KEY is required for real email sending (registration/password
# reset/etc. otherwise just log-and-skip). STORAGE_BACKEND=local needs no
# further setup; STORAGE_BACKEND=s3 needs the local MinIO container (below).

# 3. Start local Postgres + Redis + MinIO (still via Docker, just the dependencies)
docker compose up -d postgres redis minio

# 4. Apply migrations against local Postgres
bash scripts/migrate.sh local

# 5. Run the dev server
uvicorn app.main:app --reload

# 6. Seed a super admin + reference data (local Argon2id-hashed accounts)
python -m app.seeders.seed
```

### Migrations: local vs. staging
`backend/scripts/migrate.sh` runs Alembic against either environment's `.env`
file, via the `ENV_FILE` mechanism in `app/core/config.py` (not bash
`source`-ing, which breaks on values containing bash-special characters like
`BREVO_SENDER_NAME`'s spaces or a `Name <email>`-shaped value):
```bash
bash scripts/migrate.sh local              # local Postgres container
bash scripts/migrate.sh staging            # staging Postgres (.env.staging)
bash scripts/migrate.sh both               # both, in sequence — use after generating a new revision
bash scripts/migrate.sh local downgrade -1 # extra args pass through to alembic
```

Interactive API docs: `http://localhost:8000/docs` (Swagger) or `/redoc`.

Default seeded accounts (change immediately in production):
```
Super Admin:
email: superadmin@corefusiontech.com
password: SuperAdmin@123

Admin:
email: admin@corefusiontech.com
password: Admin@123
```

### Running with Docker

The compose files live at the repo root (`F:\ADP\corefusion\CF-main`), not
under `backend/`, so this stack can bring up `backend` + `frontend` + `redis`
+ a local `postgres` + a local `minio` together.

**Local dev** (default — `docker-compose.yml` + the auto-loaded
`docker-compose.override.yml`, which adds the local Postgres and MinIO
containers):
```bash
cp backend/.env.example backend/.env
docker compose up -d postgres redis minio
docker compose run --rm backend alembic upgrade head   # first-time schema setup
docker compose up -d backend frontend
```
API available at `http://localhost:8000`.

**Staging** (explicit `-f`, uses `backend/.env.staging` — optionally a
Supabase-hosted Postgres as the database layer only, no local `postgres`
service):
```bash
cp backend/.env.staging.example backend/.env.staging   # fill in staging DB_* values
docker compose -f docker-compose.yml -f docker-compose.staging.yml run --rm backend alembic upgrade head
docker compose -f docker-compose.yml -f docker-compose.staging.yml up -d backend frontend
```

### Pairing with the CoreFusion frontend

This backend is designed to pair with the CoreFusion frontend (Vite/React).
If you're using the combined `corefusion-platform` monorepo, it's the sibling
`../frontend` folder and its dev server proxies straight to `uvicorn` on
`:8000` — no CORS setup is needed for local dev. Just run both:

```bash
# terminal 1
uvicorn app.main:app --reload

# terminal 2 (in ../frontend/)
npm run dev
```

`app/main.py`'s CORS middleware also explicitly allows `http://localhost:5173`
(Vite's default port) as a fallback for non-proxied requests. See the
frontend's README ("Connecting to the Backend") for the full picture.

---

## 6. API Conventions

- Base URL: `/api/v1`
- Auth: httpOnly `cf_access_token` / `cf_refresh_token` cookies, set by
  `POST /api/v1/auth/login`. State-changing requests also require the
  `X-CSRF-Token` header to match the non-httpOnly `cf_csrf_token` cookie
  (double-submit CSRF pattern, `CSRFMiddleware`).
- Responses: `{ success, status_code, message, data, meta? }`
- Pagination: `?page=1&limit=20&sort=-created_at&search=keyword`
- Errors: `{ success: false, status_code, message, errors?: [{field, message}] }`

### Key endpoints
```
POST   /api/v1/auth/register
POST   /api/v1/auth/login
POST   /api/v1/auth/refresh
POST   /api/v1/auth/logout
POST   /api/v1/auth/logout-all
GET    /api/v1/auth/me
POST   /api/v1/auth/forgot-password
POST   /api/v1/auth/reset-password
POST   /api/v1/auth/verify-email
POST   /api/v1/auth/resend-verification
POST   /api/v1/auth/change-password
GET    /api/v1/auth/sessions
DELETE /api/v1/auth/sessions/{session_id}

# MFA/2FA — 404 unless MFA_ENABLED=true (see .env.example)
GET    /api/v1/auth/mfa/status
POST   /api/v1/auth/mfa/setup
POST   /api/v1/auth/mfa/enable
POST   /api/v1/auth/mfa/disable
POST   /api/v1/auth/mfa/verify-login
POST   /api/v1/auth/mfa/backup-codes/regenerate

# OAuth — 404 unless OAUTH_ENABLED=true AND that provider's credentials are set
GET    /api/v1/auth/oauth/{provider}/login       (provider: google | github)
GET    /api/v1/auth/oauth/{provider}/callback

GET    /api/v1/projects                    (public: published only)
GET    /api/v1/services
GET    /api/v1/careers
POST   /api/v1/careers/{career_id}/apply    (multipart/form-data, field "resume")
POST   /api/v1/contact

GET    /api/v1/employees/me/profile         (Employee Portal, auth required)
GET    /api/v1/clients/me/projects          (Client Portal, auth required)
GET    /api/v1/dashboard/overview           (Admin Panel, admin/PM/finance/sales only)
```

---

## 7. Security Notes for Production
- Put the API behind HTTPS (terminate TLS at Nginx/load balancer) — cookies are marked `Secure` and rely on this.
- Swap local disk uploads (`app/utils/uploads.py`) for S3/GCS.
- Run `alembic upgrade head` on deploy instead of relying on ad-hoc table creation.
- Rotate the default seeded admin password immediately.
- MFA/2FA and OAuth are implemented but off by default — turn on with `MFA_ENABLED`/`OAUTH_ENABLED` in `.env` when the product is ready for them; `MFA_ENCRYPTION_KEY` must be a real Fernet key before `MFA_ENABLED=true` (see `.env.example`).
- Gunicorn worker count in `docker/Dockerfile` should scale with CPU cores (`2 * cores + 1`).

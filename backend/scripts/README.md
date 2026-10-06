# Backend Scripts

Operational scripts for local/dev database and environment setup. None of these run
automatically — invoke them manually when you need them.

## `seed_users.py`

Creates the demo accounts (one per role: super admin, admin, and every employee-family
role — sales, HR, marketing, project manager, developer, QA, support, finance), the
standard department list, default public settings, and some sample analytics page-view
data. Then writes a plaintext credentials sheet to `CREDENTIALS.local.md` in this folder.

```bash
cd backend
# database must be reachable — e.g. docker compose up -d postgres
python scripts/seed_users.py
```

Safe to re-run: it skips any account/department that already exists. `CREDENTIALS.local.md`
is only (re)written when the run actually created new accounts, since passwords are
randomly generated per run and there is no way to recover a password for an account that
already existed from a previous run.

Refuses to run at all when `ENV=production` — this is demo data with well-known emails,
not something you want anywhere near a real deployment.

The actual seeding logic lives in `app/seeders/seed.py` (single source of truth for what
gets created) — this script is a thin wrapper around it plus the markdown formatting step.
If you need to add another seeded account or department, edit `seed.py`, not this file.

## `reset_demo_passwords.py`

Sets a known, fixed password on each of the standard demo accounts, regardless of whether
they already existed — unlike `seed_users.py`'s credentials sheet, which only captures a
password for accounts it *creates* on that run. Useful when you've inherited a dev database
where some demo accounts were seeded previously with since-forgotten random passwords, and
you want a complete, currently-accurate credentials sheet for all of them at once.

```bash
cd backend
python scripts/reset_demo_passwords.py
```

Also refuses to run when `ENV=production`. Overwrites `CREDENTIALS.local.md` with all 11
demo accounts' current (fixed, documented) passwords.

## `CREDENTIALS.local.md`

Generated output, not checked in (see `.gitignore`). Lists every seeded account's role,
department, email, and password in a table. Treat it like any other secret: don't paste it
into chat, tickets, or commit messages. Delete or rotate the passwords before using this
stack for anything beyond local development.

## `migrate.sh`

Runs `alembic upgrade head` (or any other alembic command) against a named environment's
`.env` file.

```bash
bash scripts/migrate.sh local              # local Postgres container (docker-compose.override.yml)
bash scripts/migrate.sh staging            # Supabase staging Postgres (backend/.env.staging)
bash scripts/migrate.sh both               # local, then staging
bash scripts/migrate.sh local downgrade -1 # extra args pass through to alembic
```

Sets `ENV_FILE` and lets pydantic-settings' real dotenv parser load it, rather than
`source`-ing the `.env` file in bash (`.env` syntax isn't bash syntax — e.g. an SMTP
`Name <email>` value breaks bash's `<` redirection).

## `generate_migration.py`

Runs `alembic revision --autogenerate` against whatever database is configured in
`backend/.env`. Requires a reachable Postgres with the schema already applied (even if
empty) so Alembic can diff against it.

```bash
cd backend
python scripts/generate_migration.py
```

## `backup_restore_drill.sh`

Reproducible, disposable pg_dump/pg_restore verification drill — proves the backup/restore
*mechanism* end-to-end against throwaway local Postgres containers (production backups
themselves are managed by Supabase/the hosting platform, which this repo has no
credentials to touch directly). Confirms: a real logical backup can be taken, it restores
cleanly into a separate empty database, row/index counts match, and the app can actually
query the restored database.

```bash
bash scripts/backup_restore_drill.sh
```

Requires Docker running locally. Cleans up its own containers and dump file on exit.

## `repro_login.py`

Legacy diagnostic script from the pre-migration Supabase Auth era (imports
`app.services.supabase_client`). Authentication is now fully CoreFusion-owned
(`app/services/auth_service.py`) — this script does not exercise the current auth path and
is kept only as a historical reference. Prefer testing login against `POST /api/v1/auth/login`
directly (or the E2E suite in `frontend/e2e/`) for anything current.

## `migrations/`

Empty scratch directory; not currently used by any script above.

"""
Seed public-facing CMS content (services, solutions, industries,
technologies, products, projects, case studies, portfolio, testimonials,
partners, awards, blogs, careers, downloads, resources, FAQs, events,
gallery, key page copy, business-stat settings) so a fresh install has
something real to show on the public website and admin CMS.

Thin wrapper — all seeding logic lives in app/seeders/cms_seed.py (single
source of truth, content sourced from docs/requirments/WEBSITE MASTER
CONTENT PACK.pdf where the PRD gives concrete copy). This script is a
discoverable entry point plus nothing else.

This is LINKED to the user auto-seeder (app/seeders/seed.py): it reuses
those demo users as blog authors / project managers, and refuses to run
until they exist. Run order on a fresh DB:

    cd backend
    alembic upgrade head
    python scripts/migrations/002_seed_users.py
    python scripts/migrations/003_cms_data.py

Safe to re-run: every row is get-or-create by natural key (slug/name/etc),
so re-running only fills in what's missing. Each run also writes a single
audit_logs entry (action="cms.bootstrap_seed") recording what was created,
attributed to the seeded super admin account, so there's a clear record of
when demo CMS content was bootstrapped into this database.
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.seeders import cms_seed  # noqa: E402

if __name__ == "__main__":
    asyncio.run(cms_seed.run())

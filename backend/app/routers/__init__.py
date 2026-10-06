from fastapi import APIRouter

from app.routers import (
    # Phase 2
    analytics,
    announcement,
    audit_log,
    auth,
    award,
    # Phase 5 — CMS/ops modules with models+schemas already defined but
    # never wired to a router (found during the production-readiness audit)
    backups,
    blog,
    career,
    case_study,
    category,
    clients,
    comment,
    contact,
    # Phase 3 �?" Sales CRM
    contracts,
    dashboard,
    # Phase 4 🡺 Super Admin
    department,
    download,
    employees,
    event,
    faq,
    finance,
    gallery,
    gdpr,
    industry,
    leadership,
    leads,
    media,
    meetings,
    newsletter,
    notification,
    oauth,
    office,
    page_content,
    partner,
    # Phase 6 — Partner Portal
    partner_account,
    portfolio,
    product,
    projects,
    proposals,
    reports,
    resource,
    role,
    seo,
    service,
    settings,
    site_content,
    solution,
    stats,
    task,
    technology,
    testimonial,
    ticket,
    training,
    users,
)

api_router = APIRouter()

api_router.include_router(auth.router)
api_router.include_router(oauth.router)
api_router.include_router(users.router)
api_router.include_router(gdpr.router)
api_router.include_router(stats.router)
api_router.include_router(employees.router)
api_router.include_router(clients.router)
api_router.include_router(projects.router)
api_router.include_router(task.router)
api_router.include_router(finance.router)
api_router.include_router(career.router)
api_router.include_router(contact.router)
api_router.include_router(blog.router)
api_router.include_router(service.router)
api_router.include_router(case_study.router)
api_router.include_router(testimonial.router)
api_router.include_router(download.router)
api_router.include_router(event.router)
api_router.include_router(ticket.router)
api_router.include_router(award.router)
api_router.include_router(announcement.router)
api_router.include_router(category.router)
api_router.include_router(faq.router)
api_router.include_router(gallery.router)
api_router.include_router(industry.router)
api_router.include_router(partner.router)
api_router.include_router(portfolio.router)
api_router.include_router(product.router)
api_router.include_router(resource.router)
api_router.include_router(technology.router)
api_router.include_router(notification.router)
api_router.include_router(media.router)
api_router.include_router(audit_log.router)
api_router.include_router(dashboard.router)
api_router.include_router(role.router)

# Phase 2
api_router.include_router(solution.router)
api_router.include_router(training.router)
api_router.include_router(analytics.router)
api_router.include_router(reports.router)

# Phase 3 — Sales CRM
api_router.include_router(leads.router)
api_router.include_router(proposals.router)
api_router.include_router(contracts.router)
api_router.include_router(meetings.router)

# Phase 4 — Super Admin
api_router.include_router(department.router)

# Phase 5 — CMS/ops modules (SEO, Settings, Newsletter, Comments, Page Content,
# Backups) — models and schemas already existed; only the router wiring was missing.
api_router.include_router(seo.router)
api_router.include_router(settings.router)
api_router.include_router(newsletter.router)
api_router.include_router(comment.router)
api_router.include_router(page_content.router)
api_router.include_router(backups.router)

# Phase 6 — Partner Portal (login-gated self-service, mirrors Client Portal's
# shape) — distinct from the pre-existing public `/partners` CMS listing.
api_router.include_router(partner_account.router)

# Phase 7 — About/Company CMS: makes data/about.js + data/company.js
# (previously hardcoded frontend constants) admin-editable.
api_router.include_router(leadership.router)
api_router.include_router(office.router)
api_router.include_router(site_content.router)

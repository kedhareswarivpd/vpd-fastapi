"""
Seeds the public-facing CMS content a fresh install needs to actually show
something on the website — services, solutions, industries, technologies,
products, projects, case studies, portfolio, testimonials, partners, awards,
blogs, careers, downloads, resources, FAQs, events, gallery, key page copy,
and business-stat settings.

Single source of truth for CONTENT is docs/requirments/WEBSITE MASTER CONTENT
PACK.pdf: the company profile, vision, mission, core values, why-choose-us,
business statistics, industries list, and services list below are transcribed
from that document. Where the PRD names a page/section but gives no concrete
copy (blog articles, testimonials, partner names, awards, careers, downloads,
sample projects, images), this module fills it with clearly-fictional but
realistic placeholder content — safe to publish on a local/demo instance,
meant to be replaced with real content before any production launch. Partner
and testimonial company names are deliberately invented (not real companies)
to avoid implying business relationships that don't exist.

Images are hot-linked from Unsplash's CDN (images.unsplash.com) by photo ID —
no binary assets are stored in this repo.

This module is LINKED to app/seeders/seed.py (the user auto-seeder): it
reuses the demo users that script creates (as blog authors / project
managers) and refuses to run until that seed has been applied, rather than
creating its own duplicate set of users. Run order on a fresh DB:

    1. alembic upgrade head
    2. python scripts/migrations/002_seed_users.py   (users, departments)
    3. python scripts/migrations/003_cms_data.py      (this module)

Every seed_* function is idempotent (get-or-create by natural key), so
re-running is safe and only fills in what's missing.
"""
import asyncio
import uuid
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import log_audit
from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models.award import Award
from app.models.blog import Blog
from app.models.career import Career
from app.models.case_study import CaseStudy
from app.models.category import Category
from app.models.download import Download
from app.models.enums import (
    BlogStatus,
    CareerEmploymentType,
    CareerStatus,
    CategoryType,
    PartnerType,
    ProjectStatus,
    TechnologyCategory,
)
from app.models.event import Event
from app.models.faq import Faq
from app.models.gallery import Gallery
from app.models.industry import Industry
from app.models.leadership import Leadership
from app.models.office import Office
from app.models.page_content import PageContent
from app.models.partner import Partner
from app.models.portfolio import Portfolio
from app.models.product import Product
from app.models.project import Project
from app.models.resource import Resource
from app.models.service import Service
from app.models.setting import Setting
from app.models.solution import Solution
from app.models.technology import Technology
from app.models.testimonial import Testimonial
from app.models.user import User
from app.seeders import seed as user_seed

_counts: dict[str, int] = {}


def _unsplash(photo_id: str, w: int = 1200, h: int = 800) -> str:
    return f"https://images.unsplash.com/photo-{photo_id}?auto=format&fit=crop&w={w}&h={h}&q=80"


async def _get_or_create(db: AsyncSession, model, lookup: dict, defaults: dict | None = None):
    existing = (await db.execute(select(model).filter_by(**lookup))).scalar_one_or_none()
    if existing:
        return existing, False
    obj = model(**lookup, **(defaults or {}))
    db.add(obj)
    await db.flush()
    _counts[model.__tablename__] = _counts.get(model.__tablename__, 0) + 1
    return obj, True


def _slugify(text: str) -> str:
    return text.lower().replace("&", "and").replace("/", "-").replace(" ", "-").replace("--", "-")


# ---------------------------------------------------------------------------
# Industries — PRD "INDUSTRIES" list (16), one paragraph description + a
# thematically matched Unsplash cover image each.
# ---------------------------------------------------------------------------
INDUSTRIES = [
    ("Healthcare", "1576091160399-112ba8d25d1d", "hospital systems, patient portals and health-tech platforms"),
    ("Finance", "1554224155-6726b3ff858f", "core banking, fintech and financial services"),
    ("Education", "1523240795612-9a054b0db644", "e-learning platforms and academic institutions"),
    ("Retail", "1441986300917-64674bd600d8", "e-commerce and omnichannel retail experiences"),
    ("Manufacturing", "1565043666747-69f6646db940", "smart factories and industrial automation"),
    ("Logistics", "1601584115197-04ecc0da31d7", "supply chain, fleet and warehouse management"),
    ("Construction", "1541888946425-d81bb19240f5", "project, site and resource management"),
    ("Real Estate", "1560518883-ce09059eeffa", "property management and PropTech platforms"),
    ("Hospitality", "1566073771259-6a8506099945", "hotels, travel and guest-experience technology"),
    ("Government", "1541872703-74c5e44368f9", "public-sector digital services and e-governance"),
    ("Insurance", "1450101499163-c8848c66ca85", "InsurTech, underwriting and claims automation"),
    ("Energy", "1466611653911-95081537e5b7", "utilities, renewables and energy monitoring"),
    ("Telecom", "1521185496955-15097b20c5fe", "network operations and telecom billing systems"),
    ("Pharma", "1584362917165-526a968579e8", "drug research, trials and pharma compliance"),
    ("Automotive", "1492144534655-ae79c964c9d7", "connected vehicles and dealer platforms"),
    ("Media", "1495020689067-958852a7765e", "streaming, publishing and digital content platforms"),
]


async def seed_industries(db: AsyncSession) -> dict[str, Industry]:
    result = {}
    for name, photo_id, focus in INDUSTRIES:
        industry, _ = await _get_or_create(
            db, Industry, {"slug": _slugify(name)},
            {
                "name": name,
                "icon": "building-office",
                "description": f"Digital transformation and enterprise software built for {focus}.",
                "cover_image": _unsplash(photo_id),
                "is_published": True,
            },
        )
        result[name] = industry
    print(f"Industries seeded ({len(INDUSTRIES)})")
    return result


# ---------------------------------------------------------------------------
# Categories — blog/gallery/download/event taxonomies used elsewhere below.
# ---------------------------------------------------------------------------
BLOG_CATEGORY_NAMES = [
    "Technology", "Artificial Intelligence", "Cloud Computing",
    "Cyber Security", "Company News", "Case Studies",
]


async def seed_categories(db: AsyncSession) -> dict[str, Category]:
    result = {}
    for name in BLOG_CATEGORY_NAMES:
        cat, _ = await _get_or_create(
            db, Category, {"slug": _slugify(name)},
            {"name": name, "type": CategoryType.blog},
        )
        result[name] = cat
    print(f"Blog categories seeded ({len(BLOG_CATEGORY_NAMES)})")
    return result


# ---------------------------------------------------------------------------
# Services — PRD "SERVICES" list (20). Each follows the PRD's "every service
# contains" structure: overview, business problems, solutions, features,
# benefits, process, technology stack, deliverables, industries, gallery, FAQs.
# ---------------------------------------------------------------------------
_PROCESS_STEPS = [
    {"step": 1, "title": "Discovery", "description": "Requirements, stakeholder interviews and technical audit."},
    {"step": 2, "title": "Design", "description": "Architecture, UX and solution design sign-off."},
    {"step": 3, "title": "Development", "description": "Agile sprints with continuous stakeholder demos."},
    {"step": 4, "title": "Testing", "description": "Functional, performance and security QA cycles."},
    {"step": 5, "title": "Deployment", "description": "Production rollout with a staged release plan."},
    {"step": 6, "title": "Support", "description": "Post-launch monitoring, maintenance and enhancements."},
]

SERVICES = [
    {"name": "Enterprise Software", "overview": "Custom enterprise-grade applications built to run core business operations at scale.",
     "problems": "Legacy systems that can't scale, disconnected departments, and manual processes slowing growth.",
     "solutions": "Modular, API-first enterprise applications tailored to your workflows and integrated with existing systems.",
     "features": ["Modular architecture", "Role-based access control", "Real-time reporting", "Third-party integrations"],
     "benefits": ["Faster operations", "Lower total cost of ownership", "Improved data visibility", "Easier scaling"],
     "stack": ["Python", "FastAPI", "PostgreSQL", "React"], "deliverables": ["Working software", "Technical documentation", "Deployment pipeline"],
     "industries": ["Manufacturing", "Finance", "Retail"]},
    {"name": "Custom Software", "overview": "Bespoke software built end-to-end around a business's exact requirements.",
     "problems": "Off-the-shelf tools that force process compromises and don't fit unique workflows.",
     "solutions": "Requirement-driven custom builds, from architecture through long-term support.",
     "features": ["Tailored workflows", "Custom integrations", "Scalable architecture", "Ongoing iteration"],
     "benefits": ["Perfect process fit", "Competitive differentiation", "Full ownership of the codebase", "No vendor lock-in"],
     "stack": ["Node.js", "TypeScript", "PostgreSQL", "Docker"], "deliverables": ["Custom application", "Source code ownership", "Documentation"],
     "industries": ["Logistics", "Healthcare", "Education"]},
    {"name": "ERP", "overview": "Enterprise Resource Planning systems that unify finance, inventory, HR and operations.",
     "problems": "Siloed spreadsheets and disconnected departmental tools causing data drift and duplicate work.",
     "solutions": "A single ERP backbone with modular finance, inventory, procurement and HR components.",
     "features": ["Unified finance & inventory", "Procurement workflows", "HR & payroll module", "Configurable dashboards"],
     "benefits": ["Single source of truth", "Reduced manual reconciliation", "Faster month-end close", "Better forecasting"],
     "stack": ["Python", "PostgreSQL", "Redis", "React"], "deliverables": ["ERP platform", "Data migration", "Training material"],
     "industries": ["Manufacturing", "Construction", "Retail"]},
    {"name": "CRM", "overview": "Customer Relationship Management platforms that unify sales, support and marketing.",
     "problems": "Leads falling through the cracks and no single view of the customer across teams.",
     "solutions": "A CRM tailored to your sales pipeline with marketing and support built in.",
     "features": ["Pipeline management", "Lead scoring", "Email & campaign tools", "Support ticketing"],
     "benefits": ["Higher conversion rates", "Shorter sales cycles", "Better customer retention", "Unified customer view"],
     "stack": ["FastAPI", "PostgreSQL", "React", "Redis"], "deliverables": ["CRM platform", "Data import", "Team onboarding"],
     "industries": ["Retail", "Insurance", "Real Estate"]},
    {"name": "Cloud Migration", "overview": "Moving on-premise systems to the cloud with minimal downtime and risk.",
     "problems": "Aging on-premise infrastructure with rising maintenance costs and limited scalability.",
     "solutions": "A phased migration plan — lift-and-shift or re-architecture — matched to business risk tolerance.",
     "features": ["Migration assessment", "Phased cutover plan", "Data migration tooling", "Rollback strategy"],
     "benefits": ["Lower infrastructure cost", "Elastic scaling", "Improved uptime", "Reduced ops burden"],
     "stack": ["AWS", "Terraform", "Docker", "Kubernetes"], "deliverables": ["Migration runbook", "Migrated workloads", "Cost report"],
     "industries": ["Finance", "Healthcare", "Telecom"]},
    {"name": "Cloud Infrastructure", "overview": "Designing and managing secure, scalable cloud infrastructure.",
     "problems": "Over-provisioned, unmonitored, or insecure cloud environments driving up cost and risk.",
     "solutions": "Infrastructure-as-code environments with autoscaling, monitoring and cost controls built in.",
     "features": ["Infrastructure as code", "Autoscaling", "Cost monitoring", "Disaster recovery"],
     "benefits": ["Predictable costs", "High availability", "Faster provisioning", "Stronger security posture"],
     "stack": ["AWS", "Azure", "Terraform", "Kubernetes"], "deliverables": ["IaC repository", "Monitoring dashboards", "Runbooks"],
     "industries": ["Telecom", "Energy", "Media"]},
    {"name": "AI Solutions", "overview": "Applied AI systems that automate decisions and unlock new capabilities.",
     "problems": "Manual, repetitive decision-making that doesn't scale with business volume.",
     "solutions": "Purpose-built AI models integrated directly into existing business workflows.",
     "features": ["Custom model development", "Model monitoring", "API-first deployment", "Human-in-the-loop review"],
     "benefits": ["Faster decisions", "Reduced manual effort", "New product capabilities", "Continuous improvement"],
     "stack": ["Python", "TensorFlow", "PyTorch", "FastAPI"], "deliverables": ["Trained model", "Inference API", "Evaluation report"],
     "industries": ["Healthcare", "Finance", "Insurance"]},
    {"name": "Machine Learning", "overview": "Predictive and classification models trained on your business data.",
     "problems": "Untapped historical data that could predict churn, demand or risk but currently sits idle.",
     "solutions": "End-to-end ML pipelines from data prep through production deployment.",
     "features": ["Feature engineering", "Model training pipelines", "A/B evaluation", "Production monitoring"],
     "benefits": ["Better forecasting", "Reduced churn", "Data-driven pricing", "Continuous learning"],
     "stack": ["Python", "scikit-learn", "TensorFlow", "PostgreSQL"], "deliverables": ["ML pipeline", "Model artifacts", "Documentation"],
     "industries": ["Retail", "Insurance", "Manufacturing"]},
    {"name": "Data Analytics", "overview": "Turning raw operational data into decision-ready insight.",
     "problems": "Data scattered across systems with no consistent reporting layer.",
     "solutions": "Centralized data pipelines feeding governed, self-serve analytics dashboards.",
     "features": ["ETL pipelines", "Data warehouse design", "Self-serve dashboards", "Data governance"],
     "benefits": ["Faster reporting", "Consistent metrics", "Self-serve insight", "Better data trust"],
     "stack": ["Python", "PostgreSQL", "Airflow", "Redis"], "deliverables": ["Data pipeline", "Dashboards", "Data dictionary"],
     "industries": ["Retail", "Finance", "Logistics"]},
    {"name": "Business Intelligence", "overview": "Executive dashboards and reporting that turn data into decisions.",
     "problems": "Leadership relying on stale, manually assembled spreadsheets for critical decisions.",
     "solutions": "Live BI dashboards pulling directly from operational systems.",
     "features": ["Executive dashboards", "Drill-down reporting", "Automated alerts", "Role-based views"],
     "benefits": ["Real-time visibility", "Faster decisions", "Reduced manual reporting", "Single source of truth"],
     "stack": ["Python", "PostgreSQL", "React", "Redis"], "deliverables": ["BI dashboards", "Data models", "Training session"],
     "industries": ["Finance", "Retail", "Manufacturing"]},
    {"name": "Cyber Security", "overview": "Securing enterprise systems against modern threats.",
     "problems": "Growing attack surface, compliance pressure, and limited in-house security expertise.",
     "solutions": "Security assessments, hardening, and continuous monitoring aligned to compliance frameworks.",
     "features": ["Vulnerability assessment", "Penetration testing", "SOC monitoring", "Compliance audits"],
     "benefits": ["Reduced breach risk", "Regulatory compliance", "Faster incident response", "Customer trust"],
     "stack": ["OWASP tooling", "SIEM", "AWS Security Hub", "Vault"], "deliverables": ["Security audit report", "Remediation plan", "Runbooks"],
     "industries": ["Finance", "Government", "Healthcare"]},
    {"name": "DevOps", "overview": "CI/CD pipelines and infrastructure automation for faster, safer releases.",
     "problems": "Slow, manual, error-prone deployments blocking release velocity.",
     "solutions": "Automated CI/CD pipelines with infrastructure as code and observability built in.",
     "features": ["CI/CD pipelines", "Infrastructure as code", "Automated testing gates", "Observability"],
     "benefits": ["Faster releases", "Fewer production incidents", "Reproducible environments", "Lower ops overhead"],
     "stack": ["Docker", "Kubernetes", "GitHub Actions", "Terraform"], "deliverables": ["CI/CD pipeline", "IaC repository", "Runbooks"],
     "industries": ["Technology", "Telecom", "Media"]},
    {"name": "Web Development", "overview": "High-performance, responsive web applications and marketing sites.",
     "problems": "Slow, outdated websites that don't convert visitors or scale with traffic.",
     "solutions": "Modern, SEO-ready, responsive web applications built for performance.",
     "features": ["Responsive design", "SEO optimization", "CMS integration", "Performance tuning"],
     "benefits": ["Higher conversion", "Better search ranking", "Faster load times", "Easy content updates"],
     "stack": ["React", "Next.js", "Node.js", "PostgreSQL"], "deliverables": ["Web application", "CMS setup", "Performance report"],
     "industries": ["Retail", "Media", "Hospitality"]},
    {"name": "Mobile Apps", "overview": "Native and cross-platform mobile applications for iOS and Android.",
     "problems": "No mobile presence, or an app that's slow, buggy, or expensive to maintain across platforms.",
     "solutions": "Cross-platform mobile apps sharing a single codebase without compromising native feel.",
     "features": ["Cross-platform builds", "Push notifications", "Offline support", "App store deployment"],
     "benefits": ["Single codebase", "Faster time to market", "Lower maintenance cost", "Consistent UX"],
     "stack": ["React Native", "Flutter", "Firebase", "REST APIs"], "deliverables": ["Mobile app", "App store listing", "Analytics setup"],
     "industries": ["Retail", "Logistics", "Hospitality"]},
    {"name": "UI UX", "overview": "User research and interface design that makes complex products usable.",
     "problems": "Confusing interfaces driving support tickets and abandoned workflows.",
     "solutions": "Research-driven UX design and a reusable design system for consistent interfaces.",
     "features": ["User research", "Wireframing & prototyping", "Design systems", "Usability testing"],
     "benefits": ["Higher user satisfaction", "Fewer support tickets", "Faster feature development", "Brand consistency"],
     "stack": ["Figma", "Design tokens", "Storybook", "React"], "deliverables": ["Design system", "Prototypes", "Usability report"],
     "industries": ["Healthcare", "Finance", "Education"]},
    {"name": "QA Testing", "overview": "Manual and automated QA that catches issues before customers do.",
     "problems": "Regressions and bugs reaching production due to inconsistent or manual-only testing.",
     "solutions": "Automated regression suites layered on top of structured manual test cycles.",
     "features": ["Test automation", "Regression suites", "Performance testing", "Bug tracking"],
     "benefits": ["Fewer production bugs", "Faster release cycles", "Higher confidence releases", "Lower support cost"],
     "stack": ["Selenium", "Playwright", "Pytest", "JMeter"], "deliverables": ["Test automation suite", "Test reports", "Bug backlog"],
     "industries": ["Finance", "Healthcare", "Retail"]},
    {"name": "API Development", "overview": "Secure, well-documented APIs that connect systems and enable integrations.",
     "problems": "Point-to-point integrations that break constantly and are impossible to document or scale.",
     "solutions": "Versioned, documented REST/GraphQL APIs with proper auth and rate limiting.",
     "features": ["REST & GraphQL APIs", "OpenAPI documentation", "Rate limiting", "API versioning"],
     "benefits": ["Reliable integrations", "Faster partner onboarding", "Easier maintenance", "Better security"],
     "stack": ["FastAPI", "GraphQL", "PostgreSQL", "Redis"], "deliverables": ["API service", "API documentation", "SDK/examples"],
     "industries": ["Finance", "Retail", "Telecom"]},
    {"name": "IT Consulting", "overview": "Strategic technology advisory to plan modernization and digital initiatives.",
     "problems": "Unclear technology roadmap and competing internal priorities stalling initiatives.",
     "solutions": "An independent technology assessment and a prioritized, realistic execution roadmap.",
     "features": ["Technology audit", "Roadmap planning", "Vendor evaluation", "Architecture review"],
     "benefits": ["Clear priorities", "Reduced technology risk", "Better vendor decisions", "Faster execution"],
     "stack": ["Architecture frameworks", "Cost modeling", "Risk assessment"], "deliverables": ["Assessment report", "Roadmap", "Executive briefing"],
     "industries": ["Manufacturing", "Government", "Construction"]},
    {"name": "Annual Maintenance", "overview": "Ongoing maintenance contracts keeping systems secure, patched and running.",
     "problems": "No dedicated owner for keeping deployed systems patched, monitored and up to date.",
     "solutions": "A structured AMC covering patching, monitoring, backups and periodic health checks.",
     "features": ["Scheduled patching", "Uptime monitoring", "Backup verification", "Quarterly health checks"],
     "benefits": ["Reduced downtime risk", "Predictable maintenance cost", "Longer system lifespan", "Peace of mind"],
     "stack": ["Monitoring stack", "Backup tooling", "Patch management"], "deliverables": ["AMC agreement", "Monthly reports", "Health check reports"],
     "industries": ["Manufacturing", "Retail", "Real Estate"]},
    {"name": "Support", "overview": "24x7 technical support keeping production systems running smoothly.",
     "problems": "No reliable support channel when production issues happen outside business hours.",
     "solutions": "Tiered 24x7 support with defined SLAs and an escalation path to engineering.",
     "features": ["24x7 helpdesk", "Tiered SLAs", "Incident escalation", "Root-cause reporting"],
     "benefits": ["Faster issue resolution", "Predictable SLAs", "Reduced business disruption", "Continuous improvement"],
     "stack": ["Ticketing system", "Monitoring & alerting", "Knowledge base"], "deliverables": ["Support SLA", "Incident reports", "Knowledge base"],
     "industries": ["Finance", "Healthcare", "Telecom"]},
]

_SERVICE_IMAGES = [
    "1522071820081-009f0129c71c", "1460925895917-afdab827c52f", "1531482615713-2afd69097998",
    "1551434678-e076c223a692", "1517245386807-bb43f82c33c4", "1498050108023-c5249f4df085",
]


async def seed_services(db: AsyncSession, industries: dict[str, Industry]) -> list[Service]:
    created = []
    for i, s in enumerate(SERVICES):
        images = [_unsplash(_SERVICE_IMAGES[i % len(_SERVICE_IMAGES)]), _unsplash(_SERVICE_IMAGES[(i + 1) % len(_SERVICE_IMAGES)])]
        faqs = [
            {"question": f"How long does a typical {s['name']} engagement take?",
             "answer": "Most engagements run 6-16 weeks depending on scope, following a phased discovery-to-launch process."},
            {"question": f"Do you provide support after {s['name']} delivery?",
             "answer": "Yes — every engagement includes a handover period, and ongoing support/maintenance can be contracted separately."},
        ]
        service, _ = await _get_or_create(
            db, Service, {"slug": _slugify(s["name"])},
            {
                "name": s["name"], "icon": "sparkles", "overview": s["overview"],
                "business_problems": s["problems"], "solutions": s["solutions"],
                "features": s["features"], "benefits": s["benefits"], "process": _PROCESS_STEPS,
                "technology_stack": s["stack"], "deliverables": s["deliverables"],
                "related_industries": s["industries"], "gallery": images, "faqs": faqs,
                "cover_image": images[0], "is_published": True, "order": i,
            },
        )
        created.append(service)
    print(f"Services seeded ({len(SERVICES)})")
    return created


# ---------------------------------------------------------------------------
# Solutions — cross-cutting offerings drawn from the PRD's company-profile
# industry/technology focus areas (Digital Transformation, Enterprise
# Software, AI, Cloud Computing, Cyber Security, Business Automation).
# ---------------------------------------------------------------------------
SOLUTIONS = [
    {"name": "Digital Transformation", "overview": "End-to-end modernization of legacy processes into connected digital systems.",
     "problem": "Manual, paper-driven processes that slow decisions and frustrate customers.",
     "approach": ["Process audit", "Digital roadmap", "Phased rollout", "Change management"],
     "outcomes": ["Faster processes", "Better customer experience", "Data-driven operations"],
     "industries": ["Manufacturing", "Government", "Retail"], "services": ["Enterprise Software", "Cloud Migration", "IT Consulting"],
     "image": "1497366216548-37526070297c"},
    {"name": "Enterprise Software Modernization", "overview": "Re-architecting monolithic legacy systems into modular, maintainable platforms.",
     "problem": "Legacy monoliths that are expensive to change and risky to scale.",
     "approach": ["Legacy audit", "Modular re-architecture", "Incremental migration", "Team upskilling"],
     "outcomes": ["Lower maintenance cost", "Faster feature delivery", "Reduced technical risk"],
     "industries": ["Finance", "Manufacturing", "Insurance"], "services": ["Enterprise Software", "DevOps", "API Development"],
     "image": "1556761175-5973dc0f32e7"},
    {"name": "AI & Intelligent Automation", "overview": "Applying AI and automation to remove manual bottlenecks from core operations.",
     "problem": "High-volume manual decisions that don't scale with business growth.",
     "approach": ["Process mining", "Model development", "Human-in-the-loop rollout", "Continuous tuning"],
     "outcomes": ["Reduced manual effort", "Faster turnaround", "Higher accuracy"],
     "industries": ["Insurance", "Healthcare", "Finance"], "services": ["AI Solutions", "Machine Learning", "Data Analytics"],
     "image": "1581091226825-a6a2a5aee158"},
    {"name": "Cloud-Native Transformation", "overview": "Rebuilding for the cloud with containerized, autoscaling architectures.",
     "problem": "Infrastructure that can't handle demand spikes or scale cost-effectively.",
     "approach": ["Cloud readiness assessment", "Containerization", "Autoscaling setup", "Cost optimization"],
     "outcomes": ["Elastic scaling", "Lower infrastructure cost", "Higher availability"],
     "industries": ["Telecom", "Media", "Retail"], "services": ["Cloud Migration", "Cloud Infrastructure", "DevOps"],
     "image": "1558494949-ef010cbdcc31"},
    {"name": "Cybersecurity & Risk Management", "overview": "Building a defensible security posture across applications and infrastructure.",
     "problem": "Rising threat exposure without a structured security program.",
     "approach": ["Risk assessment", "Control implementation", "Continuous monitoring", "Compliance alignment"],
     "outcomes": ["Reduced breach risk", "Regulatory compliance", "Faster incident response"],
     "industries": ["Finance", "Government", "Healthcare"], "services": ["Cyber Security", "IT Consulting", "Support"],
     "image": "1451187580459-43490279c0fa"},
    {"name": "Business Process Automation", "overview": "Automating repetitive workflows across departments to free up teams for higher-value work.",
     "problem": "Teams spending hours on manual, repetitive administrative work.",
     "approach": ["Workflow mapping", "Automation build", "Integration with existing tools", "Monitoring & tuning"],
     "outcomes": ["Time saved per week", "Fewer manual errors", "Faster turnaround"],
     "industries": ["Retail", "Logistics", "Real Estate"], "services": ["Enterprise Software", "API Development", "Data Analytics"],
     "image": "1504639725590-34d0984388bd"},
]


async def seed_solutions(db: AsyncSession) -> list[Solution]:
    created = []
    for i, s in enumerate(SOLUTIONS):
        sol, _ = await _get_or_create(
            db, Solution, {"slug": _slugify(s["name"])},
            {
                "name": s["name"], "icon": "cpu-chip", "overview": s["overview"],
                "problem_statement": s["problem"], "approach": s["approach"], "outcomes": s["outcomes"],
                "related_industries": s["industries"], "related_services": s["services"],
                "cover_image": _unsplash(s["image"]), "is_published": True, "order": i,
            },
        )
        created.append(sol)
    print(f"Solutions seeded ({len(SOLUTIONS)})")
    return created


# ---------------------------------------------------------------------------
# Technologies — common stack entries across the categories our services use.
# ---------------------------------------------------------------------------
TECHNOLOGIES = [
    ("React", TechnologyCategory.frontend), ("Vue.js", TechnologyCategory.frontend), ("Angular", TechnologyCategory.frontend),
    ("Node.js", TechnologyCategory.backend), ("Django", TechnologyCategory.backend), ("FastAPI", TechnologyCategory.backend),
    ("PostgreSQL", TechnologyCategory.database), ("MongoDB", TechnologyCategory.database), ("Redis", TechnologyCategory.database),
    ("AWS", TechnologyCategory.cloud), ("Microsoft Azure", TechnologyCategory.cloud), ("Google Cloud Platform", TechnologyCategory.cloud),
    ("Docker", TechnologyCategory.devops), ("Kubernetes", TechnologyCategory.devops), ("GitHub Actions", TechnologyCategory.devops),
    ("TensorFlow", TechnologyCategory.ai_ml), ("PyTorch", TechnologyCategory.ai_ml), ("OpenAI API", TechnologyCategory.ai_ml),
    ("React Native", TechnologyCategory.mobile), ("Flutter", TechnologyCategory.mobile),
    ("GraphQL", TechnologyCategory.other), ("Terraform", TechnologyCategory.other), ("Elasticsearch", TechnologyCategory.other),
]


async def seed_technologies(db: AsyncSession) -> list[Technology]:
    created = []
    for name, category in TECHNOLOGIES:
        tech, _ = await _get_or_create(
            db, Technology, {"name": name},
            {"category": category, "description": f"{name} — part of VPD Technologies's standard {category.value.replace('_', ' ')} toolkit."},
        )
        created.append(tech)
    print(f"Technologies seeded ({len(TECHNOLOGIES)})")
    return created


# ---------------------------------------------------------------------------
# Products — the PRD names "Products" as a nav/page but gives no concrete
# catalogue; these three are illustrative flagship products.
# ---------------------------------------------------------------------------
PRODUCTS = [
    {"name": "VPD Technologies ERP Suite", "tagline": "One platform for finance, inventory and HR.",
     "description": "A modular ERP suite covering finance, inventory, procurement and HR for growing enterprises.",
     "features": ["Multi-entity finance", "Real-time inventory", "Procurement workflows", "HR & payroll"],
     "benefits": ["Single source of truth", "Faster month-end close", "Lower operating cost"],
     "use_cases": ["Manufacturing operations", "Multi-branch retail", "Distribution businesses"],
     "stack": ["Python", "PostgreSQL", "React"], "image": "1460925895917-afdab827c52f"},
    {"name": "VPD Technologies CRM Cloud", "tagline": "Sell smarter, support faster.",
     "description": "A cloud CRM unifying sales pipeline, marketing campaigns and customer support in one workspace.",
     "features": ["Pipeline management", "Campaign automation", "Support ticketing", "Reporting dashboards"],
     "benefits": ["Higher conversion rates", "Unified customer view", "Faster support resolution"],
     "use_cases": ["B2B sales teams", "Customer support desks", "Marketing operations"],
     "stack": ["FastAPI", "PostgreSQL", "Redis"], "image": "1522071820081-009f0129c71c"},
    {"name": "VPD Technologies Insight Analytics", "tagline": "Turn operational data into decisions.",
     "description": "A BI and analytics platform with live dashboards, alerts and predictive forecasting.",
     "features": ["Live dashboards", "Predictive forecasting", "Automated alerts", "Role-based access"],
     "benefits": ["Faster decisions", "Reduced manual reporting", "Early risk detection"],
     "use_cases": ["Executive reporting", "Sales forecasting", "Operational monitoring"],
     "stack": ["Python", "PostgreSQL", "React"], "image": "1581091226825-a6a2a5aee158"},
]


async def seed_products(db: AsyncSession) -> list[Product]:
    created = []
    for i, p in enumerate(PRODUCTS):
        product, _ = await _get_or_create(
            db, Product, {"slug": _slugify(p["name"])},
            {
                "name": p["name"], "tagline": p["tagline"], "description": p["description"],
                "features": p["features"], "benefits": p["benefits"], "pricing_tiers": [],
                "technology_stack": p["stack"], "use_cases": p["use_cases"],
                "cover_image": _unsplash(p["image"]), "icon": "cube", "is_published": True, "order": i,
            },
        )
        created.append(product)
    print(f"Products seeded ({len(PRODUCTS)})")
    return created


# ---------------------------------------------------------------------------
# Partners (CMS "our partners" logo listing) — fictional company names,
# deliberately not real brands, so this demo never implies a real partnership.
# ---------------------------------------------------------------------------
PARTNERS = [
    ("Nimbus Cloud Systems", PartnerType.technology_partner), ("Vertex Data Labs", PartnerType.technology_partner),
    ("Quantum Security Partners", PartnerType.technology_partner), ("Skyline Integrations", PartnerType.technology_partner),
    ("BluePeak Analytics", PartnerType.business_partner), ("Northbridge Systems", PartnerType.business_partner),
    ("Meridian AI Labs", PartnerType.business_partner), ("Cobalt Networks", PartnerType.business_partner),
    ("Orbit DevOps Co", PartnerType.reseller), ("Lumen Cloud Partners", PartnerType.reseller),
    ("Apex Reseller Group", PartnerType.reseller), ("Fusion Point Technologies", PartnerType.reseller),
]


async def seed_partners(db: AsyncSession) -> list[Partner]:
    created = []
    for name, ptype in PARTNERS:
        partner, _ = await _get_or_create(
            db, Partner, {"name": name},
            {"logo": _unsplash("1519389950473-47ba0277781c", 400, 200), "website": None, "type": ptype, "is_published": True},
        )
        created.append(partner)
    print(f"Partners seeded ({len(PARTNERS)})")
    return created


# ---------------------------------------------------------------------------
# Awards — ISO certifications are literal PRD content ("Why Choose Us"); the
# rest are illustrative award names against fictional award bodies.
# ---------------------------------------------------------------------------
AWARDS = [
    ("ISO 9001:2015 Quality Management Certification", "International Organization for Standardization", 2022,
     "Certified for consistently meeting quality management standards across our delivery process."),
    ("ISO/IEC 27001:2013 Information Security Certification", "International Organization for Standardization", 2023,
     "Certified for our information security management system covering data protection and risk controls."),
    ("Digital Innovation Award", "TechConnect Summit 2024", 2024, "Recognized for innovative enterprise digital transformation work."),
    ("Cloud Excellence Recognition", "Enterprise Tech Council 2023", 2023, "Recognized for excellence in cloud-native enterprise delivery."),
    ("Top Employer Recognition", "WorkPlace India 2022", 2022, "Recognized for workplace culture and employee development practices."),
    ("Fastest Growing IT Services Company", "StartUp Digest 2021", 2021, "Recognized among the fastest-growing IT services companies of the year."),
]


async def seed_awards(db: AsyncSession) -> list[Award]:
    created = []
    for title, issued_by, year, description in AWARDS:
        award, _ = await _get_or_create(
            db, Award, {"title": title},
            {"issued_by": issued_by, "year": year, "image": _unsplash("1521791136064-7986c2920216", 600, 600),
             "description": description, "is_published": True},
        )
        created.append(award)
    print(f"Awards seeded ({len(AWARDS)})")
    return created


# ---------------------------------------------------------------------------
# FAQs — general company/service questions for the public FAQ page.
# ---------------------------------------------------------------------------
FAQS = [
    ("What industries does VPD Technologies work with?", "We work across 16+ industries including healthcare, finance, retail, manufacturing, logistics and more — see our Industries page for the full list.", "general"),
    ("How long does a typical project take?", "Most engagements run 6-16 weeks depending on scope, following our discovery-to-launch delivery process.", "general"),
    ("Do you offer post-launch support?", "Yes — every engagement includes a handover period, with ongoing Annual Maintenance and 24x7 Support contracts available separately.", "general"),
    ("Where is VPD Technologies based?", "Our head office is in Connaught Place, New Delhi, India, with branch offices in Bangalore, Hyderabad, Pune, Mumbai, Dubai and Singapore.", "company"),
    ("Is VPD Technologies ISO certified?", "Yes — we hold both ISO 9001:2015 (Quality Management) and ISO/IEC 27001:2013 (Information Security) certifications.", "company"),
    ("Can you work with our existing technology stack?", "Yes — our services are designed to integrate with existing systems rather than requiring a full rip-and-replace.", "services"),
    ("Do you offer fixed-price or time-and-materials engagements?", "Both — we scope each engagement with the client and recommend the pricing model that best fits the project's certainty level.", "services"),
    ("How do I apply for a job at VPD Technologies?", "Browse open roles on our Careers page and submit an application directly through the listing.", "careers"),
    ("Do you offer internships?", "Yes — we run internship programs across engineering, design and business functions; check the Careers page for current openings.", "careers"),
    ("How can I request a demo or proposal?", "Use the Contact page to reach our sales team, or request a callback and we'll follow up within one business day.", "general"),
]


async def seed_faqs(db: AsyncSession) -> list[Faq]:
    created = []
    for i, (question, answer, category) in enumerate(FAQS):
        faq, _ = await _get_or_create(
            db, Faq, {"question": question},
            {"answer": answer, "category": category, "order": i, "is_published": True},
        )
        created.append(faq)
    print(f"FAQs seeded ({len(FAQS)})")
    return created


# ---------------------------------------------------------------------------
# Downloads & Resources
# ---------------------------------------------------------------------------
DOWNLOADS = [
    ("VPD Technologies Company Profile", "An overview of who we are, what we do, and how we work.", "pdf", "company", False),
    ("Enterprise Services Catalogue 2026", "Full catalogue of our enterprise software and consulting services.", "pdf", "services", False),
    ("Cloud Migration Playbook", "A step-by-step playbook for planning and executing a cloud migration.", "pdf", "whitepaper", True),
    ("AI Readiness Assessment Checklist", "Self-assessment checklist to evaluate your organization's AI readiness.", "pdf", "whitepaper", True),
    ("Case Studies Compilation 2025", "A collection of client case studies across industries.", "pdf", "case-studies", False),
]


async def seed_downloads(db: AsyncSession) -> list[Download]:
    created = []
    for title, description, file_type, category, requires_lead in DOWNLOADS:
        dl, _ = await _get_or_create(
            db, Download, {"title": title},
            {"description": description, "file_url": f"/downloads/{_slugify(title)}.pdf", "file_type": file_type,
             "category": category, "requires_lead": requires_lead, "is_published": True},
        )
        created.append(dl)
    print(f"Downloads seeded ({len(DOWNLOADS)})")
    return created


RESOURCES = [
    ("The Complete Guide to Enterprise Cloud Migration", "guide", "A practical guide to planning and executing enterprise cloud migrations."),
    ("AI Adoption Playbook for Enterprises", "whitepaper", "How to identify, pilot and scale AI initiatives inside a large organization."),
    ("Cybersecurity Readiness Checklist", "guide", "A checklist to assess your organization's security posture."),
    ("Modern DevOps Practices Handbook", "ebook", "CI/CD, infrastructure as code and observability best practices."),
    ("Business Intelligence Maturity Model", "whitepaper", "A framework for assessing and improving your organization's BI maturity."),
]


async def seed_resources(db: AsyncSession, author_id: uuid.UUID | None) -> list[Resource]:
    created = []
    for title, resource_type, description in RESOURCES:
        res, _ = await _get_or_create(
            db, Resource, {"slug": _slugify(title)},
            {"title": title, "resource_type": resource_type, "description": description,
             "file_url": f"/resources/{_slugify(title)}.pdf", "cover_image": _unsplash("1519337265831-281ec6cc8514"),
             "author_id": author_id, "is_published": True},
        )
        created.append(res)
    print(f"Resources seeded ({len(RESOURCES)})")
    return created


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------
async def seed_events(db: AsyncSession) -> list[Event]:
    now = datetime.now(UTC)
    events_data = [
        ("VPD Technologies Digital Transformation Summit 2026", "A virtual summit on modernizing enterprise operations.", None, True, now + timedelta(days=45)),
        ("Cloud & AI Innovation Meetup — Bangalore", "An in-person meetup on cloud-native and AI adoption patterns.", "Bangalore, India", False, now + timedelta(days=20)),
        ("VPD Technologies Cybersecurity Webinar Series", "A recorded webinar series on enterprise security best practices.", None, True, now - timedelta(days=150)),
        ("Enterprise Tech Conclave 2025", "An industry conclave on enterprise technology trends.", "New Delhi, India", False, now - timedelta(days=280)),
    ]
    created = []
    for title, description, location, is_virtual, start in events_data:
        event, _ = await _get_or_create(
            db, Event, {"slug": _slugify(title)},
            {"title": title, "description": description, "cover_image": _unsplash("1492684223066-81342ee5ff30"),
             "location": location, "start_date": start, "end_date": start + timedelta(hours=3),
             "is_virtual": is_virtual, "registration_url": None, "is_published": True},
        )
        created.append(event)
    print(f"Events seeded ({len(events_data)})")
    return created


# ---------------------------------------------------------------------------
# Careers
# ---------------------------------------------------------------------------
CAREERS = [
    ("Senior Full Stack Developer", "Engineering", "New Delhi, India", CareerEmploymentType.full_time, "4-6 years"),
    ("DevOps Engineer", "DevOps", "Bangalore, India", CareerEmploymentType.full_time, "3-5 years"),
    ("QA Automation Engineer", "Quality Assurance", "Pune, India", CareerEmploymentType.full_time, "2-4 years"),
    ("UI/UX Designer", "Design", "Remote", CareerEmploymentType.full_time, "3-5 years"),
    ("Business Development Manager", "Sales", "Mumbai, India", CareerEmploymentType.full_time, "5-7 years"),
    ("HR Executive", "Human Resources", "New Delhi, India", CareerEmploymentType.full_time, "1-3 years"),
    ("Software Engineering Intern", "Engineering", "Hyderabad, India", CareerEmploymentType.internship, "0-1 years"),
]


async def seed_careers(db: AsyncSession) -> list[Career]:
    created = []
    for title, department, location, emp_type, experience in CAREERS:
        career, _ = await _get_or_create(
            db, Career, {"slug": _slugify(title)},
            {
                "title": title, "department": department, "location": location, "employment_type": emp_type,
                "experience_required": experience,
                "description": f"We're hiring a {title} to join our {department} team in {location}.",
                "responsibilities": ["Own delivery of assigned initiatives end to end", "Collaborate cross-functionally with product and engineering", "Mentor junior team members"],
                "requirements": [f"{experience} of relevant experience", "Strong communication skills", "Ability to work independently"],
                "status": CareerStatus.open,
            },
        )
        created.append(career)
    print(f"Careers seeded ({len(CAREERS)})")
    return created


# ---------------------------------------------------------------------------
# Blogs
# ---------------------------------------------------------------------------
BLOGS = [
    ("5 Ways AI is Transforming Enterprise Operations", "Artificial Intelligence",
     "From demand forecasting to automated support, AI is reshaping how enterprises operate.",
     ["ai", "enterprise", "automation"], "1518770660439-4636190af475"),
    ("Why Cloud Migration Should Be Your 2026 Priority", "Cloud Computing",
     "Rising infrastructure costs and scaling pressure make this the year to move to the cloud.",
     ["cloud", "migration", "infrastructure"], "1558494949-ef010cbdcc31"),
    ("VPD Technologies Achieves ISO 27001 Certification", "Company News",
     "We're proud to announce our information security management system is now ISO 27001 certified.",
     ["company-news", "security", "certification"], "1451187580459-43490279c0fa"),
    ("The Real Cost of Skipping DevOps Automation", "Technology",
     "Manual deployments don't just slow you down — they quietly cost far more than automation would.",
     ["devops", "automation", "engineering"], "1517245386807-bb43f82c33c4"),
    ("Zero Trust Security: A Practical Roadmap for Enterprises", "Cyber Security",
     "Zero trust is more than a buzzword — here's a practical path to actually implementing it.",
     ["security", "zero-trust", "enterprise"], "1526374965328-7f61d4dc18c5"),
    ("From Legacy to Cloud-Native: A Manufacturing Case Study", "Case Studies",
     "How a mid-size manufacturer modernized its ERP without disrupting production.",
     ["case-study", "manufacturing", "cloud"], "1565043666747-69f6646db940"),
    ("Building Scalable CRM Systems: Lessons from the Field", "Technology",
     "What we learned building CRM platforms that hold up under real sales-team usage.",
     ["crm", "engineering", "scalability"], "1522071820081-009f0129c71c"),
    ("How Business Intelligence Drives Better Decisions", "Technology",
     "Live dashboards beat stale spreadsheets — here's how BI changes how leadership decides.",
     ["business-intelligence", "data", "analytics"], "1581091226825-a6a2a5aee158"),
]


async def seed_blogs(db: AsyncSession, categories: dict[str, Category], author_ids: list[uuid.UUID]) -> list[Blog]:
    created = []
    now = datetime.now(UTC)
    for i, (title, category_name, excerpt, tags, image_id) in enumerate(BLOGS):
        content = (
            f"{excerpt}\n\n"
            f"At VPD Technologies, we work with enterprise teams every day who are navigating exactly this challenge. "
            f"This post walks through what we've seen work in practice, the pitfalls to avoid, and a practical "
            f"framework you can apply to your own organization.\n\n"
            f"The short version: start small, measure relentlessly, and treat this as an iterative program rather "
            f"than a one-time project. Teams that succeed here build feedback loops early and adjust course often.\n\n"
            f"If you'd like to talk through how this applies to your situation, reach out to our team — we're "
            f"always happy to share what we've learned."
        )
        blog, _ = await _get_or_create(
            db, Blog, {"slug": _slugify(title)},
            {
                "title": title, "excerpt": excerpt, "content": content,
                "cover_image": _unsplash(image_id), "category_id": categories[category_name].id,
                "author_id": author_ids[i % len(author_ids)] if author_ids else None,
                "tags": tags, "status": BlogStatus.published, "views": 0,
                "published_at": now - timedelta(days=(len(BLOGS) - i) * 18),
                "meta_title": title, "meta_description": excerpt,
            },
        )
        created.append(blog)
    print(f"Blogs seeded ({len(BLOGS)})")
    return created


# ---------------------------------------------------------------------------
# Testimonials — fictional client companies, distinct from the partner names
# above, so nothing here implies a real company endorsed VPD Technologies.
# ---------------------------------------------------------------------------
TESTIMONIALS = [
    ("Meridian Health Group", "CTO", "Working with VPD Technologies on our patient portal modernization was seamless — they understood our compliance constraints from day one.", 5),
    ("Vantage Retail Co", "Head of Digital", "Our omnichannel platform rollout was on time and on budget, which is rare for a project this size.", 5),
    ("Northwind Logistics", "COO", "The warehouse management system VPD Technologies built has cut our fulfillment errors dramatically.", 4),
    ("Sterling Finance Corp", "VP Engineering", "Their engineering team integrated cleanly with ours — genuinely felt like an extension of our team.", 5),
    ("BrightPath Education", "Director of IT", "The LMS migration was handled with almost no disruption to active students, which was our biggest worry.", 5),
    ("Coastal Hospitality Group", "CIO", "VPD Technologies's booking platform redesign directly improved our conversion rate within the first quarter.", 4),
    ("Ridgeline Manufacturing", "Plant Operations Director", "Predictive maintenance alerts have already prevented two unplanned production stops.", 5),
    ("Harbor Insurance Partners", "Head of Claims", "Claims processing time dropped significantly after the automation work VPD Technologies delivered.", 5),
]


async def seed_testimonials(db: AsyncSession) -> list[Testimonial]:
    created = []
    for i, (company, title, content, rating) in enumerate(TESTIMONIALS):
        author_name = f"{['Aditi', 'Rahul', 'Priya', 'Karan', 'Neha', 'Vikram', 'Sana', 'Arjun'][i]} {['Sharma', 'Verma', 'Iyer', 'Malhotra', 'Kapoor', 'Nair', 'Chopra', 'Reddy'][i]}"
        testimonial, _ = await _get_or_create(
            db, Testimonial, {"author_name": author_name, "company_name": company},
            {
                "author_title": title, "avatar": _unsplash("1519345182560-3f2917c472ef", 200, 200),
                "rating": rating, "content": content, "is_published": True,
            },
        )
        created.append(testimonial)
    print(f"Testimonials seeded ({len(TESTIMONIALS)})")
    return created


# ---------------------------------------------------------------------------
# Projects — PRD calls for "20 Sample Projects". Fictional clients (matching
# the testimonial companies above where the industry lines up).
# ---------------------------------------------------------------------------
PROJECT_IMAGES = [
    "1460925895917-afdab827c52f", "1522071820081-009f0129c71c", "1531482615713-2afd69097998",
    "1551434678-e076c223a692", "1517245386807-bb43f82c33c4", "1498050108023-c5249f4df085",
    "1461749280684-dccba630e2f6", "1483058712412-4245e9b90334",
]

PROJECTS = [
    ("Enterprise ERP Modernization for Ridgeline Manufacturing", "Manufacturing", ["Python", "PostgreSQL", "React"], True),
    ("Omnichannel Retail Platform for Vantage Retail Co", "Retail", ["Node.js", "React", "Redis"], True),
    ("Cloud-Native Core Banking Migration", "Finance", ["AWS", "Kubernetes", "Terraform"], True),
    ("AI-Powered Claims Automation for Harbor Insurance", "Insurance", ["Python", "TensorFlow", "FastAPI"], True),
    ("Telemedicine Platform for Meridian Health Group", "Healthcare", ["React Native", "Node.js", "PostgreSQL"], True),
    ("Smart Warehouse Management System", "Logistics", ["Python", "PostgreSQL", "React"], True),
    ("University LMS Modernization for BrightPath Education", "Education", ["Django", "PostgreSQL", "React"], False),
    ("Hotel Booking & Guest Experience App", "Hospitality", ["React Native", "FastAPI", "Redis"], False),
    ("Predictive Maintenance IoT Platform", "Manufacturing", ["Python", "TensorFlow", "PostgreSQL"], False),
    ("Government Citizen Services Portal", "Government", ["Django", "PostgreSQL", "React"], False),
    ("Renewable Energy Monitoring Dashboard", "Energy", ["React", "FastAPI", "PostgreSQL"], False),
    ("Telecom Billing System Overhaul", "Telecom", ["Java", "PostgreSQL", "React"], False),
    ("Pharma Clinical Trials Data Platform", "Pharma", ["Python", "PostgreSQL", "React"], False),
    ("Connected Vehicle Fleet Tracking App", "Automotive", ["React Native", "Node.js", "MongoDB"], False),
    ("Streaming Media Recommendation Engine", "Media", ["Python", "TensorFlow", "Redis"], False),
    ("Construction Project Management Suite", "Construction", ["React", "FastAPI", "PostgreSQL"], False),
    ("Real Estate Property Management Portal", "Real Estate", ["Node.js", "React", "PostgreSQL"], False),
    ("Cybersecurity SOC Modernization", "Finance", ["Python", "Elasticsearch", "AWS"], False),
    ("Business Intelligence Dashboard Rollout", "Retail", ["Python", "PostgreSQL", "React"], False),
    ("DevOps CI/CD Transformation Program", "Manufacturing", ["Docker", "Kubernetes", "GitHub Actions"], False),
]


async def seed_projects(db: AsyncSession, project_manager_ids: list[uuid.UUID]) -> list[Project]:
    created = []
    today = date.today()
    for i, (title, industry, stack, featured) in enumerate(PROJECTS):
        if i < 14:
            status, progress = ProjectStatus.completed, 100
        elif i < 18:
            status, progress = ProjectStatus.in_progress, 60
        else:
            status, progress = ProjectStatus.planning, 5
        start = today - timedelta(days=(20 - i) * 45 + 200)
        end = start + timedelta(days=120) if status == ProjectStatus.completed else None
        images = [_unsplash(PROJECT_IMAGES[i % len(PROJECT_IMAGES)]), _unsplash(PROJECT_IMAGES[(i + 3) % len(PROJECT_IMAGES)])]
        project, _ = await _get_or_create(
            db, Project, {"slug": _slugify(title)},
            {
                "title": title,
                "overview": f"A {industry.lower()} sector engagement to modernize core systems and improve operational efficiency.",
                "challenge": "Legacy systems and manual processes were limiting scale and slowing decision-making.",
                "solution": f"VPD Technologies designed and delivered a modern platform built on {', '.join(stack)}.",
                "technology_stack": stack, "architecture_notes": "Modular, API-first architecture with CI/CD-driven deployments.",
                "industry": industry, "start_date": start, "end_date": end, "budget": 4500000 + i * 250000,
                "status": status, "progress_percent": progress,
                "project_manager_id": project_manager_ids[i % len(project_manager_ids)] if project_manager_ids else None,
                "cover_image": images[0], "video_url": None,
                "deliverables": ["Production deployment", "Technical documentation", "Team training"],
                "gallery": images, "downloads": [], "is_featured": featured, "is_published": True,
            },
        )
        created.append(project)
    print(f"Projects seeded ({len(PROJECTS)})")
    return created


# ---------------------------------------------------------------------------
# Case Studies, Portfolio, Gallery — derived from the featured projects.
# ---------------------------------------------------------------------------
async def seed_case_studies(db: AsyncSession, projects: list[Project]) -> list[CaseStudy]:
    featured = [p for p in projects if p.is_featured][:6]
    created = []
    for project in featured:
        cs, _ = await _get_or_create(
            db, CaseStudy, {"slug": _slugify(f"{project.title} case study")},
            {
                "title": f"{project.title} — Case Study",
                "project_id": project.id, "client_name": project.title.split(" for ")[-1] if " for " in project.title else project.industry,
                "industry": project.industry, "problem": project.challenge, "solution": project.solution,
                "implementation": "Delivered in agile sprints with regular stakeholder demos across a phased rollout plan.",
                "result": "The client saw measurable operational improvements within the first quarter post-launch.",
                "roi": "3-5x within 12 months", "customer_feedback": "The team delivered exactly what we needed, on time.",
                "download_url": None, "downloads": [], "cover_image": project.cover_image, "is_published": True,
            },
        )
        created.append(cs)
    print(f"Case studies seeded ({len(created)})")
    return created


async def seed_portfolio(db: AsyncSession, projects: list[Project]) -> list[Portfolio]:
    created = []
    for i, project in enumerate(projects[:10]):
        item, _ = await _get_or_create(
            db, Portfolio, {"slug": _slugify(f"{project.title} portfolio")},
            {
                "title": project.title, "category": project.industry, "thumbnail": project.cover_image,
                "description": project.overview, "live_url": None, "project_id": project.id,
                "is_featured": project.is_featured, "order": i,
            },
        )
        created.append(item)
    print(f"Portfolio items seeded ({len(created)})")
    return created


async def seed_gallery(db: AsyncSession, projects: list[Project]) -> list[Gallery]:
    created = []
    for _i, project in enumerate(projects[:10]):
        for j, image_url in enumerate(project.gallery or [project.cover_image]):
            item, _ = await _get_or_create(
                db, Gallery, {"image_url": image_url, "project_id": project.id},
                {"title": f"{project.title} — {j + 1}", "album_name": project.industry, "is_published": True},
            )
            created.append(item)
    print(f"Gallery images seeded ({len(created)})")
    return created


# ---------------------------------------------------------------------------
# Page content — literal PRD copy (company profile, vision, mission, core
# values, why choose us).
# ---------------------------------------------------------------------------
def _legal_html(sections: list[tuple[str, str]]) -> str:
    """Renders (heading, paragraph) pairs as sanitizer-safe HTML — the shape
    LegalContent.jsx expects in PageContent.content for the legal pages
    (frontend/src/components/legal/LegalContent.jsx renders it through
    DOMPurify). Mirrors the section copy from frontend/src/data/legal.js,
    which the frontend still falls back to while this fetch is in flight."""
    return "".join(f"<h2>{heading}</h2><p>{body}</p>" for heading, body in sections)


async def seed_page_contents(db: AsyncSession) -> list[PageContent]:
    pages = [
        ("about", "About VPD Technologies",
         "VPD Technologies Private Limited (brand name: VPD Technologies) is a Private Limited "
         "company founded in 2020, working across Digital Transformation, Enterprise Software, Artificial "
         "Intelligence, Cloud Computing, Cyber Security and Business Automation.\n\n"
         "Tagline: Transforming Businesses Through Intelligent Digital Solutions.\n\n"
         "Head Office: Connaught Place, New Delhi, India. Branch Offices: Bangalore, Hyderabad, Pune, Mumbai, "
         "Dubai, Singapore.\n\n"
         "285+ Employees · 120+ Clients · 18+ Countries · 430+ Projects."),
        ("vision", "Our Vision",
         "To become one of Asia's most trusted Digital Transformation companies by building secure, scalable "
         "and intelligent enterprise software."),
        ("mission", "Our Mission",
         "Deliver world-class enterprise technology solutions through innovation, engineering excellence and "
         "customer-centric development."),
        ("core-values", "Our Core Values",
         "Innovation · Integrity · Engineering Excellence · Quality · Customer Success · Ownership · "
         "Transparency · Continuous Learning · Security First · Collaboration."),
        ("why-choose-us", "Why Choose VPD Technologies",
         "430+ Projects Delivered · 285+ Employees · 120+ Enterprise Clients · 18+ Countries Served · "
         "99.8% Uptime · 24×7 Support · ISO 9001 Certified · ISO 27001 Certified."),
        # Legal pages — consumed by pages/Privacy.jsx, Terms.jsx, Cookies.jsx
        # (fetched by slug via fetchPageContent), replacing the previously
        # static frontend/src/data/legal.js copy that's now only the
        # offline/loading fallback for those pages.
        ("privacy-policy", "Privacy Policy", _legal_html([
            ("1. Information We Collect",
             "We collect information you provide directly, including name, email address, phone number, "
             "company name, and job title when you fill out forms on our website, subscribe to newsletters, "
             "or interact with our services. We also automatically collect certain technical information "
             "such as IP address, browser type, device information, and usage data through cookies and "
             "similar technologies."),
            ("2. How We Use Your Information",
             "We use the information we collect to provide, maintain, and improve our services, communicate "
             "with you about our products and services, send marketing communications (with your consent), "
             "comply with legal obligations, and protect our rights and property."),
            ("3. Information Sharing",
             "We do not sell your personal information. We may share information with trusted service "
             "providers who assist us in operating our website and business, when required by law, or in "
             "connection with a business transaction such as a merger or acquisition. All third-party "
             "providers are contractually bound to maintain the confidentiality of your data."),
            ("4. Data Security",
             "We implement industry-standard security measures including encryption in transit and at rest, "
             "access controls, regular security audits, and employee training to protect your personal "
             "information from unauthorized access, disclosure, or destruction."),
            ("5. Your Rights",
             "Depending on your jurisdiction, you may have rights including: access to your personal data, "
             "correction of inaccurate data, deletion of your data (right to be forgotten), restriction of "
             "processing, data portability, and the right to withdraw consent at any time. To exercise these "
             "rights, please contact us at privacy@vpdtechnologies.com."),
            ("6. Cookie Policy",
             "We use essential cookies for website functionality, analytics cookies to understand how "
             "visitors interact with our site, and marketing cookies (with your consent) to deliver relevant "
             "advertisements. You can manage cookie preferences through your browser settings at any time. "
             "For more details, see our Cookie Policy."),
            ("7. International Data Transfers",
             "Your information may be transferred to and processed in countries other than your own. We "
             "ensure appropriate safeguards are in place through Standard Contractual Clauses and Data "
             "Processing Agreements to protect your data regardless of where it is processed."),
            ("8. Changes to This Policy",
             "We may update this Privacy Policy from time to time. We will notify you of material changes by "
             "posting the updated policy on this page and, where appropriate, through email notification. We "
             "encourage you to review this policy periodically."),
            ("9. Contact Us",
             "If you have questions about this Privacy Policy or our data practices, please contact our Data "
             "Protection Officer at privacy@vpdtechnologies.com or write to us at: VPD Technologies, "
             "4th Floor, Innovation Tower, Plot 27, Sector 4, HSR Layout, Bangalore 560102, India."),
        ])),
        ("terms-of-service", "Terms of Service", _legal_html([
            ("1. Acceptance of Terms",
             "By accessing or using the VPD Technologies website, products, or services, you agree to "
             "be bound by these Terms of Service. If you do not agree with any part of these terms, you may "
             "not use our services."),
            ("2. Services Description",
             "VPD Technologies provides technology consulting, software development, cloud "
             "infrastructure services, cybersecurity solutions, and managed IT services. The specific scope, "
             "deliverables, and timelines for each engagement are defined in separate Statements of Work or "
             "Service Agreements."),
            ("3. Intellectual Property",
             "All intellectual property developed specifically for a client engagement is owned by the "
             "client upon full payment. VPD Technologies retains ownership of pre-existing "
             "intellectual property, tools, frameworks, and methodologies used during service delivery. "
             "Clients are granted a perpetual, royalty-free license to any pre-existing IP incorporated into "
             "deliverables."),
            ("4. Confidentiality",
             "Both parties agree to maintain the confidentiality of all proprietary information disclosed "
             "during the engagement. Confidential information includes technical data, business strategies, "
             "source code, and any materials marked as confidential. This obligation survives the "
             "termination of the agreement for a period of five years."),
            ("5. Limitation of Liability",
             "To the maximum extent permitted by law, VPD Technologies shall not be liable for any "
             "indirect, incidental, special, consequential, or punitive damages. Our total liability for any "
             "claim arising from our services shall not exceed the total fees paid for the specific "
             "engagement giving rise to the claim."),
            ("6. Warranties",
             "We warrant that our services will be performed in a professional and workmanlike manner in "
             "accordance with industry standards. Services will conform to the specifications outlined in "
             "the applicable Statement of Work. This warranty is valid for 90 days from the date of "
             "delivery."),
            ("7. Termination",
             "Either party may terminate an agreement with 30 days written notice. In case of material "
             "breach, the non-breaching party may terminate immediately with written notice. Upon "
             "termination, the client shall pay for all services rendered up to the effective termination "
             "date."),
            ("8. Governing Law",
             "These terms shall be governed by and construed in accordance with the laws of India. Any "
             "disputes arising from these terms shall be resolved through binding arbitration in Bangalore, "
             "India, in accordance with the Arbitration and Conciliation Act, 1996."),
            ("9. Contact Information",
             "For questions about these Terms of Service, please contact us at legal@vpdtechnologies.com or "
             "at: VPD Technologies, 4th Floor, Innovation Tower, Plot 27, Sector 4, HSR Layout, "
             "Bangalore 560102, India."),
        ])),
        ("cookie-policy", "Cookie Policy", _legal_html([
            ("1. What Are Cookies",
             "Cookies are small text files stored on your device when you visit a website. They help "
             "websites function properly, improve user experience, and provide information to website "
             "owners. Cookies can be \"session\" cookies that expire when you close your browser or "
             "\"persistent\" cookies that remain until you clear them."),
            ("2. Types of Cookies We Use",
             "Essential Cookies: Required for the website to function properly. These include authentication "
             "cookies, session management, and security cookies. Analytics Cookies: Help us understand how "
             "visitors interact with our website by collecting anonymized data about page visits, navigation "
             "patterns, and referral sources. We use Google Analytics and Microsoft Clarity for this "
             "purpose. Preference Cookies: Remember your settings and preferences such as language, region, "
             "and display options. Marketing Cookies: Used (with your consent) to deliver relevant "
             "advertisements and measure their effectiveness."),
            ("3. Third-Party Cookies",
             "Some cookies are placed by third-party services we use, including Google Analytics (website "
             "analytics), Microsoft Clarity (session recording), LinkedIn Insight Tag (marketing), and "
             "HubSpot (CRM and marketing). These third parties have their own privacy policies governing the "
             "use of your data."),
            ("4. Managing Cookies",
             "You can control and manage cookies through your browser settings. Most browsers allow you to "
             "block or delete cookies entirely, or to receive a warning before a cookie is stored. Please "
             "note that disabling certain cookies may affect the functionality of our website."),
            ("5. Your Consent",
             "When you first visit our website, we display a cookie consent banner that allows you to choose "
             "which categories of cookies you accept. Essential cookies are always active as they are "
             "necessary for the website to function. You can change your preferences at any time by clicking "
             "the \"Cookie Settings\" link in the footer."),
            ("6. Updates to This Policy",
             "We may update this Cookie Policy from time to time to reflect changes in our practices or "
             "relevant regulations. We will notify you of material changes through a banner or notification "
             "on our website."),
            ("7. Contact",
             "If you have questions about our use of cookies, please contact us at privacy@vpdtechnologies.com."),
        ])),
    ]
    created = []
    for slug, title, content in pages:
        page, _ = await _get_or_create(db, PageContent, {"slug": slug}, {"title": title, "content": content, "is_published": True})
        created.append(page)
    print(f"Page content sections seeded ({len(pages)})")
    return created


# ---------------------------------------------------------------------------
# Business-statistics settings — PRD "BUSINESS STATISTICS" table, verbatim.
# ---------------------------------------------------------------------------
async def seed_stats_settings(db: AsyncSession) -> None:
    stats = [
        ("stats.employees", 285), ("stats.projects", 430), ("stats.clients", 120),
        ("stats.partners", 35), ("stats.countries", 18), ("stats.years", 5),
        ("stats.success_rate", "98%"),
        ("company.founded_year", 2020),
        ("company.head_office", "Connaught Place, New Delhi, India"),
        ("company.branch_offices", ["Bangalore", "Hyderabad", "Pune", "Mumbai", "Dubai", "Singapore"]),
    ]
    n = 0
    for key, value in stats:
        _, created = await _get_or_create(db, Setting, {"key": key}, {"value": value, "group": "public"})
        n += 1 if created else 0
    print(f"Business-stat settings seeded ({n} new)")


# ---------------------------------------------------------------------------
# Leadership / Offices / Company & About site content — transcribed verbatim
# from the previously-hardcoded frontend/src/data/about.js and
# frontend/src/data/company.js so switching those pages over to the API
# doesn't blank the site. Leadership/Offices are normal list-style CMS
# resources (own table); company info and about-page content (mission,
# core values, timeline, certifications) are simple enough that they're
# stored as structured JSON on the existing `settings` table instead of new
# single-row tables (see app/routers/site_content.py).
# ---------------------------------------------------------------------------
LEADERSHIP = [
    ("Dr. Vikram Nair", "Founder & CEO", "https://www.linkedin.com/", 0),
    ("Sara Cheng", "Chief Technology Officer", "https://www.linkedin.com/", 1),
    ("Arjun Mehta", "COO, Global Operations", "https://www.linkedin.com/", 2),
    ("Elena Rossi", "Chief Experience Officer", "https://www.linkedin.com/", 3),
]


async def seed_leadership(db: AsyncSession) -> list[Leadership]:
    created = []
    for name, title, linkedin, order in LEADERSHIP:
        leader, _ = await _get_or_create(
            db, Leadership, {"name": name},
            {"title": title, "photo_url": None, "linkedin": linkedin, "order": order, "is_published": True},
        )
        created.append(leader)
    print(f"Leadership seeded ({len(LEADERSHIP)})")
    return created


OFFICES = [
    ("Bangalore", "HQ & Innovation Lab", True, 0),
    ("Dubai", "MENA Regional Office", False, 1),
    ("Singapore", "SEA Hub", False, 2),
    ("Mumbai", "Delivery Center", False, 3),
    ("Hyderabad", "Cybersecurity CoE", False, 4),
    ("Pune", "AI & Data Science", False, 5),
]


async def seed_offices(db: AsyncSession) -> list[Office]:
    created = []
    for city, description, is_hq, order in OFFICES:
        office, _ = await _get_or_create(
            db, Office, {"city": city},
            {"description": description, "is_headquarters": is_hq, "order": order, "is_published": True},
        )
        created.append(office)
    print(f"Offices seeded ({len(OFFICES)})")
    return created


async def seed_company_info(db: AsyncSession) -> None:
    value = {
        "name": "VPD Technologies",
        "legalName": "VPD Technologies Private Limited",
        "tagline": "Transforming Businesses Through Intelligent Digital Solutions",
        "website": "www.vpdtechnologies.com",
        "email": "hello@vpdtechnologies.com",
        "founded": 2020,
        "hq": "Connaught Place, New Delhi, India",
        "offices": ["Bangalore", "Hyderabad", "Pune", "Mumbai", "Dubai", "Singapore"],
    }
    setting, created = await _get_or_create(db, Setting, {"key": "company_info"}, {"value": value, "group": "company"})
    if not created:
        setting.value = value
    print("Company info settings seeded")


async def seed_about_content(db: AsyncSession) -> None:
    core_values = [
        {"icon": "lightbulb", "title": "Innovation",
         "description": ("We don't just follow trends; we create the frameworks that define them. Our R&D labs "
                          "are constantly pushing the boundaries of AI, cloud native architectures, and cybersecurity."),
         "span": "md:col-span-8", "variant": "light", "decorativeIcon": "rocket_launch"},
        {"icon": "shield_lock", "title": "Integrity",
         "description": "Uncompromising honesty in our partnerships and security in our deliveries. Trust is our primary currency.",
         "span": "md:col-span-4", "variant": "dark"},
        {"icon": "precision_manufacturing", "title": "Engineering Excellence",
         "description": "Quality is not an act, but a habit. We employ rigorous peer reviews and automated testing for every build.",
         "span": "md:col-span-4", "variant": "light"},
        {"icon": "verified", "title": "Quality",
         "description": "Every deliverable is held to enterprise-grade standards, validated through structured QA and continuous review.",
         "span": "md:col-span-4", "variant": "light"},
        {"icon": "workspace_premium", "title": "Customer Success",
         "description": "Our engagements are measured by our clients' outcomes, not just our delivery milestones.",
         "span": "md:col-span-4", "variant": "dark"},
        {"icon": "handshake", "title": "Ownership",
         "description": "Every engineer treats client systems as their own — accountable end-to-end, not just for their slice of the code.",
         "span": "md:col-span-4", "variant": "light"},
        {"icon": "visibility", "title": "Transparency",
         "description": "Clear communication, honest timelines, and open access to project status — no surprises, no black boxes.",
         "span": "md:col-span-4", "variant": "light"},
        {"icon": "school", "title": "Continuous Learning",
         "description": "We invest in our engineers' growth continuously, staying ahead of the technology curve as a discipline, not an event.",
         "span": "md:col-span-4", "variant": "dark"},
        {"icon": "security", "title": "Security First",
         "description": "Security is designed in from day one of every engagement, not bolted on afterward.",
         "span": "md:col-span-4", "variant": "light"},
        {"icon": "public", "title": "Collaboration",
         "description": ("Operating across 6 countries, our diverse teams bring global perspectives to solve "
                          "local enterprise challenges with unified standards."),
         "span": "md:col-span-8", "variant": "light", "showAvatars": True},
    ]
    timeline = [
        {"year": "2020", "title": "Inception",
         "description": ("Engineered for scale, security, and velocity. We bridge the gap between complex "
                          "enterprise needs and cutting-edge digital implementation."),
         "side": "left"},
        {"year": "2021", "title": "Pan-India Expansion",
         "description": "Opened operational hubs in Mumbai, Hyderabad, and Pune. Surpassed the 500-engineer milestone within 18 months.",
         "side": "right"},
        {"year": "2022", "title": "Global Footprint",
         "description": "Expanded to Dubai and Singapore. Achieved ISO 9001 and ISO 27001 certifications for security and quality management.",
         "side": "left"},
        {"year": "2024", "title": "AI-First Future",
         "description": ("Launching our Global AI Center of Excellence and partnering with Fortune 500 leaders "
                          "to re-engineer their core systems for a generative age."),
         "side": "present", "icon": "rocket_launch"},
    ]
    certifications = [
        {"icon": "verified", "tag": "ISO 9001", "label": "Quality Management"},
        {"icon": "lock_person", "tag": "ISO 27001", "label": "Information Security"},
        {"icon": "trophy", "tag": "2023", "label": "Digital Innovator Award"},
    ]
    about_stats = [
        {"value": "285+", "label": "Employees", "subtitle": "Deep bench of specialists across domains"},
        {"value": "430+", "label": "Projects Delivered", "subtitle": "Consistent on-time, on-budget delivery"},
        {"value": "120+", "label": "Enterprise Clients", "subtitle": "Trusted by leading organizations worldwide"},
        {"value": "35+", "label": "Technology Partners", "subtitle": "A global ecosystem of delivery partners"},
        {"value": "18+", "label": "Countries Served", "subtitle": "Delivery hubs spanning the globe"},
        {"value": "5", "label": "Years in Business", "subtitle": "Founded in 2020, built for the long term"},
        {"value": "98%", "label": "Success Rate", "subtitle": "Projects delivered on scope and on schedule"},
    ]
    value = {
        "coreValues": core_values,
        "timeline": timeline,
        "certifications": certifications,
        "aboutStats": about_stats,
    }
    setting, created = await _get_or_create(db, Setting, {"key": "about_content"}, {"value": value, "group": "about"})
    if not created:
        setting.value = value
    print("About-page content settings seeded")


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------
async def run() -> None:
    if settings.env.lower() in {"production", "prod"}:
        raise SystemExit(
            "Refusing to run the demo CMS content seed against ENV=production. "
            "This creates fictional demo content (projects, testimonials, partners) "
            "and is for local/dev/staging only."
        )

    async with AsyncSessionLocal() as db:
        super_admin = (await db.execute(select(User).where(User.email == user_seed.SUPER_ADMIN_EMAIL))).scalar_one_or_none()
        marketing_user = (await db.execute(select(User).where(User.email == user_seed.MARKETING_EMAIL))).scalar_one_or_none()
        developer_user = (await db.execute(select(User).where(User.email == user_seed.DEVELOPER_EMAIL))).scalar_one_or_none()
        pm_user = (await db.execute(select(User).where(User.email == user_seed.PM_EMAIL))).scalar_one_or_none()

        if not super_admin:
            raise SystemExit(
                "No seeded users found (superadmin@vpdtechnologies.com is missing). "
                "This script links to app/seeders/seed.py's demo users for authorship — "
                "run `python scripts/migrations/002_seed_users.py` first."
            )

        author_ids = [u.id for u in (marketing_user, super_admin, developer_user) if u]
        pm_ids = [u.id for u in (pm_user, developer_user) if u]

        industries = await seed_industries(db)
        categories = await seed_categories(db)
        await seed_services(db, industries)
        await seed_solutions(db)
        await seed_technologies(db)
        await seed_products(db)
        await seed_partners(db)
        await seed_awards(db)
        await seed_faqs(db)
        await seed_downloads(db)
        await seed_resources(db, author_ids[0] if author_ids else None)
        await seed_events(db)
        await seed_careers(db)
        await seed_blogs(db, categories, author_ids)
        await seed_testimonials(db)
        projects = await seed_projects(db, pm_ids)
        await seed_case_studies(db, projects)
        await seed_portfolio(db, projects)
        await seed_gallery(db, projects)
        await seed_page_contents(db)
        await seed_stats_settings(db)
        await seed_leadership(db)
        await seed_offices(db)
        await seed_company_info(db)
        await seed_about_content(db)

        await db.commit()
        print(f"\nCMS content seeding complete. New rows this run: {_counts}")

    await log_audit(
        user_id=super_admin.id,
        action="cms.bootstrap_seed",
        entity_type="cms_seed",
        entity_id=None,
        log_metadata={"source": "scripts/migrations/003_cms_data.py", "new_rows_by_table": _counts},
    )
    print("Audit log entry written for this CMS seed run.")


if __name__ == "__main__":
    asyncio.run(run())

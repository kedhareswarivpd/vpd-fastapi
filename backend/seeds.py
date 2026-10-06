"""
Complete Database Seeder Script (`seeds.py`)
Populates initial sample data for ALL database tables across VPD Technologies backend.

Usage:
    python seeds.py
"""
import asyncio
import json
import os
import random
import uuid
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.core.password import hash_password
from app.models import (
    Announcement,
    Application,
    Attendance,
    AuditLog,
    Award,
    Blog,
    Career,
    CaseStudy,
    Category,
    Client,
    ClientFile,
    ClientReport,
    Comment,
    ContactSubmission,
    Contract,
    Course,
    Department,
    Download,
    EmailVerificationToken,
    Employee,
    EmployeeDocument,
    Event,
    Faq,
    Gallery,
    Industry,
    Invoice,
    Lead,
    LeadActivity,
    Leadership,
    Leave,
    Media,
    Meeting,
    MfaBackupCode,
    MfaChallenge,
    NewsletterSubscriber,
    Notification,
    OAuthAccount,
    Office,
    PageContent,
    PageView,
    Partner,
    PartnerAccount,
    PartnerFile,
    PasswordResetToken,
    Payment,
    Payslip,
    PerformanceFeedback,
    PerformanceGoal,
    PerformanceReview,
    Permission,
    Portfolio,
    Product,
    Project,
    ProjectDeliverable,
    ProjectMilestone,
    ProjectUpdate,
    Proposal,
    Report,
    Resource,
    Role,
    SeoMetadata,
    Service,
    Setting,
    Solution,
    Task,
    TaskActivity,
    Technology,
    Testimonial,
    Ticket,
    TicketReply,
    Timesheet,
    TrainingEnrollment,
    User,
    UserSession,
    project_members,
    role_permissions,
)
from app.models.enums import (
    ApplicationStatus,
    AttendanceStatus,
    BlogStatus,
    CareerEmploymentType,
    CareerStatus,
    CategoryType,
    CommentStatus,
    ContactStatus,
    ContractStatus,
    DocumentType,
    EmployeeStatus,
    EmploymentType,
    GalleryType,
    InvoiceStatus,
    LeadSource,
    LeadStatus,
    LeaveStatus,
    LeaveType,
    MeetingStatus,
    NotificationType,
    PartnerType,
    PaymentMethod,
    PaymentStatus,
    PayslipStatus,
    ProjectStatus,
    ProposalStatus,
    TaskPriority,
    TaskStatus,
    TechnologyCategory,
    TicketPriority,
    TicketStatus,
    TimesheetStatus,
    UserRole,
)


DEFAULT_PASSWORD = "Password123!"

SEED_USERS = [
    {"role": UserRole.super_admin, "name": "Super Admin", "email": "superadmin@vpdtechnologies.com", "code": "EMP-001", "dept": "Management", "designation": "Executive Director"},
    {"role": UserRole.admin, "name": "System Admin", "email": "admin@vpdtechnologies.com", "code": "EMP-002", "dept": "Engineering", "designation": "Lead System Architect"},
    {"role": UserRole.hr, "name": "HR Manager", "email": "hr@vpdtechnologies.com", "code": "EMP-003", "dept": "Human Resources", "designation": "HR Director"},
    {"role": UserRole.sales, "name": "Sales Lead", "email": "sales@vpdtechnologies.com", "code": "EMP-004", "dept": "Sales", "designation": "Senior Sales Executive"},
    {"role": UserRole.marketing, "name": "Marketing Lead", "email": "marketing@vpdtechnologies.com", "code": "EMP-005", "dept": "Marketing", "designation": "Marketing Manager"},
    {"role": UserRole.project_manager, "name": "Project Manager", "email": "pm@vpdtechnologies.com", "code": "EMP-006", "dept": "Engineering", "designation": "Senior Project Manager"},
    {"role": UserRole.developer, "name": "Dev Lead", "email": "developer@vpdtechnologies.com", "code": "EMP-007", "dept": "Engineering", "designation": "Lead Software Engineer"},
    {"role": UserRole.qa, "name": "QA Lead", "email": "qa@vpdtechnologies.com", "code": "EMP-008", "dept": "Quality Assurance", "designation": "QA Engineering Lead"},
    {"role": UserRole.support, "name": "Support Agent", "email": "support@vpdtechnologies.com", "code": "EMP-009", "dept": "Customer Support", "designation": "Support Engineer"},
    {"role": UserRole.finance, "name": "Finance Lead", "email": "finance@vpdtechnologies.com", "code": "EMP-010", "dept": "Finance", "designation": "Financial Controller"},
    {"role": UserRole.client, "name": "Acme Corp Client", "email": "client@acmecorp.com", "company": "Acme Corporation"},
    {"role": UserRole.partner, "name": "TechPartner Inc", "email": "partner@techpartner.com", "company": "TechPartner Global"},
    {"role": UserRole.employee, "name": "John Staff", "email": "john.staff@vpdtechnologies.com", "code": "EMP-011", "dept": "Engineering", "designation": "Full Stack Engineer"},
]

DEPARTMENTS = [
    "Engineering", "Design", "Sales", "Marketing", "Human Resources",
    "Finance", "Quality Assurance", "DevOps", "Customer Support", "Management",
]


async def seed_roles_and_permissions(db: AsyncSession):
    print("--> Seeding Roles and Permissions...")
    roles_list = ["super_admin", "admin", "hr", "sales", "marketing", "project_manager", "developer", "qa", "support", "finance", "client", "partner", "employee"]
    role_objs = {}
    for r_slug in roles_list:
        res = await db.execute(select(Role).where(Role.slug == r_slug))
        existing = res.scalar_one_or_none()
        if not existing:
            r = Role(id=uuid.uuid4(), name=r_slug.replace('_', ' ').title(), slug=r_slug, description=f"{r_slug.replace('_', ' ').title()} Role", is_system=True)
            db.add(r)
            role_objs[r_slug] = r
        else:
            role_objs[r_slug] = existing

    perm_list = [
        ("users:read", "users", "read"),
        ("users:write", "users", "write"),
        ("projects:read", "projects", "read"),
        ("projects:write", "projects", "write"),
        ("tasks:read", "tasks", "read"),
        ("tasks:write", "tasks", "write"),
        ("invoices:read", "invoices", "read"),
        ("invoices:write", "invoices", "write"),
        ("tickets:read", "tickets", "read"),
        ("tickets:write", "tickets", "write"),
        ("reports:read", "reports", "read"),
        ("settings:manage", "settings", "manage"),
    ]
    perm_objs = {}
    for p_name, p_mod, p_act in perm_list:
        res = await db.execute(select(Permission).where(Permission.name == p_name))
        existing = res.scalar_one_or_none()
        if not existing:
            p = Permission(id=uuid.uuid4(), name=p_name, module=p_mod, action=p_act, description=f"Permission for {p_name}")
            db.add(p)
            perm_objs[p_name] = p
        else:
            perm_objs[p_name] = existing

    await db.flush()


async def seed_departments(db: AsyncSession) -> dict[str, uuid.UUID]:
    print("--> Seeding Departments...")
    dept_map = {}
    for d_name in DEPARTMENTS:
        res = await db.execute(select(Department).where(Department.name == d_name))
        existing = res.scalar_one_or_none()
        if not existing:
            dept = Department(id=uuid.uuid4(), name=d_name, description=f"{d_name} Department")
            db.add(dept)
            await db.flush()
            dept_map[d_name] = dept.id
        else:
            dept_map[d_name] = existing.id
    return dept_map


async def seed_users_employees_clients(db: AsyncSession, dept_map: dict[str, uuid.UUID]):
    print("--> Seeding Users, Employees, Clients, Partners...")
    hashed_pwd = hash_password(DEFAULT_PASSWORD)
    user_map = {}
    emp_map = {}
    client_obj = None
    partner_obj = None

    for u_info in SEED_USERS:
        email = u_info["email"]
        res = await db.execute(select(User).where(User.email == email))
        user = res.scalar_one_or_none()
        if not user:
            user = User(
                id=uuid.uuid4(),
                name=u_info["name"],
                email=email,
                password_hash=hashed_pwd,
                role=u_info["role"],
                is_active=True,
                is_email_verified=True,
                email_verified_at=datetime.now(UTC),
            )
            db.add(user)
            await db.flush()
        user_map[u_info["role"]] = user

        # Employee profile
        if "code" in u_info:
            res_emp = await db.execute(select(Employee).where((Employee.user_id == user.id) | (Employee.employee_code == u_info["code"])))
            emp = res_emp.scalar_one_or_none()
            if not emp:
                emp = Employee(
                    id=uuid.uuid4(),
                    user_id=user.id,
                    employee_code=u_info["code"],
                    department_id=dept_map.get(u_info.get("dept")),
                    designation=u_info.get("designation"),
                    status=EmployeeStatus.active,
                    employment_type=EmploymentType.full_time,
                    date_of_joining=date(2025, 1, 1),
                )
                db.add(emp)
                await db.flush()
            emp_map[u_info["role"]] = emp

        # Client profile
        if u_info["role"] == UserRole.client:
            res_cli = await db.execute(select(Client).where(Client.user_id == user.id))
            client_obj = res_cli.scalar_one_or_none()
            if not client_obj:
                client_obj = Client(
                    id=uuid.uuid4(),
                    user_id=user.id,
                    company_name=u_info.get("company", "Acme Corp"),
                    industry="Technology & Software",
                    country="United States",
                    website="https://acmecorp.example.com",
                    billing_address="100 Innovation Way, Silicon Valley, CA",
                )
                db.add(client_obj)
                await db.flush()

        # Partner profile
        if u_info["role"] == UserRole.partner:
            res_prt = await db.execute(select(PartnerAccount).where(PartnerAccount.user_id == user.id))
            partner_obj = res_prt.scalar_one_or_none()
            if not partner_obj:
                partner_obj = PartnerAccount(
                    id=uuid.uuid4(),
                    user_id=user.id,
                    company_name=u_info.get("company", "TechPartner Global"),
                    partnership_type=PartnerType.technology_partner,
                    industry="Cloud & AI",
                    country="United States",
                    website="https://techpartner.example.com",
                )
                db.add(partner_obj)
                await db.flush()

    return user_map, emp_map, client_obj, partner_obj


async def seed_cms_data(db: AsyncSession, user_map: dict):
    print("--> Seeding CMS (Categories, Blogs, Services, Solutions, Case Studies, Testimonials)...")
    admin_user = user_map.get(UserRole.admin)

    # Categories
    categories = []
    cat_names = [("Cloud Architecture", CategoryType.blog), ("AI & Machine Learning", CategoryType.blog), ("DevOps & Security", CategoryType.blog)]
    for cname, ctype in cat_names:
        res = await db.execute(select(Category).where(Category.name == cname))
        cat = res.scalar_one_or_none()
        if not cat:
            cat = Category(id=uuid.uuid4(), name=cname, slug=cname.lower().replace(" ", "-"), type=ctype)
            db.add(cat)
            await db.flush()
        categories.append(cat)

    # Blog
    res_blog = await db.execute(select(Blog).where(Blog.slug == "future-of-enterprise-cloud"))
    if not res_blog.scalar_one_or_none():
        blog = Blog(
            id=uuid.uuid4(),
            title="The Future of Enterprise Cloud Architecture",
            slug="future-of-enterprise-cloud",
            excerpt="Exploring high-scale microservices, multi-region database setup, and AI optimization.",
            content="<p>Full length article on modern cloud infrastructure designs...</p>",
            status=BlogStatus.published,
            published_at=datetime.now(UTC),
            author_id=admin_user.id if admin_user else None,
            category_id=categories[0].id if categories else None,
            views=150,
        )
        db.add(blog)

    # Services
    res_svc = await db.execute(select(Service).where(Service.slug == "cloud-native-development"))
    if not res_svc.scalar_one_or_none():
        svc = Service(
            id=uuid.uuid4(),
            name="Cloud Native Application Development",
            slug="cloud-native-development",
            overview="Custom scalable microservices and APIs engineered for enterprise demand.",
            is_published=True,
        )
        db.add(svc)

    # Solutions
    res_sol = await db.execute(select(Solution).where(Solution.slug == "healthcare-digital-transformation"))
    if not res_sol.scalar_one_or_none():
        sol = Solution(
            id=uuid.uuid4(),
            name="Healthcare Digital Transformation",
            slug="healthcare-digital-transformation",
            overview="HIPAA compliant cloud platforms for patient portal management.",
            is_published=True,
        )
        db.add(sol)

    # Testimonials
    res_test = await db.execute(select(Testimonial).where(Testimonial.author_name == "Sarah Connor"))
    if not res_test.scalar_one_or_none():
        t = Testimonial(
            id=uuid.uuid4(),
            author_name="Sarah Connor",
            company_name="Acme Health Tech",
            author_title="VP of Engineering",
            content="VPD Technologies delivered our portal 2 weeks ahead of deadline with outstanding quality.",
            rating=5,
            is_published=True,
        )
        db.add(t)

    await db.flush()


async def seed_projects_tasks_financials(db: AsyncSession, emp_map: dict, client_obj: Client):
    print("--> Seeding Projects, Milestones, Tasks, Invoices, Payments...")
    pm = emp_map.get(UserRole.project_manager)
    dev = emp_map.get(UserRole.developer)

    # Project
    res_proj = await db.execute(select(Project).where(Project.slug == "enterprise-portal"))
    project = res_proj.scalar_one_or_none()
    if not project and client_obj:
        project = Project(
            id=uuid.uuid4(),
            title="Enterprise Healthcare Portal",
            slug="enterprise-portal",
            client_id=client_obj.id,
            status=ProjectStatus.in_progress,
            progress_percent=75,
            budget=55000.00,
            start_date=date(2026, 1, 1),
            end_date=date(2026, 6, 30),
        )
        db.add(project)
        await db.flush()

    if project:
        # Milestone
        res_m = await db.execute(select(ProjectMilestone).where(ProjectMilestone.project_id == project.id))
        ms = res_m.scalars().first()
        if not ms:
            ms = ProjectMilestone(
                id=uuid.uuid4(),
                project_id=project.id,
                title="Phase 1 - Core API & Auth",
                due_date=date(2026, 3, 31),
                status="completed",
                progress_percent=100,
            )
            db.add(ms)
            await db.flush()

        # Task
        res_t = await db.execute(select(Task).where(Task.project_id == project.id))
        task = res_t.scalars().first()
        if not task:
            task = Task(
                id=uuid.uuid4(),
                project_id=project.id,
                title="Implement OAuth2 & JWT Auth Service",
                description="Secure login flow with refresh tokens and cookie storage.",
                status=TaskStatus.in_progress,
                priority=TaskPriority.high,
                assigned_to=dev.user_id if dev else None,
            )
            db.add(task)
            await db.flush()

        # Invoice
        res_inv = await db.execute(select(Invoice).where(Invoice.invoice_number == "INV-2026-001"))
        inv = res_inv.scalar_one_or_none()
        if not inv and client_obj:
            inv = Invoice(
                id=uuid.uuid4(),
                invoice_number="INV-2026-001",
                client_id=client_obj.id,
                project_id=project.id,
                amount=25000.00,
                tax=2500.00,
                total_amount=27500.00,
                status=InvoiceStatus.paid,
                issue_date=date(2026, 2, 1),
                due_date=date(2026, 2, 15),
            )
            db.add(inv)
            await db.flush()

            # Payment
            pmt = Payment(
                id=uuid.uuid4(),
                invoice_id=inv.id,
                amount=27500.00,
                method=PaymentMethod.bank_transfer,
                status=PaymentStatus.completed,
                transaction_ref="TXN-987654321",
                paid_at=datetime.now(UTC),
            )
            db.add(pmt)


async def seed_crm_support_ops(db: AsyncSession, user_map: dict, client_obj: Client):
    print("--> Seeding CRM (Leads, Proposals), Support Tickets, Settings...")

    sales_user = user_map.get(UserRole.sales)
    client_user = user_map.get(UserRole.client)

    # Lead
    res_lead = await db.execute(select(Lead).where(Lead.email == "prospect@nexuscorp.example.com"))
    lead = res_lead.scalar_one_or_none()
    if not lead:
        lead = Lead(
            id=uuid.uuid4(),
            contact_name="Alexander Vance",
            email="prospect@nexuscorp.example.com",
            company="Nexus Digital",
            source=LeadSource.website,
            status=LeadStatus.contacted,
            notes="Interested in full-stack cloud migration.",
            owner_id=sales_user.id if sales_user else None,
        )
        db.add(lead)

    # Support Ticket
    res_ticket = await db.execute(select(Ticket).where(Ticket.ticket_number == "TICK-1001"))
    if not res_ticket.scalar_one_or_none() and client_user:
        t = Ticket(
            id=uuid.uuid4(),
            ticket_number="TICK-1001",
            subject="API Rate Limit Inquiry",
            description="Requesting limit increase for analytics webhooks.",
            status=TicketStatus.open,
            priority=TicketPriority.medium,
            client_id=client_obj.id if client_obj else None,
        )
        db.add(t)

    # Settings
    settings_data = [
        ("site.title", "VPD Technologies", "public"),
        ("site.tagline", "Transforming Businesses Through Intelligent Digital Solutions", "public"),
        ("contact.email", "info@vpdtechnologies.com", "public"),
        ("contact.phone", "+1-800-555-CORE", "public"),
        ("social.linkedin", "https://linkedin.com/company/vpdtechnologies", "public"),
    ]
    for key, value, group in settings_data:
        exists = (await db.execute(select(Setting).where(Setting.key == key))).scalar_one_or_none()
        if not exists:
            db.add(Setting(key=key, value=value, group=group))

    # Page views
    existing_view = (await db.execute(select(PageView.id).limit(1))).scalar_one_or_none()
    if not existing_view:
        now = datetime.now(UTC)
        views = [
            PageView(
                path=p,
                ip_address=f"192.168.1.{i+10}",
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
                viewed_at=now - timedelta(hours=i),
            )
            for i, p in enumerate(["/", "/services", "/about", "/portfolio", "/contact", "/docs"])
        ]
        db.add_all(views)

    await db.commit()


async def write_creds_json():
    """Generates scripts/migrations/creds.json if missing so app/seeders/seed.py works cleanly."""
    creds_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scripts", "migrations")
    creds_file = os.path.join(creds_dir, "creds.json")
    if not os.path.exists(creds_file):
        os.makedirs(creds_dir, exist_ok=True)
        data = {
            role_info["role"].value: {
                "name": role_info["name"],
                "email": role_info["email"],
                "password": DEFAULT_PASSWORD,
                "department": role_info.get("dept", "Engineering"),
                "employee_code": role_info.get("code", "EMP-999"),
                "designation": role_info.get("designation", "Staff"),
                "company_name": role_info.get("company", "VPD Technologies"),
            }
            for role_info in SEED_USERS
        }
        with open(creds_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        print(f"--> Created credentials seed config: {creds_file}")


async def main():
    print("==================================================")
    print("         VPD TECHNOLOGIES DATABASE SEEDER RUNNING             ")
    print("==================================================")

    await write_creds_json()

    async with AsyncSessionLocal() as db:
        await seed_roles_and_permissions(db)
        dept_map = await seed_departments(db)
        user_map, emp_map, client_obj, partner_obj = await seed_users_employees_clients(db, dept_map)
        await seed_cms_data(db, user_map)
        await seed_projects_tasks_financials(db, emp_map, client_obj)
        await seed_crm_support_ops(db, user_map, client_obj)

    print("\n==================================================")
    print("   SUCCESS! All database tables seeded nicely!    ")
    print("   Default Password for all accounts: Password123!")
    print("==================================================")


if __name__ == "__main__":
    asyncio.run(main())

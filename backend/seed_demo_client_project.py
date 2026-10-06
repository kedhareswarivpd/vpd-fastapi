import asyncio
import uuid
from datetime import UTC, date, datetime
from sqlalchemy import select
from app.core.database import AsyncSessionLocal
from app.models.client import Client
from app.models.employee import Employee
from app.models.enums import ProjectStatus
from app.models.project import Project
from app.models.project_milestone import ProjectMilestone
from app.models.project_deliverable import ProjectDeliverable
from app.models.project_update import ProjectUpdate

async def main():
    async with AsyncSessionLocal() as db:
        # Find client
        client = (await db.execute(select(Client))).scalars().first()
        if not client:
            print("No client found!")
            return
        
        employee = (await db.execute(select(Employee))).scalars().first()
        print(f"Assigning project to client {client.id} ({client.company_name})")

        # Check existing project for client
        existing = (await db.execute(select(Project).where(Project.client_id == client.id))).scalars().first()
        if not existing:
            project = Project(
                id=uuid.uuid4(),
                title="Enterprise Healthcare Portal",
                slug="enterprise-healthcare-portal",
                client_id=client.id,
                status=ProjectStatus.completed,
                progress_percent=100,
                budget=45000.00,
                start_date=date(2026, 1, 15),
                end_date=date(2026, 8, 30),
                client_review_status="pending",
                completion_submitted_at=datetime.now(UTC),
            )
            db.add(project)
            await db.flush()
        else:
            project = existing
            project.client_review_status = "pending"
            project.status = ProjectStatus.completed
            project.progress_percent = 100
            await db.flush()

        # Add milestone
        m1 = (await db.execute(select(ProjectMilestone).where(ProjectMilestone.project_id == project.id))).scalars().first()
        if not m1:
            m1 = ProjectMilestone(
                project_id=project.id,
                title="Architecture & MVP Release",
                due_date=date(2026, 5, 30),
                status="completed",
                progress_percent=100,
                client_visible=True,
                order=1
            )
            m2 = ProjectMilestone(
                project_id=project.id,
                title="Final Security & Performance Sign-off",
                due_date=date(2026, 8, 25),
                status="completed",
                progress_percent=100,
                client_visible=True,
                order=2
            )
            db.add_all([m1, m2])
            await db.flush()

        # Add deliverable
        d1 = (await db.execute(select(ProjectDeliverable).where(ProjectDeliverable.project_id == project.id))).scalars().first()
        if not d1:
            d1 = ProjectDeliverable(
                project_id=project.id,
                title="Production Release Package v1.0",
                description="Final build artifacts, docker images, and architecture documentation.",
                status="submitted",
                submitted_at=datetime.now(UTC)
            )
            db.add(d1)
            await db.flush()

        # Add progress update
        if employee:
            u1 = (await db.execute(select(ProjectUpdate).where(ProjectUpdate.project_id == project.id))).scalars().first()
            if not u1:
                u1 = ProjectUpdate(
                    project_id=project.id,
                    employee_id=employee.id,
                    update_text="Completed deployment verification, QA test suite passing 100%, and prepared delivery package for client sign-off.",
                    client_visible=True
                )
                db.add(u1)

        await db.commit()
        print(f"Successfully configured demo project '{project.title}' (ID: {project.id}) for client!")

if __name__ == "__main__":
    asyncio.run(main())

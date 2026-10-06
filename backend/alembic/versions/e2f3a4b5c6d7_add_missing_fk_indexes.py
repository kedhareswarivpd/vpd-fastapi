"""Add missing foreign-key indexes (CF-AUD-011 / CF-BE)

Every FK column below had no index, forcing sequential scans on joins and
filters (list-by-client, list-by-employee, tenant/authorization lookups,
etc.) — the previous audit found only 6 secondary indexes and zero FK
indexes across 58 tables; this closes that gap without guessing at
column choice, since every column here backs a real FK relationship.

Revision ID: e2f3a4b5c6d7
Revises: d1e2f3a4b5c6
Create Date: 2026-08-21 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op

revision: str = 'e2f3a4b5c6d7'
down_revision: Union[str, None] = 'd1e2f3a4b5c6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index('ix_applications_career_id', 'applications', ['career_id'], unique=False, if_not_exists=True)
    op.create_index('ix_attendance_employee_id', 'attendance', ['employee_id'], unique=False, if_not_exists=True)
    op.create_index('ix_audit_logs_user_id', 'audit_logs', ['user_id'], unique=False, if_not_exists=True)
    op.create_index('ix_blogs_category_id', 'blogs', ['category_id'], unique=False, if_not_exists=True)
    op.create_index('ix_blogs_author_id', 'blogs', ['author_id'], unique=False, if_not_exists=True)
    op.create_index('ix_case_studies_project_id', 'case_studies', ['project_id'], unique=False, if_not_exists=True)
    op.create_index('ix_client_files_client_id', 'client_files', ['client_id'], unique=False, if_not_exists=True)
    op.create_index('ix_client_reports_client_id', 'client_reports', ['client_id'], unique=False, if_not_exists=True)
    op.create_index('ix_clients_account_manager_id', 'clients', ['account_manager_id'], unique=False, if_not_exists=True)
    op.create_index('ix_comments_blog_id', 'comments', ['blog_id'], unique=False, if_not_exists=True)
    op.create_index('ix_courses_created_by', 'courses', ['created_by'], unique=False, if_not_exists=True)
    op.create_index('ix_employee_documents_employee_id', 'employee_documents', ['employee_id'], unique=False, if_not_exists=True)
    op.create_index('ix_employees_department_id', 'employees', ['department_id'], unique=False, if_not_exists=True)
    op.create_index('ix_employees_reporting_manager_id', 'employees', ['reporting_manager_id'], unique=False, if_not_exists=True)
    op.create_index('ix_gallery_project_id', 'gallery', ['project_id'], unique=False, if_not_exists=True)
    op.create_index('ix_invoices_client_id', 'invoices', ['client_id'], unique=False, if_not_exists=True)
    op.create_index('ix_invoices_project_id', 'invoices', ['project_id'], unique=False, if_not_exists=True)
    op.create_index('ix_leads_contact_submission_id', 'leads', ['contact_submission_id'], unique=False, if_not_exists=True)
    op.create_index('ix_leads_owner_id', 'leads', ['owner_id'], unique=False, if_not_exists=True)
    op.create_index('ix_leads_converted_client_id', 'leads', ['converted_client_id'], unique=False, if_not_exists=True)
    op.create_index('ix_leaves_employee_id', 'leaves', ['employee_id'], unique=False, if_not_exists=True)
    op.create_index('ix_leaves_approved_by', 'leaves', ['approved_by'], unique=False, if_not_exists=True)
    op.create_index('ix_media_uploaded_by', 'media', ['uploaded_by'], unique=False, if_not_exists=True)
    op.create_index('ix_meetings_project_id', 'meetings', ['project_id'], unique=False, if_not_exists=True)
    op.create_index('ix_meetings_client_id', 'meetings', ['client_id'], unique=False, if_not_exists=True)
    op.create_index('ix_meetings_organizer_id', 'meetings', ['organizer_id'], unique=False, if_not_exists=True)
    op.create_index('ix_notifications_user_id', 'notifications', ['user_id'], unique=False, if_not_exists=True)
    op.create_index('ix_payments_invoice_id', 'payments', ['invoice_id'], unique=False, if_not_exists=True)
    op.create_index('ix_payslips_employee_id', 'payslips', ['employee_id'], unique=False, if_not_exists=True)
    op.create_index('ix_performance_reviews_employee_id', 'performance_reviews', ['employee_id'], unique=False, if_not_exists=True)
    op.create_index('ix_performance_reviews_reviewer_id', 'performance_reviews', ['reviewer_id'], unique=False, if_not_exists=True)
    op.create_index('ix_portfolios_project_id', 'portfolios', ['project_id'], unique=False, if_not_exists=True)
    op.create_index('ix_projects_client_id', 'projects', ['client_id'], unique=False, if_not_exists=True)
    op.create_index('ix_projects_project_manager_id', 'projects', ['project_manager_id'], unique=False, if_not_exists=True)
    op.create_index('ix_proposals_lead_id', 'proposals', ['lead_id'], unique=False, if_not_exists=True)
    op.create_index('ix_proposals_created_by', 'proposals', ['created_by'], unique=False, if_not_exists=True)
    op.create_index('ix_reports_generated_by', 'reports', ['generated_by'], unique=False, if_not_exists=True)
    op.create_index('ix_resources_author_id', 'resources', ['author_id'], unique=False, if_not_exists=True)
    op.create_index('ix_tasks_project_id', 'tasks', ['project_id'], unique=False, if_not_exists=True)
    op.create_index('ix_tasks_assigned_to', 'tasks', ['assigned_to'], unique=False, if_not_exists=True)
    op.create_index('ix_testimonials_client_id', 'testimonials', ['client_id'], unique=False, if_not_exists=True)
    op.create_index('ix_ticket_replies_ticket_id', 'ticket_replies', ['ticket_id'], unique=False, if_not_exists=True)
    op.create_index('ix_ticket_replies_user_id', 'ticket_replies', ['user_id'], unique=False, if_not_exists=True)
    op.create_index('ix_tickets_client_id', 'tickets', ['client_id'], unique=False, if_not_exists=True)
    op.create_index('ix_tickets_assigned_to', 'tickets', ['assigned_to'], unique=False, if_not_exists=True)
    op.create_index('ix_timesheets_employee_id', 'timesheets', ['employee_id'], unique=False, if_not_exists=True)
    op.create_index('ix_timesheets_project_id', 'timesheets', ['project_id'], unique=False, if_not_exists=True)
    op.create_index('ix_timesheets_task_id', 'timesheets', ['task_id'], unique=False, if_not_exists=True)
    op.create_index('ix_training_enrollments_employee_id', 'training_enrollments', ['employee_id'], unique=False, if_not_exists=True)
    op.create_index('ix_training_enrollments_course_id', 'training_enrollments', ['course_id'], unique=False, if_not_exists=True)


def downgrade() -> None:
    op.drop_index('ix_applications_career_id', table_name='applications', if_exists=True)
    op.drop_index('ix_attendance_employee_id', table_name='attendance', if_exists=True)
    op.drop_index('ix_audit_logs_user_id', table_name='audit_logs', if_exists=True)
    op.drop_index('ix_blogs_category_id', table_name='blogs', if_exists=True)
    op.drop_index('ix_blogs_author_id', table_name='blogs', if_exists=True)
    op.drop_index('ix_case_studies_project_id', table_name='case_studies', if_exists=True)
    op.drop_index('ix_client_files_client_id', table_name='client_files', if_exists=True)
    op.drop_index('ix_client_reports_client_id', table_name='client_reports', if_exists=True)
    op.drop_index('ix_clients_account_manager_id', table_name='clients', if_exists=True)
    op.drop_index('ix_comments_blog_id', table_name='comments', if_exists=True)
    op.drop_index('ix_courses_created_by', table_name='courses', if_exists=True)
    op.drop_index('ix_employee_documents_employee_id', table_name='employee_documents', if_exists=True)
    op.drop_index('ix_employees_department_id', table_name='employees', if_exists=True)
    op.drop_index('ix_employees_reporting_manager_id', table_name='employees', if_exists=True)
    op.drop_index('ix_gallery_project_id', table_name='gallery', if_exists=True)
    op.drop_index('ix_invoices_client_id', table_name='invoices', if_exists=True)
    op.drop_index('ix_invoices_project_id', table_name='invoices', if_exists=True)
    op.drop_index('ix_leads_contact_submission_id', table_name='leads', if_exists=True)
    op.drop_index('ix_leads_owner_id', table_name='leads', if_exists=True)
    op.drop_index('ix_leads_converted_client_id', table_name='leads', if_exists=True)
    op.drop_index('ix_leaves_employee_id', table_name='leaves', if_exists=True)
    op.drop_index('ix_leaves_approved_by', table_name='leaves', if_exists=True)
    op.drop_index('ix_media_uploaded_by', table_name='media', if_exists=True)
    op.drop_index('ix_meetings_project_id', table_name='meetings', if_exists=True)
    op.drop_index('ix_meetings_client_id', table_name='meetings', if_exists=True)
    op.drop_index('ix_meetings_organizer_id', table_name='meetings', if_exists=True)
    op.drop_index('ix_notifications_user_id', table_name='notifications', if_exists=True)
    op.drop_index('ix_payments_invoice_id', table_name='payments', if_exists=True)
    op.drop_index('ix_payslips_employee_id', table_name='payslips', if_exists=True)
    op.drop_index('ix_performance_reviews_employee_id', table_name='performance_reviews', if_exists=True)
    op.drop_index('ix_performance_reviews_reviewer_id', table_name='performance_reviews', if_exists=True)
    op.drop_index('ix_portfolios_project_id', table_name='portfolios', if_exists=True)
    op.drop_index('ix_projects_client_id', table_name='projects', if_exists=True)
    op.drop_index('ix_projects_project_manager_id', table_name='projects', if_exists=True)
    op.drop_index('ix_proposals_lead_id', table_name='proposals', if_exists=True)
    op.drop_index('ix_proposals_created_by', table_name='proposals', if_exists=True)
    op.drop_index('ix_reports_generated_by', table_name='reports', if_exists=True)
    op.drop_index('ix_resources_author_id', table_name='resources', if_exists=True)
    op.drop_index('ix_tasks_project_id', table_name='tasks', if_exists=True)
    op.drop_index('ix_tasks_assigned_to', table_name='tasks', if_exists=True)
    op.drop_index('ix_testimonials_client_id', table_name='testimonials', if_exists=True)
    op.drop_index('ix_ticket_replies_ticket_id', table_name='ticket_replies', if_exists=True)
    op.drop_index('ix_ticket_replies_user_id', table_name='ticket_replies', if_exists=True)
    op.drop_index('ix_tickets_client_id', table_name='tickets', if_exists=True)
    op.drop_index('ix_tickets_assigned_to', table_name='tickets', if_exists=True)
    op.drop_index('ix_timesheets_employee_id', table_name='timesheets', if_exists=True)
    op.drop_index('ix_timesheets_project_id', table_name='timesheets', if_exists=True)
    op.drop_index('ix_timesheets_task_id', table_name='timesheets', if_exists=True)
    op.drop_index('ix_training_enrollments_employee_id', table_name='training_enrollments', if_exists=True)
    op.drop_index('ix_training_enrollments_course_id', table_name='training_enrollments', if_exists=True)

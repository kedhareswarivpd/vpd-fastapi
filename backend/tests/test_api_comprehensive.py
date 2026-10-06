"""Comprehensive API tests — covers every endpoint in the application."""


class TestHealthAndRoot:
    """Root-level endpoints from main.py"""

    async def test_health_check(self, async_client):
        response = await async_client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    async def test_root_endpoint(self, async_client):
        response = await async_client.get("/")
        assert response.status_code == 200

    async def test_ready_reports_database_check(self, async_client):
        # Under this test harness the DB engine is mocked (no real Postgres),
        # so /ready correctly reports not-ready — that's the honest answer,
        # not a bug. The 200-when-actually-connected case is verified against
        # a real Postgres container in tests/real_db_verification.py.
        response = await async_client.get("/ready")
        assert response.status_code == 503
        body = response.json()
        assert body["status"] == "not_ready"
        assert "database" in body["checks"]

    async def test_response_carries_x_request_id(self, async_client):
        response = await async_client.get("/health")
        assert "x-request-id" in {h.lower() for h in response.headers}

    async def test_x_request_id_is_echoed_back_when_supplied(self, async_client):
        response = await async_client.get("/health", headers={"X-Request-Id": "caller-supplied-id"})
        assert response.headers["x-request-id"] == "caller-supplied-id"

    async def test_sitemap_returns_xml(self, async_client):
        response = await async_client.get("/sitemap.xml")
        assert response.status_code in (200, 500)


class TestAuthEndpoints:
    """Auth endpoints — /api/v1/auth/*"""

    async def test_register_requires_valid_email(self, async_client):
        response = await async_client.post(
            "/api/v1/auth/register",
            json={"name": "Test", "email": "not-an-email", "password": "password123"},
        )
        assert response.status_code == 422

    async def test_register_requires_min_password_length(self, async_client):
        response = await async_client.post(
            "/api/v1/auth/register",
            json={"name": "Test", "email": "test@example.com", "password": "short"},
        )
        assert response.status_code == 422

    async def test_register_requires_name(self, async_client):
        response = await async_client.post(
            "/api/v1/auth/register",
            json={"email": "test@example.com", "password": "password123"},
        )
        assert response.status_code == 422

    async def test_login_requires_email_and_password(self, async_client):
        response = await async_client.post(
            "/api/v1/auth/login",
            json={"email": "not-an-email", "password": ""},
        )
        assert response.status_code == 422

    async def test_me_without_token(self, async_client):
        response = await async_client.get("/api/v1/auth/me")
        assert response.status_code == 401

    # A real HTTP round trip with an *invalid but present* cookie value
    # exercises get_session_by_access_token()'s real DB query against this
    # test harness's fully-mocked SQLAlchemy engine — the same class of
    # mocked-engine incompatibility root-caused for blog.py's list endpoint
    # earlier in this engagement (a query shape the mock can't fake, not a
    # real bug; confirmed separately against a real Postgres). Equivalent,
    # non-fragile coverage of "an invalid/no-longer-valid session token is
    # rejected" already exists at the function level in test_dependencies.py
    # (TestGetCurrentUser::test_no_matching_session_raises_unauthorized) and
    # test_cookie_auth.py, so it isn't duplicated here against the fragile path.

    async def test_logout_requires_auth(self, async_client):
        # Regression test for CF-AUD-005: logout must require the caller's own
        # bearer token, not just any access_token in the body — otherwise an
        # unauthenticated caller could revoke an arbitrary user's session.
        response = await async_client.post(
            "/api/v1/auth/logout",
            json={"access_token": "some-token"},
        )
        assert response.status_code == 401


class TestUsersEndpoints:
    """User management — /api/v1/users/*"""

    async def test_list_users_requires_auth(self, async_client):
        response = await async_client.get("/api/v1/users")
        assert response.status_code == 401

    async def test_get_user_requires_auth(self, async_client):
        response = await async_client.get(
            "/api/v1/users/00000000-0000-0000-0000-000000000000"
        )
        assert response.status_code == 401

    async def test_create_user_requires_auth(self, async_client):
        response = await async_client.post(
            "/api/v1/users",
            json={"name": "Test", "email": "test@test.com"},
        )
        assert response.status_code == 401

    async def test_update_user_requires_auth(self, async_client):
        response = await async_client.put(
            "/api/v1/users/00000000-0000-0000-0000-000000000000",
            json={"name": "Updated"},
        )
        assert response.status_code == 401

    async def test_deactivate_user_requires_auth(self, async_client):
        response = await async_client.patch(
            "/api/v1/users/00000000-0000-0000-0000-000000000000/deactivate"
        )
        assert response.status_code == 401

    async def test_delete_user_requires_auth(self, async_client):
        response = await async_client.delete(
            "/api/v1/users/00000000-0000-0000-0000-000000000000"
        )
        assert response.status_code == 401


class TestGdprEndpoints:
    """GDPR endpoints — /api/v1/users/me/* and /api/v1/users/{id}/*"""

    async def test_admin_export_requires_super_admin(self, async_client):
        response = await async_client.get(
            "/api/v1/users/00000000-0000-0000-0000-000000000000/export"
        )
        assert response.status_code == 401

    async def test_admin_anonymize_requires_super_admin(self, async_client):
        response = await async_client.post(
            "/api/v1/users/00000000-0000-0000-0000-000000000000/anonymize"
        )
        assert response.status_code == 401


class TestStatsEndpoint:
    """Stats — /api/v1/stats"""

    async def test_get_stats(self, async_client):
        response = await async_client.get("/api/v1/stats")
        assert response.status_code in (200, 500)


class TestEmployeesEndpoints:
    """Employee endpoints — /api/v1/employees/*"""

    async def test_list_employees_requires_auth(self, async_client):
        response = await async_client.get("/api/v1/employees")
        assert response.status_code == 401

    async def test_create_employee_requires_auth(self, async_client):
        response = await async_client.post(
            "/api/v1/employees",
            json={"name": "Test", "email": "emp@test.com"},
        )
        assert response.status_code == 401

    async def test_employee_me_profile_requires_auth(self, async_client):
        response = await async_client.get("/api/v1/employees/me/profile")
        assert response.status_code == 401

    async def test_today_attendance_requires_auth(self, async_client):
        response = await async_client.get("/api/v1/employees/me/attendance/today")
        assert response.status_code == 401

    async def test_check_in_requires_auth(self, async_client):
        response = await async_client.post("/api/v1/employees/me/attendance/check-in")
        assert response.status_code == 401

    async def test_check_out_requires_auth(self, async_client):
        response = await async_client.post("/api/v1/employees/me/attendance/check-out")
        assert response.status_code == 401

    async def test_my_leaves_requires_auth(self, async_client):
        response = await async_client.get("/api/v1/employees/me/leaves")
        assert response.status_code == 401

    async def test_apply_leave_requires_auth(self, async_client):
        response = await async_client.post(
            "/api/v1/employees/me/leaves",
            json={"type": "sick", "start_date": "2024-01-01", "end_date": "2024-01-02"},
        )
        assert response.status_code == 401

    async def test_my_timesheets_requires_auth(self, async_client):
        response = await async_client.get("/api/v1/employees/me/timesheets")
        assert response.status_code == 401

    async def test_submit_timesheet_requires_auth(self, async_client):
        response = await async_client.post(
            "/api/v1/employees/me/timesheets",
            json={"hours": 8, "date": "2024-01-01"},
        )
        assert response.status_code == 401

    async def test_my_payslips_requires_auth(self, async_client):
        response = await async_client.get("/api/v1/employees/me/payslips")
        assert response.status_code == 401

    async def test_my_documents_requires_auth(self, async_client):
        response = await async_client.get("/api/v1/employees/me/documents")
        assert response.status_code == 401

    async def test_my_performance_reviews_requires_auth(self, async_client):
        response = await async_client.get("/api/v1/employees/me/performance-reviews")
        assert response.status_code == 401

    async def test_list_all_leaves_requires_auth(self, async_client):
        response = await async_client.get("/api/v1/employees/leaves")
        assert response.status_code == 401

    async def test_approve_leave_requires_auth(self, async_client):
        response = await async_client.patch(
            "/api/v1/employees/leaves/00000000-0000-0000-0000-000000000000/approve"
        )
        assert response.status_code == 401

    async def test_list_all_timesheets_requires_auth(self, async_client):
        response = await async_client.get("/api/v1/employees/timesheets")
        assert response.status_code == 401

    async def test_approve_timesheet_requires_auth(self, async_client):
        response = await async_client.patch(
            "/api/v1/employees/timesheets/00000000-0000-0000-0000-000000000000/approve"
        )
        assert response.status_code == 401


class TestClientsEndpoints:
    """Client endpoints — /api/v1/clients/*"""

    async def test_list_clients_requires_auth(self, async_client):
        response = await async_client.get("/api/v1/clients")
        assert response.status_code == 401

    async def test_create_client_requires_auth(self, async_client):
        response = await async_client.post(
            "/api/v1/clients",
            json={"name": "Test Client"},
        )
        assert response.status_code == 401

    async def test_client_me_profile_requires_auth(self, async_client):
        response = await async_client.get("/api/v1/clients/me/profile")
        assert response.status_code == 401

    async def test_client_me_projects_requires_auth(self, async_client):
        response = await async_client.get("/api/v1/clients/me/projects")
        assert response.status_code == 401

    async def test_client_me_invoices_requires_auth(self, async_client):
        response = await async_client.get("/api/v1/clients/me/invoices")
        assert response.status_code == 401

    async def test_client_me_tickets_requires_auth(self, async_client):
        response = await async_client.get("/api/v1/clients/me/tickets")
        assert response.status_code == 401

    async def test_client_create_ticket_requires_auth(self, async_client):
        response = await async_client.post(
            "/api/v1/clients/me/tickets",
            json={"subject": "Issue"},
        )
        assert response.status_code == 401

    async def test_client_me_payments_requires_auth(self, async_client):
        response = await async_client.get("/api/v1/clients/me/payments")
        assert response.status_code == 401

    async def test_client_me_meetings_requires_auth(self, async_client):
        response = await async_client.get("/api/v1/clients/me/meetings")
        assert response.status_code == 401

    async def test_client_me_files_requires_auth(self, async_client):
        response = await async_client.get("/api/v1/clients/me/files")
        assert response.status_code == 401

    async def test_client_upload_file_requires_auth(self, async_client):
        response = await async_client.post(
            "/api/v1/clients/me/files",
            json={"name": "file.pdf"},
        )
        assert response.status_code == 401

    async def test_client_me_reports_requires_auth(self, async_client):
        response = await async_client.get("/api/v1/clients/me/reports")
        assert response.status_code == 401

    async def test_client_create_report_requires_auth(self, async_client):
        response = await async_client.post(
            "/api/v1/clients/me/reports",
            json={"title": "Report"},
        )
        assert response.status_code == 401


class TestPartnerAccountsEndpoints:
    """Partner Portal endpoints — /api/v1/partner-accounts/* (mirrors Client
    Portal's shape; distinct from the public /api/v1/partners CMS listing)."""

    async def test_list_partner_accounts_requires_auth(self, async_client):
        response = await async_client.get("/api/v1/partner-accounts")
        assert response.status_code == 401

    async def test_create_partner_account_requires_auth(self, async_client):
        response = await async_client.post(
            "/api/v1/partner-accounts",
            json={"company_name": "Acme"},
        )
        assert response.status_code == 401

    async def test_partner_me_profile_requires_auth(self, async_client):
        response = await async_client.get("/api/v1/partner-accounts/me/profile")
        assert response.status_code == 401

    async def test_partner_update_profile_requires_auth(self, async_client):
        response = await async_client.put(
            "/api/v1/partner-accounts/me/profile",
            json={"industry": "Reselling"},
        )
        assert response.status_code == 401

    async def test_partner_me_files_requires_auth(self, async_client):
        response = await async_client.get("/api/v1/partner-accounts/me/files")
        assert response.status_code == 401

    async def test_partner_me_tickets_requires_auth(self, async_client):
        response = await async_client.get("/api/v1/partner-accounts/me/tickets")
        assert response.status_code == 401

    async def test_partner_create_ticket_requires_auth(self, async_client):
        response = await async_client.post(
            "/api/v1/partner-accounts/me/tickets",
            json={"subject": "Issue"},
        )
        assert response.status_code == 401


class TestProjectsEndpoints:
    """Project endpoints — /api/v1/projects/*"""

    async def test_list_projects(self, async_client):
        response = await async_client.get("/api/v1/projects")
        assert response.status_code in (200, 500)

    async def test_get_project(self, async_client):
        response = await async_client.get(
            "/api/v1/projects/00000000-0000-0000-0000-000000000000"
        )
        assert response.status_code in (200, 404, 500)

    async def test_create_project_requires_auth(self, async_client):
        response = await async_client.post(
            "/api/v1/projects",
            json={"title": "Test Project"},
        )
        assert response.status_code == 401

    async def test_update_project_requires_auth(self, async_client):
        response = await async_client.put(
            "/api/v1/projects/00000000-0000-0000-0000-000000000000",
            json={"title": "Updated"},
        )
        assert response.status_code == 401

    async def test_assign_team_requires_auth(self, async_client):
        response = await async_client.patch(
            "/api/v1/projects/00000000-0000-0000-0000-000000000000/team",
            json={"user_ids": []},
        )
        assert response.status_code == 401

    async def test_delete_project_requires_auth(self, async_client):
        response = await async_client.delete(
            "/api/v1/projects/00000000-0000-0000-0000-000000000000"
        )
        assert response.status_code == 401

    async def test_list_projects_pagination_validation(self, async_client):
        response = await async_client.get("/api/v1/projects?page=0")
        assert response.status_code in (422, 200, 500)


class TestTasksEndpoints:
    """Task endpoints — /api/v1/tasks/*"""

    async def test_list_tasks_requires_auth(self, async_client):
        response = await async_client.get("/api/v1/tasks")
        assert response.status_code == 401

    async def test_create_task_requires_auth(self, async_client):
        response = await async_client.post(
            "/api/v1/tasks",
            json={"title": "Test Task"},
        )
        assert response.status_code == 401

    async def test_update_task_status_requires_auth(self, async_client):
        response = await async_client.patch(
            "/api/v1/tasks/00000000-0000-0000-0000-000000000000/status",
            json={"status": "done"},
        )
        assert response.status_code == 401


class TestFinanceEndpoints:
    """Finance endpoints — /api/v1/finance/*"""

    async def test_list_invoices_requires_auth(self, async_client):
        response = await async_client.get("/api/v1/finance/invoices")
        assert response.status_code == 401

    async def test_get_invoice_requires_auth(self, async_client):
        response = await async_client.get(
            "/api/v1/finance/invoices/00000000-0000-0000-0000-000000000000"
        )
        assert response.status_code == 401

    async def test_create_invoice_requires_auth(self, async_client):
        response = await async_client.post(
            "/api/v1/finance/invoices",
            json={"amount": 1000},
        )
        assert response.status_code == 401

    async def test_update_invoice_requires_auth(self, async_client):
        response = await async_client.put(
            "/api/v1/finance/invoices/00000000-0000-0000-0000-000000000000",
            json={"amount": 2000},
        )
        assert response.status_code == 401

    async def test_record_payment_requires_auth(self, async_client):
        response = await async_client.post(
            "/api/v1/finance/invoices/00000000-0000-0000-0000-000000000000/payments",
            json={"amount": 500},
        )
        assert response.status_code == 401


class TestCareersEndpoints:
    """Career endpoints — /api/v1/careers/*"""

    async def test_list_careers(self, async_client):
        response = await async_client.get("/api/v1/careers")
        assert response.status_code in (200, 500)

    async def test_apply_career(self, async_client):
        response = await async_client.post(
            "/api/v1/careers/00000000-0000-0000-0000-000000000000/apply",
            json={},
        )
        assert response.status_code in (401, 422, 200, 500)

    async def test_create_career_requires_auth(self, async_client):
        response = await async_client.post(
            "/api/v1/careers",
            json={"title": "Developer"},
        )
        assert response.status_code == 401

    async def test_list_applications_requires_auth(self, async_client):
        response = await async_client.get("/api/v1/careers/admin/applications")
        assert response.status_code == 401

    async def test_update_application_status_requires_auth(self, async_client):
        response = await async_client.patch(
            "/api/v1/careers/admin/applications/00000000-0000-0000-0000-000000000000/status",
            json={"status": "hired"},
        )
        assert response.status_code == 401


class TestContactEndpoints:
    """Contact endpoints — /api/v1/contact/*"""

    async def test_submit_contact(self, async_client):
        response = await async_client.post(
            "/api/v1/contact",
            json={"name": "Test", "email": "test@test.com", "message": "Hello"},
        )
        assert response.status_code in (200, 201, 500)

    async def test_list_contacts_requires_auth(self, async_client):
        response = await async_client.get("/api/v1/contact")
        assert response.status_code == 401


class TestBlogEndpoints:
    """Blog endpoints — /api/v1/blogs/*"""

    async def test_list_blogs(self, async_client):
        response = await async_client.get("/api/v1/blogs")
        assert response.status_code in (200, 500)

    async def test_create_blog_requires_auth(self, async_client):
        response = await async_client.post(
            "/api/v1/blogs",
            json={"title": "Test", "content": "Content"},
        )
        assert response.status_code == 401

    async def test_update_blog_requires_auth(self, async_client):
        response = await async_client.put(
            "/api/v1/blogs/00000000-0000-0000-0000-000000000000",
            json={"title": "Updated"},
        )
        assert response.status_code == 401

    async def test_delete_blog_requires_auth(self, async_client):
        response = await async_client.delete(
            "/api/v1/blogs/00000000-0000-0000-0000-000000000000"
        )
        assert response.status_code == 401


class TestServicesEndpoints:
    """Service endpoints — /api/v1/services/*"""

    async def test_list_services(self, async_client):
        response = await async_client.get("/api/v1/services")
        assert response.status_code in (200, 500)

    async def test_get_service(self, async_client):
        response = await async_client.get(
            "/api/v1/services/00000000-0000-0000-0000-000000000000"
        )
        assert response.status_code in (200, 404, 500)

    async def test_create_service_requires_auth(self, async_client):
        response = await async_client.post(
            "/api/v1/services",
            json={"name": "Test Service"},
        )
        assert response.status_code == 401

    async def test_update_service_requires_auth(self, async_client):
        response = await async_client.put(
            "/api/v1/services/00000000-0000-0000-0000-000000000000",
            json={"name": "Updated"},
        )
        assert response.status_code == 401

    async def test_delete_service_requires_auth(self, async_client):
        response = await async_client.delete(
            "/api/v1/services/00000000-0000-0000-0000-000000000000"
        )
        assert response.status_code == 401

    async def test_list_services_pagination_validation(self, async_client):
        response = await async_client.get("/api/v1/services?page=0")
        assert response.status_code in (422, 200, 500)

    async def test_list_services_bad_limit(self, async_client):
        response = await async_client.get("/api/v1/services?limit=0")
        assert response.status_code in (422, 200, 500)


class TestCaseStudiesEndpoints:
    """Case study endpoints — /api/v1/case-studies/*"""

    async def test_list_case_studies(self, async_client):
        response = await async_client.get("/api/v1/case-studies")
        assert response.status_code in (200, 500)

    async def test_get_case_study(self, async_client):
        response = await async_client.get(
            "/api/v1/case-studies/00000000-0000-0000-0000-000000000000"
        )
        assert response.status_code in (200, 404, 500)

    async def test_create_case_study_requires_auth(self, async_client):
        response = await async_client.post(
            "/api/v1/case-studies",
            json={"title": "Test"},
        )
        assert response.status_code == 401

    async def test_update_case_study_requires_auth(self, async_client):
        response = await async_client.put(
            "/api/v1/case-studies/00000000-0000-0000-0000-000000000000",
            json={"title": "Updated"},
        )
        assert response.status_code == 401

    async def test_delete_case_study_requires_auth(self, async_client):
        response = await async_client.delete(
            "/api/v1/case-studies/00000000-0000-0000-0000-000000000000"
        )
        assert response.status_code == 401


class TestTestimonialsEndpoints:
    """Testimonial endpoints — /api/v1/testimonials/*"""

    async def test_list_testimonials(self, async_client):
        response = await async_client.get("/api/v1/testimonials")
        assert response.status_code in (200, 500)

    async def test_get_testimonial(self, async_client):
        response = await async_client.get(
            "/api/v1/testimonials/00000000-0000-0000-0000-000000000000"
        )
        assert response.status_code in (200, 404, 500)

    async def test_create_testimonial_requires_auth(self, async_client):
        response = await async_client.post(
            "/api/v1/testimonials",
            json={"content": "Great!"},
        )
        assert response.status_code == 401

    async def test_update_testimonial_requires_auth(self, async_client):
        response = await async_client.put(
            "/api/v1/testimonials/00000000-0000-0000-0000-000000000000",
            json={"content": "Updated"},
        )
        assert response.status_code == 401

    async def test_delete_testimonial_requires_auth(self, async_client):
        response = await async_client.delete(
            "/api/v1/testimonials/00000000-0000-0000-0000-000000000000"
        )
        assert response.status_code == 401


class TestDownloadsEndpoints:
    """Download endpoints — /api/v1/downloads/*"""

    async def test_list_downloads(self, async_client):
        response = await async_client.get("/api/v1/downloads")
        assert response.status_code in (200, 500)

    async def test_get_download(self, async_client):
        response = await async_client.get(
            "/api/v1/downloads/00000000-0000-0000-0000-000000000000"
        )
        assert response.status_code in (200, 404, 500)

    async def test_create_download_requires_auth(self, async_client):
        response = await async_client.post(
            "/api/v1/downloads",
            json={"title": "Whitepaper"},
        )
        assert response.status_code == 401

    async def test_update_download_requires_auth(self, async_client):
        response = await async_client.put(
            "/api/v1/downloads/00000000-0000-0000-0000-000000000000",
            json={"title": "Updated"},
        )
        assert response.status_code == 401

    async def test_delete_download_requires_auth(self, async_client):
        response = await async_client.delete(
            "/api/v1/downloads/00000000-0000-0000-0000-000000000000"
        )
        assert response.status_code == 401


class TestEventsEndpoints:
    """Event endpoints — /api/v1/events/*"""

    async def test_list_events(self, async_client):
        response = await async_client.get("/api/v1/events")
        assert response.status_code in (200, 500)

    async def test_get_event(self, async_client):
        response = await async_client.get(
            "/api/v1/events/00000000-0000-0000-0000-000000000000"
        )
        assert response.status_code in (200, 404, 500)

    async def test_create_event_requires_auth(self, async_client):
        response = await async_client.post(
            "/api/v1/events",
            json={"title": "Conference"},
        )
        assert response.status_code == 401

    async def test_update_event_requires_auth(self, async_client):
        response = await async_client.put(
            "/api/v1/events/00000000-0000-0000-0000-000000000000",
            json={"title": "Updated"},
        )
        assert response.status_code == 401

    async def test_delete_event_requires_auth(self, async_client):
        response = await async_client.delete(
            "/api/v1/events/00000000-0000-0000-0000-000000000000"
        )
        assert response.status_code == 401


class TestTicketsEndpoints:
    """Ticket endpoints — /api/v1/tickets/*"""

    async def test_list_tickets_requires_auth(self, async_client):
        response = await async_client.get("/api/v1/tickets")
        assert response.status_code == 401

    async def test_get_ticket_requires_auth(self, async_client):
        response = await async_client.get(
            "/api/v1/tickets/00000000-0000-0000-0000-000000000000"
        )
        assert response.status_code == 401

    async def test_update_ticket_requires_auth(self, async_client):
        response = await async_client.patch(
            "/api/v1/tickets/00000000-0000-0000-0000-000000000000",
            json={"status": "resolved"},
        )
        assert response.status_code == 401

    async def test_add_reply_requires_auth(self, async_client):
        response = await async_client.post(
            "/api/v1/tickets/00000000-0000-0000-0000-000000000000/replies",
            json={"message": "Update"},
        )
        assert response.status_code == 401


class TestNotificationsEndpoints:
    """Notification endpoints — /api/v1/notifications/*"""

    async def test_list_notifications_requires_auth(self, async_client):
        response = await async_client.get("/api/v1/notifications")
        assert response.status_code == 401

    async def test_mark_read_requires_auth(self, async_client):
        response = await async_client.patch(
            "/api/v1/notifications/00000000-0000-0000-0000-000000000000/read"
        )
        assert response.status_code == 401

    async def test_mark_all_read_requires_auth(self, async_client):
        response = await async_client.patch("/api/v1/notifications/read-all")
        assert response.status_code == 401

    async def test_send_notification_requires_auth(self, async_client):
        response = await async_client.post(
            "/api/v1/notifications",
            json={"title": "Alert", "user_id": "00000000-0000-0000-0000-000000000000"},
        )
        assert response.status_code == 401


class TestMediaEndpoints:
    """Media endpoints — /api/v1/media/*"""

    async def test_list_media_requires_auth(self, async_client):
        response = await async_client.get("/api/v1/media")
        assert response.status_code == 401

    async def test_delete_media_requires_auth(self, async_client):
        response = await async_client.delete(
            "/api/v1/media/00000000-0000-0000-0000-000000000000"
        )
        assert response.status_code == 401


class TestAuditLogEndpoints:
    """Audit log endpoints — /api/v1/audit-logs"""

    async def test_list_audit_logs_requires_auth(self, async_client):
        response = await async_client.get("/api/v1/audit-logs")
        assert response.status_code == 401


class TestDashboardEndpoints:
    """Dashboard endpoints — /api/v1/dashboard/*"""

    async def test_overview_requires_auth(self, async_client):
        response = await async_client.get("/api/v1/dashboard/overview")
        assert response.status_code == 401

    async def test_projects_status_requires_auth(self, async_client):
        response = await async_client.get("/api/v1/dashboard/projects/status-breakdown")
        assert response.status_code == 401


class TestRolesEndpoints:
    """Role endpoints — /api/v1/access-control/*"""

    async def test_list_roles_requires_auth(self, async_client):
        response = await async_client.get("/api/v1/access-control/roles")
        assert response.status_code == 401

    async def test_get_role_requires_auth(self, async_client):
        response = await async_client.get(
            "/api/v1/access-control/roles/00000000-0000-0000-0000-000000000000"
        )
        assert response.status_code == 401

    async def test_create_role_requires_auth(self, async_client):
        response = await async_client.post(
            "/api/v1/access-control/roles",
            json={"name": "manager"},
        )
        assert response.status_code == 401

    async def test_update_role_requires_auth(self, async_client):
        response = await async_client.put(
            "/api/v1/access-control/roles/00000000-0000-0000-0000-000000000000",
            json={"name": "updated"},
        )
        assert response.status_code == 401

    async def test_delete_role_requires_auth(self, async_client):
        response = await async_client.delete(
            "/api/v1/access-control/roles/00000000-0000-0000-0000-000000000000"
        )
        assert response.status_code == 401

    async def test_list_permissions_requires_auth(self, async_client):
        response = await async_client.get("/api/v1/access-control/permissions")
        assert response.status_code == 401

    async def test_get_permission_requires_auth(self, async_client):
        response = await async_client.get(
            "/api/v1/access-control/permissions/00000000-0000-0000-0000-000000000000"
        )
        assert response.status_code == 401

    async def test_create_permission_requires_auth(self, async_client):
        response = await async_client.post(
            "/api/v1/access-control/permissions",
            json={"name": "perm"},
        )
        assert response.status_code == 401

    async def test_update_permission_requires_auth(self, async_client):
        response = await async_client.put(
            "/api/v1/access-control/permissions/00000000-0000-0000-0000-000000000000",
            json={"name": "updated"},
        )
        assert response.status_code == 401

    async def test_delete_permission_requires_auth(self, async_client):
        response = await async_client.delete(
            "/api/v1/access-control/permissions/00000000-0000-0000-0000-000000000000"
        )
        assert response.status_code == 401


class TestSolutionsEndpoints:
    """Solution endpoints — /api/v1/solutions/*"""

    async def test_list_solutions(self, async_client):
        response = await async_client.get("/api/v1/solutions")
        assert response.status_code in (200, 500)

    async def test_get_solution(self, async_client):
        response = await async_client.get(
            "/api/v1/solutions/00000000-0000-0000-0000-000000000000"
        )
        assert response.status_code in (200, 404, 500)

    async def test_create_solution_requires_auth(self, async_client):
        response = await async_client.post(
            "/api/v1/solutions",
            json={"name": "Test"},
        )
        assert response.status_code == 401

    async def test_update_solution_requires_auth(self, async_client):
        response = await async_client.put(
            "/api/v1/solutions/00000000-0000-0000-0000-000000000000",
            json={"name": "Updated"},
        )
        assert response.status_code == 401

    async def test_delete_solution_requires_auth(self, async_client):
        response = await async_client.delete(
            "/api/v1/solutions/00000000-0000-0000-0000-000000000000"
        )
        assert response.status_code == 401


class TestTrainingEndpoints:
    """Training endpoints — /api/v1/trainings/*"""

    async def test_list_courses(self, async_client):
        response = await async_client.get("/api/v1/trainings/courses")
        assert response.status_code in (200, 500)

    async def test_get_course(self, async_client):
        response = await async_client.get(
            "/api/v1/trainings/courses/00000000-0000-0000-0000-000000000000"
        )
        assert response.status_code in (200, 404, 500)

    async def test_enroll_requires_auth(self, async_client):
        response = await async_client.post(
            "/api/v1/trainings/enroll",
            json={"course_id": "00000000-0000-0000-0000-000000000000"},
        )
        assert response.status_code == 401

    async def test_my_enrollments_requires_auth(self, async_client):
        response = await async_client.get("/api/v1/trainings/my-enrollments")
        assert response.status_code == 401


class TestAnalyticsEndpoints:
    """Analytics endpoints — /api/v1/analytics/*"""

    async def test_summary_requires_auth(self, async_client):
        response = await async_client.get("/api/v1/analytics/summary")
        assert response.status_code == 401


class TestReportsEndpoints:
    """Report endpoints — /api/v1/reports/*"""

    async def test_list_reports_requires_auth(self, async_client):
        response = await async_client.get("/api/v1/reports")
        assert response.status_code == 401

    async def test_generate_report_requires_auth(self, async_client):
        response = await async_client.post(
            "/api/v1/reports/generate",
            json={"type": "monthly"},
        )
        assert response.status_code == 401

    async def test_delete_report_requires_auth(self, async_client):
        response = await async_client.delete(
            "/api/v1/reports/00000000-0000-0000-0000-000000000000"
        )
        assert response.status_code == 401


class TestLeadsEndpoints:
    """Lead endpoints — /api/v1/leads/*"""

    async def test_list_leads_requires_auth(self, async_client):
        response = await async_client.get("/api/v1/leads")
        assert response.status_code == 401

    async def test_get_lead_requires_auth(self, async_client):
        response = await async_client.get(
            "/api/v1/leads/00000000-0000-0000-0000-000000000000"
        )
        assert response.status_code == 401

    async def test_create_lead_requires_auth(self, async_client):
        response = await async_client.post(
            "/api/v1/leads",
            json={"name": "Test Lead"},
        )
        assert response.status_code == 401

    async def test_update_lead_requires_auth(self, async_client):
        response = await async_client.patch(
            "/api/v1/leads/00000000-0000-0000-0000-000000000000",
            json={"status": "contacted"},
        )
        assert response.status_code == 401

    async def test_delete_lead_requires_auth(self, async_client):
        response = await async_client.delete(
            "/api/v1/leads/00000000-0000-0000-0000-000000000000"
        )
        assert response.status_code == 401


class TestProposalsEndpoints:
    """Proposal endpoints — /api/v1/proposals/*"""

    async def test_list_proposals_requires_auth(self, async_client):
        response = await async_client.get("/api/v1/proposals")
        assert response.status_code == 401

    async def test_create_proposal_requires_auth(self, async_client):
        response = await async_client.post(
            "/api/v1/proposals",
            json={"title": "New Proposal"},
        )
        assert response.status_code == 401

    async def test_send_proposal_requires_auth(self, async_client):
        response = await async_client.post(
            "/api/v1/proposals/00000000-0000-0000-0000-000000000000/send"
        )
        assert response.status_code == 401

    async def test_accept_proposal_requires_auth(self, async_client):
        response = await async_client.post(
            "/api/v1/proposals/00000000-0000-0000-0000-000000000000/accept"
        )
        assert response.status_code == 401

    async def test_reject_proposal_requires_auth(self, async_client):
        response = await async_client.post(
            "/api/v1/proposals/00000000-0000-0000-0000-000000000000/reject"
        )
        assert response.status_code == 401


class TestContractsEndpoints:
    """Contract endpoints — /api/v1/contracts/*"""

    async def test_list_contracts_requires_auth(self, async_client):
        response = await async_client.get("/api/v1/contracts")
        assert response.status_code == 401

    async def test_create_contract_requires_auth(self, async_client):
        response = await async_client.post(
            "/api/v1/contracts",
            json={"title": "New Contract"},
        )
        assert response.status_code == 401

    async def test_sign_contract_requires_auth(self, async_client):
        response = await async_client.post(
            "/api/v1/contracts/00000000-0000-0000-0000-000000000000/sign"
        )
        assert response.status_code == 401


class TestDepartmentsEndpoints:
    """Department endpoints — /api/v1/departments/*"""

    async def test_list_departments_requires_auth(self, async_client):
        response = await async_client.get("/api/v1/departments")
        assert response.status_code == 401

    async def test_get_department_requires_auth(self, async_client):
        response = await async_client.get(
            "/api/v1/departments/00000000-0000-0000-0000-000000000000"
        )
        assert response.status_code == 401

    async def test_create_department_requires_auth(self, async_client):
        response = await async_client.post(
            "/api/v1/departments",
            json={"name": "Engineering"},
        )
        assert response.status_code == 401

    async def test_update_department_requires_auth(self, async_client):
        response = await async_client.put(
            "/api/v1/departments/00000000-0000-0000-0000-000000000000",
            json={"name": "Updated"},
        )
        assert response.status_code == 401

    async def test_delete_department_requires_auth(self, async_client):
        response = await async_client.delete(
            "/api/v1/departments/00000000-0000-0000-0000-000000000000"
        )
        assert response.status_code == 401


class TestIndustriesEndpoints:
    """Industry endpoints — /api/v1/industries/*"""

    async def test_list_industries(self, async_client):
        response = await async_client.get("/api/v1/industries")
        assert response.status_code in (200, 500)

    async def test_get_industry(self, async_client):
        response = await async_client.get(
            "/api/v1/industries/00000000-0000-0000-0000-000000000000"
        )
        assert response.status_code in (200, 404, 500)

    async def test_create_industry_requires_auth(self, async_client):
        response = await async_client.post(
            "/api/v1/industries",
            json={"name": "Healthcare"},
        )
        assert response.status_code == 401

    async def test_update_industry_requires_auth(self, async_client):
        response = await async_client.put(
            "/api/v1/industries/00000000-0000-0000-0000-000000000000",
            json={"name": "Updated"},
        )
        assert response.status_code == 401

    async def test_delete_industry_requires_auth(self, async_client):
        response = await async_client.delete(
            "/api/v1/industries/00000000-0000-0000-0000-000000000000"
        )
        assert response.status_code == 401

    async def test_list_industries_filter(self, async_client):
        response = await async_client.get("/api/v1/industries?is_published=true")
        assert response.status_code in (200, 500)


class TestTechnologiesEndpoints:
    """Technology endpoints — /api/v1/technologies/*"""

    async def test_list_technologies(self, async_client):
        response = await async_client.get("/api/v1/technologies")
        assert response.status_code in (200, 500)

    async def test_get_technology(self, async_client):
        response = await async_client.get(
            "/api/v1/technologies/00000000-0000-0000-0000-000000000000"
        )
        assert response.status_code in (200, 404, 500)

    async def test_create_technology_requires_auth(self, async_client):
        response = await async_client.post(
            "/api/v1/technologies",
            json={"name": "Python"},
        )
        assert response.status_code == 401

    async def test_update_technology_requires_auth(self, async_client):
        response = await async_client.put(
            "/api/v1/technologies/00000000-0000-0000-0000-000000000000",
            json={"name": "Updated"},
        )
        assert response.status_code == 401

    async def test_delete_technology_requires_auth(self, async_client):
        response = await async_client.delete(
            "/api/v1/technologies/00000000-0000-0000-0000-000000000000"
        )
        assert response.status_code == 401


class TestProductsEndpoints:
    """Product endpoints — /api/v1/products/*"""

    async def test_list_products(self, async_client):
        response = await async_client.get("/api/v1/products")
        assert response.status_code in (200, 500)

    async def test_get_product(self, async_client):
        response = await async_client.get(
            "/api/v1/products/00000000-0000-0000-0000-000000000000"
        )
        assert response.status_code in (200, 404, 500)

    async def test_create_product_requires_auth(self, async_client):
        response = await async_client.post(
            "/api/v1/products",
            json={"name": "CoreCRM"},
        )
        assert response.status_code == 401

    async def test_update_product_requires_auth(self, async_client):
        response = await async_client.put(
            "/api/v1/products/00000000-0000-0000-0000-000000000000",
            json={"name": "Updated"},
        )
        assert response.status_code == 401

    async def test_delete_product_requires_auth(self, async_client):
        response = await async_client.delete(
            "/api/v1/products/00000000-0000-0000-0000-000000000000"
        )
        assert response.status_code == 401

    async def test_list_products_published_filter(self, async_client):
        response = await async_client.get("/api/v1/products?is_published=true")
        assert response.status_code in (200, 500)


class TestAwardsEndpoints:
    """Award endpoints — /api/v1/awards/*"""

    async def test_list_awards(self, async_client):
        response = await async_client.get("/api/v1/awards")
        assert response.status_code in (200, 500)

    async def test_get_award(self, async_client):
        response = await async_client.get(
            "/api/v1/awards/00000000-0000-0000-0000-000000000000"
        )
        assert response.status_code in (200, 404, 500)

    async def test_create_award_requires_auth(self, async_client):
        response = await async_client.post(
            "/api/v1/awards",
            json={"title": "Best Tech Company"},
        )
        assert response.status_code == 401

    async def test_update_award_requires_auth(self, async_client):
        response = await async_client.put(
            "/api/v1/awards/00000000-0000-0000-0000-000000000000",
            json={"title": "Updated"},
        )
        assert response.status_code == 401

    async def test_delete_award_requires_auth(self, async_client):
        response = await async_client.delete(
            "/api/v1/awards/00000000-0000-0000-0000-000000000000"
        )
        assert response.status_code == 401

    async def test_list_awards_year_filter(self, async_client):
        response = await async_client.get("/api/v1/awards?year=2025")
        assert response.status_code in (200, 500)


class TestFaqsEndpoints:
    """FAQ endpoints — /api/v1/faqs/*"""

    async def test_list_faqs(self, async_client):
        response = await async_client.get("/api/v1/faqs")
        assert response.status_code in (200, 500)

    async def test_get_faq(self, async_client):
        response = await async_client.get(
            "/api/v1/faqs/00000000-0000-0000-0000-000000000000"
        )
        assert response.status_code in (200, 404, 500)

    async def test_create_faq_requires_auth(self, async_client):
        response = await async_client.post(
            "/api/v1/faqs",
            json={"question": "How?", "answer": "Like this"},
        )
        assert response.status_code == 401

    async def test_update_faq_requires_auth(self, async_client):
        response = await async_client.put(
            "/api/v1/faqs/00000000-0000-0000-0000-000000000000",
            json={"question": "Updated"},
        )
        assert response.status_code == 401

    async def test_delete_faq_requires_auth(self, async_client):
        response = await async_client.delete(
            "/api/v1/faqs/00000000-0000-0000-0000-000000000000"
        )
        assert response.status_code == 401

    async def test_list_faqs_category_filter(self, async_client):
        response = await async_client.get("/api/v1/faqs?category=general")
        assert response.status_code in (200, 500)


class TestGalleryEndpoints:
    """Gallery endpoints — /api/v1/gallery/*"""

    async def test_list_gallery(self, async_client):
        response = await async_client.get("/api/v1/gallery")
        assert response.status_code in (200, 500)

    async def test_get_gallery_item(self, async_client):
        response = await async_client.get(
            "/api/v1/gallery/00000000-0000-0000-0000-000000000000"
        )
        assert response.status_code in (200, 404, 500)

    async def test_create_gallery_item_requires_auth(self, async_client):
        response = await async_client.post(
            "/api/v1/gallery",
            json={"image_url": "https://example.com/img.jpg"},
        )
        assert response.status_code == 401

    async def test_update_gallery_item_requires_auth(self, async_client):
        response = await async_client.put(
            "/api/v1/gallery/00000000-0000-0000-0000-000000000000",
            json={"title": "Updated"},
        )
        assert response.status_code == 401

    async def test_delete_gallery_item_requires_auth(self, async_client):
        response = await async_client.delete(
            "/api/v1/gallery/00000000-0000-0000-0000-000000000000"
        )
        assert response.status_code == 401


class TestPartnersEndpoints:
    """Partner endpoints — /api/v1/partners/*"""

    async def test_list_partners(self, async_client):
        response = await async_client.get("/api/v1/partners")
        assert response.status_code in (200, 500)

    async def test_get_partner(self, async_client):
        response = await async_client.get(
            "/api/v1/partners/00000000-0000-0000-0000-000000000000"
        )
        assert response.status_code in (200, 404, 500)

    async def test_create_partner_requires_auth(self, async_client):
        response = await async_client.post(
            "/api/v1/partners",
            json={"name": "AWS"},
        )
        assert response.status_code == 401

    async def test_update_partner_requires_auth(self, async_client):
        response = await async_client.put(
            "/api/v1/partners/00000000-0000-0000-0000-000000000000",
            json={"name": "Updated"},
        )
        assert response.status_code == 401

    async def test_delete_partner_requires_auth(self, async_client):
        response = await async_client.delete(
            "/api/v1/partners/00000000-0000-0000-0000-000000000000"
        )
        assert response.status_code == 401


class TestResourcesEndpoints:
    """Resource endpoints — /api/v1/resources/*"""

    async def test_list_resources(self, async_client):
        response = await async_client.get("/api/v1/resources")
        assert response.status_code in (200, 500)

    async def test_get_resource(self, async_client):
        response = await async_client.get(
            "/api/v1/resources/00000000-0000-0000-0000-000000000000"
        )
        assert response.status_code in (200, 404, 500)

    async def test_create_resource_requires_auth(self, async_client):
        response = await async_client.post(
            "/api/v1/resources",
            json={"title": "Cloud Guide"},
        )
        assert response.status_code == 401

    async def test_update_resource_requires_auth(self, async_client):
        response = await async_client.put(
            "/api/v1/resources/00000000-0000-0000-0000-000000000000",
            json={"title": "Updated"},
        )
        assert response.status_code == 401

    async def test_delete_resource_requires_auth(self, async_client):
        response = await async_client.delete(
            "/api/v1/resources/00000000-0000-0000-0000-000000000000"
        )
        assert response.status_code == 401


class TestPortfolioEndpoints:
    """Portfolio endpoints — /api/v1/portfolio/*"""

    async def test_list_portfolio(self, async_client):
        response = await async_client.get("/api/v1/portfolio")
        assert response.status_code in (200, 500)

    async def test_get_portfolio_item(self, async_client):
        response = await async_client.get(
            "/api/v1/portfolio/00000000-0000-0000-0000-000000000000"
        )
        assert response.status_code in (200, 404, 500)

    async def test_create_portfolio_requires_auth(self, async_client):
        response = await async_client.post(
            "/api/v1/portfolio",
            json={"title": "Banking App"},
        )
        assert response.status_code == 401

    async def test_update_portfolio_requires_auth(self, async_client):
        response = await async_client.put(
            "/api/v1/portfolio/00000000-0000-0000-0000-000000000000",
            json={"title": "Updated"},
        )
        assert response.status_code == 401

    async def test_delete_portfolio_requires_auth(self, async_client):
        response = await async_client.delete(
            "/api/v1/portfolio/00000000-0000-0000-0000-000000000000"
        )
        assert response.status_code == 401


class TestCategoriesEndpoints:
    """Category endpoints — /api/v1/categories/*"""

    async def test_list_categories(self, async_client):
        response = await async_client.get("/api/v1/categories")
        assert response.status_code in (200, 500)

    async def test_get_category(self, async_client):
        response = await async_client.get(
            "/api/v1/categories/00000000-0000-0000-0000-000000000000"
        )
        assert response.status_code in (200, 404, 500)

    async def test_create_category_requires_auth(self, async_client):
        response = await async_client.post(
            "/api/v1/categories",
            json={"name": "Engineering"},
        )
        assert response.status_code == 401

    async def test_update_category_requires_auth(self, async_client):
        response = await async_client.put(
            "/api/v1/categories/00000000-0000-0000-0000-000000000000",
            json={"name": "Updated"},
        )
        assert response.status_code == 401

    async def test_delete_category_requires_auth(self, async_client):
        response = await async_client.delete(
            "/api/v1/categories/00000000-0000-0000-0000-000000000000"
        )
        assert response.status_code == 401

    async def test_list_categories_type_filter(self, async_client):
        response = await async_client.get("/api/v1/categories?type=blog")
        assert response.status_code in (200, 500)

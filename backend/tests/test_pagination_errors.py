"""Unit tests for pagination, sorting, and error classes."""
from unittest.mock import MagicMock

from app.core.errors import ApiError
from app.utils.pagination import PageParams, apply_sort


class TestPageParams:
    def test_default_values(self):
        params = PageParams()
        assert params.page == 1
        assert params.limit == 20
        assert params.sort is None
        assert params.search is None

    def test_offset_calculation_page_1(self):
        params = PageParams(page=1, limit=20)
        assert params.offset == 0

    def test_offset_calculation_page_2(self):
        params = PageParams(page=2, limit=20)
        assert params.offset == 20

    def test_offset_calculation_page_3_limit_10(self):
        params = PageParams(page=3, limit=10)
        assert params.offset == 20

    def test_custom_values(self):
        params = PageParams(page=5, limit=50, sort="-created_at", search="test")
        assert params.page == 5
        assert params.limit == 50
        assert params.sort == "-created_at"
        assert params.search == "test"
        assert params.offset == 200


class TestApplySort:
    def test_default_sort_when_no_sort_param(self):
        mock_query = MagicMock()
        mock_model = MagicMock()
        mock_model.created_at = MagicMock()

        apply_sort(mock_query, mock_model, None)
        mock_model.created_at.desc.assert_called_once()

    def test_descending_sort(self):
        mock_query = MagicMock()
        mock_model = MagicMock()
        mock_model.created_at = MagicMock()

        apply_sort(mock_query, mock_model, "-created_at")
        mock_model.created_at.desc.assert_called_once()

    def test_ascending_sort(self):
        mock_query = MagicMock()
        mock_model = MagicMock()
        mock_model.title = MagicMock()

        apply_sort(mock_query, mock_model, "title")
        mock_model.title.asc.assert_called_once()

    def test_multiple_sort_fields(self):
        mock_query = MagicMock()
        mock_model = MagicMock()
        mock_model.created_at = MagicMock()
        mock_model.title = MagicMock()

        apply_sort(mock_query, mock_model, "-created_at,title")
        mock_model.created_at.desc.assert_called_once()
        mock_model.title.asc.assert_called_once()

    def test_skips_nonexistent_columns(self):
        mock_query = MagicMock()
        mock_model = MagicMock()
        mock_model.created_at = MagicMock()
        del mock_model.nonexistent_field

        apply_sort(mock_query, mock_model, "nonexistent_field")
        mock_model.created_at.desc.assert_not_called()

    def test_custom_default_field(self):
        mock_query = MagicMock()
        mock_model = MagicMock()
        mock_model.updated_at = MagicMock()

        apply_sort(mock_query, mock_model, None, default_field="updated_at")
        mock_model.updated_at.desc.assert_called_once()


class TestApiError:
    def test_basic_error(self):
        error = ApiError(400, "Bad Request")
        assert error.status_code == 400
        assert error.message == "Bad Request"
        assert error.errors == []

    def test_error_with_errors_list(self):
        error = ApiError(422, "Validation Error", [{"field": "email", "message": "Invalid"}])
        assert error.status_code == 422
        assert len(error.errors) == 1
        assert error.errors[0]["field"] == "email"

    def test_bad_request_factory(self):
        error = ApiError.bad_request("Invalid input")
        assert error.status_code == 400
        assert error.message == "Invalid input"

    def test_unauthorized_factory(self):
        error = ApiError.unauthorized("Login required")
        assert error.status_code == 401
        assert error.message == "Login required"

    def test_forbidden_factory(self):
        error = ApiError.forbidden("Access denied")
        assert error.status_code == 403
        assert error.message == "Access denied"

    def test_not_found_factory(self):
        error = ApiError.not_found("User not found")
        assert error.status_code == 404
        assert error.message == "User not found"

    def test_conflict_factory(self):
        error = ApiError.conflict("Already exists")
        assert error.status_code == 409
        assert error.message == "Already exists"

    def test_internal_factory(self):
        error = ApiError.internal("Server error")
        assert error.status_code == 500
        assert error.message == "Server error"

    def test_service_unavailable_factory(self):
        error = ApiError.service_unavailable("Try again later")
        assert error.status_code == 503
        assert error.message == "Try again later"

    def test_is_exception_subclass(self):
        error = ApiError(400, "test")
        assert isinstance(error, Exception)
        assert str(error) == "test"

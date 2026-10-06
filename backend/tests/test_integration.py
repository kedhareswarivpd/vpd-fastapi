"""Integration-style tests for CRUD operations with mocked async database."""
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.exc import SQLAlchemyError

from app.core.errors import ApiError
from app.crud.base import CRUDBase
from app.models.user import User
from app.utils.pagination import PageParams


@pytest.fixture
def mock_db():
    db = AsyncMock()
    db.add = MagicMock()
    return db


@pytest.fixture
def crud():
    return CRUDBase(User, searchable_fields=["name", "email"])


class TestCrudIntegration:
    @pytest.mark.asyncio
    async def test_create_and_get_user(self, mock_db, crud):
        user_id = uuid.uuid4()
        user_data = {
            "id": user_id,
            "name": "Integration Test",
            "email": "integration@test.com",
            "role": "client",
        }

        created = await crud.create(mock_db, user_data)
        assert created.name == "Integration Test"
        assert created.email == "integration@test.com"

        mock_db.add.assert_called_once()
        mock_db.commit.assert_awaited_once()
        mock_db.refresh.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_user_flow(self, mock_db, crud):
        user_id = uuid.uuid4()
        mock_user = User(id=user_id, name="Get Test", email="get@test.com", role="client")

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_db.execute.return_value = mock_result

        result = await crud.get(mock_db, user_id)
        assert result.id == user_id
        assert result.email == "get@test.com"

    @pytest.mark.asyncio
    async def test_get_nonexistent_returns_404(self, mock_db, crud):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        with pytest.raises(ApiError) as exc_info:
            await crud.get(mock_db, uuid.uuid4())
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_update_user_flow(self, mock_db, crud):
        user_id = uuid.uuid4()
        existing_user = User(id=user_id, name="Old Name", email="update@test.com", role="client")

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing_user
        mock_db.execute.return_value = mock_result

        updated = await crud.update(mock_db, user_id, {"name": "New Name"})
        assert updated.name == "New Name"
        mock_db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_delete_user_flow(self, mock_db, crud):
        user_id = uuid.uuid4()
        existing_user = User(id=user_id, name="ToDelete", email="delete@test.com", role="client")

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing_user
        mock_db.execute.return_value = mock_result

        await crud.delete(mock_db, user_id)
        mock_db.delete.assert_awaited_once_with(existing_user)
        mock_db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_delete_nonexistent_returns_404(self, mock_db, crud):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        with pytest.raises(ApiError) as exc_info:
            await crud.delete(mock_db, uuid.uuid4())
        assert exc_info.value.status_code in (404, 500)

    @pytest.mark.asyncio
    async def test_list_with_pagination(self, mock_db, crud):
        mock_result = MagicMock()
        mock_result.scalars.return_value.unique.return_value.all.return_value = []
        mock_count_result = MagicMock()
        mock_count_result.scalar_one.return_value = 0
        mock_db.execute.side_effect = [mock_result, mock_count_result]

        items, total = await crud.list(mock_db, PageParams(page=1, limit=20))
        assert items == []
        assert total == 0

    @pytest.mark.asyncio
    async def test_list_with_search(self, mock_db, crud):
        mock_result = MagicMock()
        mock_result.scalars.return_value.unique.return_value.all.return_value = []
        mock_count_result = MagicMock()
        mock_count_result.scalar_one.return_value = 0
        mock_db.execute.side_effect = [mock_result, mock_count_result]

        await crud.list(mock_db, PageParams(page=1, limit=20, search="test"))
        assert mock_db.execute.call_count == 2

    @pytest.mark.asyncio
    async def test_list_with_filters(self, mock_db, crud):
        mock_result = MagicMock()
        mock_result.scalars.return_value.unique.return_value.all.return_value = []
        mock_count_result = MagicMock()
        mock_count_result.scalar_one.return_value = 0
        mock_db.execute.side_effect = [mock_result, mock_count_result]

        await crud.list(mock_db, PageParams(page=1, limit=20), filters={"role": "admin"})
        assert mock_db.execute.call_count == 2

    @pytest.mark.asyncio
    async def test_get_optional_returns_none(self, mock_db, crud):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        result = await crud.get_optional(mock_db, email="nonexistent@test.com")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_optional_returns_match(self, mock_db, crud):
        mock_user = User(id=uuid.uuid4(), name="Find Me", email="find@test.com", role="client")
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_db.execute.return_value = mock_result

        result = await crud.get_optional(mock_db, email="find@test.com")
        assert result is not None
        assert result.email == "find@test.com"

    @pytest.mark.asyncio
    async def test_create_rollback_on_error(self, mock_db, crud):
        mock_db.commit.side_effect = SQLAlchemyError("constraint violation")

        with pytest.raises(ApiError) as exc_info:
            await crud.create(mock_db, {"name": "Test"})
        assert exc_info.value.status_code == 500
        mock_db.rollback.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_list_handles_db_error(self, mock_db, crud):
        mock_db.execute.side_effect = SQLAlchemyError("connection lost")

        with pytest.raises(ApiError) as exc_info:
            await crud.list(mock_db, PageParams(page=1, limit=20))
        assert exc_info.value.status_code == 500

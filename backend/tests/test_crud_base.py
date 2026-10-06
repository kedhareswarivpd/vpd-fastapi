"""Unit tests for generic CRUD operations."""
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.exc import SQLAlchemyError

from app.core.errors import ApiError
from app.crud.base import CRUDBase
from app.models.user import User
from app.utils.pagination import PageParams


class TestCrudBaseList:
    @pytest.mark.asyncio
    async def test_list_returns_items_and_total(self):
        mock_db = AsyncMock()
        mock_db.add = MagicMock()
        crud = CRUDBase(User)

        mock_result = MagicMock()
        mock_result.scalars.return_value.unique.return_value.all.return_value = []
        mock_count_result = MagicMock()
        mock_count_result.scalar_one.return_value = 0

        mock_db.execute.side_effect = [mock_result, mock_count_result]

        items, total = await crud.list(mock_db, PageParams(page=1, limit=20))
        assert items == []
        assert total == 0

    @pytest.mark.asyncio
    async def test_list_with_filters(self):
        mock_db = AsyncMock()
        mock_db.add = MagicMock()
        crud = CRUDBase(User)

        mock_result = MagicMock()
        mock_result.scalars.return_value.unique.return_value.all.return_value = []
        mock_count_result = MagicMock()
        mock_count_result.scalar_one.return_value = 0

        mock_db.execute.side_effect = [mock_result, mock_count_result]

        await crud.list(mock_db, PageParams(page=1, limit=20), filters={"role": "client"})
        assert mock_db.execute.call_count == 2

    @pytest.mark.asyncio
    async def test_list_with_search(self):
        mock_db = AsyncMock()
        mock_db.add = MagicMock()
        crud = CRUDBase(User, searchable_fields=["name", "email"])

        mock_result = MagicMock()
        mock_result.scalars.return_value.unique.return_value.all.return_value = []
        mock_count_result = MagicMock()
        mock_count_result.scalar_one.return_value = 0

        mock_db.execute.side_effect = [mock_result, mock_count_result]

        await crud.list(mock_db, PageParams(page=1, limit=20, search="test"))
        assert mock_db.execute.call_count == 2

    @pytest.mark.asyncio
    async def test_list_skips_none_filter_values(self):
        mock_db = AsyncMock()
        mock_db.add = MagicMock()
        crud = CRUDBase(User)

        mock_result = MagicMock()
        mock_result.scalars.return_value.unique.return_value.all.return_value = []
        mock_count_result = MagicMock()
        mock_count_result.scalar_one.return_value = 0

        mock_db.execute.side_effect = [mock_result, mock_count_result]

        await crud.list(mock_db, PageParams(page=1, limit=20), filters={"role": None})
        assert mock_db.execute.call_count == 2

    @pytest.mark.asyncio
    async def test_list_handles_db_error(self):
        mock_db = AsyncMock()
        mock_db.add = MagicMock()
        mock_db.execute.side_effect = SQLAlchemyError("connection lost")
        crud = CRUDBase(User)

        with pytest.raises(ApiError) as exc_info:
            await crud.list(mock_db, PageParams(page=1, limit=20))
        assert exc_info.value.status_code == 500


class TestCrudBaseGet:
    @pytest.mark.asyncio
    async def test_get_returns_object(self):
        mock_db = AsyncMock()
        mock_db.add = MagicMock()
        crud = CRUDBase(User)

        user_id = uuid.uuid4()
        mock_user = User(id=user_id, name="Test", email="test@example.com", role="client")

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_db.execute.return_value = mock_result

        result = await crud.get(mock_db, user_id)
        assert result.id == user_id

    @pytest.mark.asyncio
    async def test_get_raises_not_found(self):
        mock_db = AsyncMock()
        mock_db.add = MagicMock()
        crud = CRUDBase(User)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        with pytest.raises(ApiError) as exc_info:
            await crud.get(mock_db, uuid.uuid4())
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_get_handles_db_error(self):
        mock_db = AsyncMock()
        mock_db.add = MagicMock()
        mock_db.execute.side_effect = SQLAlchemyError("connection lost")
        crud = CRUDBase(User)

        with pytest.raises(ApiError) as exc_info:
            await crud.get(mock_db, uuid.uuid4())
        assert exc_info.value.status_code == 404


class TestCrudBaseGetOptional:
    @pytest.mark.asyncio
    async def test_get_optional_returns_object(self):
        mock_db = AsyncMock()
        mock_db.add = MagicMock()
        crud = CRUDBase(User)

        mock_user = User(id=uuid.uuid4(), name="Test", email="test@example.com", role="client")
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_db.execute.return_value = mock_result

        result = await crud.get_optional(mock_db, email="test@example.com")
        assert result is not None
        assert result.email == "test@example.com"

    @pytest.mark.asyncio
    async def test_get_optional_returns_none_when_not_found(self):
        mock_db = AsyncMock()
        mock_db.add = MagicMock()
        crud = CRUDBase(User)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        result = await crud.get_optional(mock_db, email="missing@example.com")
        assert result is None


class TestCrudBaseCreate:
    @pytest.mark.asyncio
    async def test_create_returns_object(self):
        mock_db = AsyncMock()
        mock_db.add = MagicMock()
        crud = CRUDBase(User)

        await crud.create(
            mock_db,
            {"id": uuid.uuid4(), "name": "New User", "email": "new@example.com", "role": "client"},
        )
        mock_db.add.assert_called_once()
        mock_db.commit.assert_awaited_once()
        mock_db.refresh.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_create_rollback_on_error(self):
        mock_db = AsyncMock()
        mock_db.add = MagicMock()
        mock_db.commit.side_effect = SQLAlchemyError("constraint violation")
        crud = CRUDBase(User)

        with pytest.raises(ApiError) as exc_info:
            await crud.create(mock_db, {"name": "Test"})
        assert exc_info.value.status_code == 500
        mock_db.rollback.assert_awaited_once()


class TestCrudBaseUpdate:
    @pytest.mark.asyncio
    async def test_update_modifies_object(self):
        mock_db = AsyncMock()
        mock_db.add = MagicMock()
        crud = CRUDBase(User)

        user_id = uuid.uuid4()
        existing_user = User(id=user_id, name="Old Name", email="old@example.com", role="client")

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing_user
        mock_db.execute.return_value = mock_result

        result = await crud.update(mock_db, user_id, {"name": "New Name"})
        assert result.name == "New Name"
        mock_db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_update_raises_not_found(self):
        mock_db = AsyncMock()
        mock_db.add = MagicMock()
        crud = CRUDBase(User)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        with pytest.raises(ApiError) as exc_info:
            await crud.update(mock_db, uuid.uuid4(), {"name": "New"})
        assert exc_info.value.status_code == 404


class TestCrudBaseDelete:
    @pytest.mark.asyncio
    async def test_delete_removes_object(self):
        mock_db = AsyncMock()
        mock_db.add = MagicMock()
        crud = CRUDBase(User)

        user_id = uuid.uuid4()
        existing_user = User(id=user_id, name="ToDelete", email="del@example.com", role="client")

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing_user
        mock_db.execute.return_value = mock_result

        await crud.delete(mock_db, user_id)
        mock_db.delete.assert_awaited_once_with(existing_user)
        mock_db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_delete_raises_not_found(self):
        mock_db = AsyncMock()
        mock_db.add = MagicMock()
        crud = CRUDBase(User)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        with pytest.raises(ApiError) as exc_info:
            await crud.delete(mock_db, uuid.uuid4())
        assert exc_info.value.status_code in (404, 500)

    @pytest.mark.asyncio
    async def test_delete_rollback_on_error(self):
        mock_db = AsyncMock()
        mock_db.add = MagicMock()
        crud = CRUDBase(User)

        user_id = uuid.uuid4()
        existing_user = User(id=user_id, name="ToDelete", email="del@example.com", role="client")

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing_user
        mock_db.execute.return_value = mock_result
        mock_db.commit.side_effect = SQLAlchemyError("constraint violation")

        with pytest.raises(ApiError) as exc_info:
            await crud.delete(mock_db, user_id)
        assert exc_info.value.status_code == 500
        mock_db.rollback.assert_awaited_once()

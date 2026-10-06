"""Unit tests for finance.py::record_payment's replay/idempotency handling.

Added after a live drill against the real running stack found two real bugs
in the first implementation attempt (see status.md): (1) catching a mid-commit
IntegrityError on the request-scoped session intermittently raised
`sqlalchemy.exc.MissingGreenlet` — a known Starlette BaseHTTPMiddleware +
SQLAlchemy-async interaction, fixed by switching to check-then-insert; (2) the
route decorator's `status_code=201` silently overrode a `success_response(...,
status_code=200)` returned in the body — the real HTTP response stayed 201 on
a replay even though nothing was created, fixed via `response.status_code`.
These tests target the check-then-insert logic directly; the DB-level unique
constraint itself (`ux_payments_invoice_transaction_ref`,
alembic/versions/4a2dbc43345c) was verified separately against a real
Postgres container, since the mocked suite has no real DB to enforce it.
"""
import uuid
from datetime import UTC, date, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.invoice import Invoice
from app.models.payment import Payment
from app.routers.finance import record_payment
from app.schemas.finance import PaymentCreate


def _make_invoice(**overrides) -> Invoice:
    defaults = dict(
        id=uuid.uuid4(),
        invoice_number="INV-TEST-1",
        client_id=uuid.uuid4(),
        amount=500,
        tax=0,
        total_amount=500,
        issue_date=date(2026, 1, 1),
        due_date=date(2026, 2, 1),
        status="draft",
    )
    defaults.update(overrides)
    return Invoice(**defaults)


def _make_payload(**overrides) -> PaymentCreate:
    defaults = dict(
        amount=500,
        method="bank_transfer",
        transaction_ref="TXN-001",
        paid_at=datetime.now(UTC),
    )
    defaults.update(overrides)
    return PaymentCreate(**defaults)


def _refresh_side_effect(obj):
    """Mimics what a real db.refresh() populates on a freshly-inserted row —
    the mocked session doesn't touch a real DB, so these server-generated
    fields stay None otherwise."""
    obj.id = obj.id or uuid.uuid4()
    obj.created_at = obj.created_at or datetime.now(UTC)
    obj.updated_at = obj.updated_at or datetime.now(UTC)


class TestRecordPaymentIdempotency:
    @pytest.mark.asyncio
    async def test_replay_with_same_reference_returns_existing_payment_with_200(self):
        invoice = _make_invoice()
        existing_payment = Payment(
            id=uuid.uuid4(), invoice_id=invoice.id, amount=500, method="bank_transfer",
            transaction_ref="TXN-001", paid_at=datetime.now(UTC), status="completed",
            created_at=datetime.now(UTC), updated_at=datetime.now(UTC),
        )
        mock_db = AsyncMock()
        mock_db.add = MagicMock()
        payment_check_result = MagicMock()
        payment_check_result.scalar_one_or_none.return_value = existing_payment
        mock_db.execute.side_effect = [payment_check_result]
        mock_response = MagicMock(status_code=201)

        with patch("app.routers.finance.invoice_crud.get", return_value=invoice):
            result = await record_payment(invoice.id, _make_payload(), mock_response, mock_db)

        assert result["message"] == "Payment already recorded for this reference"
        assert result["data"].id == existing_payment.id
        # The real bug: a returned dict's status_code field alone does NOT
        # change the actual HTTP response — only response.status_code does.
        assert mock_response.status_code == 200
        mock_db.add.assert_not_called()
        mock_db.commit.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_new_reference_creates_a_payment(self):
        invoice = _make_invoice()
        mock_db = AsyncMock()
        mock_db.add = MagicMock()
        mock_db.refresh.side_effect = _refresh_side_effect
        payment_check_result = MagicMock()
        payment_check_result.scalar_one_or_none.return_value = None
        paid_total_result = MagicMock()
        paid_total_result.scalar_one.return_value = 500
        mock_db.execute.side_effect = [payment_check_result, paid_total_result]
        mock_response = MagicMock(status_code=201)

        with patch("app.routers.finance.invoice_crud.get", return_value=invoice):
            result = await record_payment(invoice.id, _make_payload(), mock_response, mock_db)

        assert result["message"] == "Payment recorded successfully"
        mock_db.add.assert_called_once()
        assert mock_db.commit.await_count >= 1
        # response.status_code was never touched in the create path — the
        # route decorator's default (201) stands, correctly.
        assert mock_response.status_code == 201

    @pytest.mark.asyncio
    async def test_payment_with_no_transaction_ref_always_creates_new(self):
        """A payment with no reference (e.g. a manual cash/cheque entry) has
        nothing to deduplicate against — the idempotency check must be
        skipped, not treated as a match against other no-reference payments."""
        invoice = _make_invoice()
        mock_db = AsyncMock()
        mock_db.add = MagicMock()
        mock_db.refresh.side_effect = _refresh_side_effect
        paid_total_result = MagicMock()
        paid_total_result.scalar_one.return_value = 500
        mock_db.execute.side_effect = [paid_total_result]
        mock_response = MagicMock(status_code=201)

        with patch("app.routers.finance.invoice_crud.get", return_value=invoice):
            result = await record_payment(
                invoice.id, _make_payload(transaction_ref=None), mock_response, mock_db
            )

        assert result["message"] == "Payment recorded successfully"
        mock_db.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_invoice_marked_paid_once_total_covers_it(self):
        invoice = _make_invoice(total_amount=500)
        mock_db = AsyncMock()
        mock_db.add = MagicMock()
        mock_db.refresh.side_effect = _refresh_side_effect
        payment_check_result = MagicMock()
        payment_check_result.scalar_one_or_none.return_value = None
        paid_total_result = MagicMock()
        paid_total_result.scalar_one.return_value = 500
        mock_db.execute.side_effect = [payment_check_result, paid_total_result]
        mock_response = MagicMock(status_code=201)

        with patch("app.routers.finance.invoice_crud.get", return_value=invoice):
            await record_payment(invoice.id, _make_payload(), mock_response, mock_db)

        assert invoice.status == "paid"

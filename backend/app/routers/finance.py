import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_roles
from app.crud.base import CRUDBase
from app.models.invoice import Invoice
from app.models.payment import Payment
from app.schemas.finance import InvoiceCreate, InvoiceOut, InvoiceUpdate, PaymentCreate, PaymentOut
from app.utils.pagination import PageParams, page_params
from app.utils.responses import build_pagination_meta, success_response

router = APIRouter(prefix="/finance", tags=["Finance"], dependencies=[Depends(require_roles("admin", "finance"))])

invoice_crud = CRUDBase(Invoice, searchable_fields=["invoice_number"])


@router.get("/invoices", response_model=dict)
async def list_invoices(request: Request, db: AsyncSession = Depends(get_db), page: PageParams = Depends(page_params)):
    filters = {k: request.query_params.get(k) for k in ("client_id", "project_id", "status") if request.query_params.get(k)}
    items, total = await invoice_crud.list(db, page, filters)
    meta = build_pagination_meta(total, page.page, page.limit)
    return success_response(data=[InvoiceOut.model_validate(i) for i in items], message="Invoices fetched", meta=meta)


@router.get("/invoices/{invoice_id}", response_model=dict)
async def get_invoice(invoice_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    invoice = await invoice_crud.get(db, invoice_id)
    return success_response(data=InvoiceOut.model_validate(invoice))


@router.post("/invoices", response_model=dict, status_code=201)
async def create_invoice(payload: InvoiceCreate, db: AsyncSession = Depends(get_db)):
    data = payload.model_dump()
    data["invoice_number"] = data.get("invoice_number") or f"INV-{int(datetime.utcnow().timestamp())}"
    data["total_amount"] = float(data["amount"]) + float(data.get("tax") or 0)
    invoice = await invoice_crud.create(db, data)
    return success_response(data=InvoiceOut.model_validate(invoice), message="Invoice created successfully", status_code=201)


@router.put("/invoices/{invoice_id}", response_model=dict)
async def update_invoice(invoice_id: uuid.UUID, payload: InvoiceUpdate, db: AsyncSession = Depends(get_db)):
    invoice = await invoice_crud.update(db, invoice_id, payload.model_dump(exclude_unset=True))
    return success_response(data=InvoiceOut.model_validate(invoice), message="Invoice updated successfully")


@router.post("/invoices/sweep-overdue", response_model=dict)
async def sweep_overdue_invoices(db: AsyncSession = Depends(get_db)):
    """Real gap found during a documentation review: InvoiceStatus.overdue
    was never set by any code path — there's no background-job runner in
    this app at all (see docs/architecture/background-jobs.md), so there
    was no way for an invoice to ever transition there automatically.
    Manual-trigger, same pattern as POST /backups/trigger, until a real job
    scheduler exists — someone (or an external cron hitting this endpoint)
    must call it; it does not run itself."""
    today = datetime.now(UTC).date()
    result = await db.execute(
        update(Invoice)
        .where(Invoice.status == "sent", Invoice.due_date < today)
        .values(status="overdue")
        .returning(Invoice.id)
    )
    updated_ids = result.scalars().all()
    await db.commit()
    return success_response(data={"updated_count": len(updated_ids)}, message="Overdue invoices swept")


@router.post("/invoices/{invoice_id}/payments", response_model=dict, status_code=201)
async def record_payment(invoice_id: uuid.UUID, payload: PaymentCreate, response: Response, db: AsyncSession = Depends(get_db)):
    invoice = await invoice_crud.get(db, invoice_id)

    # Idempotency: check-then-insert rather than insert-then-catch. A real DB
    # unique index on (invoice_id, transaction_ref) (see
    # alembic/versions/4a2dbc43345c) is the actual integrity guarantee (it
    # still catches a genuine simultaneous race this check can't); this
    # up-front check just makes the common case — a caller retrying an
    # already-recorded payment after a network blip, double-click, or a
    # payment gateway webhook firing twice — return the existing payment
    # cleanly instead of relying on catching a mid-commit IntegrityError,
    # which (confirmed while building this) interacts badly with Starlette's
    # BaseHTTPMiddleware stack: a commit-fails/rollback/requery sequence on
    # the same request-scoped session mid-response intermittently raised
    # `sqlalchemy.exc.MissingGreenlet` instead of the intended graceful reply.
    if payload.transaction_ref:
        existing = (
            await db.execute(
                select(Payment).where(
                    Payment.invoice_id == invoice.id,
                    Payment.transaction_ref == payload.transaction_ref,
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            # The `status_code=201` on the route decorator is only a
            # *default* — a returned dict doesn't override the actual HTTP
            # status Starlette sends, only `response.status_code` does.
            # Without this, the real response was 201 even though the body
            # correctly said 200 and no row was created (confirmed via a
            # live replay drill against the running stack — the mismatch is
            # exactly the kind of thing only hitting the real endpoint
            # catches, not reading the code).
            response.status_code = 200
            return success_response(
                data=PaymentOut.model_validate(existing),
                message="Payment already recorded for this reference",
                status_code=200,
            )

    payment = Payment(**payload.model_dump(), invoice_id=invoice.id)
    db.add(payment)
    await db.commit()
    await db.refresh(payment)

    paid_total = (
        await db.execute(
            select(func.coalesce(func.sum(Payment.amount), 0)).where(
                Payment.invoice_id == invoice.id, Payment.status == "completed"
            )
        )
    ).scalar_one()

    if float(paid_total) >= float(invoice.total_amount):
        invoice.status = "paid"
        await db.commit()

    return success_response(data=PaymentOut.model_validate(payment), message="Payment recorded successfully", status_code=201)

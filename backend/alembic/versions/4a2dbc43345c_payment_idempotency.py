"""Add payment idempotency constraint (replay/idempotency testing gap, open since Session 7)

`finance.py::record_payment` had no protection against a retried request
(network blip, double-click, a payment gateway webhook firing twice) creating
a second `Payment` row for the same invoice + transaction reference — which
would double-count toward the invoice's paid total and could mark it "paid"
on an over-credit. A partial unique index (only enforced when
`transaction_ref IS NOT NULL`, since manual/no-reference payments are
legitimately allowed to repeat) makes this a real DB-level guarantee rather
than an app-level check with a race condition between the check and the
insert.

Revision ID: 4a2dbc43345c
Revises: e2f3a4b5c6d7
Create Date: 2026-08-21 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op

revision: str = '4a2dbc43345c'
down_revision: Union[str, None] = 'e2f3a4b5c6d7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        'ux_payments_invoice_transaction_ref',
        'payments',
        ['invoice_id', 'transaction_ref'],
        unique=True,
        postgresql_where='transaction_ref IS NOT NULL',
        if_not_exists=True,
    )


def downgrade() -> None:
    op.drop_index('ux_payments_invoice_transaction_ref', table_name='payments', if_exists=True)

"""Add a unique constraint on training_enrollments(employee_id, course_id).

Real bug found during a documentation review: enroll() in
app/routers/training.py only did a query-then-insert existence check with
no matching database constraint, so two concurrent enroll requests for the
same employee/course could both pass the check before either committed,
producing a duplicate enrollment. This migration removes any pre-existing
duplicates (keeping the earliest row per pair) before adding the
constraint, since ADD CONSTRAINT fails outright if duplicates already
exist.

Revision ID: 664442caaa34
Revises: 6ba70af745ad
Create Date: 2026-08-23 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op

revision: str = '664442caaa34'
down_revision: Union[str, None] = '6ba70af745ad'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Keep the earliest (by enrolled_at) row per (employee_id, course_id)
    # pair, delete the rest, so the new constraint can actually be added
    # against any pre-existing accidental duplicates.
    op.execute(
        """
        DELETE FROM training_enrollments a
        USING training_enrollments b
        WHERE a.employee_id = b.employee_id
          AND a.course_id = b.course_id
          AND a.enrolled_at > b.enrolled_at
        """
    )
    op.create_unique_constraint(
        "uq_training_enrollment_employee_course",
        "training_enrollments",
        ["employee_id", "course_id"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_training_enrollment_employee_course", "training_enrollments", type_="unique")

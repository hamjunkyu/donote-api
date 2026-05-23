"""change settlement participant amount to integer

Revision ID: 3912d4fcce75
Revises: a5dc9721f577
Create Date: 2026-05-21 13:08:26.144208

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3912d4fcce75'
down_revision: Union[str, Sequence[str], None] = 'a5dc9721f577'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """SettlementParticipant.amount Numeric(12,2) → Numeric(12,0). 정수 통일."""
    op.alter_column(
        'settlement_participants', 'amount',
        existing_type=sa.Numeric(precision=12, scale=2),
        type_=sa.Numeric(precision=12, scale=0),
    )


def downgrade() -> None:
    """Numeric(12,0) → Numeric(12,2)."""
    op.alter_column(
        'settlement_participants', 'amount',
        existing_type=sa.Numeric(precision=12, scale=0),
        type_=sa.Numeric(precision=12, scale=2),
    )

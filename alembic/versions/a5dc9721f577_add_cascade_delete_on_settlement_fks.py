"""add cascade delete on settlement FKs

Revision ID: a5dc9721f577
Revises: 3b1823b234e4
Create Date: 2026-05-21 13:07:48.680282

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a5dc9721f577'
down_revision: Union[str, Sequence[str], None] = '3b1823b234e4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """거래 삭제 시 정산 + 참여자 cascade 삭제. 정산 삭제 시 참여자 cascade 삭제."""
    # settlement_participants.settlement_id → settlements (CASCADE)
    op.drop_constraint(
        'settlement_participants_settlement_id_fkey',
        'settlement_participants',
        type_='foreignkey',
    )
    op.create_foreign_key(
        'settlement_participants_settlement_id_fkey',
        'settlement_participants', 'settlements',
        ['settlement_id'], ['id'],
        ondelete='CASCADE',
    )
    # settlements.transaction_id → transactions (CASCADE)
    op.drop_constraint(
        'settlements_transaction_id_fkey',
        'settlements',
        type_='foreignkey',
    )
    op.create_foreign_key(
        'settlements_transaction_id_fkey',
        'settlements', 'transactions',
        ['transaction_id'], ['id'],
        ondelete='CASCADE',
    )


def downgrade() -> None:
    """Cascade 제거."""
    op.drop_constraint(
        'settlement_participants_settlement_id_fkey',
        'settlement_participants',
        type_='foreignkey',
    )
    op.create_foreign_key(
        'settlement_participants_settlement_id_fkey',
        'settlement_participants', 'settlements',
        ['settlement_id'], ['id'],
    )
    op.drop_constraint(
        'settlements_transaction_id_fkey',
        'settlements',
        type_='foreignkey',
    )
    op.create_foreign_key(
        'settlements_transaction_id_fkey',
        'settlements', 'transactions',
        ['transaction_id'], ['id'],
    )

"""add is_achieved_notified flag to goals

Revision ID: 3b1823b234e4
Revises: 97609afd73bb
Create Date: 2026-05-13 17:47:12.834953

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3b1823b234e4'
down_revision: Union[str, Sequence[str], None] = '97609afd73bb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'goals',
        sa.Column(
            'is_achieved_notified',
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('goals', 'is_achieved_notified')

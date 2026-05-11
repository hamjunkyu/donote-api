"""add goals table

Revision ID: 97609afd73bb
Revises: 4ef15ef76444
Create Date: 2026-05-01 15:05:00.729163

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '97609afd73bb'
down_revision: Union[str, Sequence[str], None] = '4ef15ef76444'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'goals',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('target_amount', sa.Numeric(precision=12, scale=0), nullable=False),
        sa.Column('target_date', sa.Date(), nullable=True),
        sa.Column('category_id', sa.Uuid(), nullable=False),
        sa.Column('description', sa.String(length=500), nullable=True),
        sa.Column(
            'status',
            sa.Enum('IN_PROGRESS', 'ACHIEVED', 'EXPIRED', 'CANCELLED', name='goal_status'),
            nullable=False,
        ),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('achieved_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['category_id'], ['categories.id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('goals')
    op.execute('DROP TYPE goal_status')

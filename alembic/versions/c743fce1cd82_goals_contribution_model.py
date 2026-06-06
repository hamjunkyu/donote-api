"""goals contribution model

Revision ID: c743fce1cd82
Revises: 19a8eb0dad0e
Create Date: 2026-06-06

저축 목표를 명시적 적립(goal_contributions) 모델로 전환.
진행률 = 적립 합계. goals.category_id 제거 (저축은 지출 카테고리와 무관).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c743fce1cd82'
down_revision: Union[str, Sequence[str], None] = '19a8eb0dad0e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # 적립 테이블 생성
    op.create_table(
        'goal_contributions',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('goal_id', sa.Uuid(), nullable=False),
        sa.Column('amount', sa.Numeric(precision=12, scale=0), nullable=False),
        sa.Column('memo', sa.String(length=200), nullable=True),
        sa.Column('contributed_at', sa.Date(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.CheckConstraint('amount > 0', name='ck_goal_contribution_amount_gt_zero'),
        sa.ForeignKeyConstraint(['goal_id'], ['goals.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        'ix_goal_contributions_goal_id', 'goal_contributions', ['goal_id'], unique=False
    )

    # goals.category_id 제거 (저축 목표는 지출 카테고리와 무관해짐)
    # category_id 를 참조하는 인덱스를 먼저 제거한 뒤 컬럼/FK 제거.
    op.drop_index('ix_goals_user_category', table_name='goals')
    op.drop_constraint('goals_category_id_fkey', 'goals', type_='foreignkey')
    op.drop_column('goals', 'category_id')


def downgrade() -> None:
    """Downgrade schema."""
    op.add_column(
        'goals',
        sa.Column('category_id', sa.Uuid(), autoincrement=False, nullable=False),
    )
    op.create_foreign_key(
        'goals_category_id_fkey', 'goals', 'categories', ['category_id'], ['id']
    )
    op.create_index(
        'ix_goals_user_category', 'goals', ['user_id', 'category_id'], unique=False
    )
    op.drop_index('ix_goal_contributions_goal_id', table_name='goal_contributions')
    op.drop_table('goal_contributions')

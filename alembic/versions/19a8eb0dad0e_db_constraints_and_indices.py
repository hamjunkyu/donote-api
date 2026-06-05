"""db_constraints_and_indices

Revision ID: 19a8eb0dad0e
Revises: 9435638609c2
Create Date: 2026-06-05 14:23:03.716070

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '19a8eb0dad0e'
down_revision: Union[str, Sequence[str], None] = '9435638609c2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # 1. CHECK Constraints 추가
    op.create_check_constraint("ck_transaction_amount_gt_zero", "transactions", "amount > 0")
    op.create_check_constraint("ck_budget_amount_gt_zero", "budgets", "amount > 0")
    op.create_check_constraint("ck_goal_target_amount_gt_zero", "goals", "target_amount > 0")
    op.create_check_constraint("ck_settlement_participant_amount_ge_zero", "settlement_participants", "amount >= 0")
    op.create_check_constraint("ck_budget_year_month_format", "budgets", "year_month ~ '^\\d{4}-\\d{2}$'")

    # 2. Composite / 단일 인덱스 추가
    op.create_index("ix_transactions_user_date", "transactions", ["user_id", "transaction_date"])
    op.create_index("ix_transactions_category_id", "transactions", ["category_id"])
    op.create_index("ix_goals_user_category", "goals", ["user_id", "category_id"])
    op.create_index("ix_settlements_creator_id", "settlements", ["creator_id"])
    op.create_index("ix_settlements_transaction_id", "settlements", ["transaction_id"])
    op.create_index("ix_notifications_user_is_read", "notifications", ["user_id", "is_read"])
    op.create_index("ix_settlement_participants_settlement_id", "settlement_participants", ["settlement_id"])

    # 3. Partial UNIQUE / Composite UNIQUE 제약조건 추가
    # budgets category_id IS NULL 에 대한 partial unique index
    op.create_index(
        "uq_budget_overall",
        "budgets",
        ["user_id", "year_month"],
        unique=True,
        postgresql_where=sa.text("category_id IS NULL")
    )
    # settlement_participants user_id IS NOT NULL 에 대한 partial unique index
    op.create_index(
        "uq_settlement_participant_user",
        "settlement_participants",
        ["settlement_id", "user_id"],
        unique=True,
        postgresql_where=sa.text("user_id IS NOT NULL")
    )
    # import_hashes hash 단독 UNIQUE drop 후 (user_id, hash) 복합 unique 설정
    op.drop_constraint("import_hashes_hash_key", "import_hashes", type_="unique")
    op.create_unique_constraint("uq_import_hashes_user_hash", "import_hashes", ["user_id", "hash"])

    # 4. server_default 및 nullable=False 동기화
    op.alter_column("users", "created_at", server_default=sa.text("CURRENT_TIMESTAMP"))
    op.alter_column("refresh_tokens", "created_at", server_default=sa.text("CURRENT_TIMESTAMP"))
    op.alter_column("import_hashes", "created_at", server_default=sa.text("CURRENT_TIMESTAMP"))
    op.alter_column("transactions", "created_at", server_default=sa.text("CURRENT_TIMESTAMP"))
    op.alter_column("transactions", "updated_at", server_default=sa.text("CURRENT_TIMESTAMP"))
    op.alter_column("settlements", "status", server_default="PENDING")
    op.alter_column("settlements", "created_at", server_default=sa.text("CURRENT_TIMESTAMP"))
    op.alter_column("settlement_participants", "status", server_default="PENDING")
    op.alter_column("budgets", "is_warning_notified", server_default=sa.text("false"), nullable=False)
    op.alter_column("budgets", "is_exceeded_notified", server_default=sa.text("false"), nullable=False)
    op.alter_column("notifications", "is_read", server_default=sa.text("false"), nullable=False)
    op.alter_column("notifications", "created_at", server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False)


def downgrade() -> None:
    """Downgrade schema."""
    # 4. server_default 및 nullable=False 원복
    op.alter_column("notifications", "created_at", server_default=None, nullable=True)
    op.alter_column("notifications", "is_read", server_default=None, nullable=True)
    op.alter_column("budgets", "is_exceeded_notified", server_default=None, nullable=True)
    op.alter_column("budgets", "is_warning_notified", server_default=None, nullable=True)
    op.alter_column("settlement_participants", "status", server_default=None)
    op.alter_column("settlements", "created_at", server_default=None)
    op.alter_column("settlements", "status", server_default=None)
    op.alter_column("transactions", "updated_at", server_default=None)
    op.alter_column("transactions", "created_at", server_default=None)
    op.alter_column("import_hashes", "created_at", server_default=None)
    op.alter_column("refresh_tokens", "created_at", server_default=None)
    op.alter_column("users", "created_at", server_default=None)

    # 3. Partial UNIQUE / Composite UNIQUE 원복
    op.drop_constraint("uq_import_hashes_user_hash", "import_hashes", type_="unique")
    op.create_unique_constraint("import_hashes_hash_key", "import_hashes", ["hash"])
    op.drop_index("uq_settlement_participant_user", "settlement_participants")
    op.drop_index("uq_budget_overall", "budgets")

    # 2. Composite / 단일 인덱스 삭제
    op.drop_index("ix_settlement_participants_settlement_id", "settlement_participants")
    op.drop_index("ix_notifications_user_is_read", "notifications")
    op.drop_index("ix_settlements_transaction_id", "settlements")
    op.drop_index("ix_settlements_creator_id", "settlements")
    op.drop_index("ix_goals_user_category", "goals")
    op.drop_index("ix_transactions_category_id", "transactions")
    op.drop_index("ix_transactions_user_date", "transactions")

    # 1. CHECK Constraints 삭제
    op.drop_constraint("ck_budget_year_month_format", "budgets")
    op.drop_constraint("ck_settlement_participant_amount_ge_zero", "settlement_participants")
    op.drop_constraint("ck_goal_target_amount_gt_zero", "goals")
    op.drop_constraint("ck_budget_amount_gt_zero", "budgets")
    op.drop_constraint("ck_transaction_amount_gt_zero", "transactions")

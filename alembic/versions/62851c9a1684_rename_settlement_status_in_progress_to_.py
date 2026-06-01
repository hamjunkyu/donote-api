"""rename settlement_status IN_PROGRESS to PENDING

Revision ID: 62851c9a1684
Revises: 11f31d77710f
Create Date: 2026-06-01 15:02:36.488217

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '62851c9a1684'
down_revision: Union[str, Sequence[str], None] = '11f31d77710f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """settlement_status enum 값 IN_PROGRESS → PENDING 으로 통일.

    초기 마이그레이션은 enum 을 IN_PROGRESS 로 생성하나 모델/코드는 PENDING 을 쓴다.
    IN_PROGRESS 가 존재할 때만 rename (이미 PENDING 인 DB 에서는 skip) — 멱등.
    """
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM pg_enum e
                JOIN pg_type t ON e.enumtypid = t.oid
                WHERE t.typname = 'settlement_status' AND e.enumlabel = 'IN_PROGRESS'
            ) THEN
                ALTER TYPE settlement_status RENAME VALUE 'IN_PROGRESS' TO 'PENDING';
            END IF;
        END$$;
        """
    )


def downgrade() -> None:
    """PENDING → IN_PROGRESS 복원 (멱등)."""
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM pg_enum e
                JOIN pg_type t ON e.enumtypid = t.oid
                WHERE t.typname = 'settlement_status' AND e.enumlabel = 'PENDING'
            ) THEN
                ALTER TYPE settlement_status RENAME VALUE 'PENDING' TO 'IN_PROGRESS';
            END IF;
        END$$;
        """
    )

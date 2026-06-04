"""add categories unique constraint

Revision ID: 9435638609c2
Revises: 62851c9a1684
Create Date: 2026-06-05 01:51:21.577368

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9435638609c2'
down_revision: Union[str, Sequence[str], None] = '62851c9a1684'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_unique_constraint(
        "uq_category_user_name_type",
        "categories",
        ["user_id", "name", "type"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(
        "uq_category_user_name_type",
        "categories",
        type_="unique",
    )

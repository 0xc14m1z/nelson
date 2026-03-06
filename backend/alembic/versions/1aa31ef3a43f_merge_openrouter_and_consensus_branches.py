"""merge openrouter and consensus branches

Revision ID: 1aa31ef3a43f
Revises: 8a4ac0743e64, cd633003e3e4
Create Date: 2026-03-06 13:37:18.856302

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1aa31ef3a43f'
down_revision: Union[str, Sequence[str], None] = ('8a4ac0743e64', 'cd633003e3e4')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass

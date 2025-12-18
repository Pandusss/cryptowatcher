"""add_price_to_notification_value_type

Revision ID: d21e5e103698
Revises: c7f3a8b9d2e1
Create Date: 2025-12-08 21:09:02.816198

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd21e5e103698'
down_revision = 'c7f3a8b9d2e1'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add new value 'PRICE' to enum 'notificationvaluetype'
    op.execute("ALTER TYPE notificationvaluetype ADD VALUE IF NOT EXISTS 'PRICE'")


def downgrade() -> None:
    # PostgreSQL does not support removing values from enums directly.
    # Would need to create a new enum without this value and replace the old one.
    # This is a complex operation, so leaving empty or implement if needed.
    # For production, it's better not to downgrade enum changes.
    pass


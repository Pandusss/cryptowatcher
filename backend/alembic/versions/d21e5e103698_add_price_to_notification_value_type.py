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
    # Добавляем новое значение 'PRICE' в enum 'notificationvaluetype'
    op.execute("ALTER TYPE notificationvaluetype ADD VALUE IF NOT EXISTS 'PRICE'")


def downgrade() -> None:
    # В PostgreSQL нельзя удалить значение из enum напрямую
    # Нужно создать новый enum без этого значения и заменить старый
    # Это сложная операция, поэтому оставляем пустым или реализуем при необходимости
    # Для продакшена лучше не делать downgrade для enum изменений
    pass


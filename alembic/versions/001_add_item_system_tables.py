"""Add item system tables.

Revision ID: 001
Revises:
Create Date: 2026-01-03

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Create buff_type enum
    buff_type_enum = sa.Enum(
        "damage",
        "crit_chance",
        "armor_penetration",
        "armor",
        "max_health",
        "evasion",
        "healing_power",
        "ability_power",
        name="buff_type",
    )
    buff_type_enum.create(op.get_bind(), checkfirst=True)

    # Create ability_type enum
    ability_type_enum = sa.Enum(
        "attack",
        "defense",
        "misc",
        name="ability_type",
    )
    ability_type_enum.create(op.get_bind(), checkfirst=True)

    # Create ability_effect enum
    ability_effect_enum = sa.Enum(
        "physical_damage",
        "magical_damage",
        "bleed",
        "block",
        "evade",
        "reflect",
        "heal",
        "counterspell",
        "buff_self",
        "debuff_enemy",
        name="ability_effect",
    )
    ability_effect_enum.create(op.get_bind(), checkfirst=True)

    # Create item_slot enum
    item_slot_enum = sa.Enum(
        "attack",
        "defense",
        "misc",
        name="item_slot",
    )
    item_slot_enum.create(op.get_bind(), checkfirst=True)

    # Create buff_definitions table
    op.create_table(
        "buff_definitions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False, unique=True),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("buff_type", buff_type_enum, nullable=False),
        sa.Column("base_value", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # Create ability_definitions table
    op.create_table(
        "ability_definitions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False, unique=True),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("ability_type", ability_type_enum, nullable=False),
        sa.Column("effect", ability_effect_enum, nullable=False),
        sa.Column("base_power", sa.Integer(), nullable=False, server_default="10"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # Create items table
    op.create_table(
        "items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("slot", item_slot_enum, nullable=False),
        sa.Column("rarity", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("ability_id", sa.Integer(), sa.ForeignKey("ability_definitions.id"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # Create item_buffs association table
    op.create_table(
        "item_buffs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("item_id", sa.Integer(), sa.ForeignKey("items.id"), nullable=False),
        sa.Column(
            "buff_definition_id",
            sa.Integer(),
            sa.ForeignKey("buff_definitions.id"),
            nullable=False,
        ),
        sa.Column("value", sa.Integer(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("item_buffs")
    op.drop_table("items")
    op.drop_table("ability_definitions")
    op.drop_table("buff_definitions")

    # Drop enums
    sa.Enum(name="item_slot").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="ability_effect").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="ability_type").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="buff_type").drop(op.get_bind(), checkfirst=True)

"""Rework to procedural effect system.

Revision ID: 002
Revises: 001
Create Date: 2026-01-03

This migration replaces the static buff/ability system with a dynamic
procedural effect system that supports per-chat settings and composable
conditions/actions.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision: str = "002"
down_revision: str | None = "001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ============================================
    # Drop old tables (in reverse dependency order)
    # ============================================
    op.drop_table("item_buffs")
    op.drop_table("items")
    op.drop_table("ability_definitions")
    op.drop_table("buff_definitions")

    # Drop old enums (keep item_slot as it's still used)
    sa.Enum(name="ability_effect").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="ability_type").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="buff_type").drop(op.get_bind(), checkfirst=True)

    # ============================================
    # Create new enums
    # ============================================
    attribute_category_enum = sa.Enum(
        "core_hp",
        "core_special",
        "generatable",
        name="attribute_category",
    )
    attribute_category_enum.create(op.get_bind(), checkfirst=True)

    action_type_enum = sa.Enum(
        "damage",
        "attack",
        "heal",
        "add_stacks",
        "remove_stacks",
        "modify_max",
        "modify_current_max",
        "spend",
        "reduce_incoming_damage",
        name="action_type",
    )
    action_type_enum.create(op.get_bind(), checkfirst=True)

    condition_phase_enum = sa.Enum(
        "pre_attack",
        "post_attack",
        "pre_damage",
        "post_damage",
        "pre_move",
        "post_move",
        name="condition_phase",
    )
    condition_phase_enum.create(op.get_bind(), checkfirst=True)

    condition_type_enum = sa.Enum(
        "phase",
        "has_stacks",
        "and",
        "or",
        name="condition_type",
    )
    condition_type_enum.create(op.get_bind(), checkfirst=True)

    target_type_enum = sa.Enum(
        "self",
        "enemy",
        name="target_type",
    )
    target_type_enum.create(op.get_bind(), checkfirst=True)

    effect_category_enum = sa.Enum(
        "item_effect",
        "world_rule",
        name="effect_category",
    )
    effect_category_enum.create(op.get_bind(), checkfirst=True)

    # ============================================
    # Create settings table
    # ============================================
    op.create_table(
        "settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("telegram_chat_id", sa.BigInteger(), nullable=False, unique=True, index=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("special_points_name", sa.String(50), nullable=False, server_default="Mana"),
        sa.Column("special_points_regen", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("max_generatable_attributes", sa.Integer(), nullable=False, server_default="3"),
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

    # ============================================
    # Create attribute_definitions table
    # ============================================
    op.create_table(
        "attribute_definitions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("setting_id", sa.Integer(), sa.ForeignKey("settings.id"), nullable=False, index=True),
        sa.Column("name", sa.String(50), nullable=False),
        sa.Column("display_name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("category", attribute_category_enum, nullable=False),
        sa.Column("max_stacks", sa.Integer(), nullable=True),
        sa.Column("default_stacks", sa.Integer(), nullable=False, server_default="0"),
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

    # ============================================
    # Create conditions table
    # ============================================
    op.create_table(
        "conditions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False, unique=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("condition_type", condition_type_enum, nullable=False),
        sa.Column("condition_data", JSONB(), nullable=False),
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

    # ============================================
    # Create actions table
    # ============================================
    op.create_table(
        "actions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False, unique=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("action_type", action_type_enum, nullable=False),
        sa.Column("action_data", JSONB(), nullable=False),
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

    # ============================================
    # Create items table (new version with setting_id)
    # ============================================
    # Get the existing item_slot enum
    item_slot_enum = sa.Enum(
        "attack",
        "defense",
        "misc",
        name="item_slot",
    )

    op.create_table(
        "items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("slot", item_slot_enum, nullable=False),
        sa.Column("rarity", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("setting_id", sa.Integer(), sa.ForeignKey("settings.id"), nullable=False, index=True),
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

    # ============================================
    # Create effects table
    # ============================================
    op.create_table(
        "effects",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False, index=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("condition_id", sa.Integer(), sa.ForeignKey("conditions.id"), nullable=False),
        sa.Column("target", target_type_enum, nullable=False),
        sa.Column("category", effect_category_enum, nullable=False),
        sa.Column("action_id", sa.Integer(), sa.ForeignKey("actions.id"), nullable=False),
        sa.Column("setting_id", sa.Integer(), sa.ForeignKey("settings.id"), nullable=True, index=True),
        sa.Column("item_id", sa.Integer(), sa.ForeignKey("items.id"), nullable=True, index=True),
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


def downgrade() -> None:
    # Drop new tables
    op.drop_table("effects")
    op.drop_table("items")
    op.drop_table("actions")
    op.drop_table("conditions")
    op.drop_table("attribute_definitions")
    op.drop_table("settings")

    # Drop new enums
    sa.Enum(name="effect_category").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="target_type").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="condition_type").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="condition_phase").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="action_type").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="attribute_category").drop(op.get_bind(), checkfirst=True)

    # Recreate old enums
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

    ability_type_enum = sa.Enum(
        "attack",
        "defense",
        "misc",
        name="ability_type",
    )
    ability_type_enum.create(op.get_bind(), checkfirst=True)

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

    # Recreate old tables
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

    # Get existing item_slot enum
    item_slot_enum = sa.Enum(
        "attack",
        "defense",
        "misc",
        name="item_slot",
    )

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

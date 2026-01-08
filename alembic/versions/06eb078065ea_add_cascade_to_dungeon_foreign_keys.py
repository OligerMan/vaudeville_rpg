"""Add CASCADE to dungeon foreign keys

Revision ID: 06eb078065ea
Revises: 007
Create Date: 2026-01-08 17:21:56.844261

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '06eb078065ea'
down_revision: Union[str, None] = '007'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add CASCADE to foreign keys for proper deletion handling."""
    from sqlalchemy import inspect
    conn = op.get_bind()
    inspector = inspect(conn)

    # Helper function to safely drop and recreate foreign keys
    def update_fk(table_name, constraint_name, source_column, target_table, target_column, ondelete='CASCADE'):
        """Drop and recreate a foreign key constraint with CASCADE."""
        # Get existing constraints
        existing_fks = [fk['name'] for fk in inspector.get_foreign_keys(table_name)]

        # Drop if exists
        if constraint_name in existing_fks:
            op.drop_constraint(constraint_name, table_name, type_='foreignkey')

        # Recreate with CASCADE
        op.create_foreign_key(
            constraint_name,
            table_name, target_table,
            [source_column], [target_column],
            ondelete=ondelete
        )

    # Fix dungeon_enemies.dungeon_id -> dungeons.id (CASCADE)
    update_fk('dungeon_enemies', 'dungeon_enemies_dungeon_id_fkey',
              'dungeon_id', 'dungeons', 'id', 'CASCADE')

    # Fix dungeon_enemies.enemy_player_id -> players.id (CASCADE)
    update_fk('dungeon_enemies', 'dungeon_enemies_enemy_player_id_fkey',
              'enemy_player_id', 'players', 'id', 'CASCADE')

    # Fix dungeons.player_id -> players.id (CASCADE)
    update_fk('dungeons', 'dungeons_player_id_fkey',
              'player_id', 'players', 'id', 'CASCADE')

    # Fix dungeons.setting_id -> settings.id (CASCADE)
    update_fk('dungeons', 'dungeons_setting_id_fkey',
              'setting_id', 'settings', 'id', 'CASCADE')

    # Fix dungeons.current_duel_id -> duels.id (SET NULL on delete)
    update_fk('dungeons', 'dungeons_current_duel_id_fkey',
              'current_duel_id', 'duels', 'id', 'SET NULL')

    # Fix duel_participants.duel_id -> duels.id (CASCADE)
    update_fk('duel_participants', 'duel_participants_duel_id_fkey',
              'duel_id', 'duels', 'id', 'CASCADE')

    # Fix duel_participants.player_id -> players.id (CASCADE)
    update_fk('duel_participants', 'duel_participants_player_id_fkey',
              'player_id', 'players', 'id', 'CASCADE')

    # Fix duel_actions.duel_id -> duels.id (CASCADE)
    update_fk('duel_actions', 'duel_actions_duel_id_fkey',
              'duel_id', 'duels', 'id', 'CASCADE')

    # Fix duel_actions.participant_id -> duel_participants.id (CASCADE)
    update_fk('duel_actions', 'duel_actions_participant_id_fkey',
              'participant_id', 'duel_participants', 'id', 'CASCADE')

    # Fix player_combat_states.duel_id -> duels.id (CASCADE)
    # Check for the actual constraint name
    pcs_fks = [fk['name'] for fk in inspector.get_foreign_keys('player_combat_states')]
    for fk_name in pcs_fks:
        fk_details = [fk for fk in inspector.get_foreign_keys('player_combat_states') if fk['name'] == fk_name][0]
        if 'duel_id' in fk_details['constrained_columns']:
            update_fk('player_combat_states', fk_name,
                      'duel_id', 'duels', 'id', 'CASCADE')
            break

    # Fix duels.setting_id -> settings.id (CASCADE)
    update_fk('duels', 'duels_setting_id_fkey',
              'setting_id', 'settings', 'id', 'CASCADE')


def downgrade() -> None:
    """Remove CASCADE from foreign keys (restore original state)."""

    # Restore original foreign keys without CASCADE
    op.drop_constraint('dungeon_enemies_dungeon_id_fkey', 'dungeon_enemies', type_='foreignkey')
    op.create_foreign_key(
        'dungeon_enemies_dungeon_id_fkey',
        'dungeon_enemies', 'dungeons',
        ['dungeon_id'], ['id']
    )

    op.drop_constraint('dungeon_enemies_enemy_player_id_fkey', 'dungeon_enemies', type_='foreignkey')
    op.create_foreign_key(
        'dungeon_enemies_enemy_player_id_fkey',
        'dungeon_enemies', 'players',
        ['enemy_player_id'], ['id']
    )

    op.drop_constraint('dungeons_player_id_fkey', 'dungeons', type_='foreignkey')
    op.create_foreign_key(
        'dungeons_player_id_fkey',
        'dungeons', 'players',
        ['player_id'], ['id']
    )

    op.drop_constraint('dungeons_setting_id_fkey', 'dungeons', type_='foreignkey')
    op.create_foreign_key(
        'dungeons_setting_id_fkey',
        'dungeons', 'settings',
        ['setting_id'], ['id']
    )

    op.drop_constraint('dungeons_current_duel_id_fkey', 'dungeons', type_='foreignkey')
    op.create_foreign_key(
        'dungeons_current_duel_id_fkey',
        'dungeons', 'duels',
        ['current_duel_id'], ['id']
    )

    op.drop_constraint('duel_participants_duel_id_fkey', 'duel_participants', type_='foreignkey')
    op.create_foreign_key(
        'duel_participants_duel_id_fkey',
        'duel_participants', 'duels',
        ['duel_id'], ['id']
    )

    op.drop_constraint('duel_participants_player_id_fkey', 'duel_participants', type_='foreignkey')
    op.create_foreign_key(
        'duel_participants_player_id_fkey',
        'duel_participants', 'players',
        ['player_id'], ['id']
    )

    op.drop_constraint('duel_actions_duel_id_fkey', 'duel_actions', type_='foreignkey')
    op.create_foreign_key(
        'duel_actions_duel_id_fkey',
        'duel_actions', 'duels',
        ['duel_id'], ['id']
    )

    op.drop_constraint('duel_actions_participant_id_fkey', 'duel_actions', type_='foreignkey')
    op.create_foreign_key(
        'duel_actions_participant_id_fkey',
        'duel_actions', 'duel_participants',
        ['participant_id'], ['id']
    )

    op.drop_constraint('fk_combat_state_duel', 'player_combat_states', type_='foreignkey')
    op.create_foreign_key(
        'fk_combat_state_duel',
        'player_combat_states', 'duels',
        ['duel_id'], ['id']
    )

    op.drop_constraint('duels_setting_id_fkey', 'duels', type_='foreignkey')
    op.create_foreign_key(
        'duels_setting_id_fkey',
        'duels', 'settings',
        ['setting_id'], ['id']
    )

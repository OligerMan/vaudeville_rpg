"""Integration tests for duel system with database."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from vaudeville_rpg.db.models import (
    Duel,
    DuelActionType,
    DuelStatus,
    Item,
    Player,
    PlayerCombatState,
    Setting,
)
from vaudeville_rpg.engine.duel import DuelEngine
from vaudeville_rpg.services.duels import DuelService
from vaudeville_rpg.services.players import PlayerService


class TestPlayerService:
    """Integration tests for PlayerService."""

    async def test_get_or_create_player_creates_new(self, db_session: AsyncSession, setting: Setting):
        """Test creating a new player."""
        service = PlayerService(db_session)

        player = await service.get_or_create_player(
            telegram_user_id=999999,
            setting_id=setting.id,
            display_name="NewPlayer",
        )

        assert player.id is not None
        assert player.telegram_user_id == 999999
        assert player.display_name == "NewPlayer"
        assert player.rating == 1000
        assert player.max_hp == 100

    async def test_get_or_create_player_returns_existing(self, db_session: AsyncSession, player1: Player):
        """Test getting existing player."""
        service = PlayerService(db_session)

        player = await service.get_or_create_player(
            telegram_user_id=player1.telegram_user_id,
            setting_id=player1.setting_id,
            display_name="UpdatedName",
        )

        assert player.id == player1.id
        assert player.display_name == "UpdatedName"

    async def test_get_or_create_setting_creates_new(self, db_session: AsyncSession):
        """Test creating a new setting."""
        service = PlayerService(db_session)

        setting = await service.get_or_create_setting(telegram_chat_id=987654321)

        assert setting.id is not None
        assert setting.telegram_chat_id == 987654321
        assert setting.name == "Default Setting"
        assert setting.special_points_name == "Mana"

    async def test_get_or_create_setting_returns_existing(self, db_session: AsyncSession, setting: Setting):
        """Test getting existing setting."""
        service = PlayerService(db_session)

        result = await service.get_or_create_setting(telegram_chat_id=setting.telegram_chat_id)

        assert result.id == setting.id


class TestDuelEngine:
    """Integration tests for DuelEngine."""

    async def test_create_duel(self, db_session: AsyncSession, setting: Setting, player1: Player, player2: Player):
        """Test creating a duel."""
        engine = DuelEngine(db_session)

        result = await engine.create_duel(setting.id, player1.id, player2.id)

        assert result.success is True
        assert result.duel_id is not None

        # Verify duel in database
        stmt = select(Duel).where(Duel.id == result.duel_id)
        db_result = await db_session.execute(stmt)
        duel = db_result.scalar_one()

        assert duel.status == DuelStatus.PENDING
        assert duel.setting_id == setting.id

    async def test_start_duel_creates_combat_states(self, db_session: AsyncSession, setting: Setting, player1: Player, player2: Player):
        """Test starting a duel creates combat states."""
        engine = DuelEngine(db_session)

        # Create and start duel
        create_result = await engine.create_duel(setting.id, player1.id, player2.id)
        start_result = await engine.start_duel(create_result.duel_id)

        assert start_result.success is True

        # Verify combat states created
        stmt = select(PlayerCombatState).where(PlayerCombatState.duel_id == create_result.duel_id)
        db_result = await db_session.execute(stmt)
        states = db_result.scalars().all()

        assert len(states) == 2

        # Both players should have full HP
        for state in states:
            assert state.current_hp == 100
            assert state.current_special_points == 50

    async def test_submit_action_and_resolve_turn(
        self,
        db_session: AsyncSession,
        setting: Setting,
        equipped_player1: Player,
        equipped_player2: Player,
    ):
        """Test submitting actions and resolving a turn."""
        engine = DuelEngine(db_session)

        # Create and start duel
        create_result = await engine.create_duel(setting.id, equipped_player1.id, equipped_player2.id)
        await engine.start_duel(create_result.duel_id)

        # Player 1 attacks
        result1 = await engine.submit_action(
            create_result.duel_id,
            equipped_player1.id,
            DuelActionType.ATTACK,
            equipped_player1.attack_item_id,
        )
        assert result1.success is True
        assert result1.turn_result is None  # Waiting for player 2

        # Player 2 attacks
        result2 = await engine.submit_action(
            create_result.duel_id,
            equipped_player2.id,
            DuelActionType.ATTACK,
            equipped_player2.attack_item_id,
        )
        assert result2.success is True
        assert result2.turn_result is not None  # Turn resolved

        # Check HP changed
        state = await engine.get_duel_state(create_result.duel_id)
        assert state is not None
        # Both players took 15 damage from the sword
        # State uses participants list with combat_state
        for p in state["participants"]:
            assert p["combat_state"]["current_hp"] == 85

    async def test_duel_to_completion(
        self,
        db_session: AsyncSession,
        setting: Setting,
        equipped_player1: Player,
        equipped_player2: Player,
    ):
        """Test a full duel until someone wins."""
        engine = DuelEngine(db_session)

        create_result = await engine.create_duel(setting.id, equipped_player1.id, equipped_player2.id)
        await engine.start_duel(create_result.duel_id)

        # Fight until someone dies (100 HP, 15 damage per hit = 7 turns)
        winner_participant_id = None
        for turn in range(10):
            # Player 1 attacks
            await engine.submit_action(
                create_result.duel_id,
                equipped_player1.id,
                DuelActionType.ATTACK,
                equipped_player1.attack_item_id,
            )

            # Player 2 skips (to ensure player 1 wins)
            result = await engine.submit_action(
                create_result.duel_id,
                equipped_player2.id,
                DuelActionType.SKIP,
                None,
            )

            if result.turn_result and result.turn_result.winner_participant_id:
                winner_participant_id = result.turn_result.winner_participant_id
                break

        assert winner_participant_id is not None

        # Verify duel marked as completed
        stmt = select(Duel).where(Duel.id == create_result.duel_id)
        db_result = await db_session.execute(stmt)
        duel = db_result.scalar_one()
        assert duel.status == DuelStatus.COMPLETED

    async def test_cancel_duel(self, db_session: AsyncSession, setting: Setting, player1: Player, player2: Player):
        """Test canceling a duel."""
        engine = DuelEngine(db_session)

        create_result = await engine.create_duel(setting.id, player1.id, player2.id)
        cancel_result = await engine.cancel_duel(create_result.duel_id)

        assert cancel_result.success is True

        # Verify status
        stmt = select(Duel).where(Duel.id == create_result.duel_id)
        db_result = await db_session.execute(stmt)
        duel = db_result.scalar_one()
        assert duel.status == DuelStatus.CANCELLED


class TestDuelService:
    """Integration tests for DuelService."""

    async def test_create_challenge(self, db_session: AsyncSession, setting: Setting, player1: Player, player2: Player):
        """Test creating a duel challenge."""
        service = DuelService(db_session)

        result = await service.create_challenge(setting.id, player1.id, player2.id)

        assert result.success is True
        assert result.duel_id is not None

    async def test_cannot_challenge_while_in_duel(self, db_session: AsyncSession, setting: Setting, player1: Player, player2: Player):
        """Test that player can't challenge while in active duel."""
        service = DuelService(db_session)

        # Create first challenge
        await service.create_challenge(setting.id, player1.id, player2.id)

        # Try to create another challenge with player1
        # Need a third player
        player3 = Player(
            telegram_user_id=333333,
            setting_id=setting.id,
            display_name="Player3",
            max_hp=100,
            max_special_points=50,
            rating=1000,
        )
        db_session.add(player3)
        await db_session.flush()

        result = await service.create_challenge(setting.id, player1.id, player3.id)

        assert result.success is False
        assert "already in an active duel" in result.message

    async def test_accept_challenge(self, db_session: AsyncSession, setting: Setting, player1: Player, player2: Player):
        """Test accepting a duel challenge."""
        service = DuelService(db_session)

        # Create challenge
        create_result = await service.create_challenge(setting.id, player1.id, player2.id)

        # Accept as player 2
        accept_result = await service.accept_challenge(create_result.duel_id, player2.id)

        assert accept_result.success is True

        # Verify duel is now in progress
        stmt = select(Duel).where(Duel.id == create_result.duel_id)
        db_result = await db_session.execute(stmt)
        duel = db_result.scalar_one()
        assert duel.status == DuelStatus.IN_PROGRESS

    async def test_decline_challenge(self, db_session: AsyncSession, setting: Setting, player1: Player, player2: Player):
        """Test declining a duel challenge."""
        service = DuelService(db_session)

        create_result = await service.create_challenge(setting.id, player1.id, player2.id)
        decline_result = await service.decline_challenge(create_result.duel_id, player2.id)

        assert decline_result.success is True

        # Verify duel is cancelled
        stmt = select(Duel).where(Duel.id == create_result.duel_id)
        db_result = await db_session.execute(stmt)
        duel = db_result.scalar_one()
        assert duel.status == DuelStatus.CANCELLED

    async def test_wrong_player_cannot_accept(self, db_session: AsyncSession, setting: Setting, player1: Player, player2: Player):
        """Test that wrong player can't accept challenge."""
        service = DuelService(db_session)

        create_result = await service.create_challenge(setting.id, player1.id, player2.id)

        # Try to accept as player 1 (the challenger)
        result = await service.accept_challenge(create_result.duel_id, player1.id)

        assert result.success is False
        assert "not the challenged player" in result.message

    async def test_full_duel_flow_with_service(
        self,
        db_session: AsyncSession,
        setting: Setting,
        equipped_player1: Player,
        equipped_player2: Player,
    ):
        """Test complete duel flow: challenge -> accept -> fight -> winner."""
        service = DuelService(db_session)

        # Challenge
        create_result = await service.create_challenge(setting.id, equipped_player1.id, equipped_player2.id)
        assert create_result.success is True

        # Accept
        accept_result = await service.accept_challenge(create_result.duel_id, equipped_player2.id)
        assert accept_result.success is True

        # Fight one round
        await service.submit_action(create_result.duel_id, equipped_player1.id, DuelActionType.ATTACK)
        result = await service.submit_action(create_result.duel_id, equipped_player2.id, DuelActionType.ATTACK)

        assert result.success is True
        assert result.turn_result is not None

        # Both should have taken damage
        state = await service.get_duel_state(create_result.duel_id)
        for p in state["participants"]:
            assert p["combat_state"]["current_hp"] < 100


class TestDuelWithItems:
    """Integration tests for duels with item effects."""

    async def test_attack_item_deals_damage(
        self,
        db_session: AsyncSession,
        setting: Setting,
        equipped_player1: Player,
        equipped_player2: Player,
    ):
        """Test that attack item deals correct damage."""
        engine = DuelEngine(db_session)

        create_result = await engine.create_duel(setting.id, equipped_player1.id, equipped_player2.id)
        await engine.start_duel(create_result.duel_id)

        # Player 1 attacks, player 2 skips
        await engine.submit_action(
            create_result.duel_id,
            equipped_player1.id,
            DuelActionType.ATTACK,
            equipped_player1.attack_item_id,
        )
        await engine.submit_action(
            create_result.duel_id,
            equipped_player2.id,
            DuelActionType.SKIP,
            None,
        )

        state = await engine.get_duel_state(create_result.duel_id)
        # Find player states by turn_order
        p1_state = next(p for p in state["participants"] if p["turn_order"] == 1)
        p2_state = next(p for p in state["participants"] if p["turn_order"] == 2)
        # Player 2 took 15 damage (sword base damage)
        assert p2_state["combat_state"]["current_hp"] == 85
        # Player 1 took no damage
        assert p1_state["combat_state"]["current_hp"] == 100

    async def test_defense_item_adds_armor(
        self,
        db_session: AsyncSession,
        setting_with_attributes: Setting,
        equipped_player1: Player,
        equipped_player2: Player,
    ):
        """Test that defense item adds armor stacks."""
        # Update players to use setting with attributes
        equipped_player1.setting_id = setting_with_attributes.id
        equipped_player2.setting_id = setting_with_attributes.id
        await db_session.flush()

        engine = DuelEngine(db_session)

        create_result = await engine.create_duel(setting_with_attributes.id, equipped_player1.id, equipped_player2.id)
        await engine.start_duel(create_result.duel_id)

        # Player 1 uses defense, player 2 skips
        await engine.submit_action(
            create_result.duel_id,
            equipped_player1.id,
            DuelActionType.DEFENSE,
            equipped_player1.defense_item_id,
        )
        await engine.submit_action(
            create_result.duel_id,
            equipped_player2.id,
            DuelActionType.SKIP,
            None,
        )

        state = await engine.get_duel_state(create_result.duel_id)
        # Player 1 should have armor stacks
        p1_state = next(p for p in state["participants"] if p["turn_order"] == 1)
        assert p1_state["combat_state"]["attribute_stacks"].get("armor", 0) == 3

    async def test_misc_item_heals(
        self,
        db_session: AsyncSession,
        setting: Setting,
        equipped_player1: Player,
        equipped_player2: Player,
    ):
        """Test that misc item heals."""
        engine = DuelEngine(db_session)

        create_result = await engine.create_duel(setting.id, equipped_player1.id, equipped_player2.id)
        await engine.start_duel(create_result.duel_id)

        # First turn: player 1 takes damage
        await engine.submit_action(
            create_result.duel_id,
            equipped_player1.id,
            DuelActionType.SKIP,
            None,
        )
        await engine.submit_action(
            create_result.duel_id,
            equipped_player2.id,
            DuelActionType.ATTACK,
            equipped_player2.attack_item_id,
        )

        state = await engine.get_duel_state(create_result.duel_id)
        p1_state = next(p for p in state["participants"] if p["turn_order"] == 1)
        damaged_hp = p1_state["combat_state"]["current_hp"]
        assert damaged_hp == 85  # Took 15 damage

        # Second turn: player 1 heals
        await engine.submit_action(
            create_result.duel_id,
            equipped_player1.id,
            DuelActionType.MISC,
            equipped_player1.misc_item_id,
        )
        await engine.submit_action(
            create_result.duel_id,
            equipped_player2.id,
            DuelActionType.SKIP,
            None,
        )

        state = await engine.get_duel_state(create_result.duel_id)
        p1_state = next(p for p in state["participants"] if p["turn_order"] == 1)
        # Healed for 20, but capped at max HP (100)
        # Was at 85, healed 20 = 105, capped at 100
        assert p1_state["combat_state"]["current_hp"] == 100


class TestRatingIntegration:
    """Integration tests for rating updates after duels."""

    async def test_pvp_duel_updates_ratings(
        self,
        db_session: AsyncSession,
        setting: Setting,
        equipped_player1: Player,
        equipped_player2: Player,
    ):
        """Test that PvP duel updates ratings."""
        engine = DuelEngine(db_session)

        initial_rating1 = equipped_player1.rating
        initial_rating2 = equipped_player2.rating

        create_result = await engine.create_duel(setting.id, equipped_player1.id, equipped_player2.id)
        await engine.start_duel(create_result.duel_id)

        # Player 1 wins
        for _ in range(10):
            await engine.submit_action(
                create_result.duel_id,
                equipped_player1.id,
                DuelActionType.ATTACK,
                equipped_player1.attack_item_id,
            )
            result = await engine.submit_action(
                create_result.duel_id,
                equipped_player2.id,
                DuelActionType.SKIP,
                None,
            )
            if result.turn_result and result.turn_result.winner_participant_id:
                break

        # Refresh players from database
        await db_session.refresh(equipped_player1)
        await db_session.refresh(equipped_player2)

        # Winner gained rating, loser lost rating
        assert equipped_player1.rating > initial_rating1
        assert equipped_player2.rating < initial_rating2

    async def test_pve_duel_does_not_update_rating(
        self,
        db_session: AsyncSession,
        setting: Setting,
        equipped_player1: Player,
        bot_player: Player,
        attack_item: Item,
    ):
        """Test that PvE duel does not update player rating."""
        # Equip bot
        bot_player.attack_item_id = attack_item.id
        await db_session.flush()

        engine = DuelEngine(db_session)

        initial_rating = equipped_player1.rating

        create_result = await engine.create_duel(setting.id, equipped_player1.id, bot_player.id)
        await engine.start_duel(create_result.duel_id)

        # Player wins
        for _ in range(10):
            await engine.submit_action(
                create_result.duel_id,
                equipped_player1.id,
                DuelActionType.ATTACK,
                equipped_player1.attack_item_id,
            )
            result = await engine.submit_action(
                create_result.duel_id,
                bot_player.id,
                DuelActionType.SKIP,
                None,
            )
            if result.turn_result and result.turn_result.winner_participant_id:
                break

        await db_session.refresh(equipped_player1)

        # Rating should not change for PvE
        assert equipped_player1.rating == initial_rating


class TestEnemyGenerator:
    """Integration tests for EnemyGenerator."""

    async def test_generate_enemy_creates_bot(self, db_session: AsyncSession, setting: Setting):
        """Test generating an enemy creates a bot player."""
        from vaudeville_rpg.db.models.enums import DungeonDifficulty
        from vaudeville_rpg.services.enemies import EnemyGenerator

        generator = EnemyGenerator(db_session)

        enemy = await generator.generate_enemy(
            setting_id=setting.id,
            difficulty=DungeonDifficulty.NORMAL,
            stage=1,
        )

        assert enemy.id is not None
        assert enemy.is_bot is True
        assert enemy.telegram_user_id < 0  # Bots have negative IDs
        assert enemy.setting_id == setting.id
        assert enemy.max_hp == 80  # Normal base HP
        assert enemy.max_special_points == 40  # Normal base SP

    async def test_enemy_stats_scale_with_stage(self, db_session: AsyncSession, setting: Setting):
        """Test enemy stats increase with stage."""
        from vaudeville_rpg.db.models.enums import DungeonDifficulty
        from vaudeville_rpg.services.enemies import EnemyGenerator

        generator = EnemyGenerator(db_session)

        enemy1 = await generator.generate_enemy(setting.id, DungeonDifficulty.NORMAL, 1)
        enemy3 = await generator.generate_enemy(setting.id, DungeonDifficulty.NORMAL, 3)

        # Stage 3 should have more HP (base 80 + 2*15 = 110)
        assert enemy3.max_hp > enemy1.max_hp
        assert enemy3.max_hp == 110

    async def test_enemy_stats_scale_with_difficulty(self, db_session: AsyncSession, setting: Setting):
        """Test enemy stats increase with difficulty."""
        from vaudeville_rpg.db.models.enums import DungeonDifficulty
        from vaudeville_rpg.services.enemies import EnemyGenerator

        generator = EnemyGenerator(db_session)

        easy_enemy = await generator.generate_enemy(setting.id, DungeonDifficulty.EASY, 1)
        hard_enemy = await generator.generate_enemy(setting.id, DungeonDifficulty.HARD, 1)

        assert hard_enemy.max_hp > easy_enemy.max_hp
        assert easy_enemy.max_hp == 60  # Easy base
        assert hard_enemy.max_hp == 100  # Hard base


class TestDungeonService:
    """Integration tests for DungeonService."""

    async def test_start_dungeon(
        self,
        db_session: AsyncSession,
        setting: Setting,
        equipped_player1: Player,
    ):
        """Test starting a dungeon."""
        from vaudeville_rpg.db.models.enums import DungeonDifficulty
        from vaudeville_rpg.services.dungeons import DungeonService

        service = DungeonService(db_session)

        result = await service.start_dungeon(
            player_id=equipped_player1.id,
            setting_id=setting.id,
            difficulty=DungeonDifficulty.EASY,
        )

        assert result.success is True
        assert result.dungeon_id is not None
        assert result.duel_id is not None
        assert "Goblin Cave" in result.message

    async def test_cannot_start_dungeon_while_in_dungeon(
        self,
        db_session: AsyncSession,
        setting: Setting,
        equipped_player1: Player,
    ):
        """Test player can't start dungeon while in another."""
        from vaudeville_rpg.db.models.enums import DungeonDifficulty
        from vaudeville_rpg.services.dungeons import DungeonService

        service = DungeonService(db_session)

        # Start first dungeon
        await service.start_dungeon(
            player_id=equipped_player1.id,
            setting_id=setting.id,
            difficulty=DungeonDifficulty.EASY,
        )

        # Try to start another
        result = await service.start_dungeon(
            player_id=equipped_player1.id,
            setting_id=setting.id,
            difficulty=DungeonDifficulty.NORMAL,
        )

        assert result.success is False
        assert "already in a dungeon" in result.message

    async def test_get_dungeon_state(
        self,
        db_session: AsyncSession,
        setting: Setting,
        equipped_player1: Player,
    ):
        """Test getting dungeon state."""
        from vaudeville_rpg.db.models.enums import DungeonDifficulty
        from vaudeville_rpg.services.dungeons import DungeonService

        service = DungeonService(db_session)

        start_result = await service.start_dungeon(
            player_id=equipped_player1.id,
            setting_id=setting.id,
            difficulty=DungeonDifficulty.EASY,
        )

        state = await service.get_dungeon_state(start_result.dungeon_id)

        assert state is not None
        assert state["current_stage"] == 1
        assert state["total_stages"] == 2  # Easy has 2 stages
        assert state["status"] == "in_progress"
        assert state["current_enemy"] is not None

    async def test_abandon_dungeon(
        self,
        db_session: AsyncSession,
        setting: Setting,
        equipped_player1: Player,
    ):
        """Test abandoning a dungeon."""
        from vaudeville_rpg.db.models.enums import DungeonDifficulty
        from vaudeville_rpg.services.dungeons import DungeonService

        service = DungeonService(db_session)

        start_result = await service.start_dungeon(
            player_id=equipped_player1.id,
            setting_id=setting.id,
            difficulty=DungeonDifficulty.EASY,
        )

        abandon_result = await service.abandon_dungeon(
            dungeon_id=start_result.dungeon_id,
            player_id=equipped_player1.id,
        )

        assert abandon_result.success is True

        # Verify status
        state = await service.get_dungeon_state(start_result.dungeon_id)
        assert state["status"] == "abandoned"

    async def test_dungeon_stage_progression(
        self,
        db_session: AsyncSession,
        setting: Setting,
        equipped_player1: Player,
    ):
        """Test dungeon advances to next stage after winning."""
        from vaudeville_rpg.db.models.enums import DungeonDifficulty
        from vaudeville_rpg.services.dungeons import DungeonService

        service = DungeonService(db_session)

        start_result = await service.start_dungeon(
            player_id=equipped_player1.id,
            setting_id=setting.id,
            difficulty=DungeonDifficulty.EASY,
        )

        # Simulate winning stage 1
        result = await service.on_duel_completed(
            dungeon_id=start_result.dungeon_id,
            player_id=equipped_player1.id,
            player_won=True,
        )

        assert result.success is True
        assert result.stage_completed is True
        assert result.duel_id is not None  # New duel started

        # Verify state
        state = await service.get_dungeon_state(start_result.dungeon_id)
        assert state["current_stage"] == 2

    async def test_dungeon_completion(
        self,
        db_session: AsyncSession,
        setting: Setting,
        equipped_player1: Player,
    ):
        """Test dungeon completes after all stages."""
        from vaudeville_rpg.db.models.enums import DungeonDifficulty
        from vaudeville_rpg.services.dungeons import DungeonService

        service = DungeonService(db_session)

        start_result = await service.start_dungeon(
            player_id=equipped_player1.id,
            setting_id=setting.id,
            difficulty=DungeonDifficulty.EASY,  # 2 stages
        )

        # Win stage 1
        await service.on_duel_completed(
            dungeon_id=start_result.dungeon_id,
            player_id=equipped_player1.id,
            player_won=True,
        )

        # Win stage 2 (final)
        result = await service.on_duel_completed(
            dungeon_id=start_result.dungeon_id,
            player_id=equipped_player1.id,
            player_won=True,
        )

        assert result.success is True
        assert result.dungeon_completed is True

        state = await service.get_dungeon_state(start_result.dungeon_id)
        assert state["status"] == "completed"

    async def test_dungeon_failure(
        self,
        db_session: AsyncSession,
        setting: Setting,
        equipped_player1: Player,
    ):
        """Test dungeon fails when player loses."""
        from vaudeville_rpg.db.models.enums import DungeonDifficulty
        from vaudeville_rpg.services.dungeons import DungeonService

        service = DungeonService(db_session)

        start_result = await service.start_dungeon(
            player_id=equipped_player1.id,
            setting_id=setting.id,
            difficulty=DungeonDifficulty.EASY,
        )

        # Lose
        result = await service.on_duel_completed(
            dungeon_id=start_result.dungeon_id,
            player_id=equipped_player1.id,
            player_won=False,
        )

        assert result.success is True
        assert result.dungeon_failed is True

        state = await service.get_dungeon_state(start_result.dungeon_id)
        assert state["status"] == "failed"

"""Dungeon service - handles dungeon operations."""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..db.models.dungeons import Dungeon, DungeonEnemy
from ..db.models.enums import DungeonDifficulty, DungeonStatus
from ..db.models.items import Item
from ..engine.duel import DuelEngine
from .enemies import EnemyGenerator

# Rarity range by difficulty for rewards
REWARD_RARITY_BY_DIFFICULTY: dict[DungeonDifficulty, tuple[int, int]] = {
    DungeonDifficulty.EASY: (1, 1),  # Common only
    DungeonDifficulty.NORMAL: (1, 2),  # Common-Uncommon
    DungeonDifficulty.HARD: (2, 3),  # Uncommon-Rare
    DungeonDifficulty.NIGHTMARE: (2, 3),  # Uncommon-Rare
}


@dataclass
class DungeonResult:
    """Result of a dungeon operation."""

    success: bool
    message: str
    dungeon_id: int | None = None
    duel_id: int | None = None
    stage_completed: bool = False
    dungeon_completed: bool = False
    dungeon_failed: bool = False
    reward_item_id: int | None = None  # Reward item for dungeon completion


class DungeonService:
    """Service for dungeon operations."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.enemy_generator = EnemyGenerator(session)
        self.duel_engine = DuelEngine(session)

    async def start_dungeon(
        self,
        player_id: int,
        setting_id: int,
        difficulty: DungeonDifficulty = DungeonDifficulty.NORMAL,
    ) -> DungeonResult:
        """Start a new dungeon run.

        Args:
            player_id: Player starting the dungeon
            setting_id: Setting for the dungeon
            difficulty: Dungeon difficulty

        Returns:
            DungeonResult with dungeon ID and first duel ID
        """
        # Check if player is already in a dungeon
        active_dungeon = await self._get_active_dungeon(player_id)
        if active_dungeon:
            return DungeonResult(
                success=False,
                message="You are already in a dungeon! Complete or abandon it first.",
                dungeon_id=active_dungeon.id,
            )

        # Get dungeon name based on difficulty
        name = self._get_dungeon_name(difficulty)
        stages = self.enemy_generator.get_stages_for_difficulty(difficulty)

        # Create dungeon
        dungeon = Dungeon(
            player_id=player_id,
            setting_id=setting_id,
            name=name,
            difficulty=difficulty,
            total_stages=stages,
            current_stage=1,
            status=DungeonStatus.IN_PROGRESS,
        )
        self.session.add(dungeon)
        await self.session.flush()

        # Generate enemies for all stages
        for stage in range(1, stages + 1):
            enemy = await self.enemy_generator.generate_enemy(setting_id, difficulty, stage)
            dungeon_enemy = DungeonEnemy(
                dungeon_id=dungeon.id,
                stage=stage,
                enemy_player_id=enemy.id,
                defeated=False,
            )
            self.session.add(dungeon_enemy)

        await self.session.flush()

        # Reload dungeon with enemies to avoid lazy loading issues
        dungeon = await self._get_dungeon_with_enemies(dungeon.id)

        # Start first duel
        result = await self._start_stage_duel(dungeon, player_id)
        if not result.success:
            return result

        return DungeonResult(
            success=True,
            message=f"Entered {name}! Stage 1/{stages}",
            dungeon_id=dungeon.id,
            duel_id=result.duel_id,
        )

    async def get_dungeon_state(self, dungeon_id: int) -> dict | None:
        """Get current dungeon state."""
        dungeon = await self._get_dungeon_with_enemies(dungeon_id)
        if not dungeon:
            return None

        current_enemy = None
        for enemy in dungeon.enemies:
            if enemy.stage == dungeon.current_stage:
                current_enemy = enemy
                break

        return {
            "dungeon_id": dungeon.id,
            "name": dungeon.name,
            "difficulty": dungeon.difficulty.value,
            "current_stage": dungeon.current_stage,
            "total_stages": dungeon.total_stages,
            "status": dungeon.status.value,
            "current_duel_id": dungeon.current_duel_id,
            "current_enemy": {
                "name": current_enemy.enemy_player.display_name,
                "defeated": current_enemy.defeated,
            }
            if current_enemy
            else None,
        }

    async def on_duel_completed(
        self,
        dungeon_id: int,
        player_id: int,
        player_won: bool,
    ) -> DungeonResult:
        """Handle duel completion in a dungeon.

        Args:
            dungeon_id: Dungeon the duel was part of
            player_id: The human player's ID
            player_won: Whether the player won

        Returns:
            DungeonResult with next action
        """
        dungeon = await self._get_dungeon_with_enemies(dungeon_id)
        if not dungeon:
            return DungeonResult(success=False, message="Dungeon not found")

        if dungeon.status != DungeonStatus.IN_PROGRESS:
            return DungeonResult(
                success=False,
                message=f"Dungeon is {dungeon.status.value}",
            )

        if player_won:
            # Mark current enemy as defeated
            for enemy in dungeon.enemies:
                if enemy.stage == dungeon.current_stage:
                    enemy.defeated = True
                    break

            # Check if dungeon complete
            if dungeon.current_stage >= dungeon.total_stages:
                dungeon.status = DungeonStatus.COMPLETED
                dungeon.current_duel_id = None
                await self.session.flush()

                # Generate reward item based on difficulty
                reward_item = await self._generate_reward(dungeon)
                reward_item_id = reward_item.id if reward_item else None

                return DungeonResult(
                    success=True,
                    message=f"🎉 {dungeon.name} completed! All {dungeon.total_stages} stages cleared!",
                    dungeon_id=dungeon.id,
                    dungeon_completed=True,
                    reward_item_id=reward_item_id,
                )

            # Advance to next stage
            dungeon.current_stage += 1
            await self.session.flush()

            # Start next duel
            result = await self._start_stage_duel(dungeon, player_id)
            if not result.success:
                return result

            return DungeonResult(
                success=True,
                message=f"Stage {dungeon.current_stage - 1} cleared! Moving to stage {dungeon.current_stage}/{dungeon.total_stages}",
                dungeon_id=dungeon.id,
                duel_id=result.duel_id,
                stage_completed=True,
            )
        else:
            # Player lost
            dungeon.status = DungeonStatus.FAILED
            dungeon.current_duel_id = None
            await self.session.flush()

            return DungeonResult(
                success=True,
                message=f"💀 Defeated at stage {dungeon.current_stage}/{dungeon.total_stages}. {dungeon.name} failed!",
                dungeon_id=dungeon.id,
                dungeon_failed=True,
            )

    async def abandon_dungeon(self, dungeon_id: int, player_id: int) -> DungeonResult:
        """Abandon a dungeon run.

        Args:
            dungeon_id: Dungeon to abandon
            player_id: Player abandoning

        Returns:
            DungeonResult
        """
        dungeon = await self._get_dungeon(dungeon_id)
        if not dungeon:
            return DungeonResult(success=False, message="Dungeon not found")

        if dungeon.player_id != player_id:
            return DungeonResult(success=False, message="This is not your dungeon")

        if dungeon.status != DungeonStatus.IN_PROGRESS:
            return DungeonResult(
                success=False,
                message=f"Dungeon is already {dungeon.status.value}",
            )

        # Cancel current duel if any
        if dungeon.current_duel_id:
            await self.duel_engine.cancel_duel(dungeon.current_duel_id)

        dungeon.status = DungeonStatus.ABANDONED
        dungeon.current_duel_id = None
        await self.session.flush()

        return DungeonResult(
            success=True,
            message=f"Abandoned {dungeon.name}",
            dungeon_id=dungeon.id,
        )

    async def get_active_dungeon(self, player_id: int) -> Dungeon | None:
        """Get player's active dungeon if any."""
        return await self._get_active_dungeon(player_id)

    async def _start_stage_duel(self, dungeon: Dungeon, player_id: int) -> DungeonResult:
        """Start a duel for the current stage."""
        # Get current stage enemy
        enemy = None
        for e in dungeon.enemies:
            if e.stage == dungeon.current_stage:
                enemy = e
                break

        if not enemy:
            return DungeonResult(success=False, message="No enemy found for stage")

        # Create duel
        duel_result = await self.duel_engine.create_duel(
            setting_id=dungeon.setting_id,
            player1_id=player_id,
            player2_id=enemy.enemy_player_id,
        )

        if not duel_result.success:
            return DungeonResult(success=False, message=duel_result.message)

        # Start duel immediately (PvE doesn't need acceptance)
        start_result = await self.duel_engine.start_duel(duel_result.duel_id)
        if not start_result.success:
            return DungeonResult(success=False, message=start_result.message)

        # Update dungeon with current duel
        dungeon.current_duel_id = duel_result.duel_id
        await self.session.flush()

        return DungeonResult(
            success=True,
            message="Duel started",
            dungeon_id=dungeon.id,
            duel_id=duel_result.duel_id,
        )

    async def _get_dungeon(self, dungeon_id: int) -> Dungeon | None:
        """Get dungeon by ID."""
        stmt = select(Dungeon).where(Dungeon.id == dungeon_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def _get_dungeon_with_enemies(self, dungeon_id: int) -> Dungeon | None:
        """Get dungeon with enemies loaded."""
        stmt = (
            select(Dungeon).where(Dungeon.id == dungeon_id).options(selectinload(Dungeon.enemies).selectinload(DungeonEnemy.enemy_player))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def _get_active_dungeon(self, player_id: int) -> Dungeon | None:
        """Get player's active dungeon."""
        stmt = select(Dungeon).where(
            Dungeon.player_id == player_id,
            Dungeon.status == DungeonStatus.IN_PROGRESS,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    def _get_dungeon_name(self, difficulty: DungeonDifficulty) -> str:
        """Get dungeon name based on difficulty."""
        match difficulty:
            case DungeonDifficulty.EASY:
                return "Goblin Cave"
            case DungeonDifficulty.NORMAL:
                return "Dark Dungeon"
            case DungeonDifficulty.HARD:
                return "Dragon's Lair"
            case DungeonDifficulty.NIGHTMARE:
                return "Abyss of Torment"
            case _:
                return "Mysterious Dungeon"

    async def _generate_reward(self, dungeon: Dungeon) -> Item | None:
        """Generate a reward item for dungeon completion.

        Args:
            dungeon: Completed dungeon

        Returns:
            Reward item or None
        """
        import random

        # Get rarity range for this difficulty
        min_rarity, max_rarity = REWARD_RARITY_BY_DIFFICULTY.get(dungeon.difficulty, (1, 1))

        # Query items within the rarity range for this setting
        stmt = select(Item).where(
            Item.setting_id == dungeon.setting_id,
            Item.rarity >= min_rarity,
            Item.rarity <= max_rarity,
        )
        result = await self.session.execute(stmt)
        items = list(result.scalars().all())

        if not items:
            return None

        return random.choice(items)

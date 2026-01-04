"""Enemy generator - creates bot players for dungeons."""

import random
import time

from sqlalchemy.ext.asyncio import AsyncSession

from ..db.models.enums import DungeonDifficulty
from ..db.models.players import Player

# Enemy name templates
ENEMY_NAMES = [
    "Goblin",
    "Skeleton",
    "Zombie",
    "Orc",
    "Troll",
    "Spider",
    "Wolf",
    "Bandit",
    "Ghost",
    "Slime",
    "Rat",
    "Bat",
    "Snake",
    "Golem",
    "Demon",
]

ENEMY_PREFIXES = [
    "Angry",
    "Vicious",
    "Dark",
    "Shadow",
    "Cursed",
    "Ancient",
    "Giant",
    "Feral",
    "Undead",
    "Corrupted",
]


class EnemyGenerator:
    """Generates bot enemies for dungeons."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def generate_enemy(
        self,
        setting_id: int,
        difficulty: DungeonDifficulty,
        stage: int,
    ) -> Player:
        """Generate a bot enemy for a dungeon stage.

        Args:
            setting_id: Setting this enemy belongs to
            difficulty: Dungeon difficulty (affects stats)
            stage: Current stage (affects stats scaling)

        Returns:
            Created bot Player
        """
        # Generate name
        name = self._generate_name(stage)

        # Calculate stats based on difficulty and stage
        base_hp, base_sp = self._get_base_stats(difficulty)
        hp = base_hp + (stage - 1) * self._get_hp_scaling(difficulty)
        sp = base_sp + (stage - 1) * self._get_sp_scaling(difficulty)

        # Create bot player with unique negative telegram_user_id
        # Use negative timestamp + random to avoid unique constraint conflicts
        unique_bot_id = -(int(time.time() * 1000000) + random.randint(0, 999999))

        enemy = Player(
            telegram_user_id=unique_bot_id,
            setting_id=setting_id,
            display_name=name,
            max_hp=hp,
            max_special_points=sp,
            rating=1000,
            is_bot=True,
        )
        self.session.add(enemy)
        await self.session.flush()

        return enemy

    def _generate_name(self, stage: int) -> str:
        """Generate a random enemy name."""
        base_name = random.choice(ENEMY_NAMES)

        # Higher stages get prefixes
        if stage >= 3:
            prefix = random.choice(ENEMY_PREFIXES)
            return f"{prefix} {base_name}"

        return base_name

    def _get_base_stats(self, difficulty: DungeonDifficulty) -> tuple[int, int]:
        """Get base HP and SP for difficulty."""
        match difficulty:
            case DungeonDifficulty.EASY:
                return (60, 30)
            case DungeonDifficulty.NORMAL:
                return (80, 40)
            case DungeonDifficulty.HARD:
                return (100, 50)
            case DungeonDifficulty.NIGHTMARE:
                return (120, 60)
            case _:
                return (80, 40)

    def _get_hp_scaling(self, difficulty: DungeonDifficulty) -> int:
        """Get HP increase per stage."""
        match difficulty:
            case DungeonDifficulty.EASY:
                return 10
            case DungeonDifficulty.NORMAL:
                return 15
            case DungeonDifficulty.HARD:
                return 20
            case DungeonDifficulty.NIGHTMARE:
                return 30
            case _:
                return 15

    def _get_sp_scaling(self, difficulty: DungeonDifficulty) -> int:
        """Get SP increase per stage."""
        match difficulty:
            case DungeonDifficulty.EASY:
                return 5
            case DungeonDifficulty.NORMAL:
                return 5
            case DungeonDifficulty.HARD:
                return 10
            case DungeonDifficulty.NIGHTMARE:
                return 15
            case _:
                return 5

    def get_stages_for_difficulty(self, difficulty: DungeonDifficulty) -> int:
        """Get number of stages for a difficulty."""
        match difficulty:
            case DungeonDifficulty.EASY:
                return 2
            case DungeonDifficulty.NORMAL:
                return 3
            case DungeonDifficulty.HARD:
                return 4
            case DungeonDifficulty.NIGHTMARE:
                return 5
            case _:
                return 3

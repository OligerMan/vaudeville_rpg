"""Duel service - handles duel operations for bot handlers."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..db.models.duels import Duel, DuelParticipant
from ..db.models.enums import DuelActionType, DuelStatus
from ..db.models.players import Player
from ..engine.duel import DuelEngine, DuelResult


class DuelService:
    """Service for duel operations."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.engine = DuelEngine(session)

    async def create_challenge(
        self,
        setting_id: int,
        challenger_id: int,
        challenged_id: int,
    ) -> DuelResult:
        """Create a new duel challenge.

        Args:
            setting_id: Setting this duel takes place in
            challenger_id: Player ID of the challenger
            challenged_id: Player ID of the challenged player

        Returns:
            DuelResult with the created duel
        """
        # Check if either player is already in an active duel
        active_duel = await self._get_active_duel_for_player(challenger_id)
        if active_duel:
            return DuelResult(
                success=False,
                message="You are already in an active duel!",
            )

        active_duel = await self._get_active_duel_for_player(challenged_id)
        if active_duel:
            return DuelResult(
                success=False,
                message="That player is already in an active duel!",
            )

        return await self.engine.create_duel(setting_id, challenger_id, challenged_id)

    async def accept_challenge(self, duel_id: int, player_id: int) -> DuelResult:
        """Accept a duel challenge.

        Args:
            duel_id: ID of the duel to accept
            player_id: ID of the player accepting

        Returns:
            DuelResult indicating success or failure
        """
        duel = await self._get_duel_with_participants(duel_id)
        if not duel:
            return DuelResult(success=False, message="Duel not found")

        # Check if this player is the challenged one (turn_order=2)
        challenged = None
        for p in duel.participants:
            if p.turn_order == 2:
                challenged = p
                break

        if not challenged or challenged.player_id != player_id:
            return DuelResult(success=False, message="You are not the challenged player")

        return await self.engine.start_duel(duel_id)

    async def decline_challenge(self, duel_id: int, player_id: int) -> DuelResult:
        """Decline a duel challenge.

        Args:
            duel_id: ID of the duel to decline
            player_id: ID of the player declining

        Returns:
            DuelResult indicating success or failure
        """
        duel = await self._get_duel_with_participants(duel_id)
        if not duel:
            return DuelResult(success=False, message="Duel not found")

        # Check if this player is the challenged one
        challenged = None
        for p in duel.participants:
            if p.turn_order == 2:
                challenged = p
                break

        if not challenged or challenged.player_id != player_id:
            return DuelResult(success=False, message="You are not the challenged player")

        return await self.engine.cancel_duel(duel_id)

    async def submit_action(
        self,
        duel_id: int,
        player_id: int,
        action_type: DuelActionType,
    ) -> DuelResult:
        """Submit an action for a player.

        Args:
            duel_id: ID of the duel
            player_id: ID of the player submitting
            action_type: Type of action

        Returns:
            DuelResult with turn result if both players submitted
        """
        # Get item_id based on action type
        item_id = await self._get_item_for_action(player_id, action_type)

        return await self.engine.submit_action(duel_id, player_id, action_type, item_id)

    async def get_duel_state(self, duel_id: int) -> dict | None:
        """Get current duel state for display."""
        return await self.engine.get_duel_state(duel_id)

    async def get_pending_duel(self, duel_id: int) -> Duel | None:
        """Get a pending duel by ID."""
        stmt = (
            select(Duel)
            .where(Duel.id == duel_id, Duel.status == DuelStatus.PENDING)
            .options(selectinload(Duel.participants).selectinload(DuelParticipant.player))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_active_duel(self, duel_id: int) -> Duel | None:
        """Get an active (in-progress) duel by ID."""
        stmt = (
            select(Duel)
            .where(Duel.id == duel_id, Duel.status == DuelStatus.IN_PROGRESS)
            .options(
                selectinload(Duel.participants).selectinload(DuelParticipant.player),
                selectinload(Duel.combat_states),
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def _get_duel_with_participants(self, duel_id: int) -> Duel | None:
        """Get duel with participants loaded."""
        stmt = select(Duel).where(Duel.id == duel_id).options(selectinload(Duel.participants))
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def _get_active_duel_for_player(self, player_id: int) -> Duel | None:
        """Check if player is in an active duel."""
        stmt = (
            select(Duel)
            .join(DuelParticipant)
            .where(
                DuelParticipant.player_id == player_id,
                Duel.status.in_([DuelStatus.PENDING, DuelStatus.IN_PROGRESS]),
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def _get_item_for_action(self, player_id: int, action_type: DuelActionType) -> int | None:
        """Get the item ID for an action based on player's equipped items."""
        if action_type == DuelActionType.SKIP:
            return None

        stmt = select(Player).where(Player.id == player_id)
        result = await self.session.execute(stmt)
        player = result.scalar_one_or_none()

        if not player:
            return None

        match action_type:
            case DuelActionType.ATTACK:
                return player.attack_item_id
            case DuelActionType.DEFENSE:
                return player.defense_item_id
            case DuelActionType.MISC:
                return player.misc_item_id
            case _:
                return None

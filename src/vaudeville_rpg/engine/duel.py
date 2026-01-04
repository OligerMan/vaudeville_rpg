"""Duel engine - orchestrates the full duel flow."""

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..db.models.duels import Duel, DuelAction, DuelParticipant
from ..db.models.effects import Condition, Effect
from ..db.models.enums import ConditionType, DuelActionType, DuelStatus, EffectCategory, ItemSlot
from ..db.models.items import Item
from ..db.models.players import Player, PlayerCombatState
from ..utils.rating import RatingChange, calculate_rating_change
from .effects import EffectData
from .turn import ItemData, ParticipantAction, TurnResolver
from .types import CombatState, DuelContext, TurnResult

if TYPE_CHECKING:
    from .logging import CombatLog, CombatLogger


@dataclass
class DuelResult:
    """Result of a duel operation."""

    success: bool
    message: str
    duel_id: int | None = None
    turn_result: TurnResult | None = None
    rating_change: RatingChange | None = None
    combat_log: "CombatLog | None" = None


class DuelEngine:
    """Main duel engine - orchestrates duels from start to finish."""

    def __init__(
        self,
        session: AsyncSession,
        logger: "CombatLogger | None" = None,
    ) -> None:
        self.session = session
        self.logger = logger
        self.turn_resolver = TurnResolver(logger=logger)

    async def create_duel(
        self,
        setting_id: int,
        player1_id: int,
        player2_id: int,
    ) -> DuelResult:
        """Create a new duel between two players.

        Args:
            setting_id: Setting this duel takes place in
            player1_id: First player's ID
            player2_id: Second player's ID

        Returns:
            DuelResult with the created duel ID
        """
        # Create the duel
        duel = Duel(setting_id=setting_id, status=DuelStatus.PENDING, current_turn=1)
        self.session.add(duel)
        await self.session.flush()

        # Create participants
        participant1 = DuelParticipant(
            duel_id=duel.id,
            player_id=player1_id,
            turn_order=1,
            is_ready=False,
        )
        participant2 = DuelParticipant(
            duel_id=duel.id,
            player_id=player2_id,
            turn_order=2,
            is_ready=False,
        )
        self.session.add_all([participant1, participant2])
        await self.session.flush()

        # Load player stats and create combat states
        players = await self._load_players([player1_id, player2_id])
        for participant in [participant1, participant2]:
            player = players.get(participant.player_id)
            if player:
                combat_state = PlayerCombatState(
                    player_id=participant.player_id,
                    duel_id=duel.id,
                    current_hp=player.max_hp,
                    current_special_points=player.max_special_points,
                    attribute_stacks={},
                )
                self.session.add(combat_state)

        await self.session.commit()

        return DuelResult(
            success=True,
            message="Duel created",
            duel_id=duel.id,
        )

    async def start_duel(self, duel_id: int) -> DuelResult:
        """Start a pending duel (transition to IN_PROGRESS).

        Args:
            duel_id: ID of the duel to start

        Returns:
            DuelResult indicating success or failure
        """
        duel = await self._load_duel(duel_id)
        if duel is None:
            return DuelResult(success=False, message="Duel not found")

        if duel.status != DuelStatus.PENDING:
            return DuelResult(success=False, message=f"Duel is {duel.status.value}, cannot start")

        duel.status = DuelStatus.IN_PROGRESS
        await self.session.commit()

        return DuelResult(success=True, message="Duel started", duel_id=duel_id)

    async def submit_action(
        self,
        duel_id: int,
        player_id: int,
        action_type: DuelActionType,
        item_id: int | None = None,
    ) -> DuelResult:
        """Submit an action for a player in the current turn.

        Args:
            duel_id: ID of the duel
            player_id: ID of the player submitting
            action_type: Type of action (ATTACK, DEFENSE, MISC, SKIP)
            item_id: ID of item used (required for non-SKIP actions)

        Returns:
            DuelResult indicating success, and turn result if both players ready
        """
        duel = await self._load_duel(duel_id)
        if duel is None:
            return DuelResult(success=False, message="Duel not found")

        if duel.status != DuelStatus.IN_PROGRESS:
            return DuelResult(success=False, message=f"Duel is {duel.status.value}")

        # Find participant
        participant = None
        for p in duel.participants:
            if p.player_id == player_id:
                participant = p
                break

        if participant is None:
            return DuelResult(success=False, message="Player not in this duel")

        if participant.is_ready:
            return DuelResult(success=False, message="Already submitted action this turn")

        # Create action record
        action = DuelAction(
            duel_id=duel_id,
            participant_id=participant.id,
            turn_number=duel.current_turn,
            action_type=action_type,
            item_id=item_id if action_type != DuelActionType.SKIP else None,
        )
        self.session.add(action)

        # Mark as ready
        participant.is_ready = True
        await self.session.flush()

        # Check if both players are ready
        all_ready = all(p.is_ready for p in duel.participants)
        if not all_ready:
            await self.session.commit()
            return DuelResult(
                success=True,
                message="Action submitted, waiting for opponent",
                duel_id=duel_id,
            )

        # Both ready - resolve the turn
        turn_result = await self._resolve_turn(duel)

        # Update duel state based on result
        rating_change = None
        if turn_result.is_duel_over:
            duel.status = DuelStatus.COMPLETED
            duel.winner_participant_id = turn_result.winner_participant_id

            # Update ratings (PvP only, skip if any participant is a bot)
            rating_change = await self._update_ratings(duel, turn_result.winner_participant_id)
        else:
            # Advance to next turn
            duel.current_turn += 1
            for p in duel.participants:
                p.is_ready = False

        await self.session.commit()

        # Get combat log if logger is active
        combat_log = self.logger.get_log() if self.logger else None

        return DuelResult(
            success=True,
            message="Turn resolved",
            duel_id=duel_id,
            turn_result=turn_result,
            rating_change=rating_change,
            combat_log=combat_log,
        )

    async def cancel_duel(self, duel_id: int) -> DuelResult:
        """Cancel a duel.

        Args:
            duel_id: ID of the duel to cancel

        Returns:
            DuelResult indicating success or failure
        """
        duel = await self._load_duel(duel_id)
        if duel is None:
            return DuelResult(success=False, message="Duel not found")

        if duel.status == DuelStatus.COMPLETED:
            return DuelResult(success=False, message="Cannot cancel completed duel")

        duel.status = DuelStatus.CANCELLED
        await self.session.commit()

        return DuelResult(success=True, message="Duel cancelled", duel_id=duel_id)

    async def get_duel_state(self, duel_id: int) -> dict[str, Any] | None:
        """Get the current state of a duel.

        Args:
            duel_id: ID of the duel

        Returns:
            Dict with duel state, or None if not found
        """
        duel = await self._load_duel(duel_id)
        if duel is None:
            return None

        combat_states = await self._load_combat_states(duel_id)

        return {
            "duel_id": duel.id,
            "status": duel.status.value,
            "current_turn": duel.current_turn,
            "participants": [
                {
                    "participant_id": p.id,
                    "player_id": p.player_id,
                    "turn_order": p.turn_order,
                    "is_ready": p.is_ready,
                    "combat_state": {
                        "current_hp": combat_states[p.player_id].current_hp,
                        "current_special_points": combat_states[p.player_id].current_special_points,
                        "attribute_stacks": combat_states[p.player_id].attribute_stacks,
                    }
                    if p.player_id in combat_states
                    else None,
                }
                for p in duel.participants
            ],
            "winner_participant_id": duel.winner_participant_id,
        }

    async def _load_duel(self, duel_id: int) -> Duel | None:
        """Load a duel with its participants."""
        stmt = select(Duel).where(Duel.id == duel_id).options(selectinload(Duel.participants))
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def _load_players(self, player_ids: list[int]) -> dict[int, Player]:
        """Load players by ID."""
        stmt = select(Player).where(Player.id.in_(player_ids))
        result = await self.session.execute(stmt)
        players = result.scalars().all()
        return {p.id: p for p in players}

    async def _load_combat_states(self, duel_id: int) -> dict[int, PlayerCombatState]:
        """Load combat states for a duel."""
        stmt = select(PlayerCombatState).where(PlayerCombatState.duel_id == duel_id)
        result = await self.session.execute(stmt)
        states = result.scalars().all()
        return {s.player_id: s for s in states}

    async def _resolve_turn(self, duel: Duel) -> TurnResult:
        """Resolve the current turn."""
        # Load all required data
        combat_states = await self._load_combat_states(duel.id)
        actions = await self._load_turn_actions(duel.id, duel.current_turn)
        world_rules = await self._load_world_rules(duel.setting_id)
        participant_items = await self._load_participant_items(duel.participants)
        all_conditions = await self._load_all_conditions()

        # Build context
        context = DuelContext(
            duel_id=duel.id,
            setting_id=duel.setting_id,
            current_turn=duel.current_turn,
            states={},
        )

        # Convert DB combat states to engine CombatState
        players = await self._load_players([p.player_id for p in duel.participants])
        for participant in duel.participants:
            player = players.get(participant.player_id)
            db_state = combat_states.get(participant.player_id)
            if player and db_state:
                context.states[participant.id] = CombatState(
                    player_id=participant.player_id,
                    participant_id=participant.id,
                    current_hp=db_state.current_hp,
                    max_hp=player.max_hp,
                    current_special_points=db_state.current_special_points,
                    max_special_points=player.max_special_points,
                    attribute_stacks=dict(db_state.attribute_stacks),
                )

        # Convert actions
        participant_actions = [
            ParticipantAction(
                participant_id=a.participant_id,
                action_type=a.action_type,
                item_id=a.item_id,
            )
            for a in actions
        ]

        # Resolve the turn
        result = self.turn_resolver.resolve_turn(
            context,
            participant_actions,
            world_rules,
            participant_items,
            all_conditions,
        )

        # Persist updated combat states back to DB
        for participant_id, state in context.states.items():
            for participant in duel.participants:
                if participant.id == participant_id:
                    db_state = combat_states.get(participant.player_id)
                    if db_state:
                        db_state.current_hp = state.current_hp
                        db_state.current_special_points = state.current_special_points
                        db_state.attribute_stacks = state.attribute_stacks

        return result

    async def _load_turn_actions(self, duel_id: int, turn_number: int) -> list[DuelAction]:
        """Load actions for a specific turn."""
        stmt = select(DuelAction).where(
            DuelAction.duel_id == duel_id,
            DuelAction.turn_number == turn_number,
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def _load_world_rules(self, setting_id: int) -> list[EffectData]:
        """Load world rules for a setting."""
        stmt = (
            select(Effect)
            .where(
                Effect.setting_id == setting_id,
                Effect.category == EffectCategory.WORLD_RULE,
            )
            .options(
                selectinload(Effect.condition),
                selectinload(Effect.action),
            )
        )
        result = await self.session.execute(stmt)
        effects = result.scalars().all()

        return [
            EffectData(
                id=e.id,
                name=e.name,
                condition_type=e.condition.condition_type,
                condition_data=e.condition.condition_data,
                target=e.target,
                category=e.category,
                action_type=e.action.action_type.value,
                action_data=e.action.action_data,
                owner_participant_id=0,  # Will be set per-participant
            )
            for e in effects
        ]

    async def _load_participant_items(self, participants: list[DuelParticipant]) -> dict[int, dict[ItemSlot, ItemData]]:
        """Load equipped items for all participants."""
        player_ids = [p.player_id for p in participants]
        players = await self._load_players(player_ids)

        # Load items with effects
        item_ids: set[int] = set()
        for player in players.values():
            if player.attack_item_id:
                item_ids.add(player.attack_item_id)
            if player.defense_item_id:
                item_ids.add(player.defense_item_id)
            if player.misc_item_id:
                item_ids.add(player.misc_item_id)

        items: dict[int, Item] = {}
        if item_ids:
            stmt = (
                select(Item)
                .where(Item.id.in_(item_ids))
                .options(
                    selectinload(Item.effects).selectinload(Effect.condition),
                    selectinload(Item.effects).selectinload(Effect.action),
                )
            )
            result = await self.session.execute(stmt)
            items = {i.id: i for i in result.scalars().all()}

        # Build result
        result_dict: dict[int, dict[ItemSlot, ItemData]] = {}
        for participant in participants:
            player = players.get(participant.player_id)
            if not player:
                continue

            participant_items: dict[ItemSlot, ItemData] = {}

            for slot, item_id in [
                (ItemSlot.ATTACK, player.attack_item_id),
                (ItemSlot.DEFENSE, player.defense_item_id),
                (ItemSlot.MISC, player.misc_item_id),
            ]:
                if item_id and item_id in items:
                    item = items[item_id]
                    effects = [
                        EffectData(
                            id=e.id,
                            name=e.name,
                            condition_type=e.condition.condition_type,
                            condition_data=e.condition.condition_data,
                            target=e.target,
                            category=e.category,
                            action_type=e.action.action_type.value,
                            action_data=e.action.action_data,
                            owner_participant_id=participant.id,
                        )
                        for e in item.effects
                    ]
                    participant_items[slot] = ItemData(
                        id=item.id,
                        slot=slot,
                        effects=effects,
                    )

            result_dict[participant.id] = participant_items

        return result_dict

    async def _load_all_conditions(self) -> dict[int, tuple[ConditionType, dict[str, Any]]]:
        """Load all conditions for AND/OR resolution."""
        stmt = select(Condition)
        result = await self.session.execute(stmt)
        conditions = result.scalars().all()
        return {c.id: (c.condition_type, c.condition_data) for c in conditions}

    async def _update_ratings(self, duel: Duel, winner_participant_id: int | None) -> RatingChange | None:
        """Update player ratings after a duel.

        Only updates ratings for PvP duels (skips if any player is a bot).

        Args:
            duel: The completed duel
            winner_participant_id: ID of the winning participant

        Returns:
            RatingChange if ratings were updated, None otherwise
        """
        if winner_participant_id is None:
            return None

        # Load players to check if any is a bot
        player_ids = [p.player_id for p in duel.participants]
        players = await self._load_players(player_ids)

        # Skip rating update for PvE (bot involved)
        for player in players.values():
            if player.is_bot:
                return None

        # Find winner and loser
        winner_player: Player | None = None
        loser_player: Player | None = None

        for participant in duel.participants:
            player = players.get(participant.player_id)
            if not player:
                continue

            if participant.id == winner_participant_id:
                winner_player = player
            else:
                loser_player = player

        if not winner_player or not loser_player:
            return None

        # Calculate rating change
        rating_change = calculate_rating_change(
            winner_rating=winner_player.rating,
            loser_rating=loser_player.rating,
        )

        # Update ratings
        winner_player.rating = rating_change.winner_new_rating
        loser_player.rating = rating_change.loser_new_rating

        return rating_change

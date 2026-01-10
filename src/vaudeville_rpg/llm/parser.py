"""Parsers for converting structured data to database models."""

import time
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from ..db.models.effects import Action, Condition, Effect
from ..db.models.enums import (
    ActionType,
    ConditionPhase,
    ConditionType,
    EffectCategory,
    ItemSlot,
    TargetType,
)
from ..db.models.items import Item
from .schemas import (
    EffectTemplate,
    GeneratedWorldRules,
    ItemType,
    RarityScaledValue,
    WorldRuleDefinition,
)


@dataclass
class ParseResult:
    """Result of parsing operation."""

    success: bool
    message: str
    created_ids: list[int] | None = None


class WorldRulesParser:
    """Parse world rules from structured data to database models."""

    # Mapping from string to enum
    PHASE_MAP = {
        "pre_move": ConditionPhase.PRE_MOVE,
        "post_move": ConditionPhase.POST_MOVE,
        "pre_attack": ConditionPhase.PRE_ATTACK,
        "post_attack": ConditionPhase.POST_ATTACK,
        "pre_damage": ConditionPhase.PRE_DAMAGE,
        "post_damage": ConditionPhase.POST_DAMAGE,
    }

    ACTION_TYPE_MAP = {
        "damage": ActionType.DAMAGE,
        "attack": ActionType.ATTACK,
        "heal": ActionType.HEAL,
        "add_stacks": ActionType.ADD_STACKS,
        "remove_stacks": ActionType.REMOVE_STACKS,
        "reduce_incoming_damage": ActionType.REDUCE_INCOMING_DAMAGE,
    }

    TARGET_MAP = {
        "self": TargetType.SELF,
        "enemy": TargetType.ENEMY,
    }

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def parse(self, setting_id: int, world_rules: GeneratedWorldRules) -> ParseResult:
        """Parse world rules and create database models.

        Args:
            setting_id: Setting to create rules for
            world_rules: Generated world rules data

        Returns:
            ParseResult with created effect IDs
        """
        created_ids = []

        for rule in world_rules.rules:
            try:
                effect_id = await self._create_rule(setting_id, rule)
                created_ids.append(effect_id)
            except Exception as e:
                return ParseResult(
                    success=False,
                    message=f"Failed to create rule {rule.name}: {e!s}",
                )

        return ParseResult(
            success=True,
            message=f"Created {len(created_ids)} world rules",
            created_ids=created_ids,
        )

    async def _create_rule(self, setting_id: int, rule: WorldRuleDefinition) -> int:
        """Create a single world rule with conditions, actions, and effect."""
        # Use timestamp suffix to ensure unique names even on retry
        unique_suffix = int(time.time() * 1000000)

        # 1. Create phase condition
        phase_condition = Condition(
            name=f"{rule.name}_phase_{unique_suffix}",
            condition_type=ConditionType.PHASE,
            condition_data={"phase": rule.phase},
        )
        self.session.add(phase_condition)
        await self.session.flush()

        # 2. Create has_stacks condition
        stacks_condition = Condition(
            name=f"{rule.name}_stacks_{unique_suffix}",
            condition_type=ConditionType.HAS_STACKS,
            condition_data={
                "attribute": rule.requires_attribute,
                "min_count": rule.min_stacks,
            },
        )
        self.session.add(stacks_condition)
        await self.session.flush()

        # 3. Create composite AND condition
        and_condition = Condition(
            name=f"{rule.name}_condition_{unique_suffix}",
            condition_type=ConditionType.AND,
            condition_data={"condition_ids": [phase_condition.id, stacks_condition.id]},
        )
        self.session.add(and_condition)
        await self.session.flush()

        # 4. Create action
        action_type = self.ACTION_TYPE_MAP.get(rule.action.action_type, ActionType.DAMAGE)
        target = self.TARGET_MAP.get(rule.target, TargetType.SELF)

        action_data = {"value": rule.action.value}
        if rule.action.attribute:
            action_data["attribute"] = rule.action.attribute
        if rule.per_stack:
            action_data["per_stack"] = True
            # For per_stack actions, use the requires_attribute if no attribute specified
            # This is needed for reduce_incoming_damage which scales with armor stacks
            if not rule.action.attribute and rule.requires_attribute:
                action_data["attribute"] = rule.requires_attribute

        action = Action(
            name=f"{rule.name}_action_{unique_suffix}",
            action_type=action_type,
            action_data=action_data,
        )
        self.session.add(action)
        await self.session.flush()

        # 5. Create effect
        effect = Effect(
            setting_id=setting_id,
            name=rule.name,
            description=rule.description,
            condition_id=and_condition.id,
            action_id=action.id,
            target=target,
            category=EffectCategory.WORLD_RULE,
        )
        self.session.add(effect)
        await self.session.flush()

        return effect.id

    async def create_armor_rules(self, setting_id: int) -> ParseResult:
        """Create hardcoded armor world rules.

        These rules are always needed because defense items always add 'armor' stacks.
        This ensures armor damage reduction works regardless of what the LLM generates.

        Creates:
        1. armor_damage_reduction: At PRE_DAMAGE, reduce damage by 2 per armor stack
        2. armor_decay: At POST_DAMAGE, remove 1 armor stack when hit

        Args:
            setting_id: Setting to create rules for

        Returns:
            ParseResult with created effect IDs
        """
        import time

        created_ids = []
        unique_suffix = int(time.time() * 1000000)

        try:
            # Rule 1: Armor Damage Reduction (PRE_DAMAGE)
            # Phase condition
            phase_cond_1 = Condition(
                name=f"armor_reduction_phase_{unique_suffix}",
                condition_type=ConditionType.PHASE,
                condition_data={"phase": "pre_damage"},
            )
            self.session.add(phase_cond_1)
            await self.session.flush()

            # Has stacks condition
            stacks_cond_1 = Condition(
                name=f"armor_reduction_stacks_{unique_suffix}",
                condition_type=ConditionType.HAS_STACKS,
                condition_data={"attribute": "armor", "min_count": 1},
            )
            self.session.add(stacks_cond_1)
            await self.session.flush()

            # AND condition
            and_cond_1 = Condition(
                name=f"armor_reduction_condition_{unique_suffix}",
                condition_type=ConditionType.AND,
                condition_data={"condition_ids": [phase_cond_1.id, stacks_cond_1.id]},
            )
            self.session.add(and_cond_1)
            await self.session.flush()

            # Action: reduce incoming damage by 2 per armor stack
            action_1 = Action(
                name=f"armor_reduction_action_{unique_suffix}",
                action_type=ActionType.REDUCE_INCOMING_DAMAGE,
                action_data={"value": 2, "per_stack": True, "attribute": "armor"},
            )
            self.session.add(action_1)
            await self.session.flush()

            # Effect
            effect_1 = Effect(
                setting_id=setting_id,
                name="armor_damage_reduction",
                description="Armor reduces incoming damage by 2 per stack",
                condition_id=and_cond_1.id,
                action_id=action_1.id,
                target=TargetType.SELF,
                category=EffectCategory.WORLD_RULE,
            )
            self.session.add(effect_1)
            await self.session.flush()
            created_ids.append(effect_1.id)

            # Rule 2: Armor Decay (POST_DAMAGE)
            unique_suffix_2 = unique_suffix + 1

            # Phase condition
            phase_cond_2 = Condition(
                name=f"armor_decay_phase_{unique_suffix_2}",
                condition_type=ConditionType.PHASE,
                condition_data={"phase": "post_damage"},
            )
            self.session.add(phase_cond_2)
            await self.session.flush()

            # Has stacks condition
            stacks_cond_2 = Condition(
                name=f"armor_decay_stacks_{unique_suffix_2}",
                condition_type=ConditionType.HAS_STACKS,
                condition_data={"attribute": "armor", "min_count": 1},
            )
            self.session.add(stacks_cond_2)
            await self.session.flush()

            # AND condition
            and_cond_2 = Condition(
                name=f"armor_decay_condition_{unique_suffix_2}",
                condition_type=ConditionType.AND,
                condition_data={"condition_ids": [phase_cond_2.id, stacks_cond_2.id]},
            )
            self.session.add(and_cond_2)
            await self.session.flush()

            # Action: remove 1 armor stack
            action_2 = Action(
                name=f"armor_decay_action_{unique_suffix_2}",
                action_type=ActionType.REMOVE_STACKS,
                action_data={"value": 1, "attribute": "armor"},
            )
            self.session.add(action_2)
            await self.session.flush()

            # Effect
            effect_2 = Effect(
                setting_id=setting_id,
                name="armor_decay",
                description="Armor loses 1 stack when hit",
                condition_id=and_cond_2.id,
                action_id=action_2.id,
                target=TargetType.SELF,
                category=EffectCategory.WORLD_RULE,
            )
            self.session.add(effect_2)
            await self.session.flush()
            created_ids.append(effect_2.id)

            return ParseResult(
                success=True,
                message="Created 2 armor world rules",
                created_ids=created_ids,
            )

        except Exception as e:
            return ParseResult(
                success=False,
                message=f"Failed to create armor rules: {e!s}",
            )


class ItemParser:
    """Parse items from structured data to database models."""

    SLOT_MAP = {
        "attack": ItemSlot.ATTACK,
        "defense": ItemSlot.DEFENSE,
        "misc": ItemSlot.MISC,
    }

    ACTION_TYPE_MAP = {
        "damage": ActionType.DAMAGE,
        "attack": ActionType.ATTACK,
        "heal": ActionType.HEAL,
        "add_stacks": ActionType.ADD_STACKS,
        "remove_stacks": ActionType.REMOVE_STACKS,
        "reduce_incoming_damage": ActionType.REDUCE_INCOMING_DAMAGE,
    }

    TARGET_MAP = {
        "self": TargetType.SELF,
        "enemy": TargetType.ENEMY,
    }

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def parse_item(
        self,
        setting_id: int,
        name: str,
        description: str,
        slot: str,
        rarity: int,
        actions: list[dict],
    ) -> ParseResult:
        """Parse and create a single item.

        Args:
            setting_id: Setting to create item for
            name: Item name
            description: Item description
            slot: Item slot (attack, defense, misc)
            rarity: Item rarity (1-5)
            actions: List of action definitions

        Returns:
            ParseResult with created item ID
        """
        try:
            item_slot = self.SLOT_MAP.get(slot, ItemSlot.MISC)

            # Create item
            item = Item(
                setting_id=setting_id,
                name=name,
                description=description,
                slot=item_slot,
                rarity=rarity,
            )
            self.session.add(item)
            await self.session.flush()

            # Create effects for each action
            for i, action_def in enumerate(actions):
                await self._create_item_effect(setting_id, item.id, slot, i, action_def)

            return ParseResult(
                success=True,
                message=f"Created item: {name}",
                created_ids=[item.id],
            )

        except Exception as e:
            return ParseResult(
                success=False,
                message=f"Failed to create item {name}: {e!s}",
            )

    async def _create_item_effect(
        self,
        setting_id: int,
        item_id: int,
        item_slot: str,
        priority: int,
        action_def: dict,
    ) -> None:
        """Create an effect linked to an item."""
        # Use timestamp suffix to ensure unique names even on retry
        unique_suffix = int(time.time() * 1000000)

        action_type = self.ACTION_TYPE_MAP.get(action_def.get("action_type", "damage"), ActionType.DAMAGE)
        target = self.TARGET_MAP.get(action_def.get("target", "enemy"), TargetType.ENEMY)

        action_data = {"value": action_def.get("value", 0)}
        if "attribute" in action_def and action_def["attribute"]:
            action_data["attribute"] = action_def["attribute"]

        # Create action
        action = Action(
            name=f"item_{item_id}_action_{priority}_{unique_suffix}",
            action_type=action_type,
            action_data=action_data,
        )
        self.session.add(action)
        await self.session.flush()

        # Create condition based on item slot
        # All item effects trigger on PRE_ATTACK when the item is used as an action.
        # Defense items add armor stacks at PRE_ATTACK, then world rules convert
        # those stacks to damage reduction at PRE_DAMAGE when damage occurs.
        phase_map = {
            "attack": "pre_attack",
            "defense": "pre_attack",
            "misc": "pre_attack",
        }
        phase = phase_map.get(item_slot, "pre_attack")

        condition = Condition(
            name=f"item_{item_id}_condition_{priority}_{unique_suffix}",
            condition_type=ConditionType.PHASE,
            condition_data={"phase": phase},
        )
        self.session.add(condition)
        await self.session.flush()

        # Create effect with item_id set
        effect = Effect(
            setting_id=setting_id,
            name=f"item_{item_id}_effect_{priority}_{unique_suffix}",
            description=f"{action_def.get('action_type', 'effect')}",
            condition_id=condition.id,
            action_id=action.id,
            target=target,
            category=EffectCategory.ITEM_EFFECT,
            item_id=item_id,
        )
        self.session.add(effect)
        await self.session.flush()

    async def create_from_templates(
        self,
        setting_id: int,
        item_type: ItemType,
        effect_template: EffectTemplate,
        rarity: int,
    ) -> ParseResult:
        """Create an item from item type and effect template.

        Args:
            setting_id: Setting to create item for
            item_type: Item type definition
            effect_template: Effect template to apply
            rarity: Item rarity (1-5)

        Returns:
            ParseResult with created item ID
        """
        # Build item name
        rarity_names = {1: "Common", 2: "Uncommon", 3: "Rare", 4: "Epic", 5: "Legendary"}
        name_parts = [rarity_names.get(rarity, "Common"), effect_template.prefix, item_type.name]
        if effect_template.suffix:
            name_parts.append(effect_template.suffix)
        name = " ".join(name_parts)

        # Build description
        description = f"{effect_template.description} {item_type.description}"

        # Build actions list
        actions = []

        # Add base action from item type
        base_values = None
        if item_type.slot == "attack" and item_type.base_damage:
            base_values = item_type.base_damage
            action_type = "attack"
            target = "enemy"
            attribute = None
        elif item_type.slot == "defense" and item_type.base_armor:
            base_values = item_type.base_armor
            action_type = "add_stacks"
            target = "self"
            attribute = "armor"
        elif item_type.slot == "misc" and item_type.base_heal:
            base_values = item_type.base_heal
            action_type = "heal"
            target = "self"
            attribute = None

        if base_values:
            value = self._get_rarity_value(base_values, rarity)
            actions.append(
                {
                    "action_type": action_type,
                    "target": target,
                    "value": value,
                    "attribute": attribute,
                }
            )

        # Add effect template actions
        for template_action in effect_template.actions:
            value = self._get_rarity_value(template_action.values, rarity)
            actions.append(
                {
                    "action_type": template_action.action_type,
                    "target": template_action.target,
                    "value": value,
                    "attribute": template_action.attribute,
                }
            )

        return await self.parse_item(
            setting_id=setting_id,
            name=name,
            description=description,
            slot=item_type.slot,
            rarity=rarity,
            actions=actions,
        )

    def _get_rarity_value(self, scaled: RarityScaledValue, rarity: int) -> int:
        """Get value for a specific rarity."""
        match rarity:
            case 1:
                return scaled.common
            case 2:
                return scaled.uncommon
            case 3:
                return scaled.rare
            case 4:
                return scaled.epic
            case 5:
                return scaled.legendary
            case _:
                return scaled.common

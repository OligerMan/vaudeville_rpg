"""Item factory for creating items from generated templates."""

import random
from dataclasses import dataclass
from enum import IntEnum

from .schemas import (
    EffectTemplate,
    GeneratedEffectTemplates,
    GeneratedItemTypes,
    ItemType,
    RarityScaledValue,
)


class Rarity(IntEnum):
    """Item rarity levels."""

    COMMON = 1
    UNCOMMON = 2
    RARE = 3
    EPIC = 4
    LEGENDARY = 5


RARITY_NAMES = {
    Rarity.COMMON: "Common",
    Rarity.UNCOMMON: "Uncommon",
    Rarity.RARE: "Rare",
    Rarity.EPIC: "Epic",
    Rarity.LEGENDARY: "Legendary",
}


@dataclass
class GeneratedAction:
    """An action generated for an item."""

    action_type: str
    target: str
    value: int
    attribute: str | None = None


@dataclass
class GeneratedItem:
    """A generated item ready for database insertion."""

    name: str
    description: str
    slot: str
    rarity: int
    actions: list[GeneratedAction]


def _get_rarity_value(scaled: RarityScaledValue, rarity: Rarity) -> int:
    """Get value for a specific rarity from scaled values."""
    match rarity:
        case Rarity.COMMON:
            return scaled.common
        case Rarity.UNCOMMON:
            return scaled.uncommon
        case Rarity.RARE:
            return scaled.rare
        case Rarity.EPIC:
            return scaled.epic
        case Rarity.LEGENDARY:
            return scaled.legendary


class ItemFactory:
    """Factory for generating items from templates."""

    def __init__(
        self,
        item_types: GeneratedItemTypes,
        effect_templates: GeneratedEffectTemplates,
    ) -> None:
        """Initialize factory with generated content.

        Args:
            item_types: Generated item types
            effect_templates: Generated effect templates
        """
        self.item_types = item_types
        self.effect_templates = effect_templates

        # Index templates by slot for quick lookup
        self._attack_effects = [t for t in effect_templates.templates if t.slot_type == "attack"]
        self._defense_effects = [t for t in effect_templates.templates if t.slot_type == "defense"]
        self._misc_effects = [t for t in effect_templates.templates if t.slot_type == "misc"]

    def create_item(
        self,
        slot: str,
        rarity: Rarity,
        item_type: ItemType | None = None,
        effect: EffectTemplate | None = None,
    ) -> GeneratedItem:
        """Create an item with given parameters.

        Args:
            slot: Item slot (attack, defense, misc)
            rarity: Item rarity
            item_type: Specific item type, or random if None
            effect: Specific effect, or random if None

        Returns:
            GeneratedItem ready for database
        """
        # Select item type if not specified
        if item_type is None:
            item_type = self._random_item_type(slot)

        # Select effect if not specified
        if effect is None:
            effect = self._random_effect(slot)

        # Build item name
        name = self._build_name(rarity, effect, item_type)

        # Build description
        description = f"{effect.description} {item_type.description}"

        # Build actions
        actions = self._build_actions(slot, rarity, item_type, effect)

        return GeneratedItem(
            name=name,
            description=description,
            slot=slot,
            rarity=rarity.value,
            actions=actions,
        )

    def create_random_item(self, rarity: Rarity | None = None) -> GeneratedItem:
        """Create a random item.

        Args:
            rarity: Specific rarity, or random if None

        Returns:
            Random GeneratedItem
        """
        if rarity is None:
            rarity = random.choice(list(Rarity))

        slot = random.choice(["attack", "defense", "misc"])
        return self.create_item(slot=slot, rarity=rarity)

    def create_starter_items(self) -> list[GeneratedItem]:
        """Create a set of common starter items.

        Returns:
            List of 3 common items (one per slot)
        """
        return [
            self.create_item(slot="attack", rarity=Rarity.COMMON),
            self.create_item(slot="defense", rarity=Rarity.COMMON),
            self.create_item(slot="misc", rarity=Rarity.COMMON),
        ]

    def create_dungeon_reward(self, min_rarity: int, max_rarity: int) -> GeneratedItem:
        """Create a dungeon reward item within rarity range.

        Args:
            min_rarity: Minimum rarity (1-5)
            max_rarity: Maximum rarity (1-5)

        Returns:
            Random item within rarity range
        """
        rarity_value = random.randint(min_rarity, max_rarity)
        rarity = Rarity(rarity_value)
        return self.create_random_item(rarity=rarity)

    def _random_item_type(self, slot: str) -> ItemType:
        """Get random item type for slot."""
        match slot:
            case "attack":
                return random.choice(self.item_types.attack_types)
            case "defense":
                return random.choice(self.item_types.defense_types)
            case "misc":
                return random.choice(self.item_types.misc_types)
            case _:
                raise ValueError(f"Unknown slot: {slot}")

    def _random_effect(self, slot: str) -> EffectTemplate:
        """Get random effect for slot."""
        match slot:
            case "attack":
                if not self._attack_effects:
                    raise ValueError("No attack effects available")
                return random.choice(self._attack_effects)
            case "defense":
                if not self._defense_effects:
                    raise ValueError("No defense effects available")
                return random.choice(self._defense_effects)
            case "misc":
                if not self._misc_effects:
                    raise ValueError("No misc effects available")
                return random.choice(self._misc_effects)
            case _:
                raise ValueError(f"Unknown slot: {slot}")

    def _build_name(self, rarity: Rarity, effect: EffectTemplate, item_type: ItemType) -> str:
        """Build item name from components."""
        parts = [RARITY_NAMES[rarity], effect.prefix, item_type.name]
        if effect.suffix:
            parts.append(effect.suffix)
        return " ".join(parts)

    def _build_actions(
        self,
        slot: str,
        rarity: Rarity,
        item_type: ItemType,
        effect: EffectTemplate,
    ) -> list[GeneratedAction]:
        """Build actions list for item."""
        actions = []

        # Add base action from item type
        match slot:
            case "attack":
                if item_type.base_damage:
                    damage = _get_rarity_value(item_type.base_damage, rarity)
                    actions.append(GeneratedAction(action_type="attack", target="enemy", value=damage))
            case "defense":
                if item_type.base_armor:
                    armor = _get_rarity_value(item_type.base_armor, rarity)
                    actions.append(GeneratedAction(action_type="add_stacks", target="self", value=armor, attribute="armor"))
            case "misc":
                if item_type.base_heal:
                    heal = _get_rarity_value(item_type.base_heal, rarity)
                    actions.append(GeneratedAction(action_type="heal", target="self", value=heal))

        # Add effect actions
        for action in effect.actions:
            value = _get_rarity_value(action.values, rarity)
            actions.append(
                GeneratedAction(
                    action_type=action.action_type,
                    target=action.target,
                    value=value,
                    attribute=action.attribute,
                )
            )

        return actions

"""Content generators using LLM."""

import json
import re

from .client import LLMClient
from .schemas import (
    EffectTemplate,
    GeneratedEffectTemplates,
    GeneratedItemTypes,
    GeneratedSetting,
    GeneratedWorldRules,
    ItemType,
)


def _extract_json(text: str) -> dict:
    """Extract JSON from LLM response text.

    Handles responses with markdown code blocks or raw JSON.
    """
    # Try to find JSON in code blocks first
    json_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
    if json_match:
        json_str = json_match.group(1).strip()
    else:
        # Try to find raw JSON object
        json_match = re.search(r"\{.*\}", text, re.DOTALL)
        if json_match:
            json_str = json_match.group(0)
        else:
            raise ValueError(f"No JSON found in response: {text[:200]}...")

    return json.loads(json_str)


class SettingGenerator:
    """Generate setting description and attributes from simple input."""

    SYSTEM_PROMPT = """You are a game content designer for a turn-based RPG.
Your task is to expand a simple setting description into detailed game content.
Always respond with valid JSON matching the requested schema."""

    GENERATION_PROMPT = """Given this setting idea: "{user_input}"

Generate a complete setting with:
1. A broad description (2-3 paragraphs of world lore)
2. A special points attribute (like mana, energy, ki) with name, display_name, description
3. 3-5 stack-based combat attributes (buffs/debuffs like poison, armor, rage)

Each attribute needs:
- name: lowercase snake_case identifier
- display_name: Title Case for UI
- description: Flavor text explaining what it represents and how it works
- is_positive: true for buffs, false for debuffs

Respond with JSON matching this schema:
{{
    "broad_description": "string - expanded world lore",
    "special_points": {{
        "name": "string - lowercase",
        "display_name": "string - Title Case",
        "description": "string - flavor text",
        "regen_per_turn": number
    }},
    "attributes": [
        {{
            "name": "string - lowercase snake_case",
            "display_name": "string - Title Case",
            "description": "string - what it does",
            "is_positive": boolean
        }}
    ]
}}"""

    def __init__(self, client: LLMClient) -> None:
        self.client = client

    async def generate(self, user_input: str) -> GeneratedSetting:
        """Generate setting from user input.

        Args:
            user_input: Simple setting description (e.g., "world of might and magic")

        Returns:
            GeneratedSetting with broad description and attributes
        """
        prompt = self.GENERATION_PROMPT.format(user_input=user_input)
        response = await self.client.generate(prompt, system=self.SYSTEM_PROMPT)
        data = _extract_json(response.content)
        return GeneratedSetting.model_validate(data)


class WorldRulesGenerator:
    """Generate formal world rules from attribute descriptions."""

    SYSTEM_PROMPT = """You are a game mechanics designer for a turn-based RPG.
Your task is to convert attribute descriptions into formal game rules.
Always respond with valid JSON matching the requested schema.
CRITICAL: You must ONLY reference attributes that exist in the world."""

    GENERATION_PROMPT = """Convert this attribute into formal game rules for this setting:

Setting: {setting_description}

Available Attributes (you MUST only reference these):
{known_attributes_list}

Attribute to generate rules for:
Name: {name} ({display_name})
Description: {description}
Is Positive: {is_positive}

Generate rules that define how this attribute behaves in combat.
Common patterns:
- Tick effects: Trigger PRE_MOVE (start of turn) - damage, heal, etc.
- Decay: Trigger POST_MOVE (end of turn) - remove 1 stack
- Damage reduction: Trigger PRE_DAMAGE - reduce incoming damage
- On-hit effects: Trigger POST_DAMAGE - after taking damage

Available phases: pre_move, post_move, pre_attack, post_attack, pre_damage, post_damage
Available action_types: damage, heal, add_stacks, remove_stacks, reduce_incoming_damage
Target is usually "self" (the player who has the stacks)

CRITICAL: All rules must ONLY reference attributes from the "Available Attributes" list above.
Use the exact attribute names provided. Do NOT invent new attributes.

Respond with JSON:
{{
    "attribute_name": "{name}",
    "rules": [
        {{
            "name": "string - unique rule name like '{name}_tick'",
            "description": "string - what this rule does",
            "phase": "string - when it triggers",
            "requires_attribute": "{name}",
            "min_stacks": 1,
            "target": "self",
            "action": {{
                "action_type": "string",
                "value": number,
                "attribute": "string or null (MUST be from Available Attributes list)"
            }},
            "per_stack": boolean
        }}
    ]
}}"""

    def __init__(self, client: LLMClient) -> None:
        self.client = client

    async def generate(
        self,
        attribute_name: str,
        display_name: str,
        description: str,
        is_positive: bool,
        setting_description: str = "",
        known_attributes: set[str] | None = None,
    ) -> GeneratedWorldRules:
        """Generate world rules for an attribute.

        Args:
            attribute_name: Lowercase attribute name
            display_name: Display name
            description: Flavor description
            is_positive: Whether it's a buff or debuff
            setting_description: Broad description of the setting
            known_attributes: Set of known attribute names

        Returns:
            GeneratedWorldRules with formal rule definitions
        """
        # Format known attributes list
        if known_attributes:
            attrs_list = "\n".join(f"- {attr}" for attr in sorted(known_attributes))
        else:
            attrs_list = f"- {attribute_name}"

        prompt = self.GENERATION_PROMPT.format(
            setting_description=setting_description or "A fantasy world",
            known_attributes_list=attrs_list,
            name=attribute_name,
            display_name=display_name,
            description=description,
            is_positive=str(is_positive).lower(),
        )
        response = await self.client.generate(prompt, system=self.SYSTEM_PROMPT)
        data = _extract_json(response.content)
        return GeneratedWorldRules.model_validate(data)


class EffectTemplateGenerator:
    """Generate item effect templates from setting context."""

    SYSTEM_PROMPT = """You are a game item designer for a turn-based RPG.
Your task is to create item effect templates that fit the setting.
Always respond with valid JSON matching the requested schema."""

    GENERATION_PROMPT = """Given this setting:
{setting_description}

Available attributes: {attributes}

Generate 6-10 item effect templates. Include:
- 2-3 attack effects (damage + attribute application)
- 2-3 defense effects (armor, damage reduction, self-buffs)
- 2-3 misc effects (healing, utility, attribute manipulation)

Each effect needs:
- name: lowercase snake_case identifier
- description: what it does
- prefix: naming prefix (e.g., "Poisonous", "Holy")
- suffix: optional naming suffix (e.g., "of Flames", "of Protection")
- slot_type: attack, defense, or misc
- actions: list of actions with rarity-scaled values

Rarity scaling (common → legendary should increase power):
- Common: base values
- Uncommon: ~1.5x
- Rare: ~2x
- Epic: ~2.5x
- Legendary: ~3x

Respond with JSON:
{{
    "templates": [
        {{
            "name": "string",
            "description": "string",
            "prefix": "string",
            "suffix": "string or null",
            "slot_type": "attack|defense|misc",
            "actions": [
                {{
                    "action_type": "attack|damage|heal|add_stacks|remove_stacks",
                    "target": "self|enemy",
                    "attribute": "string or null",
                    "values": {{
                        "common": number,
                        "uncommon": number,
                        "rare": number,
                        "epic": number,
                        "legendary": number
                    }}
                }}
            ]
        }}
    ]
}}"""

    def __init__(self, client: LLMClient) -> None:
        self.client = client

    async def generate(self, setting_description: str, attributes: list[str]) -> GeneratedEffectTemplates:
        """Generate effect templates for a setting.

        Args:
            setting_description: Broad setting description
            attributes: List of attribute names available

        Returns:
            GeneratedEffectTemplates with effect definitions
        """
        prompt = self.GENERATION_PROMPT.format(
            setting_description=setting_description,
            attributes=", ".join(attributes),
        )
        response = await self.client.generate(prompt, system=self.SYSTEM_PROMPT, max_tokens=2048)
        data = _extract_json(response.content)

        # Convert to proper schema
        templates = []
        for t in data.get("templates", []):
            templates.append(EffectTemplate.model_validate(t))

        return GeneratedEffectTemplates(templates=templates)


class ItemTypeGenerator:
    """Generate setting-specific item types."""

    SYSTEM_PROMPT = """You are a game item designer for a turn-based RPG.
Your task is to create item types that fit the setting theme.
Always respond with valid JSON matching the requested schema."""

    GENERATION_PROMPT = """Given this setting:
{setting_description}

Generate item types for each slot:
- 3-4 attack types (weapons)
- 3-4 defense types (armor/shields)
- 3-4 misc types (consumables/utility)

Each type needs:
- name: item type name (e.g., "Sword", "Staff", "Shield")
- slot: attack, defense, or misc
- description: flavor text
- base values scaled by rarity (for attack: damage, defense: armor, misc: heal)

Rarity scaling for base values:
- Common: 8-10
- Uncommon: 12-15
- Rare: 18-22
- Epic: 25-30
- Legendary: 35-40

Respond with JSON:
{{
    "attack_types": [
        {{
            "name": "string",
            "slot": "attack",
            "description": "string",
            "base_damage": {{"common": n, "uncommon": n, "rare": n, "epic": n, "legendary": n}}
        }}
    ],
    "defense_types": [
        {{
            "name": "string",
            "slot": "defense",
            "description": "string",
            "base_armor": {{"common": n, "uncommon": n, "rare": n, "epic": n, "legendary": n}}
        }}
    ],
    "misc_types": [
        {{
            "name": "string",
            "slot": "misc",
            "description": "string",
            "base_heal": {{"common": n, "uncommon": n, "rare": n, "epic": n, "legendary": n}}
        }}
    ]
}}"""

    def __init__(self, client: LLMClient) -> None:
        self.client = client

    async def generate(self, setting_description: str) -> GeneratedItemTypes:
        """Generate item types for a setting.

        Args:
            setting_description: Broad setting description

        Returns:
            GeneratedItemTypes with item type definitions
        """
        prompt = self.GENERATION_PROMPT.format(setting_description=setting_description)
        response = await self.client.generate(prompt, system=self.SYSTEM_PROMPT, max_tokens=2048)
        data = _extract_json(response.content)

        # Convert to proper schema
        attack_types = [ItemType.model_validate(t) for t in data.get("attack_types", [])]
        defense_types = [ItemType.model_validate(t) for t in data.get("defense_types", [])]
        misc_types = [ItemType.model_validate(t) for t in data.get("misc_types", [])]

        return GeneratedItemTypes(
            attack_types=attack_types,
            defense_types=defense_types,
            misc_types=misc_types,
        )

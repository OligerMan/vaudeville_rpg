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
CRITICAL: You must ONLY reference attributes that exist in the world.
Most temporary effects should include decay mechanics to prevent infinite stacking."""

    GENERATION_PROMPT = """Convert this attribute into formal game rules for this setting:

Setting: {setting_description}

Available Attributes (you MUST only reference these):
{known_attributes_list}

Attribute to generate rules for:
Name: {name} ({display_name})
Description: {description}
Is Positive: {is_positive}

Generate rules that define how this attribute behaves in combat.

COMBAT PHASES (when rules trigger):
- pre_move: Start of turn, before any actions
- post_move: End of turn, after all actions
- pre_attack: Before attacking
- post_attack: After attacking
- pre_damage: Before receiving damage
- post_damage: After receiving damage

ACTION TYPES (what the rule does):
- damage: Deal INTEGER damage to target (value: 5 means 5 HP damage)
- heal: Heal INTEGER HP to target (value: 10 means heal 10 HP)
- add_stacks: Add INTEGER stacks of an attribute (value: 2, attribute: "poison" means add 2 poison stacks)
- remove_stacks: Remove INTEGER stacks of an attribute (value: 1, attribute: "poison" means remove 1 poison stack)
- reduce_incoming_damage: Reduce incoming damage by INTEGER (value: 5 means reduce damage by 5, NOT a percentage)

IMPORTANT: All "value" fields MUST be integers (whole numbers like 5, 10, 15), NEVER floats (like 0.5, 1.5, 2.3).

Target is usually "self" (the player who has the stacks)

IMPORTANT DECAY GUIDANCE:
Most temporary effects (buffs, debuffs, stacks) MUST decay to prevent infinite stacking.
ONLY skip decay for truly permanent effects (rare).

DECAY PATTERNS:
1. Standard Decay (most common):
   - Phase: POST_MOVE (end of turn)
   - Action: remove_stacks with value: 1
   - Effect: Removes 1 stack per turn
   - Use for: Poison, burn, armor, most temporary buffs/debuffs

2. Fast Decay:
   - Phase: POST_MOVE
   - Action: remove_stacks with value: 2 or more
   - Effect: Removes multiple stacks per turn
   - Use for: Very temporary effects that should fade quickly

3. Per-Stack Decay:
   - Phase: POST_MOVE
   - Action: remove_stacks with per_stack: true
   - Effect: Decay scales with stack count
   - Use for: Effects that should decay faster when stronger

COMMON EFFECT PATTERNS WITH EXAMPLES:

1. Tick + Decay (most common for DoTs/HoTs):
   Example for "poison" attribute:
   Rule 1: {{phase: "pre_move", action: {{action_type: "damage", value: 3}}, per_stack: true}}
   Rule 2: {{phase: "post_move", action: {{action_type: "remove_stacks", value: 1, attribute: "poison"}}}}
   → Deals 3 damage per poison stack at start of turn, then removes 1 poison stack at end

2. Damage Reduction + Decay:
   Example for "armor" attribute:
   Rule 1: {{phase: "pre_damage", action: {{action_type: "reduce_incoming_damage", value: 5}}, per_stack: true}}
   Rule 2: {{phase: "post_move", action: {{action_type: "remove_stacks", value: 1, attribute: "armor"}}}}
   → Reduces damage by 5 per armor stack when hit, decays 1 armor at end of turn

3. Buff + Decay:
   Example for "rage" attribute (positive):
   Rule 1: Add bonus to attacks via attribute tracking (handled elsewhere)
   Rule 2: {{phase: "post_move", action: {{action_type: "remove_stacks", value: 1, attribute: "rage"}}}}
   → Rage stacks decay over time

4. On-Hit Effect:
   Example for "retaliation" attribute:
   Rule: {{phase: "post_damage", action: {{action_type: "damage", value: 5}}, target: "enemy"}}
   → Deals damage back to attacker when hit

When to SKIP decay:
- Truly permanent effects (very rare, like quest buffs)
- Effects that decay through other means (e.g., consumed on use)
- Passive abilities that don't stack

DEFAULT RULE: If unsure, add decay. It's easier to remove decay than fix infinite stacking.

CRITICAL: All rules must ONLY reference attributes from the "Available Attributes" list above.
Use the exact attribute names provided. Do NOT invent new attributes.

Respond with JSON:
{{
    "attribute_name": "{name}",
    "rules": [
        {{
            "name": "string - unique rule name like '{name}_tick'",
            "description": "string - what this rule does",
            "phase": "string - one of the phases listed above",
            "requires_attribute": "{name}",
            "min_stacks": 1,
            "target": "self",
            "action": {{
                "action_type": "string - one of the action types listed above",
                "value": integer - MUST be a whole number like 5 or 10, NOT 0.5 or 1.5,
                "attribute": "string or null (MUST be from Available Attributes list, required for add_stacks/remove_stacks)"
            }},
            "per_stack": boolean - true if effect scales with stack count
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
Always respond with valid JSON matching the requested schema.
CRITICAL: You must ONLY reference attributes that are explicitly listed as available."""

    GENERATION_PROMPT = """Given this setting:
{setting_description}

Available Attributes (you MUST only reference these):
{attributes}

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

IMPORTANT: ALL numeric values MUST be integers (whole numbers), NEVER floats.

Rarity scaling (common → legendary should increase power):
Example scaling for damage value starting at 10:
- Common: 10 (base)
- Uncommon: 15 (50% more)
- Rare: 20 (2x)
- Epic: 25 (2.5x)
- Legendary: 30 (3x)

Example scaling for stack value starting at 1:
- Common: 1
- Uncommon: 2
- Rare: 3
- Epic: 4
- Legendary: 5

CRITICAL: When using "add_stacks" or "remove_stacks" action_type, the "attribute" field MUST be one of the attributes listed above.
Do NOT invent new attributes. Only use attributes from the Available Attributes list.
ALL values in the "values" object MUST be integers like 10, 15, 20 - NOT floats like 10.5, 15.5, 20.5.

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
                        "common": integer (whole number like 10, NOT 10.5),
                        "uncommon": integer (whole number like 15, NOT 15.5),
                        "rare": integer (whole number like 20, NOT 20.5),
                        "epic": integer (whole number like 25, NOT 25.5),
                        "legendary": integer (whole number like 30, NOT 30.5)
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
        # Format attributes list
        attrs_list = "\n".join(f"- {attr}" for attr in sorted(attributes))

        prompt = self.GENERATION_PROMPT.format(
            setting_description=setting_description,
            attributes=attrs_list,
        )
        response = await self.client.generate(prompt, system=self.SYSTEM_PROMPT, max_tokens=3000)
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
Always respond with valid JSON matching the requested schema.
CRITICAL: Item names and descriptions should thematically align with the world's attributes."""

    GENERATION_PROMPT = """Given this setting:
{setting_description}

Available Attributes in this world (items should thematically align):
{attributes_list}

Generate item types for each slot:
- 3-4 attack types (weapons)
- 3-4 defense types (armor/shields)
- 3-4 misc types (consumables/utility)

Each type needs:
- name: item type name (e.g., "Sword", "Staff", "Shield")
- slot: attack, defense, or misc
- description: flavor text
- base values scaled by rarity (for attack: damage, defense: armor, misc: heal)

IMPORTANT: ALL base values MUST be integers (whole numbers), NEVER floats.

Rarity scaling for base values (use whole numbers only):
- Common: 8-10 (e.g., 8, 9, or 10)
- Uncommon: 12-15 (e.g., 12, 13, 14, or 15)
- Rare: 18-22 (e.g., 18, 19, 20, 21, or 22)
- Epic: 25-30 (e.g., 25, 26, 27, 28, 29, or 30)
- Legendary: 35-40 (e.g., 35, 36, 37, 38, 39, or 40)

CRITICAL: Item names and descriptions should reference or complement the attributes listed above.
Create items that make thematic sense with these attributes and the world they exist in.

Respond with JSON (ALL values must be integers, NOT floats):
{{
    "attack_types": [
        {{
            "name": "string",
            "slot": "attack",
            "description": "string",
            "base_damage": {{"common": integer, "uncommon": integer, "rare": integer, "epic": integer, "legendary": integer}}
        }}
    ],
    "defense_types": [
        {{
            "name": "string",
            "slot": "defense",
            "description": "string",
            "base_armor": {{"common": integer, "uncommon": integer, "rare": integer, "epic": integer, "legendary": integer}}
        }}
    ],
    "misc_types": [
        {{
            "name": "string",
            "slot": "misc",
            "description": "string",
            "base_heal": {{"common": integer, "uncommon": integer, "rare": integer, "epic": integer, "legendary": integer}}
        }}
    ]
}}"""

    def __init__(self, client: LLMClient) -> None:
        self.client = client

    async def generate(self, setting_description: str, attribute_names: list[str] | None = None) -> GeneratedItemTypes:
        """Generate item types for a setting.

        Args:
            setting_description: Broad setting description
            attribute_names: List of attribute names for thematic alignment

        Returns:
            GeneratedItemTypes with item type definitions
        """
        # Format attributes list
        if attribute_names:
            attrs_list = "\n".join(f"- {attr}" for attr in sorted(attribute_names))
        else:
            attrs_list = "- (No attributes defined)"

        prompt = self.GENERATION_PROMPT.format(
            setting_description=setting_description,
            attributes_list=attrs_list,
        )
        response = await self.client.generate(prompt, system=self.SYSTEM_PROMPT, max_tokens=3000)
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

"""Tests for parsing JSON into game schemas.

These tests verify that realistic JSON (like LLM output) can be correctly
parsed into our Pydantic models with all fields properly populated.
"""

import json

import pytest

from vaudeville_rpg.llm.generators import _extract_json
from vaudeville_rpg.llm.schemas import (
    EffectTemplate,
    FullSettingContent,
    GeneratedEffectTemplates,
    GeneratedItemTypes,
    GeneratedSetting,
    GeneratedWorldRules,
    ItemType,
)


class TestGeneratedSettingParsing:
    """Tests for parsing GeneratedSetting from JSON."""

    FANTASY_SETTING_JSON = """{
        "broad_description": "In the realm of Eldergrove, ancient magic flows through ley lines.",
        "special_points": {
            "name": "mana",
            "display_name": "Mana",
            "description": "Mystical energy drawn from the ley lines that powers all magical abilities",
            "regen_per_turn": 5
        },
        "attributes": [
            {
                "name": "poison",
                "display_name": "Poison",
                "description": "A deadly toxin that damages over time",
                "is_positive": false
            },
            {
                "name": "armor",
                "display_name": "Armor",
                "description": "Protective barrier that reduces incoming damage",
                "is_positive": true
            },
            {
                "name": "burning",
                "display_name": "Burning",
                "description": "Flames that sear the target each turn",
                "is_positive": false
            }
        ]
    }"""

    SCIFI_SETTING_JSON = """{
        "broad_description": "The year is 3047. Humanity has spread across the galaxy.",
        "special_points": {
            "name": "energy",
            "display_name": "Energy Cells",
            "description": "Power cells that fuel weapons and shields",
            "regen_per_turn": 3
        },
        "attributes": [
            {
                "name": "shield",
                "display_name": "Shield",
                "description": "Energy barrier that absorbs damage",
                "is_positive": true
            },
            {
                "name": "emp",
                "display_name": "EMP Charge",
                "description": "Electromagnetic pulse that disrupts systems",
                "is_positive": false
            }
        ]
    }"""

    def test_parse_fantasy_setting(self):
        """Parse a complete fantasy setting from JSON."""
        data = json.loads(self.FANTASY_SETTING_JSON)
        setting = GeneratedSetting.model_validate(data)

        assert "Eldergrove" in setting.broad_description
        assert setting.special_points.name == "mana"
        assert setting.special_points.display_name == "Mana"
        assert setting.special_points.regen_per_turn == 5
        assert len(setting.attributes) == 3

        # Check specific attributes
        poison = next(a for a in setting.attributes if a.name == "poison")
        assert poison.display_name == "Poison"
        assert poison.is_positive is False

        armor = next(a for a in setting.attributes if a.name == "armor")
        assert armor.is_positive is True

    def test_parse_scifi_setting(self):
        """Parse a sci-fi setting from JSON."""
        data = json.loads(self.SCIFI_SETTING_JSON)
        setting = GeneratedSetting.model_validate(data)

        assert "3047" in setting.broad_description
        assert setting.special_points.name == "energy"
        assert setting.special_points.regen_per_turn == 3
        assert len(setting.attributes) == 2

    def test_parse_setting_from_markdown_block(self):
        """Parse setting from JSON wrapped in markdown code block."""
        markdown_response = f"""Here's the generated setting:

```json
{self.FANTASY_SETTING_JSON}
```

This setting captures the magical essence of the world."""

        data = _extract_json(markdown_response)
        setting = GeneratedSetting.model_validate(data)

        assert setting.special_points.name == "mana"
        assert len(setting.attributes) == 3


class TestGeneratedWorldRulesParsing:
    """Tests for parsing GeneratedWorldRules from JSON."""

    POISON_RULES_JSON = """{
        "attribute_name": "poison",
        "rules": [
            {
                "name": "poison_tick",
                "description": "Poison deals damage at the start of each turn",
                "phase": "pre_move",
                "requires_attribute": "poison",
                "min_stacks": 1,
                "target": "self",
                "action": {
                    "action_type": "damage",
                    "value": 5,
                    "attribute": null
                },
                "per_stack": true
            },
            {
                "name": "poison_decay",
                "description": "Poison wears off over time",
                "phase": "post_move",
                "requires_attribute": "poison",
                "min_stacks": 1,
                "target": "self",
                "action": {
                    "action_type": "remove_stacks",
                    "value": 1,
                    "attribute": "poison"
                },
                "per_stack": false
            }
        ]
    }"""

    ARMOR_RULES_JSON = """{
        "attribute_name": "armor",
        "rules": [
            {
                "name": "armor_block",
                "description": "Armor reduces incoming damage",
                "phase": "pre_damage",
                "requires_attribute": "armor",
                "min_stacks": 1,
                "target": "self",
                "action": {
                    "action_type": "reduce_incoming_damage",
                    "value": 3,
                    "attribute": null
                },
                "per_stack": true
            }
        ]
    }"""

    def test_parse_poison_rules(self):
        """Parse poison world rules from JSON."""
        data = json.loads(self.POISON_RULES_JSON)
        rules = GeneratedWorldRules.model_validate(data)

        assert rules.attribute_name == "poison"
        assert len(rules.rules) == 2

        # Check poison tick rule
        tick = next(r for r in rules.rules if r.name == "poison_tick")
        assert tick.phase == "pre_move"
        assert tick.requires_attribute == "poison"
        assert tick.action.action_type == "damage"
        assert tick.action.value == 5
        assert tick.per_stack is True

        # Check poison decay rule
        decay = next(r for r in rules.rules if r.name == "poison_decay")
        assert decay.phase == "post_move"
        assert decay.action.action_type == "remove_stacks"
        assert decay.action.attribute == "poison"
        assert decay.per_stack is False

    def test_parse_armor_rules(self):
        """Parse armor world rules from JSON."""
        data = json.loads(self.ARMOR_RULES_JSON)
        rules = GeneratedWorldRules.model_validate(data)

        assert rules.attribute_name == "armor"
        assert len(rules.rules) == 1

        block = rules.rules[0]
        assert block.name == "armor_block"
        assert block.action.action_type == "reduce_incoming_damage"
        assert block.per_stack is True


class TestGeneratedEffectTemplatesParsing:
    """Tests for parsing GeneratedEffectTemplates from JSON."""

    EFFECT_TEMPLATES_JSON = """{
        "templates": [
            {
                "name": "poison_strike",
                "description": "Coats the weapon in deadly venom",
                "prefix": "Venomous",
                "suffix": null,
                "slot_type": "attack",
                "actions": [
                    {
                        "action_type": "add_stacks",
                        "target": "enemy",
                        "attribute": "poison",
                        "values": {
                            "common": 1,
                            "uncommon": 2,
                            "rare": 3,
                            "epic": 4,
                            "legendary": 5
                        }
                    }
                ]
            },
            {
                "name": "fortify",
                "description": "Reinforces defensive capabilities",
                "prefix": "Fortified",
                "suffix": "of the Bulwark",
                "slot_type": "defense",
                "actions": [
                    {
                        "action_type": "add_stacks",
                        "target": "self",
                        "attribute": "armor",
                        "values": {
                            "common": 2,
                            "uncommon": 3,
                            "rare": 4,
                            "epic": 6,
                            "legendary": 8
                        }
                    }
                ]
            },
            {
                "name": "life_drain",
                "description": "Siphons life force from enemies",
                "prefix": "Vampiric",
                "suffix": null,
                "slot_type": "misc",
                "actions": [
                    {
                        "action_type": "damage",
                        "target": "enemy",
                        "attribute": null,
                        "values": {
                            "common": 5,
                            "uncommon": 8,
                            "rare": 12,
                            "epic": 16,
                            "legendary": 20
                        }
                    },
                    {
                        "action_type": "heal",
                        "target": "self",
                        "attribute": null,
                        "values": {
                            "common": 3,
                            "uncommon": 5,
                            "rare": 8,
                            "epic": 12,
                            "legendary": 15
                        }
                    }
                ]
            }
        ]
    }"""

    def test_parse_effect_templates(self):
        """Parse effect templates from JSON."""
        data = json.loads(self.EFFECT_TEMPLATES_JSON)
        templates = GeneratedEffectTemplates.model_validate(data)

        assert len(templates.templates) == 3

        # Check poison strike
        poison = next(t for t in templates.templates if t.name == "poison_strike")
        assert poison.prefix == "Venomous"
        assert poison.suffix is None
        assert poison.slot_type == "attack"
        assert len(poison.actions) == 1
        assert poison.actions[0].attribute == "poison"
        assert poison.actions[0].values.common == 1
        assert poison.actions[0].values.legendary == 5

        # Check fortify has suffix
        fortify = next(t for t in templates.templates if t.name == "fortify")
        assert fortify.suffix == "of the Bulwark"
        assert fortify.slot_type == "defense"

        # Check life drain has multiple actions
        drain = next(t for t in templates.templates if t.name == "life_drain")
        assert len(drain.actions) == 2
        action_types = [a.action_type for a in drain.actions]
        assert "damage" in action_types
        assert "heal" in action_types

    def test_parse_single_template(self):
        """Parse a single effect template."""
        template_json = """{
            "name": "flame_burst",
            "description": "Engulfs the target in flames",
            "prefix": "Fiery",
            "suffix": "of Inferno",
            "slot_type": "attack",
            "actions": [
                {
                    "action_type": "add_stacks",
                    "target": "enemy",
                    "attribute": "burning",
                    "values": {
                        "common": 2,
                        "uncommon": 3,
                        "rare": 4,
                        "epic": 5,
                        "legendary": 6
                    }
                }
            ]
        }"""
        data = json.loads(template_json)
        template = EffectTemplate.model_validate(data)

        assert template.name == "flame_burst"
        assert template.prefix == "Fiery"
        assert template.suffix == "of Inferno"
        assert template.actions[0].values.epic == 5


class TestGeneratedItemTypesParsing:
    """Tests for parsing GeneratedItemTypes from JSON."""

    ITEM_TYPES_JSON = """{
        "attack_types": [
            {
                "name": "Sword",
                "slot": "attack",
                "description": "A balanced blade for skilled warriors",
                "base_damage": {
                    "common": 10,
                    "uncommon": 15,
                    "rare": 20,
                    "epic": 28,
                    "legendary": 35
                },
                "base_armor": null,
                "base_heal": null
            },
            {
                "name": "Staff",
                "slot": "attack",
                "description": "A conduit for magical energies",
                "base_damage": {
                    "common": 8,
                    "uncommon": 12,
                    "rare": 18,
                    "epic": 25,
                    "legendary": 32
                },
                "base_armor": null,
                "base_heal": null
            }
        ],
        "defense_types": [
            {
                "name": "Shield",
                "slot": "defense",
                "description": "A sturdy barrier against attacks",
                "base_damage": null,
                "base_armor": {
                    "common": 2,
                    "uncommon": 3,
                    "rare": 4,
                    "epic": 5,
                    "legendary": 7
                },
                "base_heal": null
            }
        ],
        "misc_types": [
            {
                "name": "Healing Potion",
                "slot": "misc",
                "description": "A restorative elixir",
                "base_damage": null,
                "base_armor": null,
                "base_heal": {
                    "common": 15,
                    "uncommon": 22,
                    "rare": 30,
                    "epic": 40,
                    "legendary": 50
                }
            }
        ]
    }"""

    def test_parse_item_types(self):
        """Parse complete item types from JSON."""
        data = json.loads(self.ITEM_TYPES_JSON)
        item_types = GeneratedItemTypes.model_validate(data)

        assert len(item_types.attack_types) == 2
        assert len(item_types.defense_types) == 1
        assert len(item_types.misc_types) == 1

        # Check sword
        sword = next(t for t in item_types.attack_types if t.name == "Sword")
        assert sword.slot == "attack"
        assert sword.base_damage.common == 10
        assert sword.base_damage.legendary == 35
        assert sword.base_armor is None
        assert sword.base_heal is None

        # Check shield
        shield = item_types.defense_types[0]
        assert shield.name == "Shield"
        assert shield.base_armor.legendary == 7

        # Check potion
        potion = item_types.misc_types[0]
        assert potion.base_heal.common == 15

    def test_parse_single_item_type(self):
        """Parse a single item type."""
        item_json = """{
            "name": "Dagger",
            "slot": "attack",
            "description": "A swift weapon for quick strikes",
            "base_damage": {
                "common": 7,
                "uncommon": 11,
                "rare": 15,
                "epic": 20,
                "legendary": 26
            },
            "base_armor": null,
            "base_heal": null
        }"""
        data = json.loads(item_json)
        item_type = ItemType.model_validate(data)

        assert item_type.name == "Dagger"
        assert item_type.base_damage.rare == 15


class TestFullSettingContentParsing:
    """Tests for parsing complete FullSettingContent from JSON."""

    FULL_SETTING_JSON = """{
        "setting": {
            "broad_description": "A dark fantasy world where necromancers battle paladins.",
            "special_points": {
                "name": "soul_energy",
                "display_name": "Soul Energy",
                "description": "Power drawn from the spirit realm",
                "regen_per_turn": 4
            },
            "attributes": [
                {
                    "name": "blight",
                    "display_name": "Blight",
                    "description": "Necrotic corruption",
                    "is_positive": false
                },
                {
                    "name": "holy_shield",
                    "display_name": "Holy Shield",
                    "description": "Divine protection",
                    "is_positive": true
                }
            ]
        },
        "world_rules": [
            {
                "attribute_name": "blight",
                "rules": [
                    {
                        "name": "blight_damage",
                        "description": "Blight corrupts the soul",
                        "phase": "pre_move",
                        "requires_attribute": "blight",
                        "min_stacks": 1,
                        "target": "self",
                        "action": {
                            "action_type": "damage",
                            "value": 4,
                            "attribute": null
                        },
                        "per_stack": true
                    }
                ]
            }
        ],
        "effect_templates": {
            "templates": [
                {
                    "name": "curse",
                    "description": "Inflicts necrotic blight",
                    "prefix": "Cursed",
                    "suffix": null,
                    "slot_type": "attack",
                    "actions": [
                        {
                            "action_type": "add_stacks",
                            "target": "enemy",
                            "attribute": "blight",
                            "values": {
                                "common": 1,
                                "uncommon": 2,
                                "rare": 3,
                                "epic": 4,
                                "legendary": 5
                            }
                        }
                    ]
                }
            ]
        },
        "item_types": {
            "attack_types": [
                {
                    "name": "Scythe",
                    "slot": "attack",
                    "description": "Weapon of the reaper",
                    "base_damage": {
                        "common": 12,
                        "uncommon": 18,
                        "rare": 24,
                        "epic": 32,
                        "legendary": 40
                    },
                    "base_armor": null,
                    "base_heal": null
                }
            ],
            "defense_types": [
                {
                    "name": "Bone Armor",
                    "slot": "defense",
                    "description": "Armor made from the fallen",
                    "base_damage": null,
                    "base_armor": {
                        "common": 3,
                        "uncommon": 4,
                        "rare": 6,
                        "epic": 8,
                        "legendary": 10
                    },
                    "base_heal": null
                }
            ],
            "misc_types": [
                {
                    "name": "Soul Vial",
                    "slot": "misc",
                    "description": "Trapped soul essence",
                    "base_damage": null,
                    "base_armor": null,
                    "base_heal": {
                        "common": 10,
                        "uncommon": 15,
                        "rare": 22,
                        "epic": 30,
                        "legendary": 40
                    }
                }
            ]
        }
    }"""

    def test_parse_full_setting_content(self):
        """Parse complete setting content from JSON."""
        data = json.loads(self.FULL_SETTING_JSON)
        content = FullSettingContent.model_validate(data)

        # Verify setting
        assert content.setting.special_points.name == "soul_energy"
        assert len(content.setting.attributes) == 2

        # Verify world rules
        assert len(content.world_rules) == 1
        assert content.world_rules[0].attribute_name == "blight"
        assert len(content.world_rules[0].rules) == 1

        # Verify effect templates
        assert len(content.effect_templates.templates) == 1
        assert content.effect_templates.templates[0].name == "curse"

        # Verify item types
        assert len(content.item_types.attack_types) == 1
        assert content.item_types.attack_types[0].name == "Scythe"
        assert len(content.item_types.defense_types) == 1
        assert len(content.item_types.misc_types) == 1


class TestExtractJsonWithRealisticResponses:
    """Tests for extracting JSON from LLM-like responses."""

    def test_extract_from_conversational_response(self):
        """Extract JSON from conversational LLM response."""
        response = """I've designed a complete setting for your medieval fantasy world. Here's the configuration:

```json
{
    "broad_description": "The kingdom of Valoria stands at the crossroads of ancient magic and modern warfare.",
    "special_points": {
        "name": "mana",
        "display_name": "Mana",
        "description": "Arcane energy",
        "regen_per_turn": 5
    },
    "attributes": [
        {
            "name": "shield",
            "display_name": "Shield",
            "description": "Magical barrier",
            "is_positive": true
        }
    ]
}
```

This setting provides a balanced combat experience with magical elements."""

        data = _extract_json(response)
        setting = GeneratedSetting.model_validate(data)

        assert setting.special_points.name == "mana"
        assert len(setting.attributes) == 1

    def test_extract_from_code_block_without_json_tag(self):
        """Extract JSON from code block without language tag."""
        response = """Here are the world rules:

```
{
    "attribute_name": "fire",
    "rules": [
        {
            "name": "burn_tick",
            "description": "Fire burns each turn",
            "phase": "pre_move",
            "requires_attribute": "fire",
            "min_stacks": 1,
            "target": "self",
            "action": {
                "action_type": "damage",
                "value": 3
            },
            "per_stack": true
        }
    ]
}
```"""

        data = _extract_json(response)
        rules = GeneratedWorldRules.model_validate(data)

        assert rules.attribute_name == "fire"
        assert rules.rules[0].action.value == 3

    def test_extract_nested_json_with_arrays(self):
        """Extract complex nested JSON with arrays."""
        response = """Generated templates:

```json
{
    "templates": [
        {
            "name": "frost",
            "description": "Freezing cold",
            "prefix": "Frozen",
            "suffix": "of Winter",
            "slot_type": "attack",
            "actions": [
                {
                    "action_type": "add_stacks",
                    "target": "enemy",
                    "attribute": "chill",
                    "values": {"common": 1, "uncommon": 2, "rare": 3, "epic": 4, "legendary": 5}
                },
                {
                    "action_type": "damage",
                    "target": "enemy",
                    "attribute": null,
                    "values": {"common": 5, "uncommon": 7, "rare": 10, "epic": 14, "legendary": 18}
                }
            ]
        }
    ]
}
```"""

        data = _extract_json(response)
        templates = GeneratedEffectTemplates.model_validate(data)

        assert len(templates.templates) == 1
        assert len(templates.templates[0].actions) == 2
        assert templates.templates[0].actions[1].values.epic == 14


class TestEdgeCases:
    """Tests for edge cases in JSON parsing."""

    def test_missing_optional_fields_use_defaults(self):
        """Verify optional fields use default values."""
        minimal_json = """{
            "name": "basic_rule",
            "description": "A simple rule",
            "phase": "pre_move",
            "requires_attribute": "test",
            "action": {
                "action_type": "damage",
                "value": 10
            }
        }"""
        data = json.loads(minimal_json)
        from vaudeville_rpg.llm.schemas import WorldRuleDefinition

        rule = WorldRuleDefinition.model_validate(data)

        # Check defaults
        assert rule.min_stacks == 1
        assert rule.target == "self"
        assert rule.per_stack is False
        assert rule.action.attribute is None

    def test_unicode_in_descriptions(self):
        """Handle unicode characters in descriptions."""
        unicode_json = """{
            "broad_description": "In the realm of \u00c9ldritch, dragons speak in \u4e2d\u6587 runes.",
            "special_points": {
                "name": "qi",
                "display_name": "\u6c14",
                "description": "Life force energy",
                "regen_per_turn": 5
            },
            "attributes": []
        }"""
        data = json.loads(unicode_json)
        setting = GeneratedSetting.model_validate(data)

        assert "Éldritch" in setting.broad_description
        assert setting.special_points.display_name == "气"

    def test_empty_attributes_list(self):
        """Handle empty attributes list."""
        json_data = """{
            "broad_description": "A world without stacking mechanics.",
            "special_points": {
                "name": "energy",
                "display_name": "Energy",
                "description": "Pure power",
                "regen_per_turn": 10
            },
            "attributes": []
        }"""
        data = json.loads(json_data)
        setting = GeneratedSetting.model_validate(data)

        assert len(setting.attributes) == 0

    def test_null_suffix_in_effect_template(self):
        """Handle null suffix in effect template."""
        json_data = """{
            "name": "basic",
            "description": "Basic effect",
            "prefix": "Simple",
            "suffix": null,
            "slot_type": "attack",
            "actions": []
        }"""
        data = json.loads(json_data)
        template = EffectTemplate.model_validate(data)

        assert template.suffix is None

    def test_validation_error_on_invalid_json(self):
        """Verify validation errors are raised for invalid data."""
        invalid_json = """{
            "broad_description": "Valid description",
            "special_points": {
                "name": "mana"
            },
            "attributes": []
        }"""
        data = json.loads(invalid_json)

        with pytest.raises(Exception):  # Pydantic ValidationError
            GeneratedSetting.model_validate(data)

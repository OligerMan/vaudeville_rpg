"""Tests for the content generation system."""

from vaudeville_rpg.llm import (
    GeneratedEffectTemplates,
    GeneratedItemTypes,
    GeneratedSetting,
    ItemFactory,
    Rarity,
)
from vaudeville_rpg.llm.factory import GeneratedAction, GeneratedItem
from vaudeville_rpg.llm.generators import _extract_json
from vaudeville_rpg.llm.schemas import (
    ActionData,
    AttributeDescription,
    EffectTemplate,
    EffectTemplateAction,
    ItemType,
    RarityScaledValue,
    SpecialPointsDescription,
    WorldRuleDefinition,
)


class TestExtractJson:
    """Tests for JSON extraction from LLM responses."""

    def test_extract_raw_json(self):
        """Extract JSON from raw response."""
        text = '{"key": "value"}'
        result = _extract_json(text)
        assert result == {"key": "value"}

    def test_extract_json_with_markdown(self):
        """Extract JSON from markdown code block."""
        text = """Here is the response:
```json
{"key": "value", "number": 42}
```
That's the result."""
        result = _extract_json(text)
        assert result == {"key": "value", "number": 42}

    def test_extract_json_without_language_tag(self):
        """Extract JSON from code block without language tag."""
        text = """```
{"items": [1, 2, 3]}
```"""
        result = _extract_json(text)
        assert result == {"items": [1, 2, 3]}

    def test_extract_json_with_surrounding_text(self):
        """Extract JSON when surrounded by text."""
        text = 'The result is: {"data": true} and that\'s it.'
        result = _extract_json(text)
        assert result == {"data": True}


class TestSchemaValidation:
    """Tests for Pydantic schema validation."""

    def test_attribute_description(self):
        """Validate AttributeDescription schema."""
        attr = AttributeDescription(
            name="poison",
            display_name="Poison",
            description="A deadly toxin",
            is_positive=False,
        )
        assert attr.name == "poison"
        assert attr.is_positive is False

    def test_special_points_description(self):
        """Validate SpecialPointsDescription schema."""
        sp = SpecialPointsDescription(
            name="mana",
            display_name="Mana",
            description="Magical energy",
            regen_per_turn=5,
        )
        assert sp.name == "mana"
        assert sp.regen_per_turn == 5

    def test_generated_setting(self):
        """Validate GeneratedSetting schema."""
        setting = GeneratedSetting(
            broad_description="A world of magic",
            special_points=SpecialPointsDescription(
                name="mana",
                display_name="Mana",
                description="Magic power",
                regen_per_turn=5,
            ),
            attributes=[
                AttributeDescription(
                    name="poison",
                    display_name="Poison",
                    description="Toxin",
                    is_positive=False,
                ),
            ],
        )
        assert len(setting.attributes) == 1
        assert setting.special_points.name == "mana"

    def test_action_data(self):
        """Validate ActionData schema."""
        action = ActionData(
            action_type="damage",
            value=10,
            attribute="poison",
        )
        assert action.action_type == "damage"
        assert action.value == 10

    def test_world_rule_definition(self):
        """Validate WorldRuleDefinition schema."""
        rule = WorldRuleDefinition(
            name="poison_tick",
            description="Deals damage each turn",
            phase="pre_move",
            requires_attribute="poison",
            min_stacks=1,
            target="self",
            action=ActionData(action_type="damage", value=5),
            per_stack=True,
        )
        assert rule.name == "poison_tick"
        assert rule.per_stack is True

    def test_rarity_scaled_value(self):
        """Validate RarityScaledValue schema."""
        scaled = RarityScaledValue(
            common=10,
            uncommon=15,
            rare=20,
            epic=25,
            legendary=30,
        )
        assert scaled.common == 10
        assert scaled.legendary == 30

    def test_effect_template(self):
        """Validate EffectTemplate schema."""
        template = EffectTemplate(
            name="poison_strike",
            description="Applies poison",
            prefix="Poisonous",
            suffix="of Venom",
            slot_type="attack",
            actions=[
                EffectTemplateAction(
                    action_type="add_stacks",
                    target="enemy",
                    attribute="poison",
                    values=RarityScaledValue(common=1, uncommon=2, rare=3, epic=4, legendary=5),
                ),
            ],
        )
        assert template.prefix == "Poisonous"
        assert len(template.actions) == 1

    def test_item_type(self):
        """Validate ItemType schema."""
        item_type = ItemType(
            name="Sword",
            slot="attack",
            description="A sharp blade",
            base_damage=RarityScaledValue(common=10, uncommon=15, rare=20, epic=25, legendary=30),
        )
        assert item_type.name == "Sword"
        assert item_type.base_damage.common == 10


class TestItemFactory:
    """Tests for ItemFactory."""

    def _create_factory(self):
        """Create a factory with test data."""
        item_types = GeneratedItemTypes(
            attack_types=[
                ItemType(
                    name="Sword",
                    slot="attack",
                    description="A sharp blade",
                    base_damage=RarityScaledValue(common=10, uncommon=15, rare=20, epic=25, legendary=30),
                ),
            ],
            defense_types=[
                ItemType(
                    name="Shield",
                    slot="defense",
                    description="A sturdy shield",
                    base_armor=RarityScaledValue(common=2, uncommon=3, rare=4, epic=5, legendary=6),
                ),
            ],
            misc_types=[
                ItemType(
                    name="Potion",
                    slot="misc",
                    description="A healing potion",
                    base_heal=RarityScaledValue(common=10, uncommon=15, rare=20, epic=25, legendary=30),
                ),
            ],
        )

        effect_templates = GeneratedEffectTemplates(
            templates=[
                EffectTemplate(
                    name="poison_strike",
                    description="Applies poison",
                    prefix="Poisonous",
                    suffix=None,
                    slot_type="attack",
                    actions=[
                        EffectTemplateAction(
                            action_type="add_stacks",
                            target="enemy",
                            attribute="poison",
                            values=RarityScaledValue(common=1, uncommon=2, rare=3, epic=4, legendary=5),
                        ),
                    ],
                ),
                EffectTemplate(
                    name="fortify",
                    description="Adds extra armor",
                    prefix="Fortified",
                    suffix=None,
                    slot_type="defense",
                    actions=[
                        EffectTemplateAction(
                            action_type="add_stacks",
                            target="self",
                            attribute="armor",
                            values=RarityScaledValue(common=1, uncommon=2, rare=3, epic=4, legendary=5),
                        ),
                    ],
                ),
                EffectTemplate(
                    name="regenerate",
                    description="Adds regeneration",
                    prefix="Regenerating",
                    suffix=None,
                    slot_type="misc",
                    actions=[
                        EffectTemplateAction(
                            action_type="add_stacks",
                            target="self",
                            attribute="regen",
                            values=RarityScaledValue(common=1, uncommon=2, rare=3, epic=4, legendary=5),
                        ),
                    ],
                ),
            ],
        )

        return ItemFactory(item_types, effect_templates)

    def test_create_common_attack_item(self):
        """Create a common attack item."""
        factory = self._create_factory()
        item = factory.create_item(slot="attack", rarity=Rarity.COMMON)

        assert item.slot == "attack"
        assert item.rarity == 1
        assert "Common" in item.name
        assert "Sword" in item.name
        assert len(item.actions) >= 2  # Base attack + effect

    def test_create_legendary_defense_item(self):
        """Create a legendary defense item."""
        factory = self._create_factory()
        item = factory.create_item(slot="defense", rarity=Rarity.LEGENDARY)

        assert item.slot == "defense"
        assert item.rarity == 5
        assert "Legendary" in item.name
        assert "Shield" in item.name

    def test_create_misc_item(self):
        """Create a misc item."""
        factory = self._create_factory()
        item = factory.create_item(slot="misc", rarity=Rarity.RARE)

        assert item.slot == "misc"
        assert item.rarity == 3
        assert "Rare" in item.name
        assert "Potion" in item.name

    def test_create_starter_items(self):
        """Create starter items (one per slot)."""
        factory = self._create_factory()
        items = factory.create_starter_items()

        assert len(items) == 3
        slots = [item.slot for item in items]
        assert "attack" in slots
        assert "defense" in slots
        assert "misc" in slots

        # All should be common
        for item in items:
            assert item.rarity == 1

    def test_create_dungeon_reward(self):
        """Create dungeon reward within rarity range."""
        factory = self._create_factory()
        item = factory.create_dungeon_reward(min_rarity=2, max_rarity=4)

        assert item.rarity >= 2
        assert item.rarity <= 4

    def test_create_random_item(self):
        """Create a random item."""
        factory = self._create_factory()
        item = factory.create_random_item()

        assert isinstance(item, GeneratedItem)
        assert item.slot in ["attack", "defense", "misc"]
        assert 1 <= item.rarity <= 5

    def test_rarity_scaling_damage(self):
        """Verify damage scales with rarity."""
        factory = self._create_factory()

        common = factory.create_item(slot="attack", rarity=Rarity.COMMON)
        legendary = factory.create_item(slot="attack", rarity=Rarity.LEGENDARY)

        common_damage = next(a.value for a in common.actions if a.action_type == "attack")
        legendary_damage = next(a.value for a in legendary.actions if a.action_type == "attack")

        assert legendary_damage > common_damage
        assert common_damage == 10
        assert legendary_damage == 30

    def test_rarity_scaling_effects(self):
        """Verify effect values scale with rarity."""
        factory = self._create_factory()

        common = factory.create_item(slot="attack", rarity=Rarity.COMMON)
        epic = factory.create_item(slot="attack", rarity=Rarity.EPIC)

        common_stacks = next(a.value for a in common.actions if a.action_type == "add_stacks" and a.attribute == "poison")
        epic_stacks = next(a.value for a in epic.actions if a.action_type == "add_stacks" and a.attribute == "poison")

        assert epic_stacks > common_stacks
        assert common_stacks == 1
        assert epic_stacks == 4

    def test_item_name_format(self):
        """Verify item name format."""
        factory = self._create_factory()
        item = factory.create_item(slot="attack", rarity=Rarity.UNCOMMON)

        # Should be "Uncommon Poisonous Sword"
        parts = item.name.split()
        assert parts[0] == "Uncommon"
        assert parts[1] == "Poisonous"
        assert parts[2] == "Sword"


class TestGeneratedAction:
    """Tests for GeneratedAction dataclass."""

    def test_action_without_attribute(self):
        """Create action without attribute."""
        action = GeneratedAction(
            action_type="damage",
            target="enemy",
            value=10,
        )
        assert action.action_type == "damage"
        assert action.attribute is None

    def test_action_with_attribute(self):
        """Create action with attribute."""
        action = GeneratedAction(
            action_type="add_stacks",
            target="enemy",
            value=3,
            attribute="poison",
        )
        assert action.action_type == "add_stacks"
        assert action.attribute == "poison"


class TestGeneratedItem:
    """Tests for GeneratedItem dataclass."""

    def test_item_creation(self):
        """Create a generated item."""
        item = GeneratedItem(
            name="Common Poisonous Sword",
            description="A sword that poisons enemies",
            slot="attack",
            rarity=1,
            actions=[
                GeneratedAction(action_type="attack", target="enemy", value=10),
                GeneratedAction(
                    action_type="add_stacks",
                    target="enemy",
                    value=2,
                    attribute="poison",
                ),
            ],
        )
        assert item.name == "Common Poisonous Sword"
        assert len(item.actions) == 2


class TestRarity:
    """Tests for Rarity enum."""

    def test_rarity_values(self):
        """Verify rarity integer values."""
        assert Rarity.COMMON == 1
        assert Rarity.UNCOMMON == 2
        assert Rarity.RARE == 3
        assert Rarity.EPIC == 4
        assert Rarity.LEGENDARY == 5

    def test_rarity_from_int(self):
        """Create Rarity from integer."""
        assert Rarity(1) == Rarity.COMMON
        assert Rarity(5) == Rarity.LEGENDARY

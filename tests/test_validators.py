"""Tests for content generation validators."""

from vaudeville_rpg.llm import (
    EffectTemplateValidator,
    ItemTypeValidator,
    SettingValidator,
    WorldRulesValidator,
    validate_all,
)
from vaudeville_rpg.llm.schemas import (
    ActionData,
    AttributeDescription,
    EffectTemplate,
    EffectTemplateAction,
    GeneratedEffectTemplates,
    GeneratedItemTypes,
    GeneratedSetting,
    GeneratedWorldRules,
    ItemType,
    RarityScaledValue,
    SpecialPointsDescription,
    WorldRuleDefinition,
)


class TestSettingValidator:
    """Tests for SettingValidator."""

    def _create_valid_setting(self) -> GeneratedSetting:
        """Create a valid setting for testing."""
        return GeneratedSetting(
            broad_description="A world of magic and wonder where heroes battle monsters. " * 5,
            special_points=SpecialPointsDescription(
                name="mana",
                display_name="Mana",
                description="Magical energy",
                regen_per_turn=5,
            ),
            attributes=[
                AttributeDescription(
                    name="poison",
                    display_name="Poison",
                    description="A deadly toxin",
                    is_positive=False,
                ),
                AttributeDescription(
                    name="armor",
                    display_name="Armor",
                    description="Protective stacks",
                    is_positive=True,
                ),
            ],
        )

    def test_valid_setting(self):
        """Valid setting should pass validation."""
        setting = self._create_valid_setting()
        validator = SettingValidator()
        result = validator.validate(setting)
        assert result.valid
        assert len(result.errors) == 0

    def test_short_description(self):
        """Short description should fail validation."""
        setting = self._create_valid_setting()
        setting.broad_description = "Too short"
        validator = SettingValidator()
        result = validator.validate(setting)
        assert not result.valid
        assert any("broad_description" in e.field for e in result.errors)

    def test_missing_special_points_name(self):
        """Missing special points name should fail."""
        setting = self._create_valid_setting()
        setting.special_points.name = ""
        validator = SettingValidator()
        result = validator.validate(setting)
        assert not result.valid
        assert any("special_points.name" in e.field for e in result.errors)

    def test_negative_regen(self):
        """Negative regen should fail."""
        setting = self._create_valid_setting()
        setting.special_points.regen_per_turn = -5
        validator = SettingValidator()
        result = validator.validate(setting)
        assert not result.valid
        assert any("regen_per_turn" in e.field for e in result.errors)

    def test_too_few_attributes(self):
        """Less than 2 attributes should fail."""
        setting = self._create_valid_setting()
        setting.attributes = [setting.attributes[0]]
        validator = SettingValidator()
        result = validator.validate(setting)
        assert not result.valid
        assert any("attributes" in e.field for e in result.errors)

    def test_duplicate_attribute_names(self):
        """Duplicate attribute names should fail."""
        setting = self._create_valid_setting()
        setting.attributes[1].name = setting.attributes[0].name
        validator = SettingValidator()
        result = validator.validate(setting)
        assert not result.valid
        assert any("Duplicate" in e.message for e in result.errors)


class TestWorldRulesValidator:
    """Tests for WorldRulesValidator."""

    def _create_valid_rules(self) -> GeneratedWorldRules:
        """Create valid world rules for testing."""
        return GeneratedWorldRules(
            attribute_name="poison",
            rules=[
                WorldRuleDefinition(
                    name="poison_tick",
                    description="Deals damage each turn",
                    phase="pre_move",
                    requires_attribute="poison",
                    min_stacks=1,
                    target="self",
                    action=ActionData(action_type="damage", value=5),
                    per_stack=True,
                ),
                WorldRuleDefinition(
                    name="poison_decay",
                    description="Loses stacks each turn",
                    phase="post_move",
                    requires_attribute="poison",
                    min_stacks=1,
                    target="self",
                    action=ActionData(action_type="remove_stacks", value=1, attribute="poison"),
                    per_stack=False,
                ),
            ],
        )

    def test_valid_rules(self):
        """Valid rules should pass validation."""
        rules = self._create_valid_rules()
        validator = WorldRulesValidator(known_attributes={"poison"})
        result = validator.validate(rules)
        assert result.valid
        assert len(result.errors) == 0

    def test_invalid_phase(self):
        """Invalid phase should fail."""
        rules = self._create_valid_rules()
        rules.rules[0].phase = "invalid_phase"
        validator = WorldRulesValidator()
        result = validator.validate(rules)
        assert not result.valid
        assert any("phase" in e.field for e in result.errors)

    def test_invalid_action_type(self):
        """Invalid action type should fail."""
        rules = self._create_valid_rules()
        rules.rules[0].action.action_type = "invalid_action"
        validator = WorldRulesValidator()
        result = validator.validate(rules)
        assert not result.valid
        assert any("action_type" in e.field for e in result.errors)

    def test_unknown_attribute(self):
        """Unknown attribute should fail when known_attributes provided."""
        rules = self._create_valid_rules()
        rules.rules[0].requires_attribute = "unknown"
        validator = WorldRulesValidator(known_attributes={"poison", "armor"})
        result = validator.validate(rules)
        assert not result.valid
        assert any("Unknown attribute" in e.message for e in result.errors)

    def test_missing_attribute_for_stacks(self):
        """Stack operations without attribute should fail."""
        rules = self._create_valid_rules()
        rules.rules[1].action.attribute = None
        validator = WorldRulesValidator()
        result = validator.validate(rules)
        assert not result.valid
        assert any("Attribute required" in e.message for e in result.errors)

    def test_duplicate_rule_names(self):
        """Duplicate rule names should fail."""
        rules = self._create_valid_rules()
        rules.rules[1].name = rules.rules[0].name
        validator = WorldRulesValidator()
        result = validator.validate(rules)
        assert not result.valid
        assert any("Duplicate" in e.message for e in result.errors)

    def test_negative_value(self):
        """Negative action value should fail."""
        rules = self._create_valid_rules()
        rules.rules[0].action.value = -5
        validator = WorldRulesValidator()
        result = validator.validate(rules)
        assert not result.valid
        assert any("negative" in e.message for e in result.errors)


class TestEffectTemplateValidator:
    """Tests for EffectTemplateValidator."""

    def _create_valid_templates(self) -> GeneratedEffectTemplates:
        """Create valid effect templates for testing."""
        return GeneratedEffectTemplates(
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
            ]
        )

    def test_valid_templates(self):
        """Valid templates should pass validation."""
        templates = self._create_valid_templates()
        validator = EffectTemplateValidator(known_attributes={"poison"})
        result = validator.validate(templates)
        assert result.valid
        assert len(result.errors) == 0

    def test_invalid_slot_type(self):
        """Invalid slot type should fail."""
        templates = self._create_valid_templates()
        templates.templates[0].slot_type = "invalid"
        validator = EffectTemplateValidator()
        result = validator.validate(templates)
        assert not result.valid
        assert any("slot_type" in e.field for e in result.errors)

    def test_missing_prefix(self):
        """Missing prefix should fail."""
        templates = self._create_valid_templates()
        templates.templates[0].prefix = ""
        validator = EffectTemplateValidator()
        result = validator.validate(templates)
        assert not result.valid
        assert any("prefix" in e.field for e in result.errors)

    def test_legendary_less_than_common(self):
        """Legendary value less than common should warn."""
        templates = self._create_valid_templates()
        templates.templates[0].actions[0].values.legendary = 0
        validator = EffectTemplateValidator()
        result = validator.validate(templates)
        assert not result.valid
        assert any("Legendary" in e.message for e in result.errors)

    def test_empty_templates(self):
        """Empty templates should fail."""
        templates = GeneratedEffectTemplates(templates=[])
        validator = EffectTemplateValidator()
        result = validator.validate(templates)
        assert not result.valid
        assert any("At least one" in e.message for e in result.errors)


class TestItemTypeValidator:
    """Tests for ItemTypeValidator."""

    def _create_valid_item_types(self) -> GeneratedItemTypes:
        """Create valid item types for testing."""
        return GeneratedItemTypes(
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

    def test_valid_item_types(self):
        """Valid item types should pass validation."""
        item_types = self._create_valid_item_types()
        validator = ItemTypeValidator()
        result = validator.validate(item_types)
        assert result.valid
        assert len(result.errors) == 0

    def test_missing_attack_types(self):
        """Missing attack types should fail."""
        item_types = self._create_valid_item_types()
        item_types.attack_types = []
        validator = ItemTypeValidator()
        result = validator.validate(item_types)
        assert not result.valid
        assert any("attack_types" in e.field for e in result.errors)

    def test_wrong_slot(self):
        """Wrong slot for item type should fail."""
        item_types = self._create_valid_item_types()
        item_types.attack_types[0].slot = "defense"
        validator = ItemTypeValidator()
        result = validator.validate(item_types)
        assert not result.valid
        assert any("slot" in e.field for e in result.errors)

    def test_missing_base_damage_for_attack(self):
        """Missing base_damage for attack item should fail."""
        item_types = self._create_valid_item_types()
        item_types.attack_types[0].base_damage = None
        validator = ItemTypeValidator()
        result = validator.validate(item_types)
        assert not result.valid
        assert any("base_damage" in e.field for e in result.errors)


class TestValidateAll:
    """Tests for the combined validate_all function."""

    def test_validate_all_valid(self):
        """All valid content should pass validation."""
        setting = GeneratedSetting(
            broad_description="A world of magic and wonder. " * 10,
            special_points=SpecialPointsDescription(name="mana", display_name="Mana", description="Magic", regen_per_turn=5),
            attributes=[
                AttributeDescription(name="poison", display_name="Poison", description="Toxin", is_positive=False),
                AttributeDescription(name="armor", display_name="Armor", description="Defense", is_positive=True),
            ],
        )

        world_rules = [
            GeneratedWorldRules(
                attribute_name="poison",
                rules=[
                    WorldRuleDefinition(
                        name="poison_tick",
                        description="Damage",
                        phase="pre_move",
                        requires_attribute="poison",
                        min_stacks=1,
                        target="self",
                        action=ActionData(action_type="damage", value=5),
                    ),
                ],
            ),
        ]

        templates = GeneratedEffectTemplates(
            templates=[
                EffectTemplate(
                    name="poison_strike",
                    description="Apply poison",
                    prefix="Poisonous",
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
            ],
        )

        item_types = GeneratedItemTypes(
            attack_types=[
                ItemType(
                    name="Sword",
                    slot="attack",
                    description="Blade",
                    base_damage=RarityScaledValue(common=10, uncommon=15, rare=20, epic=25, legendary=30),
                ),
            ],
            defense_types=[
                ItemType(
                    name="Shield",
                    slot="defense",
                    description="Shield",
                    base_armor=RarityScaledValue(common=2, uncommon=3, rare=4, epic=5, legendary=6),
                ),
            ],
            misc_types=[
                ItemType(
                    name="Potion",
                    slot="misc",
                    description="Potion",
                    base_heal=RarityScaledValue(common=10, uncommon=15, rare=20, epic=25, legendary=30),
                ),
            ],
        )

        result = validate_all(setting, world_rules, templates, item_types)
        assert result.valid
        assert len(result.errors) == 0

    def test_validate_all_catches_cross_references(self):
        """Invalid cross-references should be caught."""
        setting = GeneratedSetting(
            broad_description="A world of magic and wonder. " * 10,
            special_points=SpecialPointsDescription(name="mana", display_name="Mana", description="Magic", regen_per_turn=5),
            attributes=[
                AttributeDescription(name="poison", display_name="Poison", description="Toxin", is_positive=False),
                AttributeDescription(name="armor", display_name="Armor", description="Defense", is_positive=True),
            ],
        )

        # Effect template references unknown attribute "fire"
        templates = GeneratedEffectTemplates(
            templates=[
                EffectTemplate(
                    name="fire_strike",
                    description="Apply fire",
                    prefix="Fiery",
                    slot_type="attack",
                    actions=[
                        EffectTemplateAction(
                            action_type="add_stacks",
                            target="enemy",
                            attribute="fire",  # Unknown attribute
                            values=RarityScaledValue(common=1, uncommon=2, rare=3, epic=4, legendary=5),
                        ),
                    ],
                ),
            ],
        )

        item_types = GeneratedItemTypes(
            attack_types=[
                ItemType(
                    name="Sword",
                    slot="attack",
                    description="Blade",
                    base_damage=RarityScaledValue(common=10, uncommon=15, rare=20, epic=25, legendary=30),
                ),
            ],
            defense_types=[
                ItemType(
                    name="Shield",
                    slot="defense",
                    description="Shield",
                    base_armor=RarityScaledValue(common=2, uncommon=3, rare=4, epic=5, legendary=6),
                ),
            ],
            misc_types=[
                ItemType(
                    name="Potion",
                    slot="misc",
                    description="Potion",
                    base_heal=RarityScaledValue(common=10, uncommon=15, rare=20, epic=25, legendary=30),
                ),
            ],
        )

        result = validate_all(setting, [], templates, item_types)
        assert not result.valid
        # Check that unknown attribute error is caught
        assert any("Unknown" in e.message or "fire" in str(e.value) for e in result.errors)

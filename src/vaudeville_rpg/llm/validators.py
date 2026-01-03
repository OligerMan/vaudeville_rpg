"""Validators for LLM-generated content."""

from dataclasses import dataclass, field

from .schemas import (
    EffectTemplate,
    GeneratedEffectTemplates,
    GeneratedItemTypes,
    GeneratedSetting,
    GeneratedWorldRules,
    ItemType,
    WorldRuleDefinition,
)


@dataclass
class ValidationError:
    """A single validation error."""

    field: str
    message: str
    value: str | None = None


@dataclass
class ValidationResult:
    """Result of validation."""

    valid: bool
    errors: list[ValidationError] = field(default_factory=list)

    def add_error(self, field: str, message: str, value: str | None = None) -> None:
        """Add a validation error."""
        self.errors.append(ValidationError(field=field, message=message, value=value))
        self.valid = False

    def merge(self, other: "ValidationResult") -> None:
        """Merge another validation result into this one."""
        if not other.valid:
            self.valid = False
            self.errors.extend(other.errors)


# Valid values for enums
VALID_PHASES = {"pre_move", "post_move", "pre_attack", "post_attack", "pre_damage", "post_damage"}
VALID_ACTION_TYPES = {"damage", "attack", "heal", "add_stacks", "remove_stacks", "reduce_incoming_damage"}
VALID_TARGETS = {"self", "enemy"}
VALID_SLOTS = {"attack", "defense", "misc"}


class SettingValidator:
    """Validate generated setting data."""

    def validate(self, setting: GeneratedSetting) -> ValidationResult:
        """Validate a generated setting.

        Args:
            setting: Generated setting to validate

        Returns:
            ValidationResult with any errors found
        """
        result = ValidationResult(valid=True)

        # Validate broad description
        if not setting.broad_description or len(setting.broad_description) < 50:
            result.add_error(
                "broad_description",
                "Broad description must be at least 50 characters",
                setting.broad_description[:50] if setting.broad_description else None,
            )

        # Validate special points
        if not setting.special_points.name:
            result.add_error("special_points.name", "Special points name is required")
        if not setting.special_points.display_name:
            result.add_error("special_points.display_name", "Special points display name is required")
        if setting.special_points.regen_per_turn < 0:
            result.add_error(
                "special_points.regen_per_turn",
                "Regen per turn cannot be negative",
                str(setting.special_points.regen_per_turn),
            )

        # Validate attributes
        if len(setting.attributes) < 2:
            result.add_error("attributes", "At least 2 attributes are required", str(len(setting.attributes)))
        if len(setting.attributes) > 10:
            result.add_error("attributes", "Maximum 10 attributes allowed", str(len(setting.attributes)))

        seen_names = set()
        for i, attr in enumerate(setting.attributes):
            if not attr.name:
                result.add_error(f"attributes[{i}].name", "Attribute name is required")
            elif attr.name in seen_names:
                result.add_error(f"attributes[{i}].name", "Duplicate attribute name", attr.name)
            else:
                seen_names.add(attr.name)

            if not attr.display_name:
                result.add_error(f"attributes[{i}].display_name", "Attribute display name is required")

        return result


class WorldRulesValidator:
    """Validate generated world rules."""

    def __init__(self, known_attributes: set[str] | None = None) -> None:
        """Initialize with known attributes for reference validation.

        Args:
            known_attributes: Set of valid attribute names
        """
        self.known_attributes = known_attributes or set()

    def validate(self, world_rules: GeneratedWorldRules) -> ValidationResult:
        """Validate world rules.

        Args:
            world_rules: Generated world rules to validate

        Returns:
            ValidationResult with any errors found
        """
        result = ValidationResult(valid=True)

        if not world_rules.attribute_name:
            result.add_error("attribute_name", "Attribute name is required")

        if not world_rules.rules:
            result.add_error("rules", "At least one rule is required")
            return result

        seen_names = set()
        for i, rule in enumerate(world_rules.rules):
            rule_result = self._validate_rule(i, rule, seen_names)
            result.merge(rule_result)

        return result

    def _validate_rule(self, index: int, rule: WorldRuleDefinition, seen_names: set[str]) -> ValidationResult:
        """Validate a single world rule."""
        result = ValidationResult(valid=True)
        prefix = f"rules[{index}]"

        # Validate name
        if not rule.name:
            result.add_error(f"{prefix}.name", "Rule name is required")
        elif rule.name in seen_names:
            result.add_error(f"{prefix}.name", "Duplicate rule name", rule.name)
        else:
            seen_names.add(rule.name)

        # Validate phase
        if rule.phase not in VALID_PHASES:
            result.add_error(f"{prefix}.phase", f"Invalid phase. Must be one of: {VALID_PHASES}", rule.phase)

        # Validate requires_attribute
        if not rule.requires_attribute:
            result.add_error(f"{prefix}.requires_attribute", "Required attribute is required")
        elif self.known_attributes and rule.requires_attribute not in self.known_attributes:
            result.add_error(
                f"{prefix}.requires_attribute",
                f"Unknown attribute. Known: {self.known_attributes}",
                rule.requires_attribute,
            )

        # Validate min_stacks
        if rule.min_stacks < 1:
            result.add_error(f"{prefix}.min_stacks", "Min stacks must be at least 1", str(rule.min_stacks))

        # Validate target
        if rule.target not in VALID_TARGETS:
            result.add_error(f"{prefix}.target", f"Invalid target. Must be one of: {VALID_TARGETS}", rule.target)

        # Validate action
        if not rule.action:
            result.add_error(f"{prefix}.action", "Action is required")
        else:
            if rule.action.action_type not in VALID_ACTION_TYPES:
                result.add_error(
                    f"{prefix}.action.action_type",
                    f"Invalid action type. Must be one of: {VALID_ACTION_TYPES}",
                    rule.action.action_type,
                )
            if rule.action.value < 0:
                result.add_error(f"{prefix}.action.value", "Action value cannot be negative", str(rule.action.value))

            # Validate attribute reference for stack operations
            if rule.action.action_type in {"add_stacks", "remove_stacks"}:
                if not rule.action.attribute:
                    result.add_error(f"{prefix}.action.attribute", "Attribute required for stack operations")
                elif self.known_attributes and rule.action.attribute not in self.known_attributes:
                    result.add_error(
                        f"{prefix}.action.attribute",
                        f"Unknown attribute. Known: {self.known_attributes}",
                        rule.action.attribute,
                    )

        return result


class EffectTemplateValidator:
    """Validate generated effect templates."""

    def __init__(self, known_attributes: set[str] | None = None) -> None:
        """Initialize with known attributes for reference validation."""
        self.known_attributes = known_attributes or set()

    def validate(self, templates: GeneratedEffectTemplates) -> ValidationResult:
        """Validate effect templates.

        Args:
            templates: Generated effect templates to validate

        Returns:
            ValidationResult with any errors found
        """
        result = ValidationResult(valid=True)

        if not templates.templates:
            result.add_error("templates", "At least one template is required")
            return result

        seen_names = set()
        for i, template in enumerate(templates.templates):
            template_result = self._validate_template(i, template, seen_names)
            result.merge(template_result)

        return result

    def _validate_template(self, index: int, template: EffectTemplate, seen_names: set[str]) -> ValidationResult:
        """Validate a single effect template."""
        result = ValidationResult(valid=True)
        prefix = f"templates[{index}]"

        # Validate name
        if not template.name:
            result.add_error(f"{prefix}.name", "Template name is required")
        elif template.name in seen_names:
            result.add_error(f"{prefix}.name", "Duplicate template name", template.name)
        else:
            seen_names.add(template.name)

        # Validate prefix
        if not template.prefix:
            result.add_error(f"{prefix}.prefix", "Prefix is required")

        # Validate slot_type
        if template.slot_type not in VALID_SLOTS:
            result.add_error(
                f"{prefix}.slot_type",
                f"Invalid slot type. Must be one of: {VALID_SLOTS}",
                template.slot_type,
            )

        # Validate actions
        if not template.actions:
            result.add_error(f"{prefix}.actions", "At least one action is required")
        else:
            for j, action in enumerate(template.actions):
                action_prefix = f"{prefix}.actions[{j}]"

                if action.action_type not in VALID_ACTION_TYPES:
                    result.add_error(
                        f"{action_prefix}.action_type",
                        f"Invalid action type. Must be one of: {VALID_ACTION_TYPES}",
                        action.action_type,
                    )

                if action.target not in VALID_TARGETS:
                    result.add_error(
                        f"{action_prefix}.target",
                        f"Invalid target. Must be one of: {VALID_TARGETS}",
                        action.target,
                    )

                # Validate rarity values
                if action.values.common < 0:
                    result.add_error(f"{action_prefix}.values.common", "Value cannot be negative")
                if action.values.legendary < action.values.common:
                    result.add_error(
                        f"{action_prefix}.values",
                        "Legendary value should be >= common value",
                    )

                # Validate attribute reference
                if action.action_type in {"add_stacks", "remove_stacks"}:
                    if not action.attribute:
                        result.add_error(f"{action_prefix}.attribute", "Attribute required for stack operations")
                    elif self.known_attributes and action.attribute not in self.known_attributes:
                        result.add_error(
                            f"{action_prefix}.attribute",
                            f"Unknown attribute. Known: {self.known_attributes}",
                            action.attribute,
                        )

        return result


class ItemTypeValidator:
    """Validate generated item types."""

    def validate(self, item_types: GeneratedItemTypes) -> ValidationResult:
        """Validate item types.

        Args:
            item_types: Generated item types to validate

        Returns:
            ValidationResult with any errors found
        """
        result = ValidationResult(valid=True)

        # Validate attack types
        if not item_types.attack_types:
            result.add_error("attack_types", "At least one attack type is required")
        else:
            for i, item_type in enumerate(item_types.attack_types):
                type_result = self._validate_item_type(f"attack_types[{i}]", item_type, "attack")
                result.merge(type_result)

        # Validate defense types
        if not item_types.defense_types:
            result.add_error("defense_types", "At least one defense type is required")
        else:
            for i, item_type in enumerate(item_types.defense_types):
                type_result = self._validate_item_type(f"defense_types[{i}]", item_type, "defense")
                result.merge(type_result)

        # Validate misc types
        if not item_types.misc_types:
            result.add_error("misc_types", "At least one misc type is required")
        else:
            for i, item_type in enumerate(item_types.misc_types):
                type_result = self._validate_item_type(f"misc_types[{i}]", item_type, "misc")
                result.merge(type_result)

        return result

    def _validate_item_type(self, prefix: str, item_type: ItemType, expected_slot: str) -> ValidationResult:
        """Validate a single item type."""
        result = ValidationResult(valid=True)

        if not item_type.name:
            result.add_error(f"{prefix}.name", "Item type name is required")

        if item_type.slot != expected_slot:
            result.add_error(f"{prefix}.slot", f"Slot should be '{expected_slot}'", item_type.slot)

        # Validate base values exist
        if expected_slot == "attack" and not item_type.base_damage:
            result.add_error(f"{prefix}.base_damage", "Base damage is required for attack items")
        elif expected_slot == "defense" and not item_type.base_armor:
            result.add_error(f"{prefix}.base_armor", "Base armor is required for defense items")
        elif expected_slot == "misc" and not item_type.base_heal:
            result.add_error(f"{prefix}.base_heal", "Base heal is required for misc items")

        return result


def validate_all(
    setting: GeneratedSetting,
    world_rules_list: list[GeneratedWorldRules],
    effect_templates: GeneratedEffectTemplates,
    item_types: GeneratedItemTypes,
) -> ValidationResult:
    """Validate all generated content together.

    Args:
        setting: Generated setting
        world_rules_list: List of world rules for each attribute
        effect_templates: Generated effect templates
        item_types: Generated item types

    Returns:
        Combined ValidationResult
    """
    result = ValidationResult(valid=True)

    # Validate setting first to get attribute names
    setting_validator = SettingValidator()
    setting_result = setting_validator.validate(setting)
    result.merge(setting_result)

    if not setting_result.valid:
        return result  # Can't continue without valid setting

    # Get known attributes
    known_attributes = {attr.name for attr in setting.attributes}

    # Validate world rules
    rules_validator = WorldRulesValidator(known_attributes)
    for world_rules in world_rules_list:
        rules_result = rules_validator.validate(world_rules)
        result.merge(rules_result)

    # Validate effect templates
    templates_validator = EffectTemplateValidator(known_attributes)
    templates_result = templates_validator.validate(effect_templates)
    result.merge(templates_result)

    # Validate item types
    types_validator = ItemTypeValidator()
    types_result = types_validator.validate(item_types)
    result.merge(types_result)

    return result

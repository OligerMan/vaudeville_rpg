"""Structured output schemas for LLM content generation."""

from pydantic import BaseModel, Field

# =============================================================================
# Step 1: Setting Generation Schemas
# =============================================================================


class AttributeDescription(BaseModel):
    """Generated attribute description."""

    name: str = Field(description="Short name for the attribute (e.g., 'poison', 'holy_defense')")
    display_name: str = Field(description="Display name for UI (e.g., 'Poison', 'Holy Defense')")
    description: str = Field(description="Flavor description of what this attribute represents")
    is_positive: bool = Field(description="True if this is a buff, False if debuff")


class SpecialPointsDescription(BaseModel):
    """Generated special points (mana/energy) description."""

    name: str = Field(description="Name for special points (e.g., 'mana', 'energy', 'ki')")
    display_name: str = Field(description="Display name for UI (e.g., 'Mana', 'Energy')")
    description: str = Field(description="Flavor description of what powers abilities")
    regen_per_turn: int = Field(default=5, description="How much regenerates per turn")


class GeneratedSetting(BaseModel):
    """Complete setting generation output."""

    broad_description: str = Field(description="Expanded world lore and flavor text")
    special_points: SpecialPointsDescription = Field(description="Special points attribute")
    attributes: list[AttributeDescription] = Field(description="Stack-based attributes (3-5)")


# =============================================================================
# Step 2: World Rules Generation Schemas
# =============================================================================


class ActionData(BaseModel):
    """Formal action definition."""

    action_type: str = Field(description="Action type: damage, heal, add_stacks, remove_stacks, reduce_incoming_damage")
    value: int = Field(description="Numeric value for the action")
    attribute: str | None = Field(default=None, description="Target attribute for stack operations")


class WorldRuleDefinition(BaseModel):
    """Formal world rule definition."""

    name: str = Field(description="Unique rule name (e.g., 'poison_tick', 'armor_block')")
    description: str = Field(description="Human-readable description")
    phase: str = Field(description="When to trigger: pre_move, post_move, pre_damage, post_damage")
    requires_attribute: str = Field(description="Attribute that must have stacks")
    min_stacks: int = Field(default=1, description="Minimum stacks required")
    target: str = Field(default="self", description="Target: self or enemy")
    action: ActionData = Field(description="What happens when triggered")
    per_stack: bool = Field(default=False, description="If true, action repeats per stack")


class GeneratedWorldRules(BaseModel):
    """World rules generated from attribute descriptions."""

    attribute_name: str = Field(description="Which attribute these rules are for")
    rules: list[WorldRuleDefinition] = Field(description="List of rules for this attribute")


# =============================================================================
# Step 3: Item Effect Generation Schemas
# =============================================================================


class RarityScaledValue(BaseModel):
    """Value scaled by rarity."""

    common: int = Field(description="Value at common rarity")
    uncommon: int = Field(description="Value at uncommon rarity")
    rare: int = Field(description="Value at rare rarity")
    epic: int = Field(description="Value at epic rarity")
    legendary: int = Field(description="Value at legendary rarity")


class EffectTemplateAction(BaseModel):
    """Action template with rarity scaling."""

    action_type: str = Field(description="Action type: attack, damage, heal, add_stacks, remove_stacks")
    target: str = Field(default="enemy", description="Target: self or enemy")
    attribute: str | None = Field(default=None, description="Target attribute for stack operations")
    values: RarityScaledValue = Field(description="Values for each rarity level")


class EffectTemplate(BaseModel):
    """Item effect template with naming and rarity scaling."""

    name: str = Field(description="Internal effect name (e.g., 'poison_strike')")
    description: str = Field(description="What this effect does")
    prefix: str = Field(description="Naming prefix (e.g., 'Poisonous', 'Fiery')")
    suffix: str | None = Field(default=None, description="Optional naming suffix (e.g., 'of Flames')")
    slot_type: str = Field(description="Which slot: attack, defense, misc")
    actions: list[EffectTemplateAction] = Field(description="Actions this effect performs")


class GeneratedEffectTemplates(BaseModel):
    """Collection of generated effect templates."""

    templates: list[EffectTemplate] = Field(description="List of effect templates")


# =============================================================================
# Step 4: Item Type Generation Schemas
# =============================================================================


class ItemType(BaseModel):
    """Item type definition."""

    name: str = Field(description="Item type name (e.g., 'Sword', 'Shield', 'Potion')")
    slot: str = Field(description="Which slot: attack, defense, misc")
    description: str = Field(description="Flavor description of this item type")
    base_damage: RarityScaledValue | None = Field(default=None, description="Base damage for attack items")
    base_armor: RarityScaledValue | None = Field(default=None, description="Base armor for defense items")
    base_heal: RarityScaledValue | None = Field(default=None, description="Base heal for misc items")


class GeneratedItemTypes(BaseModel):
    """Collection of generated item types."""

    attack_types: list[ItemType] = Field(description="Attack item types (weapons)")
    defense_types: list[ItemType] = Field(description="Defense item types (armor/shields)")
    misc_types: list[ItemType] = Field(description="Misc item types (consumables/utility)")


# =============================================================================
# Combined Generation Result
# =============================================================================


class FullSettingContent(BaseModel):
    """Complete generated content for a setting."""

    setting: GeneratedSetting
    world_rules: list[GeneratedWorldRules]
    effect_templates: GeneratedEffectTemplates
    item_types: GeneratedItemTypes

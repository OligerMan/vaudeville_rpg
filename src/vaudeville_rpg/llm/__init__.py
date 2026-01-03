"""LLM client abstraction for content generation."""

from .client import LLMClient, LLMResponse, get_llm_client
from .factory import GeneratedAction, GeneratedItem, ItemFactory, Rarity
from .generators import (
    EffectTemplateGenerator,
    ItemTypeGenerator,
    SettingGenerator,
    WorldRulesGenerator,
)
from .schemas import (
    ActionData,
    AttributeDescription,
    EffectTemplate,
    EffectTemplateAction,
    FullSettingContent,
    GeneratedEffectTemplates,
    GeneratedItemTypes,
    GeneratedSetting,
    GeneratedWorldRules,
    ItemType,
    RarityScaledValue,
    SpecialPointsDescription,
    WorldRuleDefinition,
)

__all__ = [
    # Client
    "LLMClient",
    "LLMResponse",
    "get_llm_client",
    # Factory
    "ItemFactory",
    "GeneratedItem",
    "GeneratedAction",
    "Rarity",
    # Generators
    "SettingGenerator",
    "WorldRulesGenerator",
    "EffectTemplateGenerator",
    "ItemTypeGenerator",
    # Schemas
    "ActionData",
    "AttributeDescription",
    "EffectTemplate",
    "EffectTemplateAction",
    "FullSettingContent",
    "GeneratedEffectTemplates",
    "GeneratedItemTypes",
    "GeneratedSetting",
    "GeneratedWorldRules",
    "ItemType",
    "RarityScaledValue",
    "SpecialPointsDescription",
    "WorldRuleDefinition",
]

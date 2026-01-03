"""LLM client abstraction for content generation."""

from .client import LLMClient, LLMResponse, get_llm_client
from .factory import GeneratedAction, GeneratedItem, ItemFactory, Rarity
from .generators import (
    EffectTemplateGenerator,
    ItemTypeGenerator,
    SettingGenerator,
    WorldRulesGenerator,
)
from .parser import ItemParser, ParseResult, WorldRulesParser
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
from .setting_factory import PipelineResult, PipelineStep, SettingFactory
from .validators import (
    EffectTemplateValidator,
    ItemTypeValidator,
    SettingValidator,
    ValidationError,
    ValidationResult,
    WorldRulesValidator,
    validate_all,
)

__all__ = [
    # Client
    "LLMClient",
    "LLMResponse",
    "get_llm_client",
    # Setting Factory (main entry point)
    "SettingFactory",
    "PipelineResult",
    "PipelineStep",
    # Item Factory
    "ItemFactory",
    "GeneratedItem",
    "GeneratedAction",
    "Rarity",
    # Parsers
    "WorldRulesParser",
    "ItemParser",
    "ParseResult",
    # Validators
    "SettingValidator",
    "WorldRulesValidator",
    "EffectTemplateValidator",
    "ItemTypeValidator",
    "ValidationResult",
    "ValidationError",
    "validate_all",
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

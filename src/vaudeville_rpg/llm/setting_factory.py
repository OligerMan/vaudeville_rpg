"""Setting factory - orchestrates the complete content generation pipeline."""

import asyncio
from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession

from ..config import Settings, get_settings
from ..db.models.enums import AttributeCategory
from ..db.models.settings import AttributeDefinition, Setting
from .client import LLMClient, get_llm_client
from .factory import ItemFactory, Rarity
from .generators import (
    EffectTemplateGenerator,
    ItemTypeGenerator,
    SettingGenerator,
    WorldRulesGenerator,
)
from .parser import ItemParser, WorldRulesParser
from .schemas import GeneratedEffectTemplates, GeneratedItemTypes, GeneratedSetting, GeneratedWorldRules
from .validators import (
    EffectTemplateValidator,
    ItemTypeValidator,
    SettingValidator,
    WorldRulesValidator,
)


@dataclass
class PipelineStep:
    """Result of a single pipeline step."""

    name: str
    success: bool
    message: str
    data: object | None = None
    validation_errors: list[str] = field(default_factory=list)


@dataclass
class PipelineResult:
    """Result of the complete pipeline."""

    success: bool
    message: str
    setting: Setting | None = None
    steps: list[PipelineStep] = field(default_factory=list)

    # Statistics
    attributes_created: int = 0
    world_rules_created: int = 0
    effect_templates_created: int = 0
    item_types_created: int = 0
    items_created: int = 0

    def add_step(self, step: PipelineStep) -> None:
        """Add a step result."""
        self.steps.append(step)
        if not step.success:
            self.success = False


class SettingFactory:
    """Factory for creating complete settings from user input.

    This is the main entry point for the content generation pipeline.
    It orchestrates all steps from user input to database persistence.
    """

    def __init__(
        self,
        session: AsyncSession,
        llm_client: LLMClient | None = None,
        settings: Settings | None = None,
    ) -> None:
        """Initialize the factory.

        Args:
            session: Database session
            llm_client: LLM client (created from settings if not provided)
            settings: Application settings (loaded from env if not provided)
        """
        self.session = session
        self.settings = settings or get_settings()

        # Initialize LLM client
        if llm_client:
            self.client = llm_client
        else:
            self.client = get_llm_client(self.settings)

        # Initialize generators
        self.setting_gen = SettingGenerator(self.client)
        self.rules_gen = WorldRulesGenerator(self.client)
        self.effects_gen = EffectTemplateGenerator(self.client)
        self.types_gen = ItemTypeGenerator(self.client)

        # Initialize parsers
        self.rules_parser = WorldRulesParser(session)
        self.item_parser = ItemParser(session)

    async def create_setting(
        self,
        telegram_chat_id: int,
        user_prompt: str,
        validate: bool = True,
        retry_on_validation_fail: bool = True,
        max_retries: int = 5,
    ) -> PipelineResult:
        """Create a complete setting from user prompt.

        This is the main method that orchestrates the full pipeline:
        1. Generate setting description and attributes
        2. Generate world rules for each attribute
        3. Generate effect templates
        4. Generate item types
        5. Create items using the factory
        6. Persist everything to database

        Args:
            telegram_chat_id: Telegram chat ID for the setting
            user_prompt: User's setting description
            validate: Whether to validate LLM outputs
            retry_on_validation_fail: Retry generation on validation failure
            max_retries: Maximum retry attempts

        Returns:
            PipelineResult with complete setting and statistics
        """
        result = PipelineResult(success=True, message="")

        try:
            # Step 1: Generate setting
            setting_step = await self._step_generate_setting(user_prompt, validate, retry_on_validation_fail, max_retries)
            result.add_step(setting_step)
            if not setting_step.success:
                result.message = f"Failed at step 1: {setting_step.message}"
                return result

            generated_setting: GeneratedSetting = setting_step.data
            attribute_names = {attr.name for attr in generated_setting.attributes}
            result.attributes_created = len(generated_setting.attributes)

            # Create database setting
            db_setting = Setting(
                telegram_chat_id=telegram_chat_id,
                name=generated_setting.broad_description[:100],
                description=generated_setting.broad_description,
                special_points_name=generated_setting.special_points.display_name,
                special_points_regen=generated_setting.special_points.regen_per_turn,
            )
            self.session.add(db_setting)
            await self.session.flush()
            result.setting = db_setting

            # Persist attributes to database
            for attr in generated_setting.attributes:
                attr_def = AttributeDefinition(
                    setting_id=db_setting.id,
                    name=attr.name,
                    display_name=attr.display_name,
                    description=attr.description,
                    category=AttributeCategory.GENERATABLE,
                    max_stacks=10,  # Default max stacks
                    default_stacks=0,
                )
                self.session.add(attr_def)
            await self.session.flush()

            # Step 2: Generate world rules for each attribute
            world_rules_list: list[GeneratedWorldRules] = []
            for attr in generated_setting.attributes:
                rules_step = await self._step_generate_world_rules(
                    attr,
                    attribute_names,
                    generated_setting.broad_description,
                    validate,
                    retry_on_validation_fail,
                    max_retries,
                )
                result.add_step(rules_step)
                if not rules_step.success:
                    result.message = f"Failed generating rules for {attr.name}: {rules_step.message}"
                    return result

                world_rules: GeneratedWorldRules = rules_step.data
                world_rules_list.append(world_rules)

                # Parse and persist world rules
                parse_result = await self.rules_parser.parse(db_setting.id, world_rules)
                if not parse_result.success:
                    result.message = f"Failed parsing rules for {attr.name}: {parse_result.message}"
                    result.success = False
                    return result
                result.world_rules_created += len(world_rules.rules)

            # Step 3: Generate effect templates
            effects_step = await self._step_generate_effect_templates(
                generated_setting.broad_description,
                attribute_names,
                validate,
                retry_on_validation_fail,
                max_retries,
            )
            result.add_step(effects_step)
            if not effects_step.success:
                result.message = f"Failed at step 3: {effects_step.message}"
                return result

            effect_templates: GeneratedEffectTemplates = effects_step.data
            result.effect_templates_created = len(effect_templates.templates)

            # Step 4: Generate item types
            types_step = await self._step_generate_item_types(
                generated_setting.broad_description,
                list(attribute_names),
                validate,
                retry_on_validation_fail,
                max_retries,
            )
            result.add_step(types_step)
            if not types_step.success:
                result.message = f"Failed at step 4: {types_step.message}"
                return result

            item_types: GeneratedItemTypes = types_step.data
            result.item_types_created = len(item_types.attack_types) + len(item_types.defense_types) + len(item_types.misc_types)

            # Step 5: Create items
            items_step = await self._step_create_items(db_setting.id, item_types, effect_templates)
            result.add_step(items_step)
            if not items_step.success:
                result.message = f"Failed at step 5: {items_step.message}"
                return result

            result.items_created = items_step.data

            await self.session.flush()
            result.message = "Setting created successfully"
            return result

        except Exception as e:
            result.success = False
            result.message = f"Pipeline failed: {e!s}"
            return result

    async def _step_generate_setting(
        self,
        user_prompt: str,
        validate: bool,
        retry: bool,
        max_retries: int,
    ) -> PipelineStep:
        """Step 1: Generate setting description and attributes."""
        step = PipelineStep(name="generate_setting", success=False, message="")

        for attempt in range(max_retries + 1):
            try:
                generated = await self.setting_gen.generate(user_prompt)

                if validate:
                    validator = SettingValidator()
                    validation = validator.validate(generated)
                    if not validation.valid:
                        step.validation_errors = [f"{e.field}: {e.message}" for e in validation.errors]
                        if retry and attempt < max_retries:
                            await asyncio.sleep(self.settings.llm_retry_delay)
                            continue
                        step.message = f"Validation failed: {step.validation_errors}"
                        return step

                step.success = True
                step.message = f"Generated setting with {len(generated.attributes)} attributes"
                step.data = generated
                return step

            except Exception as e:
                step.message = f"Generation failed: {e!s}"
                if attempt < max_retries:
                    await asyncio.sleep(self.settings.llm_retry_delay)
                    continue
                return step

        return step

    async def _step_generate_world_rules(
        self,
        attr,
        known_attributes: set[str],
        setting_description: str,
        validate: bool,
        retry: bool,
        max_retries: int,
    ) -> PipelineStep:
        """Step 2: Generate world rules for an attribute."""
        step = PipelineStep(name=f"generate_rules_{attr.name}", success=False, message="")

        for attempt in range(max_retries + 1):
            try:
                generated = await self.rules_gen.generate(
                    attribute_name=attr.name,
                    display_name=attr.display_name,
                    description=attr.description,
                    is_positive=attr.is_positive,
                    setting_description=setting_description,
                    known_attributes=known_attributes,
                )

                if validate:
                    validator = WorldRulesValidator(known_attributes)
                    validation = validator.validate(generated)
                    if not validation.valid:
                        step.validation_errors = [f"{e.field}: {e.message}" for e in validation.errors]
                        if retry and attempt < max_retries:
                            await asyncio.sleep(self.settings.llm_retry_delay)
                            continue
                        step.message = f"Validation failed: {step.validation_errors}"
                        return step

                step.success = True
                step.message = f"Generated {len(generated.rules)} rules for {attr.name}"
                step.data = generated
                return step

            except Exception as e:
                step.message = f"Generation failed: {e!s}"
                if attempt < max_retries:
                    await asyncio.sleep(self.settings.llm_retry_delay)
                    continue
                return step

        return step

    async def _step_generate_effect_templates(
        self,
        setting_description: str,
        known_attributes: set[str],
        validate: bool,
        retry: bool,
        max_retries: int,
    ) -> PipelineStep:
        """Step 3: Generate effect templates."""
        step = PipelineStep(name="generate_effect_templates", success=False, message="")

        try:
            templates = []
            existing_effects = []

            # Generate 2-3 templates for each slot type
            slot_counts = {"attack": 3, "defense": 3, "misc": 2}

            for slot_type, count in slot_counts.items():
                for i in range(count):
                    for attempt in range(max_retries + 1):
                        try:
                            # Generate single template with context of existing effects
                            template = await self.effects_gen.generate(
                                setting_description=setting_description,
                                attributes=list(known_attributes),
                                slot_type=slot_type,
                                existing_effects=existing_effects if existing_effects else None,
                            )

                            if validate:
                                # Validate single template by wrapping it
                                validator = EffectTemplateValidator(known_attributes)
                                wrapped = GeneratedEffectTemplates(templates=[template])
                                validation = validator.validate(wrapped)
                                if not validation.valid:
                                    step.validation_errors = [f"{e.field}: {e.message}" for e in validation.errors]
                                    if retry and attempt < max_retries:
                                        await asyncio.sleep(self.settings.llm_retry_delay)
                                        continue
                                    step.message = f"Validation failed for {slot_type} template {i + 1}: {step.validation_errors}"
                                    return step

                            # Add to collection
                            templates.append(template)
                            existing_effects.append({"name": template.name, "description": template.description})
                            break  # Success, exit retry loop

                        except Exception as e:
                            if attempt < max_retries:
                                await asyncio.sleep(self.settings.llm_retry_delay)
                                continue
                            step.message = f"Generation failed for {slot_type} template {i + 1}: {e!s}"
                            return step

            # Wrap templates in GeneratedEffectTemplates
            generated = GeneratedEffectTemplates(templates=templates)

            step.success = True
            step.message = f"Generated {len(templates)} effect templates"
            step.data = generated
            return step

        except Exception as e:
            step.message = f"Generation failed: {e!s}"
            return step

    async def _step_generate_item_types(
        self,
        setting_description: str,
        attribute_names: list[str],
        validate: bool,
        retry: bool,
        max_retries: int,
    ) -> PipelineStep:
        """Step 4: Generate item types."""
        step = PipelineStep(name="generate_item_types", success=False, message="")

        for attempt in range(max_retries + 1):
            try:
                generated = await self.types_gen.generate(
                    setting_description=setting_description,
                    attribute_names=attribute_names,
                )

                if validate:
                    validator = ItemTypeValidator()
                    validation = validator.validate(generated)
                    if not validation.valid:
                        step.validation_errors = [f"{e.field}: {e.message}" for e in validation.errors]
                        if retry and attempt < max_retries:
                            await asyncio.sleep(self.settings.llm_retry_delay)
                            continue
                        step.message = f"Validation failed: {step.validation_errors}"
                        return step

                step.success = True
                total = len(generated.attack_types) + len(generated.defense_types) + len(generated.misc_types)
                step.message = f"Generated {total} item types"
                step.data = generated
                return step

            except Exception as e:
                step.message = f"Generation failed: {e!s}"
                if attempt < max_retries:
                    await asyncio.sleep(self.settings.llm_retry_delay)
                    continue
                return step

        return step

    async def _step_create_items(
        self,
        setting_id: int,
        item_types: GeneratedItemTypes,
        effect_templates: GeneratedEffectTemplates,
    ) -> PipelineStep:
        """Step 5: Create items from templates."""
        step = PipelineStep(name="create_items", success=False, message="")
        items_created = 0

        try:
            # Create item factory
            factory = ItemFactory(item_types, effect_templates)

            # Create items for each rarity and slot
            rarities_to_create = [Rarity.COMMON, Rarity.UNCOMMON, Rarity.RARE]

            for rarity in rarities_to_create:
                for slot in ["attack", "defense", "misc"]:
                    # Get random item type and effect for this slot
                    gen_item = factory.create_item(slot=slot, rarity=rarity)

                    # Parse and persist
                    parse_result = await self.item_parser.parse_item(
                        setting_id=setting_id,
                        name=gen_item.name,
                        description=gen_item.description,
                        slot=gen_item.slot,
                        rarity=gen_item.rarity,
                        actions=[
                            {
                                "action_type": a.action_type,
                                "target": a.target,
                                "value": a.value,
                                "attribute": a.attribute,
                            }
                            for a in gen_item.actions
                        ],
                    )

                    if parse_result.success:
                        items_created += 1

            # Create default "Fist" item for new players
            fist_result = await self.item_parser.parse_item(
                setting_id=setting_id,
                name="Fist",
                description="Your bare fists. Not very effective, but always available.",
                slot="attack",
                rarity=1,
                actions=[
                    {
                        "action_type": "damage",
                        "target": "enemy",
                        "value": 8,
                        "attribute": None,
                    }
                ],
            )
            if fist_result.success:
                items_created += 1

            step.success = True
            step.message = f"Created {items_created} items"
            step.data = items_created
            return step

        except Exception as e:
            step.message = f"Item creation failed: {e!s}"
            return step

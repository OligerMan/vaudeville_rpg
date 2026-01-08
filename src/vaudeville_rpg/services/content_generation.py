"""Content generation service - orchestrates LLM-based content creation."""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.models.effects import Action, Condition, Effect
from ..db.models.enums import (
    ActionType,
    ConditionPhase,
    ConditionType,
    EffectCategory,
    ItemSlot,
    TargetType,
)
from ..db.models.items import Item
from ..db.models.settings import Setting
from ..llm import (
    EffectTemplateGenerator,
    GeneratedItem,
    ItemFactory,
    ItemTypeGenerator,
    LLMClient,
    Rarity,
    SettingGenerator,
    WorldRulesGenerator,
)


@dataclass
class GenerationResult:
    """Result of content generation."""

    success: bool
    message: str
    setting: Setting | None = None
    attributes_created: int = 0
    world_rules_created: int = 0
    items_created: int = 0


class ContentGenerationService:
    """Service for LLM-based content generation."""

    def __init__(self, session: AsyncSession, llm_client: LLMClient) -> None:
        self.session = session
        self.client = llm_client

        # Initialize generators
        self.setting_gen = SettingGenerator(llm_client)
        self.rules_gen = WorldRulesGenerator(llm_client)
        self.effects_gen = EffectTemplateGenerator(llm_client)
        self.types_gen = ItemTypeGenerator(llm_client)

        # Cache for generated content
        self._item_factory: ItemFactory | None = None

    async def generate_setting_content(
        self,
        setting: Setting,
        user_prompt: str,
    ) -> GenerationResult:
        """Generate all content for a setting from user prompt.

        Args:
            setting: Setting to populate
            user_prompt: User's setting description

        Returns:
            GenerationResult with statistics
        """
        try:
            # Step 1: Generate setting description and attributes
            generated = await self.setting_gen.generate(user_prompt)

            # Update setting with generated content
            setting.name = generated.broad_description[:100]  # Truncate for name
            setting.description = generated.broad_description
            setting.special_points_name = generated.special_points.display_name
            setting.special_points_regen = generated.special_points.regen_per_turn

            # Store attribute names for later
            attribute_names = [attr.name for attr in generated.attributes]

            # Step 2: Generate world rules for each attribute
            rules_created = 0
            for attr in generated.attributes:
                world_rules = await self.rules_gen.generate(
                    attribute_name=attr.name,
                    display_name=attr.display_name,
                    description=attr.description,
                    is_positive=attr.is_positive,
                )
                rules_created += await self._persist_world_rules(setting.id, world_rules)

            # Step 3: Generate effect templates
            templates = []
            existing_effects = []

            # Generate 2-3 templates for each slot type
            slot_counts = {"attack": 3, "defense": 3, "misc": 2}

            for slot_type, count in slot_counts.items():
                for i in range(count):
                    template = await self.effects_gen.generate(
                        setting_description=generated.broad_description,
                        attributes=attribute_names,
                        slot_type=slot_type,
                        existing_effects=existing_effects if existing_effects else None,
                    )
                    templates.append(template)
                    existing_effects.append({"name": template.name, "description": template.description})

            # Wrap templates in GeneratedEffectTemplates
            from ..llm.schemas import GeneratedEffectTemplates

            effect_templates = GeneratedEffectTemplates(templates=templates)

            # Step 4: Generate item types
            item_types = await self.types_gen.generate(
                setting_description=generated.broad_description,
            )

            # Step 5: Create item factory and generate items
            self._item_factory = ItemFactory(
                item_types=item_types,
                effect_templates=effect_templates,
            )

            # Generate starter items and some variety
            items_created = await self._generate_initial_items(setting.id)

            await self.session.flush()

            return GenerationResult(
                success=True,
                message="Content generated successfully",
                setting=setting,
                attributes_created=len(generated.attributes),
                world_rules_created=rules_created,
                items_created=items_created,
            )

        except Exception as e:
            return GenerationResult(
                success=False,
                message=f"Generation failed: {e!s}",
            )

    async def get_starter_items(self, setting_id: int) -> dict[ItemSlot, Item]:
        """Get starter items for a setting.

        Args:
            setting_id: Setting ID

        Returns:
            Dict mapping slot to starter item
        """
        result = {}
        for slot in [ItemSlot.ATTACK, ItemSlot.DEFENSE, ItemSlot.MISC]:
            stmt = (
                select(Item)
                .where(
                    Item.setting_id == setting_id,
                    Item.slot == slot,
                    Item.rarity == 1,
                )
                .limit(1)
            )
            items = await self.session.execute(stmt)
            item = items.scalar_one_or_none()
            if item:
                result[slot] = item
        return result

    async def get_random_reward_item(
        self,
        setting_id: int,
        min_rarity: int,
        max_rarity: int,
    ) -> Item | None:
        """Get a random item within rarity range for dungeon rewards.

        Args:
            setting_id: Setting ID
            min_rarity: Minimum rarity (1-5)
            max_rarity: Maximum rarity (1-5)

        Returns:
            Random item or None
        """
        import random

        stmt = select(Item).where(
            Item.setting_id == setting_id,
            Item.rarity >= min_rarity,
            Item.rarity <= max_rarity,
        )
        result = await self.session.execute(stmt)
        items = list(result.scalars().all())

        if not items:
            return None

        return random.choice(items)

    async def _persist_world_rules(self, setting_id: int, world_rules) -> int:
        """Persist world rules to database.

        Returns number of rules created.
        """
        count = 0
        for rule in world_rules.rules:
            # Create phase condition
            phase_condition = Condition(
                setting_id=setting_id,
                name=f"{rule.name}_phase",
                condition_type=ConditionType.PHASE,
                condition_data={"phase": rule.phase},
            )
            self.session.add(phase_condition)
            await self.session.flush()

            # Create has_stacks condition
            stacks_condition = Condition(
                setting_id=setting_id,
                name=f"{rule.name}_stacks",
                condition_type=ConditionType.HAS_STACKS,
                condition_data={
                    "attribute": rule.requires_attribute,
                    "min_count": rule.min_stacks,
                },
            )
            self.session.add(stacks_condition)
            await self.session.flush()

            # Create composite AND condition
            and_condition = Condition(
                setting_id=setting_id,
                name=f"{rule.name}_condition",
                condition_type=ConditionType.AND,
                condition_data={"condition_ids": [phase_condition.id, stacks_condition.id]},
            )
            self.session.add(and_condition)
            await self.session.flush()

            # Create action
            action_type = self._map_action_type(rule.action.action_type)
            action_data = {"value": rule.action.value}
            if rule.action.attribute:
                action_data["attribute"] = rule.action.attribute

            action = Action(
                setting_id=setting_id,
                name=f"{rule.name}_action",
                action_type=action_type,
                target=TargetType.SELF if rule.target == "self" else TargetType.ENEMY,
                action_data=action_data,
            )
            self.session.add(action)
            await self.session.flush()

            # Create effect
            effect = Effect(
                setting_id=setting_id,
                name=rule.name,
                description=rule.description,
                condition_id=and_condition.id,
                action_id=action.id,
                category=EffectCategory.WORLD_RULE,
            )
            self.session.add(effect)
            count += 1

        return count

    async def _generate_initial_items(self, setting_id: int) -> int:
        """Generate initial items for a setting.

        Creates:
        - 3 common items (one per slot) as starters
        - 3 uncommon items
        - 3 rare items

        Returns number of items created.
        """
        if not self._item_factory:
            return 0

        count = 0

        # Generate starter items (common, one per slot)
        for slot in ["attack", "defense", "misc"]:
            gen_item = self._item_factory.create_item(slot=slot, rarity=Rarity.COMMON)
            await self._persist_item(setting_id, gen_item)
            count += 1

        # Generate uncommon items
        for slot in ["attack", "defense", "misc"]:
            gen_item = self._item_factory.create_item(slot=slot, rarity=Rarity.UNCOMMON)
            await self._persist_item(setting_id, gen_item)
            count += 1

        # Generate rare items
        for slot in ["attack", "defense", "misc"]:
            gen_item = self._item_factory.create_item(slot=slot, rarity=Rarity.RARE)
            await self._persist_item(setting_id, gen_item)
            count += 1

        return count

    async def _persist_item(self, setting_id: int, gen_item: GeneratedItem) -> Item:
        """Persist a generated item to database."""
        slot = self._map_item_slot(gen_item.slot)

        item = Item(
            setting_id=setting_id,
            name=gen_item.name,
            description=gen_item.description,
            slot=slot,
            rarity=gen_item.rarity,
        )
        self.session.add(item)
        await self.session.flush()

        # Create actions and effects for each item action
        for i, gen_action in enumerate(gen_item.actions):
            # Create action
            action_type = self._map_action_type(gen_action.action_type)
            action_data = {"value": gen_action.value}
            if gen_action.attribute:
                action_data["attribute"] = gen_action.attribute

            target = TargetType.SELF if gen_action.target == "self" else TargetType.ENEMY

            action = Action(
                setting_id=setting_id,
                name=f"{item.name}_{i}_action".lower().replace(" ", "_"),
                action_type=action_type,
                target=target,
                action_data=action_data,
            )
            self.session.add(action)
            await self.session.flush()

            # Create condition based on item slot
            phase_map = {
                ItemSlot.ATTACK: ConditionPhase.PRE_ATTACK.value,
                ItemSlot.DEFENSE: ConditionPhase.PRE_DAMAGE.value,
                ItemSlot.MISC: ConditionPhase.PRE_MOVE.value,
            }
            phase = phase_map.get(slot, ConditionPhase.PRE_MOVE.value)

            condition = Condition(
                setting_id=setting_id,
                name=f"{item.name}_{i}_condition".lower().replace(" ", "_"),
                condition_type=ConditionType.PHASE,
                condition_data={"phase": phase},
            )
            self.session.add(condition)
            await self.session.flush()

            # Create effect with item_id set directly
            effect = Effect(
                setting_id=setting_id,
                name=f"{item.name}_{i}_effect".lower().replace(" ", "_"),
                description=f"{gen_action.action_type} effect",
                condition_id=condition.id,
                action_id=action.id,
                target=target,
                category=EffectCategory.ITEM_EFFECT,
                item_id=item.id,
            )
            self.session.add(effect)
            await self.session.flush()

        return item

    def _map_action_type(self, action_type: str) -> ActionType:
        """Map string action type to enum."""
        mapping = {
            "damage": ActionType.DAMAGE,
            "attack": ActionType.ATTACK,
            "heal": ActionType.HEAL,
            "add_stacks": ActionType.ADD_STACKS,
            "remove_stacks": ActionType.REMOVE_STACKS,
            "reduce_incoming_damage": ActionType.REDUCE_INCOMING_DAMAGE,
        }
        return mapping.get(action_type, ActionType.DAMAGE)

    def _map_item_slot(self, slot: str) -> ItemSlot:
        """Map string slot to enum."""
        mapping = {
            "attack": ItemSlot.ATTACK,
            "defense": ItemSlot.DEFENSE,
            "misc": ItemSlot.MISC,
        }
        return mapping.get(slot, ItemSlot.MISC)

    def _map_condition_phase(self, phase: str) -> ConditionPhase:
        """Map string phase to enum."""
        mapping = {
            "pre_move": ConditionPhase.PRE_MOVE,
            "post_move": ConditionPhase.POST_MOVE,
            "pre_attack": ConditionPhase.PRE_ATTACK,
            "post_attack": ConditionPhase.POST_ATTACK,
            "pre_damage": ConditionPhase.PRE_DAMAGE,
            "post_damage": ConditionPhase.POST_DAMAGE,
        }
        return mapping.get(phase, ConditionPhase.PRE_MOVE)

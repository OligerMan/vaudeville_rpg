# VaudevilleRPG Game Mechanics Wiki

## Overview

VaudevilleRPG is a Telegram bot game based on turn-based duels between players (PvP) and between players and computer enemies (PvE/Dungeons).

---

## Duel System

### Duel Model

```
Duel {
  id: int
  setting_id: int              # Which setting this duel is in
  status: DuelStatus           # PENDING, IN_PROGRESS, COMPLETED, CANCELLED
  winner_participant_id: int?  # Which participant won (null if not finished)
  current_turn: int            # Current turn number (starts at 1)
}
```

### DuelParticipant Model

```
DuelParticipant {
  id: int
  duel_id: int                 # Which duel
  player_id: int               # Which player (can be bot)
  turn_order: int              # 1 or 2 (for effect ordering)
  is_ready: bool               # Has submitted action for current turn
}
```

### DuelAction Model

Actions are **persisted to database** to survive bot restarts.

```
DuelAction {
  id: int
  duel_id: int
  participant_id: int
  turn_number: int             # Which turn this action is for
  action_type: DuelActionType  # ATTACK, DEFENSE, MISC, SKIP
  item_id: int?                # Which item was used (null for SKIP)
}
```

### Duel Status Flow

```
PENDING → IN_PROGRESS → COMPLETED
    ↓         ↓
    └─────────┴──→ CANCELLED
```

| Status | Description |
|--------|-------------|
| `PENDING` | Duel created, waiting for acceptance (PvP) or start (PvE) |
| `IN_PROGRESS` | Both players joined, turns being processed |
| `COMPLETED` | One player won (HP reached 0) |
| `CANCELLED` | Duel was cancelled before completion |

### Turn Structure

Duels are **turn-based** with **simultaneous action selection**:

1. **Action Selection Phase**
   - Both players choose their actions **hidden** from each other
   - Each player submits one action (ATTACK, DEFENSE, MISC, or SKIP)
   - Player marked as `is_ready = true` after submitting

2. **Resolution Phase** (when both ready)
   - PRE_MOVE effects trigger
   - Both actions revealed and applied **simultaneously**
   - PRE_ATTACK → ATTACK → POST_ATTACK effects
   - PRE_DAMAGE → DAMAGE → POST_DAMAGE effects
   - POST_MOVE effects trigger
   - Check win condition (any player HP = 0)
   - Advance to next turn or end duel

### Action Types

| Action | Description |
|--------|-------------|
| `ATTACK` | Use attack item ability |
| `DEFENSE` | Use defense item ability |
| `MISC` | Use misc item ability |
| `SKIP` | Do nothing this turn |

### Combat Resolution

- **Attack** = player-initiated action that can crit/miss
- **Damage** = raw HP reduction (used by effects like poison, bypasses crit/miss)
- Win condition: Enemy HP reaches 0

### PvE Enemies (Bots)

Bot enemies reuse the **Player model** with `is_bot = true`:
- Same combat logic as PvP
- Bot AI selects actions automatically
- Can have equipped items like regular players

---

## Settings (Per-Chat Configuration)

Each Telegram chat can have its own **Setting** that defines:
- Attribute names and behaviors (what "mana" is called, how it regenerates)
- World rules (how poison works, etc.)
- Available attributes for item generation

Settings are stored in the database and fully dynamic.

---

## Attribute System

### Attribute Categories

#### 1. Core Attributes (Always Present)
| Attribute | Description |
|-----------|-------------|
| **HP** | Health Points. 0 HP = death. Universal across all settings. |
| **Special Points** | Flexible resource (Mana/Energy/etc.). Interpretation varies by setting. |

#### 2. Generatable Attributes (Setting-Specific)
- Configurable number per setting (default: 3)
- Stack-based with optional limits
- Examples in Fantasy setting: Armor, Might, Poison

### Attribute Properties
| Property | Description |
|----------|-------------|
| `name` | Display name (e.g., "Armor", "Poison") |
| `max_stacks` | Maximum stack limit (null = unlimited) |
| `setting_id` | Which setting this attribute belongs to |

### Attribute Interactions (Actions)
| Action | Description |
|--------|-------------|
| `DAMAGE` | Reduce HP (bypasses crit/miss) |
| `ATTACK` | Player-initiated damage (can crit/miss) |
| `HEAL` | Restore HP |
| `ADD_STACKS` | Add stacks to an attribute |
| `REMOVE_STACKS` | Remove stacks from an attribute |
| `MODIFY_MAX` | Increase/decrease attribute's max stacks |
| `MODIFY_CURRENT_MAX` | Increase/decrease HP/Special max for current combat |
| `SPEND` | Price/cost - spend HP or Special Points |

### Example: Fantasy Setting Attributes

| Attribute | Type | Behavior |
|-----------|------|----------|
| HP | Core | Damage/heal target. 0 = death |
| Mana | Special | Spent on spells, regenerates each turn |
| Armor | Generatable | Each stack = flat damage reduction, loses 1 stack per damage instance |
| Might | Generatable | Each stack = +damage/+crit, loses stacks on attack |
| Poison | Generatable | Deals 1 damage per stack pre-move, loses 1 stack post-move |

---

## Effect System

Effects are the core building blocks for all game mechanics. Both item abilities and world rules are defined as Effects.

### Effect Structure
```
Effect {
  name: string           # Unique identifier, used for ordering
  condition: Condition   # When this effect triggers
  target: Target         # Who is affected (SELF or ENEMY)
  category: Category     # ITEM_EFFECT or WORLD_RULE
  action: Action         # What happens
}
```

### Conditions

Conditions define **when** an effect triggers.

#### Condition Phases
| Phase | Description |
|-------|-------------|
| `PRE_ATTACK` | Before attack is resolved |
| `POST_ATTACK` | After attack is resolved |
| `PRE_DAMAGE` | Before damage is applied |
| `POST_DAMAGE` | After damage is applied |
| `PRE_MOVE` | Before turn actions resolve |
| `POST_MOVE` | After turn actions resolve |

#### Condition Composition
Conditions can be combined using AND/OR logic:
```
and([condition1, condition2, ...])  # All must be true
or([condition1, condition2, ...])   # At least one must be true
```

#### Stack Conditions
Check if target has stacks of an attribute:
```
has_stacks(attribute_name, min_count)  # True if stacks >= min_count
```

### Targets
| Target | Description |
|--------|-------------|
| `SELF` | Effect applies to the player who owns the item/triggered the effect |
| `ENEMY` | Effect applies to the opponent |

### Categories
| Category | Description |
|----------|-------------|
| `ITEM_EFFECT` | Effect comes from an equipped item |
| `WORLD_RULE` | Effect is a setting-level rule (e.g., poison tick) |

### Effect Ordering
When multiple effects trigger at the same phase, they execute in **alphabetical order by effect name**.

### Values
Currently: flat integers
Future: formula expressions (e.g., `base_damage * 1.5`)

---

## Effect Examples

### Example 1: Poison Sword (Item Effect)
A sword that applies poison on attack.

```
Effect {
  name: "poison_sword_apply"
  condition: phase(PRE_ATTACK)
  target: ENEMY
  category: ITEM_EFFECT
  action: add_stacks("poison", 3)
}
```

### Example 2: Poison World Rules
Setting-level rules that make poison work.

**Poison Damage (deals damage each turn):**
```
Effect {
  name: "poison_damage"
  condition: and([phase(PRE_MOVE), has_stacks("poison", 1)])
  target: SELF  # Applied to whoever has the poison
  category: WORLD_RULE
  action: damage(1)  # Per stack? Or flat? (configurable)
}
```

**Poison Decay (loses stacks each turn):**
```
Effect {
  name: "poison_decay"
  condition: and([phase(POST_MOVE), has_stacks("poison", 1)])
  target: SELF
  category: WORLD_RULE
  action: remove_stacks("poison", 1)
}
```

### Example 3: Armor World Rules

**Armor Damage Reduction:**
```
Effect {
  name: "armor_reduction"
  condition: and([phase(PRE_DAMAGE), has_stacks("armor", 1)])
  target: SELF
  category: WORLD_RULE
  action: reduce_incoming_damage(1)  # Per stack
}
```

**Armor Decay on Hit:**
```
Effect {
  name: "armor_decay"
  condition: and([phase(POST_DAMAGE), has_stacks("armor", 1)])
  target: SELF
  category: WORLD_RULE
  action: remove_stacks("armor", 1)
}
```

---

## Items

### Item Structure
Items are containers for effects. Each item can have multiple effects (passive and active).

```
Item {
  name: string
  description: string
  slot: ATTACK | DEFENSE | MISC
  rarity: 1-5
  effects: Effect[]      # All effects this item provides
  setting_id: int        # Which setting this item belongs to
}
```

### Item Slots
| Slot | Typical Use |
|------|-------------|
| `ATTACK` | Offensive abilities (sword swing, fireball) |
| `DEFENSE` | Defensive abilities (block, evade) |
| `MISC` | Utility abilities (heal, counterspell) |

### Procedural Generation
Items are procedurally generated by:
1. Selecting a base template
2. Rolling for effects based on rarity
3. Combining compatible effects

---

## Complex Actions and Validation

### Recursion Prevention
Complex actions (composed of multiple basic actions) **cannot reference other complex actions**. This is validated at definition time to prevent infinite loops.

### Action Templates
Once a complex action pattern is validated and saved, it can be used as a template for procedural generation.

---

## Player System

### Player Model

Players are **per-chat** - the same Telegram user has separate player profiles in different chats/settings.

```
Player {
  telegram_user_id: BigInteger   # Telegram user ID
  setting_id: int                # Which chat/setting this player belongs to
  display_name: string           # Display name (from Telegram)
  max_hp: int                    # Maximum health points
  max_special_points: int        # Maximum special points (mana/energy)
  rating: int                    # PvP rating (default: 1000)
  attack_item_id: int?           # Equipped attack item (nullable)
  defense_item_id: int?          # Equipped defense item (nullable)
  misc_item_id: int?             # Equipped misc item (nullable)
}
```

### Equipped Items

Players have exactly **3 item slots** (no inventory):
- **Attack slot** - One attack item
- **Defense slot** - One defense item
- **Misc slot** - One misc item

When a player receives a new item, it **replaces** the existing item in that slot.

### Combat State

Combat state is **persisted to database** to survive bot restarts.

```
PlayerCombatState {
  player_id: int                 # Which player
  duel_id: int                   # Which duel this state is for
  current_hp: int                # Current health
  current_special_points: int    # Current special points
  attribute_stacks: JSONB        # {"poison": 3, "armor": 2, ...}
}
```

### Player Creation

Players are created automatically when a Telegram user first interacts with the bot in a chat:
1. Check if player exists for (telegram_user_id, setting_id)
2. If not, create with default stats from setting
3. Player starts with no items equipped

### Default Stats

| Stat | Default Value |
|------|---------------|
| `max_hp` | 100 |
| `max_special_points` | 50 |
| `rating` | 1000 |

---

## Dungeons (PvE)

### Overview
A dungeon is a **series of consecutive duels** between one player and computer-controlled enemies. The player progresses through stages, fighting a different enemy at each stage, until they either complete all stages or are defeated.

### Dungeon Model

```
Dungeon {
  id: int
  player_id: int              # Player running this dungeon
  setting_id: int             # Setting this dungeon is in
  name: string                # Dungeon name (based on difficulty)
  difficulty: DungeonDifficulty
  total_stages: int           # Number of enemies to defeat
  current_stage: int          # Current progress (1-indexed)
  status: DungeonStatus       # IN_PROGRESS, COMPLETED, FAILED, ABANDONED
  current_duel_id: int?       # Active duel (if any)
}
```

### DungeonEnemy Model

```
DungeonEnemy {
  id: int
  dungeon_id: int             # Which dungeon
  stage: int                  # Which stage (1-indexed)
  enemy_player_id: int        # Bot player for this stage
  defeated: bool              # Has this enemy been beaten?
}
```

### Difficulty Levels

| Difficulty | Stages | Base HP | Base SP | HP/Stage | SP/Stage |
|------------|--------|---------|---------|----------|----------|
| EASY | 2 | 60 | 30 | +10 | +5 |
| NORMAL | 3 | 80 | 40 | +15 | +5 |
| HARD | 4 | 100 | 50 | +20 | +10 |
| NIGHTMARE | 5 | 120 | 60 | +30 | +15 |

### Dungeon Names by Difficulty

| Difficulty | Name |
|------------|------|
| EASY | Goblin Cave |
| NORMAL | Dark Dungeon |
| HARD | Dragon's Lair |
| NIGHTMARE | Abyss of Torment |

### Enemy Generation

Enemies are bot players (`is_bot = true`) with:
- Stats scaled by difficulty and stage number
- Random names from pool (e.g., "Goblin", "Skeleton", "Orc")
- Higher stages (3+) get prefixes (e.g., "Cursed Goblin", "Ancient Demon")

### Dungeon Status Flow

```
IN_PROGRESS → COMPLETED (all stages cleared)
      ↓
      └──→ FAILED (player lost a duel)
      └──→ ABANDONED (player quit)
```

| Status | Description |
|--------|-------------|
| `IN_PROGRESS` | Player is actively in the dungeon |
| `COMPLETED` | All stages cleared successfully |
| `FAILED` | Player lost to an enemy |
| `ABANDONED` | Player chose to leave |

### Dungeon Flow

```
/dungeon
    ↓
Select Difficulty
    ↓
[Dungeon Created + Stage 1 Duel Started]
    ↓
Combat (player vs bot enemy)
    ↓
┌───┴───┐
↓       ↓
WIN    LOSE
↓       ↓
More   FAILED
stages?
↓   ↓
Yes No
↓   ↓
Next COMPLETED
Stage
```

### Bot Commands

| Command | Description |
|---------|-------------|
| `/dungeon` | Start a new dungeon or check current progress |

### Inline Buttons

**Difficulty Selection:**
- Easy (2 stages)
- Normal (3 stages)
- Hard (4 stages)
- Nightmare (5 stages)

**Combat Actions:**
- ⚔️ Attack - Use attack item
- 🛡️ Defense - Use defense item
- ✨ Misc - Use misc item
- ⏭️ Skip - Do nothing
- 🚪 Abandon Dungeon - Leave dungeon (counts as loss)

### Bot AI

During dungeon combat, bot enemies automatically respond with randomly chosen actions:
- Higher weight for Attack actions
- Responds immediately after player action
- No delay or thinking time

### Validation Rules

1. **Starting a Dungeon:**
   - Player cannot start if already in an active dungeon
   - Must complete, fail, or abandon current dungeon first

2. **During Combat:**
   - Only the dungeon owner can submit actions
   - One action per turn
   - Cannot leave mid-turn (only via abandon button)

3. **Abandoning:**
   - Can abandon at any time
   - Current duel is cancelled
   - No rewards given

---

## PvP System

### Challenge Flow

```
/challenge (reply to user)
        ↓
   [PENDING Duel Created]
        ↓
    ┌───┴───┐
    ↓       ↓
 Accept   Decline
    ↓       ↓
 [START]  [CANCEL]
    ↓
 Action Selection (both players)
    ↓
 Turn Resolution
    ↓
 ┌──┴──┐
 ↓     ↓
Win?  Next Turn
 ↓     ↓
END   Loop back
```

### Bot Commands

| Command | Description |
|---------|-------------|
| `/challenge` | Reply to a user's message to challenge them |
| `/help` | Show available commands |

### Inline Buttons

**Challenge Response:**
- ⚔️ Accept - Start the duel
- ❌ Decline - Cancel the duel

**Action Selection:**
- ⚔️ Attack - Use attack item ability
- 🛡️ Defense - Use defense item ability
- ✨ Misc - Use misc item ability
- ⏭️ Skip - Do nothing this turn

### Duel State Display

```
⚔️ Duel - Turn 3

✅ Player1
   ❤️ 75 HP | 💙 30 SP
   📊 armor: 2

⏳ Player2
   ❤️ 60 HP | 💙 45 SP
   📊 poison: 3

📜 Turn 2 Results:
• Dealt 15 damage
• Added 3 poison stacks
```

### Validation Rules

1. **Challenge Validation:**
   - Cannot challenge yourself
   - Cannot challenge bots
   - Cannot challenge if either player is in an active duel

2. **Action Validation:**
   - Only duel participants can submit actions
   - Each player can only submit once per turn
   - Actions submitted are final

### Rating System

Players have a **rating** based on PvP duel results, using the **Elo rating system**.

#### Default Rating
- All players start with **1000** rating
- Rating floor is **0** (cannot go negative)

#### Elo Formula

Expected score for player A against player B:
```
E_A = 1 / (1 + 10^((R_B - R_A) / 400))
```

Rating change after match:
```
ΔR = K × (S - E)
```
Where:
- `K` = K-factor (rating volatility)
- `S` = Actual score (1 for win, 0 for loss)
- `E` = Expected score

#### K-Factor Values

| Condition | K-Factor |
|-----------|----------|
| New players (<10 games) | 40 |
| Standard players | 32 |
| High-rated players (2000+) | 16 |

#### Rating Updates

- Ratings update **immediately** after PvP duel completion
- PvE duels (dungeons) do **not** affect rating
- Both winner and loser ratings update in single transaction

#### Bot Commands

| Command | Description |
|---------|-------------|
| `/profile` | Show your stats, rating, and rank |
| `/leaderboard` | Show top 10 players by rating |

#### Profile Display

```
PlayerName

Rating: 1234 (#5)
HP: 100
SP: 50

Equipped Items:
  Attack: Sword of Fire
  Defense: Iron Shield
  Misc: Healing Potion
```

#### Leaderboard Display

```
Leaderboard

1. 🥇 TopPlayer - 1523
2. 🥈 SecondBest - 1456
3. 🥉 ThirdPlace - 1398
4. FourthPlace - 1234
...
```

---

## Content Generation System

The game uses **LLM-driven procedural generation** to create unique settings, attributes, world rules, and items from simple user descriptions.

### Generation Pipeline

```
User Input (simple description)
        ↓
Step 1: Setting Generator
        ↓
    [Broad Description + Attributes]
        ↓
Step 2: World Rules Generator
        ↓
    [Formal Rules for Each Attribute]
        ↓
Step 3: Effect Template Generator
        ↓
    [Item Effect Templates with Rarity Scaling]
        ↓
Step 4: Item Type Generator
        ↓
    [Setting-Specific Item Types]
        ↓
Step 5: Item Factory
        ↓
    [Actual Items in Database]
```

### Step 1: Setting Generation

**Input:** Simple user description (e.g., "I want to live in world of might and magic")

**Output:**
- **Broad Description:** Expanded world lore (2-3 paragraphs)
- **Special Points:** Name + description for the mana/energy resource
- **Attributes:** 3-5 stack-based combat attributes (buffs/debuffs)

```
Example Output:
{
  "broad_description": "This is a world where ancient magic flows through...",
  "special_points": {
    "name": "mana",
    "display_name": "Mana",
    "description": "Magical energy that powers spells and abilities"
  },
  "attributes": [
    {"name": "poison", "display_name": "Poison", "is_positive": false},
    {"name": "holy_defense", "display_name": "Holy Defense", "is_positive": true}
  ]
}
```

### Step 2: World Rules Generation

Converts attribute descriptions into **formal game rules**.

**Input:** Attribute description (e.g., "poison - damages every move and removes stacks")

**Output:** World rule definitions with:
- `phase`: When to trigger (pre_move, post_move, pre_damage, etc.)
- `requires_attribute`: Which attribute must have stacks
- `action`: What happens (damage, heal, add_stacks, remove_stacks)

```
Example: Poison Attribute → 2 Rules

Rule 1 - Poison Tick:
  phase: pre_move
  requires_attribute: poison
  action: damage(5)
  per_stack: true

Rule 2 - Poison Decay:
  phase: post_move
  requires_attribute: poison
  action: remove_stacks(poison, 1)
```

### Step 3: Effect Template Generation

Creates **item effect templates** that can be applied to items.

**Output per template:**
- `prefix`: Naming prefix (e.g., "Poisonous", "Holy")
- `suffix`: Optional naming suffix (e.g., "of Flames")
- `slot_type`: Which item slot (attack, defense, misc)
- `actions`: Effects with **rarity-scaled values**

```
Example: Poison Strike Template
{
  "name": "poison_strike",
  "prefix": "Poisonous",
  "slot_type": "attack",
  "actions": [{
    "action_type": "add_stacks",
    "attribute": "poison",
    "values": {
      "common": 1,
      "uncommon": 2,
      "rare": 3,
      "epic": 4,
      "legendary": 5
    }
  }]
}
```

### Step 4: Item Type Generation

Creates **setting-specific item types** for each slot.

**Output:**
- Attack types: Swords, Staves, Daggers, etc.
- Defense types: Shields, Armor, Cloaks, etc.
- Misc types: Potions, Scrolls, Amulets, etc.

Each type includes **base values** scaled by rarity.

### Step 5: Item Factory

Combines components to create actual items:

```
Rarity + Effect Template + Item Type = Complete Item

Example:
Uncommon + Poisonous + Sword = "Uncommon Poisonous Sword"
  → attack(15 damage)
  → add_stacks(poison, 2)
```

### Item Rarity System

| Rarity | Value | Base Damage | Effect Scaling |
|--------|-------|-------------|----------------|
| Common | 1 | 10 | 1x |
| Uncommon | 2 | 15 | 1.5x |
| Rare | 3 | 20 | 2x |
| Epic | 4 | 25 | 2.5x |
| Legendary | 5 | 30 | 3x |

### Item Naming Convention

Items are named using the pattern:
```
[Rarity] [Effect Prefix] [Item Type] [Effect Suffix]?
```

Examples:
- "Common Poisonous Sword"
- "Legendary Holy Shield of Protection"
- "Rare Regenerating Potion"

### LLM Configuration

The system supports multiple LLM backends:

| Setting | Description |
|---------|-------------|
| `LLM_PROVIDER` | "anthropic" or "openai" |
| `LLM_API_KEY` | API key for the provider |
| `LLM_BASE_URL` | Custom endpoint (for vLLM/local inference) |
| `LLM_MODEL` | Model to use (default: claude-sonnet-4-20250514) |

**Local Inference:** Set `LLM_PROVIDER=openai` and `LLM_BASE_URL` to your vLLM endpoint.

### Initial Content Generation

When a setting is created with content generation:
1. **9 items** are created (3 per rarity: common, uncommon, rare)
2. **World rules** are persisted for all generated attributes
3. **New players** receive common starter items automatically

### Dungeon Rewards

Completed dungeons award items based on difficulty:

| Difficulty | Rarity Range |
|------------|--------------|
| Easy | Common only |
| Normal | Common - Uncommon |
| Hard | Uncommon - Rare |
| Nightmare | Uncommon - Rare |

---

## Setting Factory

The `SettingFactory` is the main entry point for creating complete settings from user input. It orchestrates the full pipeline with validation and retry logic.

### Usage

```python
from vaudeville_rpg.llm import SettingFactory, get_llm_client

# Initialize factory
factory = SettingFactory(session=db_session)

# Create complete setting from user prompt
result = await factory.create_setting(
    telegram_chat_id=12345,
    user_prompt="I want a world of might and magic",
    validate=True,
    retry_on_validation_fail=True,
    max_retries=2,
)

if result.success:
    print(f"Setting created: {result.setting.name}")
    print(f"Attributes: {result.attributes_created}")
    print(f"World rules: {result.world_rules_created}")
    print(f"Items: {result.items_created}")
else:
    print(f"Failed: {result.message}")
```

### Pipeline Result

The factory returns a `PipelineResult` with:

| Field | Description |
|-------|-------------|
| `success` | Whether the pipeline completed successfully |
| `message` | Status or error message |
| `setting` | Created Setting database object |
| `steps` | List of PipelineStep results |
| `attributes_created` | Number of attributes generated |
| `world_rules_created` | Number of world rules created |
| `effect_templates_created` | Number of effect templates |
| `item_types_created` | Number of item types |
| `items_created` | Number of items persisted |

### Pipeline Steps

Each step is tracked with:
- `name`: Step identifier
- `success`: Whether the step succeeded
- `message`: Status or error message
- `data`: Generated data (if successful)
- `validation_errors`: List of validation errors (if any)

---

## Validation Layer

All LLM outputs are validated before being parsed into database models.

### Validators

| Validator | Purpose |
|-----------|---------|
| `SettingValidator` | Validates setting description and attributes |
| `WorldRulesValidator` | Validates world rule definitions |
| `EffectTemplateValidator` | Validates effect templates |
| `ItemTypeValidator` | Validates item type definitions |

### Validation Checks

**Setting Validation:**
- Broad description minimum 50 characters
- Special points name and display name required
- 2-10 attributes required
- No duplicate attribute names

**World Rules Validation:**
- Valid phase (pre_move, post_move, etc.)
- Valid action type (damage, heal, add_stacks, etc.)
- Valid target (self, enemy)
- Attribute references exist
- No duplicate rule names

**Effect Template Validation:**
- Valid slot type (attack, defense, misc)
- Prefix required
- Legendary values >= common values
- Attribute references exist for stack operations

**Item Type Validation:**
- Required base values for each slot type
- Correct slot assignment

### Cross-Reference Validation

The `validate_all` function validates all content together, ensuring:
- Effect templates reference valid attributes
- World rules reference valid attributes
- Consistent naming across all content

---

## Parser Layer

Parsers convert validated LLM outputs into database models.

### WorldRulesParser

Converts world rule definitions into:
- `Condition` records (phase + has_stacks + AND composite)
- `Action` records
- `Effect` records (category: WORLD_RULE)

### ItemParser

Converts item definitions into:
- `Item` records
- `Condition` records (based on item slot)
- `Action` records
- `Effect` records (category: ITEM_EFFECT, linked to item)

### Item Slot to Phase Mapping

| Slot | Trigger Phase |
|------|---------------|
| Attack | PRE_ATTACK |
| Defense | PRE_DAMAGE |
| Misc | PRE_MOVE |

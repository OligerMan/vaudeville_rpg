# VaudevilleRPG Game Mechanics Wiki

## Overview

VaudevilleRPG is a Telegram bot game based on turn-based duels between players (PvP) and between players and computer enemies (PvE/Dungeons).

---

## Duel System

### Turn Structure
- Duels are **turn-based** with **simultaneous action selection**
- Each turn:
  1. Both players choose their actions **hidden** from each other
  2. Once both players have chosen, actions are **revealed**
  3. Both actions are **applied simultaneously**

### Action Types
Players can use one of their three item abilities per turn:
- **Attack ability** - from attack item (e.g., sword swing, fire blast)
- **Defense ability** - from defense item (e.g., shield block, evade)
- **Misc ability** - from misc item (e.g., heal, counterspell)

### Combat Resolution
- **Attack** = player-initiated action that can crit/miss
- **Damage** = raw HP reduction (used by effects like poison, bypasses crit/miss)
- Win condition: Enemy HP reaches 0

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

### Structure
- A dungeon is a **series of duels** between one player and computer enemies
- Player fights through sequential encounters
- Ends with a **reward** upon completion

### Dungeon Properties
TODO: Define difficulty levels, enemy scaling, reward tiers

---

## PvP System

### Challenge System
- PvP duels are initiated via **direct challenges**
- One player challenges another
- Challenged player accepts or declines

### Rating System
- Players have a **rating** based on duel results
- **Leaderboard** displays player rankings

TODO: Define rating algorithm (Elo, Glicko, custom)

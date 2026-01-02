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
TODO: Define damage calculation, ability interactions, win conditions

---

## Items

### Item Slots
Each player has exactly **3 item slots**:
1. **Attack Item** - provides attack buffs and one active attack ability
2. **Defense Item** - provides defense buffs and one active defense ability
3. **Misc Item** - provides a special ability

### Item Properties
- **Buffs** - passive stat modifications (attack items and defense items can have multiple)
- **Active Ability** - one ability per item that can be used during duels
- **Rarity** - determines item power level (1=Common, 2=Uncommon, 3=Rare, 4=Epic, 5=Legendary)

### Item Acquisition
- **Primary**: Dungeon completion rewards
- **Future considerations**: Shop, crafting, trading (not in initial scope)

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

---

## Player Stats

TODO: Define base stats, how buffs modify them, health system

---

## Abilities Reference

### Attack Abilities
Attack abilities come from attack items and deal damage to the enemy.

| Effect Type | Description |
|-------------|-------------|
| `PHYSICAL_DAMAGE` | Direct physical damage (reduced by armor) |
| `MAGICAL_DAMAGE` | Direct magical damage (ignores armor) |
| `BLEED` | Applies damage over time effect |

### Defense Abilities
Defense abilities come from defense items and reduce or prevent damage.

| Effect Type | Description |
|-------------|-------------|
| `BLOCK` | Reduces incoming damage for the turn |
| `EVADE` | Chance to completely avoid damage |
| `REFLECT` | Returns a portion of damage to the attacker |

### Misc Abilities
Misc abilities come from misc items and provide utility effects.

| Effect Type | Description |
|-------------|-------------|
| `HEAL` | Restore health points |
| `COUNTERSPELL` | Cancel the enemy's ability for the turn |
| `BUFF_SELF` | Apply a temporary buff to self |
| `DEBUFF_ENEMY` | Apply a temporary debuff to enemy |

---

## Buff Types

### Offensive Buffs
| Buff Type | Description |
|-----------|-------------|
| `DAMAGE` | Flat bonus to damage dealt |
| `CRIT_CHANCE` | Percentage chance to deal critical damage |
| `ARMOR_PENETRATION` | Ignores a portion of enemy armor |

### Defensive Buffs
| Buff Type | Description |
|-----------|-------------|
| `ARMOR` | Flat damage reduction from incoming attacks |
| `MAX_HEALTH` | Bonus to maximum health points |
| `EVASION` | Percentage chance to dodge attacks entirely |

### Utility Buffs
| Buff Type | Description |
|-----------|-------------|
| `HEALING_POWER` | Bonus effectiveness to healing effects |
| `ABILITY_POWER` | General bonus to ability effectiveness |

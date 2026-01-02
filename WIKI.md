# RandomRPG Game Mechanics Wiki

## Overview

RandomRPG is a Telegram bot game based on turn-based duels between players (PvP) and between players and computer enemies (PvE/Dungeons).

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
TODO: List all attack abilities with effects

### Defense Abilities
TODO: List all defense abilities with effects

### Misc Abilities
TODO: List all misc abilities with effects

---

## Buff Types

TODO: Define all buff types and their effects

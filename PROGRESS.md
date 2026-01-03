# VaudevilleRPG Development Progress

This file tracks development progress to restore context between sessions.

---

## Current State

**Branch:** `feature/rating-system` (ready to merge)
**Last Updated:** 2026-01-03
**Last Commit:** `a7356f7` - feat: Document rating system in WIKI.md

### Completed Phases

| Phase | Status | Description |
|-------|--------|-------------|
| Phase 1: Foundation | Done | Python setup, PostgreSQL, Telegram bot |
| Phase 2: Core Game Systems | Done | Effect, Item, Player, Duel engine |
| Phase 3: Game Modes | Done | PvP duels, Dungeon system |
| Phase 4: Meta Systems | Done | Rating system, Leaderboard |

### Current Phase

**Phase 5: Content & Polish** (Not Started)
- [ ] Initial item/ability content population
- [ ] Balance tuning
- [ ] Telegram UI/UX improvements

---

## Recent Session Summary

### Session: 2026-01-03 (Part 4)

**Completed:** Rating System and Leaderboard

#### What Was Done
1. Created `feature/rating-system` branch
2. Added Elo rating calculator (`src/vaudeville_rpg/utils/rating.py`):
   - Expected score calculation
   - Rating change calculation
   - Dynamic K-factor based on rating/experience

3. Integrated rating updates in DuelEngine:
   - Updates ratings on PvP duel completion
   - Skips rating changes for PvE (bot involved)

4. Added bot commands:
   - `/profile` - shows player stats, rating, rank, equipped items
   - `/leaderboard` - shows top 10 players by rating
   - Updated `/help` with all commands

5. Updated WIKI.md with rating system documentation

#### Key Files Added/Modified
- `src/vaudeville_rpg/utils/__init__.py` (new)
- `src/vaudeville_rpg/utils/rating.py` (new)
- `src/vaudeville_rpg/engine/duel.py` (rating integration)
- `src/vaudeville_rpg/bot/handlers/common.py` (profile/leaderboard)

---

### Session: 2026-01-03 (Part 3)

**Completed:** Dungeon System Implementation

#### What Was Done
1. Created `feature/dungeon-system` branch
2. Added Dungeon models (`src/vaudeville_rpg/db/models/dungeons.py`):
   - `Dungeon`: tracks dungeon runs (player, difficulty, stage, status)
   - `DungeonEnemy`: links stages to bot enemies
   - Added `DungeonDifficulty` and `DungeonStatus` enums

3. Created Alembic migration (`005_add_dungeon_system_tables.py`)

4. Added services layer:
   - `EnemyGenerator`: creates bot players with difficulty-scaled stats
   - `DungeonService`: start_dungeon, on_duel_completed, abandon_dungeon

5. Added bot handlers (`src/vaudeville_rpg/bot/handlers/dungeons.py`):
   - `/dungeon` command - start new or check current
   - Difficulty selection (Easy/Normal/Hard/Nightmare)
   - Combat actions with abandon option
   - Bot AI auto-responds to player actions

6. Updated WIKI.md with comprehensive dungeon documentation

#### Key Files Added
- `src/vaudeville_rpg/db/models/dungeons.py`
- `src/vaudeville_rpg/services/enemies.py`
- `src/vaudeville_rpg/services/dungeons.py`
- `src/vaudeville_rpg/bot/handlers/dungeons.py`
- `alembic/versions/005_add_dungeon_system_tables.py`

---

### Session: 2026-01-03 (Part 2)

**Completed:** PvP Duel Flow Implementation

#### What Was Done
1. Created `feature/pvp-duel-flow` branch
2. Added service layer (`src/vaudeville_rpg/services/`):
   - `PlayerService`: get_or_create_player, get_or_create_setting
   - `DuelService`: create_challenge, accept/decline, submit_action

3. Added bot handlers (`src/vaudeville_rpg/bot/handlers/duels.py`):
   - `/challenge` command (reply to user)
   - Accept/Decline inline buttons
   - Action selection (Attack/Defense/Misc/Skip)
   - Duel state display with HP, SP, stacks
   - Turn result formatting

4. Updated WIKI.md with PvP flow documentation

#### Key Files Added
- `src/vaudeville_rpg/services/__init__.py`
- `src/vaudeville_rpg/services/players.py`
- `src/vaudeville_rpg/services/duels.py`
- `src/vaudeville_rpg/bot/handlers/duels.py`

---

### Session: 2026-01-03 (Part 1)

**Completed:** Duel Engine Implementation

#### What Was Done
1. Merged `feature/duel-engine` branch into master (14 commits)
2. Created full duel engine module (`src/vaudeville_rpg/engine/`):
   - `types.py` - CombatState, DuelContext, TurnResult data classes
   - `conditions.py` - ConditionEvaluator (PHASE, HAS_STACKS, AND, OR)
   - `actions.py` - ActionExecutor (damage, heal, stacks, etc.)
   - `effects.py` - EffectProcessor (phase-based execution)
   - `turn.py` - TurnResolver (simultaneous action processing)
   - `duel.py` - DuelEngine (main API with async DB operations)

3. Added comprehensive tests (`tests/test_engine.py`):
   - 50 engine tests including complex scenarios
   - Multi-turn duel simulations
   - Poison tick + decay, armor reduction, multiple DoTs
   - 78 total tests passing

4. Database:
   - Added Duel, DuelParticipant, DuelAction models
   - Created Alembic migration `004_add_duel_system_tables.py`

#### Key Files Modified
- `src/vaudeville_rpg/engine/` (new module, 7 files)
- `src/vaudeville_rpg/db/models/duels.py` (new)
- `src/vaudeville_rpg/db/models/enums.py` (added DuelStatus, DuelActionType)
- `tests/test_engine.py` (new, 1409 lines)
- `WIKI.md` (duel system documentation)
- `CLAUDE.md` (marked duel engine complete)

---

## Architecture Overview

### Duel Engine Flow
```
DuelEngine.submit_action()
    ↓
TurnResolver.resolve_turn()
    ↓
Phase Processing:
    1. PRE_MOVE (poison tick, buffs)
    2. PRE_ATTACK → ATTACK → POST_ATTACK
    3. PRE_DAMAGE → DAMAGE → POST_DAMAGE
    4. POST_MOVE (stack decay)
    5. Win condition check
    ↓
EffectProcessor.process_phase()
    ↓
ConditionEvaluator + ActionExecutor
```

### Key Classes
| Class | Purpose |
|-------|---------|
| `DuelEngine` | Main API - create_duel, submit_action, cancel_duel |
| `TurnResolver` | Orchestrates full turn with all phases |
| `EffectProcessor` | Collects and executes effects by phase |
| `ConditionEvaluator` | Checks if effect conditions are met |
| `ActionExecutor` | Applies actions to combat state |
| `CombatState` | In-memory player state during duel |

---

## Next Steps

### Immediate (Phase 5)
1. **Item Content**
   - Create initial item templates
   - Procedural item generation
   - Item drop/reward system

2. **Balance Tuning**
   - Adjust HP/SP values
   - Effect damage/healing values
   - Dungeon difficulty scaling

3. **UI/UX Polish**
   - Better duel state display
   - Progress messages
   - Error handling improvements

---

## Commands Reference

```bash
# Activate virtual environment
.venv/Scripts/activate

# Run tests
pytest tests/ -v

# Run linter
python -m ruff check src/

# Run formatter
python -m ruff format src/

# Run bot
python -m vaudeville_rpg
```

---

## Branches

| Branch | Status | Description |
|--------|--------|-------------|
| `master` | Active | Main development branch |
| `feature/rating-system` | Ready | Rating system and leaderboard |
| `feature/dungeon-system` | Merged | Dungeon system (PvE) |
| `feature/pvp-duel-flow` | Merged | PvP duel handlers |
| `feature/duel-engine` | Merged | Duel engine implementation |
| `feature/player-system` | Merged | Player models and combat state |
| `feature/item-system` | Merged | Item models and effects |
| `feature/effect-system-rework` | Merged | Procedural effect system |

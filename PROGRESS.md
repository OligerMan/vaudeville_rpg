# VaudevilleRPG Development Progress

This file tracks development progress to restore context between sessions.

---

## Current State

**Branch:** `master`
**Last Updated:** 2026-01-05
**Last Commit:** Merge branch 'feature/phase-system-refactor'

### Completed Phases

| Phase | Status | Description |
|-------|--------|-------------|
| Phase 1: Foundation | Done | Python setup, PostgreSQL, Telegram bot |
| Phase 2: Core Game Systems | Done | Effect, Item, Player, Duel engine |
| Phase 3: Game Modes | Done | PvP duels, Dungeon system |
| Phase 4: Meta Systems | Done | Rating system, Leaderboard |

### Current Phase

**Phase 5: Content & Polish** (In Progress)
- [x] LLM content generation system (generators, schemas)
- [x] Content validation layer (validators)
- [x] JSON parsing and database integration (parser)
- [x] SettingFactory pipeline orchestration
- [ ] Balance tuning
- [ ] Telegram UI/UX improvements

---

## Recent Session Summary

### Session: 2026-01-05

**Completed:** Phase System Refactor & Combat Logging (MERGED)

#### What Was Done
1. Created `feature/phase-system-refactor` branch (built on engine-logging work)

2. **Combat Logging System** (`src/vaudeville_rpg/engine/logging.py`):
   - `LogEventType`: enum for event types (turn/phase/effect/action/state)
   - `StateSnapshot`: captures combat state at a point in time
   - `LogEntry`: structured log entry with all relevant fields
   - `CombatLog`: collection with filtering and formatting methods
   - `CombatLogger`: main class for tracking combat events

3. **Phase System Refactor** - State machine architecture:
   - `DamageInterruptHandler`: manages PRE/POST_DAMAGE interrupt flow
   - Split `TurnResolver` into `resolve_pre_move()` and `resolve_combat()`
   - Added `TurnPhase` enum and `current_phase` column on Duel model
   - PRE_DAMAGE/POST_DAMAGE effects only trigger for damage recipient
   - Updated `DuelEngine` API for state machine flow

4. **Database Migration**:
   - `006_add_turn_phase_to_duels.py`: adds `current_phase` column

5. **Comprehensive Tests**:
   - `tests/test_combat_logging.py` (1003 lines)
   - `tests/test_interrupts.py` (568 lines)
   - `tests/test_logging_integration.py` (621 lines)

#### Key Files Added/Modified
- `src/vaudeville_rpg/engine/logging.py` (553 lines) - NEW
- `src/vaudeville_rpg/engine/interrupts.py` (208 lines) - NEW
- `src/vaudeville_rpg/engine/turn.py` (major refactor)
- `src/vaudeville_rpg/engine/duel.py` (state machine API)
- `src/vaudeville_rpg/engine/effects.py` (interrupt support)
- `src/vaudeville_rpg/engine/actions.py` (interrupt handler)
- `src/vaudeville_rpg/db/models/duels.py` (TurnPhase column)
- `src/vaudeville_rpg/db/models/enums.py` (TurnPhase enum)

#### Test Coverage
- **Total tests:** 235 passing
- New tests: ~90 (logging, interrupts, integration)

#### Branch Status
- Merged to `master` on 2026-01-05

---

### Session: 2026-01-04

**Completed:** Generation Pipeline - Validation and Parsing Layer

#### What Was Done
1. Created `feature/generation-pipeline` branch
2. Added validation layer (`src/vaudeville_rpg/llm/validators.py`):
   - `SettingValidator`: validates settings (description, attributes, special points)
   - `WorldRulesValidator`: validates world rules (phases, actions, attributes)
   - `EffectTemplateValidator`: validates effect templates (slots, rarity scaling)
   - `ItemTypeValidator`: validates item types (base stats per slot)
   - `validate_all()`: cross-reference validation

3. Added parser layer (`src/vaudeville_rpg/llm/parser.py`):
   - `WorldRulesParser`: converts world rules to database models (Condition, Action, Effect)
   - `ItemParser`: converts items to database models with proper phase conditions

4. Added SettingFactory (`src/vaudeville_rpg/llm/setting_factory.py`):
   - Orchestrates 5-step generation pipeline
   - Returns `PipelineResult` with all generated content
   - Handles validation at each step

5. Added comprehensive tests:
   - `tests/test_validators.py`: 48 tests for validation layer
   - `tests/test_json_parsing.py`: 18 tests for JSON → schema parsing
   - `tests/test_generation.py`: Added effect verification tests

6. Updated WIKI.md with pipeline documentation

#### Key Files Added
- `src/vaudeville_rpg/llm/validators.py` (409 lines)
- `src/vaudeville_rpg/llm/parser.py` (395 lines)
- `src/vaudeville_rpg/llm/setting_factory.py` (429 lines)
- `tests/test_validators.py` (482 lines)
- `tests/test_json_parsing.py` (825 lines)

#### Test Coverage
- **Total tests:** 147 passing
- Validation: 48 tests
- JSON parsing: 18 tests
- Generation/Factory: 28 tests

---

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

## Architecture Overview

### Content Generation Pipeline
```
User Input (simple description)
        ↓
Step 1: SettingGenerator → GeneratedSetting
        ↓
Step 2: WorldRulesGenerator → GeneratedWorldRules (per attribute)
        ↓
Step 3: EffectTemplateGenerator → GeneratedEffectTemplates
        ↓
Step 4: ItemTypeGenerator → GeneratedItemTypes
        ↓
Step 5: ItemFactory → Database Items
        ↓
    PipelineResult (validated content)
```

### Duel Engine Flow (State Machine)
```
DuelEngine.submit_action()
    ↓
TurnResolver.resolve_pre_move()     ← PRE_MOVE phase (poison, buffs)
    ↓
TurnResolver.resolve_combat()       ← Combat resolution
    ↓
Phase Processing with Interrupts:
    1. PRE_ATTACK → ATTACK → POST_ATTACK (per participant)
    2. For each damage event:
       - DamageInterruptHandler.begin_damage()
       - PRE_DAMAGE (recipient only)
       - DAMAGE applied
       - POST_DAMAGE (recipient only)
       - DamageInterruptHandler.end_damage()
    3. POST_MOVE (stack decay)
    4. Win condition check
    ↓
EffectProcessor.process_phase()
    ↓
ConditionEvaluator + ActionExecutor
```

### Key Classes
| Class | Purpose |
|-------|---------|
| `SettingFactory` | Orchestrates content generation pipeline |
| `ItemFactory` | Creates items from templates with rarity scaling |
| `DuelEngine` | Main API - create_duel, submit_action, cancel_duel |
| `TurnResolver` | Orchestrates turn phases (resolve_pre_move, resolve_combat) |
| `DamageInterruptHandler` | Manages PRE/POST_DAMAGE interrupt flow per recipient |
| `EffectProcessor` | Collects and executes effects by phase |
| `ConditionEvaluator` | Checks if effect conditions are met |
| `ActionExecutor` | Applies actions to combat state |
| `CombatLogger` | Tracks combat events for debugging/testing |

---

## Next Steps

### Immediate (Phase 5 - Remaining)
1. **Balance Tuning**
   - Adjust HP/SP values
   - Effect damage/healing values
   - Dungeon difficulty scaling

2. **UI/UX Polish**
   - Better duel state display
   - Progress messages
   - Error handling improvements

3. **Integration Testing**
   - End-to-end content generation
   - Full game flow testing

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
| `feature/phase-system-refactor` | Merged | State machine + combat logging + interrupts |
| `feature/generation-pipeline` | Merged | Validation and parsing layer |
| `feature/item-content` | Merged | LLM content generation system |
| `feature/rating-system` | Merged | Rating system and leaderboard |
| `feature/dungeon-system` | Merged | Dungeon system (PvE) |
| `feature/pvp-duel-flow` | Merged | PvP duel handlers |
| `feature/duel-engine` | Merged | Duel engine implementation |
| `feature/player-system` | Merged | Player models and combat state |
| `feature/item-system` | Merged | Item models and effects |
| `feature/effect-system-rework` | Merged | Procedural effect system |

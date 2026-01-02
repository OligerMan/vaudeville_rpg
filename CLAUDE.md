# Project VaudevilleRPG

Game made in telegram bot, which is based on duels between players and between players and bots(in dungeons).
Dungeons are series of duels between one player and one computer enemy, which ends with a reward.
Each player is defined via three items, one attack item, one defensive and one misc item.
Attack item have up to several attack buffs and one active attack ability(sword swing, fire blast, etc).
Defensive item have up to several attack buffs and one active defensive ability(shield block, evade, etc).
Misc item does something special with its ability(heal, counterspell, etc).


## Project Plan

### Phase 1: Foundation
- [x] Python project setup (structure, dependencies, config)
- [x] PostgreSQL database connection and base models
- [x] Telegram bot basic setup (connection, command handling)

### Phase 2: Core Game Systems
- [ ] Item system (item models, buff types, ability definitions)
- [ ] Player system (player model, stats, inventory management)
- [ ] Duel engine (turn processing, action resolution, damage calculation)

### Phase 3: Game Modes
- [ ] PvP duel flow (challenge, accept/decline, duel execution, result)
- [ ] Dungeon system (enemy generation, dungeon progression, rewards)

### Phase 4: Meta Systems
- [ ] Rating system (rating algorithm, updates after duels)
- [ ] Leaderboard (ranking display, filtering)

### Phase 5: Content & Polish
- [ ] Initial item/ability content population
- [ ] Balance tuning
- [ ] Telegram UI/UX improvements

## Project Structure

```
src/vaudeville_rpg/
├── __init__.py
├── __main__.py          # Entry point
├── config.py            # Pydantic settings
├── bot/
│   ├── __init__.py
│   ├── app.py           # Bot setup, dispatcher
│   └── handlers/
│       ├── __init__.py
│       └── common.py    # /start, /help commands
└── db/
    ├── __init__.py
    ├── engine.py        # Async engine, session factory
    └── models/
        ├── __init__.py
        └── base.py      # Base model class
alembic/                 # Database migrations
tests/                   # Test files
```

## Running the Server

```bash
# Install dependencies
pip install -e .

# Copy and configure environment
cp .env.example .env
# Edit .env with your BOT_TOKEN and DATABASE_URL

# Run the bot
python -m vaudeville_rpg
```

Environment variables:
- `BOT_TOKEN` - Telegram bot token from @BotFather
- `DATABASE_URL` - PostgreSQL connection string (e.g., `postgresql+asyncpg://user:pass@localhost:5432/vaudeville_rpg`)
- `DEBUG` - Enable debug logging (optional, default: false)

## Running Tests

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest
```

## Implemented Features

- [x] Project foundation (aiogram 3.x, SQLAlchemy 2.0, pydantic-settings)
- [x] Basic bot commands (/start, /help)
- [x] Database engine with async support
- [x] Alembic migrations setup

---

## Important agent instructions about git usage

- Each feature that should be added, should be added in a separate git branch.
- The naming of the branch should have the following schema: <type_of_branch>/<feature_name>. For example: feature/async_judging
- Types of branches can be: feature, refactor, bugfix and methodology. feature branches add completely new features, refactor branches refactor and/or simplify the code, bugfix are for fixing bugs and methodology branches are for changing methodology of the experiments.
- Each meaningful code change should be formalized into a commit. This change may span multiple files and functions, but it should contain only one TODO item.
- Commit names follow the schema: <type_of_commit>: <description_of_commit>. For example: feat: Added asynchronous querying of the API for the judging
- Types of commits can be: feat, refactor, fix. feat commits are the commits that add new features, refactor are for refactoring of the code without any changes, fix are for bugfixes.
- Unit tests should be added after each branch merge.
- After the feature is finished and tested, the agent should ask whether the branch should be merged into main. If the user agrees, the agent should merge.
- Branches should never break main -- if feature A breaks the main branch, it should not be merged.


## Most important agent instructions on general productivity

- Each TODO list item MUST be committed right after it was checked as completed. Refer to the git usage instructions for commit message format.
- NEVER commit the changes from TODOs in bulk -- only commit them RIGHT AFTER the TODO is checked as completed. This is needed to have TODO lists appear in the commit history, so be sure to strictly follow this rule
- Before merging, the code should be ran through linter and formatter. If any problems arise, they should be fixed before merging.

## Important agent instructions about WIKI.md

- WIKI.md contains detailed game mechanics documentation
- ALWAYS check WIKI.md before implementing any game feature to ensure consistency
- ALWAYS update WIKI.md when adding new features or changing existing mechanics
- Keep WIKI.md as the single source of truth for game design decisions
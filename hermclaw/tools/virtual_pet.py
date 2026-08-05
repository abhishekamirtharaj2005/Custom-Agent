"""Virtual Pet System: ASCII art virtual pet companion.

A fun gamification feature that gives the agent a virtual pet with:
- Mood states (happy, hungry, tired, energetic, playful)
- Evolution stages (egg -> baby -> juvenile -> adult -> legendary)
- Hunger/energy mechanics
- ASCII art animations
- AI-generated personality
"""

from __future__ import annotations

import json
import random
import sqlite3
import time
from pathlib import Path
from typing import Any, Optional

from hermclaw.tools.base import ToolABC, ToolResult, ToolSpec

_PET_SCHEMA = """
CREATE TABLE IF NOT EXISTS pets (
    id TEXT PRIMARY KEY DEFAULT 'main',
    name TEXT NOT NULL,
    species TEXT NOT NULL DEFAULT 'hermit_crab',
    stage TEXT NOT NULL DEFAULT 'egg',
    mood TEXT NOT NULL DEFAULT 'curious',
    hunger INTEGER NOT NULL DEFAULT 50,
    energy INTEGER NOT NULL DEFAULT 100,
    happiness INTEGER NOT NULL DEFAULT 50,
    experience INTEGER NOT NULL DEFAULT 0,
    level INTEGER NOT NULL DEFAULT 1,
    created_at REAL NOT NULL,
    last_fed REAL,
    last_played REAL,
    last_rested REAL,
    total_interactions INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS pet_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pet_id TEXT NOT NULL,
    event TEXT NOT NULL,
    details TEXT DEFAULT '',
    created_at REAL NOT NULL
);
"""

STAGES = ["egg", "baby", "juvenile", "adult", "legendary"]
MOODS = ["happy", "sad", "hungry", "tired", "energetic", "playful", "curious", "sleepy", "excited"]

# ASCII art for different stages
PET_ART = {
    "egg": r"""
    .---.
   /     \
  |  o o  |
  |   ~   |
   \     /
    '---'
  [Egg Stage]
""",
    "baby": r"""
    /\_/\
   ( o.o )
    > ^ <
   /|   |\
  (_|   |_)
  [Baby Stage]
""",
    "juvenile": r"""
      /\_/\
     / o o \
    (  =^=  )
     )     (
    /       \
   (___|___|_)
  [Juvenile Stage]
""",
    "adult": r"""
       /\_____/\
      /  o   o  \
     ( ==  ^  == )
      )         (
     /    |||    \
    /     |||     \
   (______|_|______)
  [Adult Stage]
""",
    "legendary": r"""
    *  .  *  .  *
       /\_____/\
  *   /  @   @  \   *
     ( ==  ^  == )
  .   )  ~~~~~  (  .
     / * |||||* * \
    /   *|||||*    \
   (___*__|_|__*___)
  * . [LEGENDARY] . *
""",
}

MOOD_EMOTES = {
    "happy": "(^_^)",
    "sad": "(T_T)",
    "hungry": "(>_<) nom nom?",
    "tired": "(-_-)zzz",
    "energetic": "\\(^o^)/",
    "playful": "(>w<)",
    "curious": "(o_O)?",
    "sleepy": "(u_u)...",
    "excited": "(!!!)",
}


class VirtualPet:
    """SQLite-backed virtual pet."""

    def __init__(self, db_path: Optional[Path] = None) -> None:
        if db_path is None:
            db_path = Path.home() / ".hermclaw" / "pet.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(str(db_path))
        self._db.row_factory = sqlite3.Row
        self._db.executescript(_PET_SCHEMA)

    def close(self) -> None:
        self._db.close()

    def _get_pet(self) -> Optional[dict]:
        row = self._db.execute("SELECT * FROM pets WHERE id = 'main'").fetchone()
        return dict(row) if row else None

    def adopt(self, name: str, species: str = "hermit_crab") -> dict:
        existing = self._get_pet()
        if existing:
            return {"error": f"You already have a pet named {existing['name']}!"}

        now = time.time()
        self._db.execute(
            "INSERT INTO pets (id, name, species, created_at) VALUES ('main', ?, ?, ?)",
            (name, species, now),
        )
        self._log("adopted", f"A wild {species} named {name} appeared!")
        self._db.commit()
        return self._get_pet()

    def status(self) -> dict:
        pet = self._get_pet()
        if not pet:
            return {"error": "No pet! Use 'adopt' to get one."}

        # Decay over time
        self._apply_time_decay(pet)
        self._update_mood(pet)
        self._check_evolution(pet)

        return self._get_pet()

    def feed(self) -> dict:
        pet = self._get_pet()
        if not pet:
            return {"error": "No pet to feed!"}
        hunger = max(0, pet["hunger"] - 30)
        happiness = min(100, pet["happiness"] + 10)
        xp = pet["experience"] + 5
        self._db.execute(
            "UPDATE pets SET hunger = ?, happiness = ?, experience = ?, last_fed = ?, total_interactions = total_interactions + 1 WHERE id = 'main'",
            (hunger, happiness, xp, time.time()),
        )
        self._log("fed", f"{pet['name']} munches happily!")
        self._db.commit()
        return self._get_pet()

    def play(self) -> dict:
        pet = self._get_pet()
        if not pet:
            return {"error": "No pet to play with!"}
        energy = max(0, pet["energy"] - 15)
        happiness = min(100, pet["happiness"] + 20)
        xp = pet["experience"] + 10
        self._db.execute(
            "UPDATE pets SET energy = ?, happiness = ?, experience = ?, last_played = ?, total_interactions = total_interactions + 1 WHERE id = 'main'",
            (energy, happiness, xp, time.time()),
        )
        self._log("played", f"{pet['name']} chases its tail!")
        self._db.commit()
        return self._get_pet()

    def rest(self) -> dict:
        pet = self._get_pet()
        if not pet:
            return {"error": "No pet to rest!"}
        energy = min(100, pet["energy"] + 40)
        hunger = min(100, pet["hunger"] + 10)
        self._db.execute(
            "UPDATE pets SET energy = ?, hunger = ?, last_rested = ?, total_interactions = total_interactions + 1 WHERE id = 'main'",
            (energy, hunger, time.time()),
        )
        self._log("rested", f"{pet['name']} curls up for a nap...")
        self._db.commit()
        return self._get_pet()

    def rename(self, new_name: str) -> dict:
        pet = self._get_pet()
        if not pet:
            return {"error": "No pet!"}
        self._db.execute("UPDATE pets SET name = ? WHERE id = 'main'", (new_name,))
        self._log("renamed", f"Pet renamed to {new_name}!")
        self._db.commit()
        return self._get_pet()

    def _apply_time_decay(self, pet: dict) -> None:
        now = time.time()
        hours_since_fed = (now - (pet.get("last_fed") or pet["created_at"])) / 3600
        hours_since_played = (now - (pet.get("last_played") or pet["created_at"])) / 3600

        hunger_increase = min(100, int(hours_since_fed * 5))
        happiness_decrease = min(50, int(hours_since_played * 3))

        self._db.execute(
            "UPDATE pets SET hunger = MIN(100, hunger + ?), happiness = MAX(0, happiness - ?) WHERE id = 'main'",
            (hunger_increase, happiness_decrease),
        )
        self._db.commit()

    def _update_mood(self, pet: dict) -> None:
        pet = self._get_pet()
        if pet["hunger"] > 70:
            mood = "hungry"
        elif pet["energy"] < 20:
            mood = "tired"
        elif pet["happiness"] > 80:
            mood = random.choice(["happy", "excited", "playful"])
        elif pet["happiness"] < 30:
            mood = "sad"
        elif pet["energy"] > 80:
            mood = "energetic"
        else:
            mood = random.choice(["curious", "happy"])
        self._db.execute("UPDATE pets SET mood = ? WHERE id = 'main'", (mood,))
        self._db.commit()

    def _check_evolution(self, pet: dict) -> None:
        pet = self._get_pet()
        xp = pet["experience"]
        current_idx = STAGES.index(pet["stage"]) if pet["stage"] in STAGES else 0
        thresholds = [0, 50, 200, 500, 1000]
        for i, threshold in enumerate(thresholds):
            if xp >= threshold:
                new_idx = i
        if new_idx > current_idx:
            new_stage = STAGES[new_idx]
            self._db.execute("UPDATE pets SET stage = ?, level = ? WHERE id = 'main'", (new_stage, new_idx + 1))
            self._log("evolved", f"{pet['name']} evolved to {new_stage}!")
            self._db.commit()

    def _log(self, event: str, details: str) -> None:
        self._db.execute(
            "INSERT INTO pet_log (pet_id, event, details, created_at) VALUES ('main', ?, ?, ?)",
            (event, details, time.time()),
        )

    def render_ascii(self) -> str:
        pet = self._get_pet()
        if not pet:
            return "No pet yet! Use 'adopt' to get one."
        art = PET_ART.get(pet["stage"], PET_ART["baby"])
        emote = MOOD_EMOTES.get(pet["mood"], "(^_^)")
        bars = (
            f"  Hunger:    [{'#' * (pet['hunger'] // 10):<10}] {pet['hunger']}%\n"
            f"  Energy:    [{'#' * (pet['energy'] // 10):<10}] {pet['energy']}%\n"
            f"  Happiness: [{'#' * (pet['happiness'] // 10):<10}] {pet['happiness']}%\n"
            f"  XP:        {pet['experience']} (Lv.{pet['level']})"
        )
        return f"{art}\n  {pet['name']} {emote}\n  Mood: {pet['mood']} | Stage: {pet['stage']}\n{bars}"


class VirtualPetTool(ToolABC):
    """Virtual pet companion tool."""

    def __init__(self) -> None:
        self._pet = VirtualPet()

    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="pet",
            description=(
                "Your virtual pet companion! Actions: adopt (name, species), status, "
                "feed, play, rest, rename, show (ASCII art). Your pet evolves as you "
                "interact with it. Keep it happy and fed!"
            ),
            parameters={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["adopt", "status", "feed", "play", "rest", "rename", "show"],
                    },
                    "name": {"type": "string", "description": "Pet name (for adopt/rename)."},
                    "species": {"type": "string", "description": "Pet species (for adopt). Default: hermit_crab."},
                },
                "required": ["action"],
            },
        )

    async def execute(self, args: dict[str, Any]) -> ToolResult:
        action = args.get("action", "")
        try:
            if action == "adopt":
                name = args.get("name", "Clawbert")
                species = args.get("species", "hermit_crab")
                result = self._pet.adopt(name, species)
                if "error" in result:
                    return ToolResult(ok=False, output="", error=result["error"])
                return ToolResult(ok=True, output=f"Adopted {species} named {name}!\n\n{self._pet.render_ascii()}")

            elif action == "status":
                result = self._pet.status()
                if "error" in result:
                    return ToolResult(ok=False, output="", error=result["error"])
                return ToolResult(ok=True, output=self._pet.render_ascii())

            elif action == "feed":
                result = self._pet.feed()
                if "error" in result:
                    return ToolResult(ok=False, output="", error=result["error"])
                return ToolResult(ok=True, output=f"Fed {result['name']}!\n\n{self._pet.render_ascii()}")

            elif action == "play":
                result = self._pet.play()
                if "error" in result:
                    return ToolResult(ok=False, output="", error=result["error"])
                return ToolResult(ok=True, output=f"Played with {result['name']}!\n\n{self._pet.render_ascii()}")

            elif action == "rest":
                result = self._pet.rest()
                if "error" in result:
                    return ToolResult(ok=False, output="", error=result["error"])
                return ToolResult(ok=True, output=f"{result['name']} is resting...\n\n{self._pet.render_ascii()}")

            elif action == "rename":
                new_name = args.get("name", "")
                if not new_name:
                    return ToolResult(ok=False, output="", error="'name' required.")
                result = self._pet.rename(new_name)
                return ToolResult(ok=True, output=f"Renamed to {new_name}!")

            elif action == "show":
                return ToolResult(ok=True, output=self._pet.render_ascii())

            else:
                return ToolResult(ok=False, output="", error=f"Unknown action: {action}")
        except Exception as exc:
            return ToolResult(ok=False, output="", error=f"Pet error: {exc}")

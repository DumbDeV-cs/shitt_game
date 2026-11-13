#!/usr/bin/env python3
"""Word Guess — a professional Wordle-style terminal game built with Textual.

Guess the secret word in a limited number of tries.
  green  = right letter, right spot
  yellow = right letter, wrong spot
  grey   = letter not in the word

Features:
  * Three difficulties: Easy (8 tries, 2 hints), Medium (6 tries, 1 hint),
    Hard (5 tries, no hints, hard mode on)
  * Optional hard mode: you must reuse revealed hints in later guesses
  * Hints (Alt+H) and one undo per game (Alt+U)
  * Persistent stats: streak, best streak, win distribution, hard wins
  * Wordle-style tile flip animations and a professional keyboard

Run:  python shitt_game.py          Textual UI (default)
      python shitt_game.py --plain  simple text mode
      python shitt_game.py --selftest
"""

import asyncio
import base64
import json
import os
import random
import sys
import tempfile
import zlib

try:
    from textual.app import App, ComposeResult
    from textual.containers import Container, Horizontal, Vertical
    from textual.events import Key
    from textual.reactive import reactive
    from textual.widget import Widget
    from textual.widgets import Static, Label, Button, Footer
    from textual.binding import Binding
except ImportError:  # pragma: no cover - fallback when Textual is missing
    App = None  # type: ignore


# ---------------------------------------------------------------------------
# Game core (shared by every UI)
# ---------------------------------------------------------------------------

_WORD_BLOB = (
    "eJwlllt2riAMRqfi1FBRaZFQLr/Hjv7sL33ZixViyI1gWG2OJaz2iUvYhrUl7DMjOUZkfYZUYIvs"
    "5tBuuE4xNnRy0lflbO8Sas2sWywBnlPr1MVbNlsL6PS0I+k98u3H0r6EJ3xHsfm6xWUNe37hN6ev"
    "fLAtawzbBU88WWMqJ8z2wCJ5Dtu3eEexaJ3KDs3lZqxN9lezPpa1KSKI52uLYXei2dLmjIeoU5r5"
    "rj3oz5RZzyYL88W3LazYgUS9hbK/sDVx4NUWJrFvl84Sm5i/RXIoDtF1Yqjipt3Yu1O78gRyrpiX"
    "LYd0i9LJMRRnExvfZvkP7xWar032s00smHIIZdkyFdlsumQWSab8oQWQNyovlij2S/wlLrLE6S3d"
    "kpt8IDO7E09mI597SNRuD2VjHcO4YKbue6xauwXItzsZ/hb5KoaTc4mEbyGaMZ3XWGJOg927DuQl"
    "3uKXierM+DNDXmJrxBI/yETyH//RxTB1cbSwHCFh8wiZbBz49kJ1+KEPliNFMnykQzp+7pEKlo+k"
    "Wh/eV5A8HDlGSYwTD9tmh41Ij+Y6xIVOMzw52kxwlvIu56WuO1NAfnrtzmxrXM4WNufupE8gfSsO"
    "sbpc+uRNkhilY7Mu51Q/c8e0O9Ut59TNuriE73IpieKHtRW8vawR+2UjZqjOvOZN/0B2+ZJ4000Z"
    "Fm5O/AcLmUmlMhkSEb1L6p0b/RUzNfqyhIdfc0f/ayai+C7pENUJOXA7YWOXcLGTw3DO84K6O2rb"
    "IuI5pAdyPPEhUxHoVaCRySGNLLmdzAESj+d5bt8v1N3HZeR3+CKK2yfGHZrLh/Mlz1C7cccOTAEO"
    "rf2UOyk/t9GnsMRXpBPIi3Rs+K7uyO15g777SaynphOZwv/ivVTiQ36KWy6m6Yd19IsprjJVBdt0"
    "c+040DdmLGufolaSsW675OMSp/JWg7JduY4ZVpc0bkQleWGpUV1UdXmW6vOkUnLnsKXSdWI2LCTl"
    "pKbfX77K/lVW18Hia52iUi3V61vt0Vl+W2tTleHuvJ3SaelXa7NDZM78THXpz9QsgtwXGjwZVDZo"
    "7VOsTP4WhuQ+2zWGX6icNCbGP1jJpA5E4vnUqGBtK7FwFL0EuS9NaYIv9WpTVes8VPvSaZwImRzQ"
    "qpP3pcfSRVWta3As/dIdhNXZ/lhhjH8cYj6c2L8YFqIsX6lprXkLzdeSuM896b70pHnYs1vLydfK"
    "ZL+DrN26rf1O8vY2XsNe9CZ22mIX5adH2r33elXtoPyserlg3EXpVLdfGZ3QPRnhOEQyD3mJoDRH"
    "+NsdkmsyQ3qsD9WuD/ujYhyeN3g7iWi0RCxj7lq/8nyevER9qj/7o4wNfxkHXQq9yvQ6/o9LbzQN"
    "TheNS++sKElipo1LfxqQ930kvQsjDdnxl2vYzmsySDN2jFCh7vLwt2x4VwzvW+Y+/g+frjBlZ4Ga"
    "pZAMEIS+bWmVznT9Sb2gzmrK9niUT4ZNFtWN0+8p5A4yF7A8q6KeVX81s63c7tn1Nn2CKgiZnB8K"
    "bhDTsFOdT5Ln/ARh//EsPT61Hp+Wz6VaQDL/XEnySx0CpXmZrzUPH9Mkf6zxikGq8/jMeWxK0lyf"
    "GX4ur790L710iuj8Rv6D/gPhc7aX"
)
WORDS = zlib.decompress(base64.b64decode(_WORD_BLOB)).decode().split()
WORD_LEN = 5

STATS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)) or ".", "wordguess_stats.json")

DIFFICULTIES = {
    "easy":   dict(tries=8, hints=2, hard=False, label="Easy"),
    "medium": dict(tries=6, hints=1, hard=False, label="Medium"),
    "hard":   dict(tries=5, hints=0, hard=True,  label="Hard"),
}

RANK = {"x": 0, "y": 1, "g": 2}


def score(secret: str, guess: str) -> list[str]:
    """Return a list of 'g' / 'y' / 'x' for each letter, handling repeated letters correctly."""
    result = ["x"] * len(guess)
    remaining = {}
    for s, g in zip(secret, guess):
        if s == g:
            continue
        remaining[s] = remaining.get(s, 0) + 1
    for i, (s, g) in enumerate(zip(secret, guess)):
        if s == g:
            result[i] = "g"
        elif remaining.get(g, 0) > 0:
            result[i] = "y"
            remaining[g] -= 1
    return result


class GameStats:
    """Persistent stats stored as JSON next to the game file."""

    def __init__(self, path=STATS_FILE):
        self.path = path
        self.games = 0
        self.wins = 0
        self.streak = 0
        self.max_streak = 0
        self.distribution = {}  # str(turn) -> count
        self.hard_wins = 0
        self.total_hints = 0
        self.total_undos = 0
        self.load()

    def load(self):
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError):
            return
        self.games = int(data.get("games", 0))
        self.wins = int(data.get("wins", 0))
        self.streak = int(data.get("streak", 0))
        self.max_streak = int(data.get("max_streak", 0))
        self.distribution = {str(k): int(v) for k, v in data.get("distribution", {}).items()}
        self.hard_wins = int(data.get("hard_wins", 0))
        self.total_hints = int(data.get("total_hints", 0))
        self.total_undos = int(data.get("total_undos", 0))

    def save(self):
        data = {
            "games": self.games,
            "wins": self.wins,
            "streak": self.streak,
            "max_streak": self.max_streak,
            "distribution": self.distribution,
            "hard_wins": self.hard_wins,
            "total_hints": self.total_hints,
            "total_undos": self.total_undos,
        }
        try:
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except OSError:
            pass

    def record(self, won: bool, turn, hard: bool, hints: int, undos: int):
        self.games += 1
        if won:
            self.wins += 1
            self.streak += 1
            self.max_streak = max(self.max_streak, self.streak)
            if turn is not None:
                self.distribution[str(turn)] = self.distribution.get(str(turn), 0) + 1
            if hard:
                self.hard_wins += 1
        else:
            self.streak = 0
        self.total_hints += hints
        self.total_undos += undos
        self.save()


# ---------------------------------------------------------------------------
# Textual UI
# ---------------------------------------------------------------------------

if App is not None:

    class Tile(Static):
        """A single letter tile with Wordle-style flip animation."""

        def __init__(self, r: int, c: int):
            super().__init__("", id=f"tile-{r}-{c}")
            self.r = r
            self.c = c

        def set_letter(self, ch: str, mark: str = "") -> None:
            self.update(ch.upper() if ch else " ")
            self.remove_class("empty", "active", "correct", "present", "absent")
            if mark:
                self.add_class({"g": "correct", "y": "present", "x": "absent"}[mark])
            elif ch:
                self.add_class("active")
            else:
                self.add_class("empty")

    class Key(Static):
        """A single keyboard key."""

        def __init__(self, ch: str):
            super().__init__(ch.upper(), id=f"key-{ch}")
            self.ch = ch

        def set_mark(self, mark: str | None) -> None:
            self.remove_class("correct", "present", "absent")
            if mark == "g":
                self.add_class("correct")
            elif mark == "y":
                self.add_class("present")
            elif mark == "x":
                self.add_class("absent")

    class WordGuessApp(App):
        CSS = """
        Screen {
            background: #121213;
            color: #ffffff;
        }

        #title {
            color: #ffffff;
            text-style: bold;
            text-align: center;
            margin: 1 0;
        }

        #subtitle {
            text-align: center;
            color: #878a8c;
            margin: 0 0 1 0;
        }

        #views {
            height: 1fr;
            align: center middle;
        }

        .view {
            display: none;
        }

        .view.active {
            display: block;
        }

        /* ---------- menu ---------- */
        #menu {
            align: center middle;
        }

        #menu Vertical {
            align: center middle;
        }

        .menu-btn {
            width: 26;
            height: 3;
            margin: 1;
            color: #ffffff;
            background: #3a3a3c;
            border: solid #565759;
            text-align: center;
        }

        .menu-btn:hover {
            background: #565759;
            border: solid #ffffff;
        }

        .menu-btn.-active {
            background: #6aaa64;
            border: solid #6aaa64;
            color: #000000;
        }

        /* ---------- game ---------- */
        #game {
            align: center middle;
        }

        #header-row {
            layout: horizontal;
            align: center middle;
            width: 100%;
            height: 3;
            margin: 0 0 1 0;
        }

        #diff-chip {
            width: 22;
            height: 1;
            color: #000000;
            background: #c9b458;
            text-align: center;
            text-style: bold;
            margin: 0 1;
        }

        #stats-line {
            color: #878a8c;
            text-align: center;
            width: 1fr;
        }

        #clue {
            text-align: center;
            color: #c9b458;
            text-style: bold;
            margin: 0 0 1 0;
        }

        GuessRow {
            layout: horizontal;
            align: center middle;
            height: 3;
            margin: 0 0 1 0;
        }

        Tile {
            width: 6;
            height: 3;
            margin: 0 1;
            border: solid #3a3a3c;
            color: #ffffff;
            text-align: center;
            text-style: bold;
        }

        Tile.empty {
            color: #3a3a3c;
        }

        Tile.active {
            border: solid #ffffff;
            color: #ffffff;
        }

        Tile.correct {
            background: #6aaa64;
            border: #6aaa64;
            color: #000000;
        }

        Tile.present {
            background: #c9b458;
            border: #c9b458;
            color: #000000;
        }

        Tile.absent {
            background: #3a3a3c;
            border: #3a3a3c;
            color: #ffffff;
        }

        #message {
            text-align: center;
            margin: 1 0;
            color: #ff3b30;
            text-style: bold;
        }

        #keyboard {
            align: center middle;
            margin: 2 0 0 0;
        }

        KeyRow {
            layout: horizontal;
            align: center middle;
            height: 1;
            margin: 0 0 1 0;
        }

        Key {
            width: 3;
            height: 1;
            margin: 0 1;
            color: #ffffff;
            text-align: center;
            text-style: bold;
        }

        Key.correct {
            background: #6aaa64;
            color: #000000;
        }

        Key.present {
            background: #c9b458;
            color: #000000;
        }

        Key.absent {
            background: #3a3a3c;
            color: #ffffff;
        }

        /* ---------- stats / difficulty ---------- */
        #stats-view, #diff-view {
            align: center middle;
        }

        #stats-view Vertical, #diff-view Vertical {
            align: center middle;
        }

        .stat-line {
            text-align: center;
            color: #ffffff;
            margin: 0 0 0 0;
        }

        .hint {
            color: #878a8c;
            text-align: center;
            margin: 1 0 0 0;
        }

        #footer {
            text-align: center;
            color: #878a8c;
            margin: 1 0 0 0;
        }
        """

        BINDINGS = [
            Binding("enter", "submit", "Submit guess", show=True),
            Binding("backspace", "delete", "Delete", show=True),
            Binding("delete", "delete", "Delete", show=True),
            Binding("escape", "menu", "Menu / Quit", show=True),
            Binding("alt+h", "hint", "Hint", show=True),
            Binding("alt+u", "undo", "Undo", show=True),
            Binding("q", "quit", "Quit", show=False),
        ]

        def __init__(self):
            super().__init__()
            self.stats = GameStats(STATS_FILE)
            self.difficulty = "medium"
            self.hard_override = False
            self.secret = ""
            self.tries_allowed = 6
            self.hints_left = 1
            self.hard_mode = False
            self.guesses = []          # list of (word, marks)
            self.current = ""
            self.used = {}             # letter -> best mark
            self.state = "menu"        # menu | playing | won | lost | stats | difficulty
            self.message = ""
            self.hints_used = 0
            self.undos_used = 0
            self.clue = ["_"] * WORD_LEN
            self.hinted = set()
            self.rows = {}             # (r, c) -> Tile
            self.keys = {}             # ch -> Key
            self.animating = False

        # -- composition ---------------------------------------------------
        def compose(self) -> ComposeResult:
            yield Label("WORD GUESS", id="title")
            yield Static("Guess the secret word before you run out of tries.", id="subtitle")
            with Container(id="views"):
                # menu view
                with Container(id="menu", classes="view active"):
                    yield Vertical(
                        Button("1  Play", id="btn-play", classes="menu-btn -active"),
                        Button("2  Stats", id="btn-stats", classes="menu-btn"),
                        Button("3  Difficulty", id="btn-diff", classes="menu-btn"),
                        Button("4  Quit", id="btn-quit", classes="menu-btn"),
                    )
                    yield Static(f"Difficulty: {DIFFICULTIES[self.difficulty]['label']}", id="menu-diff")
                    yield Static(f"Streak: {self.stats.streak}  ·  Best: {self.stats.max_streak}", id="menu-streak")
                # game view
                with Container(id="game", classes="view"):
                    with Horizontal(id="header-row"):
                        yield Static("Medium", id="diff-chip")
                        yield Static("", id="stats-line")
                    yield Static("", id="clue")
                    for r in range(8):
                        with Horizontal(classes="GuessRow", id=f"row-{r}"):
                            for c in range(WORD_LEN):
                                yield Tile(r, c)
                    yield Static("", id="message")
                    with Container(id="keyboard"):
                        for i, row in enumerate(["qwertyuiop", "asdfghjkl", "zxcvbnm"]):
                            with Horizontal(classes="KeyRow", id=f"krow-{i}"):
                                for ch in row:
                                    yield Key(ch)
                # stats view
                with Container(id="stats-view", classes="view"):
                    with Vertical():
                        yield Static("S T A T S", classes="stat-line")
                        yield Static(f"Games played : {self.stats.games}", classes="stat-line")
                        yield Static(f"Games won    : {self.stats.wins}", classes="stat-line")
                        yield Static(f"Win rate     : {self.stats.wins * 100 // max(1, self.stats.games)}%", classes="stat-line")
                        yield Static(f"Current streak: {self.stats.streak}   Best streak : {self.stats.max_streak}", classes="stat-line")
                        yield Static(f"Hard-mode wins: {self.stats.hard_wins}", classes="stat-line")
                        yield Static(f"Hints used   : {self.stats.total_hints}   Undos used   : {self.stats.total_undos}", classes="stat-line")
                        yield Static("", id="stats-dist")
                        yield Static("Press any key to return", classes="hint")
                # difficulty view
                with Container(id="diff-view", classes="view"):
                    with Vertical():
                        yield Static("D I F F I C U L T Y", classes="stat-line")
                        yield Static("Pick a difficulty:", classes="stat-line")
                        yield Button("1  Easy   (8 tries, 2 hints)", id="d-easy", classes="menu-btn")
                        yield Button("2  Medium (6 tries, 1 hint)", id="d-medium", classes="menu-btn")
                        yield Button("3  Hard   (5 tries, hard mode)", id="d-hard", classes="menu-btn")
                        yield Static("", id="diff-hard-note")
                        yield Static("Press any key to return", classes="hint")
            yield Footer()
            yield Static("Enter: submit  Bksp: delete  Alt+H: hint  Alt+U: undo  Esc: menu", id="footer")

        # -- lifecycle -----------------------------------------------------
        def on_mount(self) -> None:
            self.refresh_ui()

        def on_button_pressed(self, event: Button.Pressed) -> None:
            bid = event.button.id
            if self.state == "menu":
                if bid == "btn-play":
                    self.start_game()
                elif bid == "btn-stats":
                    self.state = "stats"
                elif bid == "btn-diff":
                    self.state = "difficulty"
                elif bid == "btn-quit":
                    self.exit()
            elif self.state == "difficulty":
                if bid == "d-easy":
                    self.difficulty = "easy"
                elif bid == "d-medium":
                    self.difficulty = "medium"
                elif bid == "d-hard":
                    self.difficulty = "hard"
                self.refresh_diff_view()
            self.refresh_ui()

        def on_key(self, event: Key) -> None:
            ch = event.character or ""

            # ----- non-playing states: navigate with number keys -----
            if self.state == "menu":
                if ch == "1":
                    self.start_game()
                elif ch == "2":
                    self.state = "stats"
                elif ch == "3":
                    self.state = "difficulty"
                elif ch == "4":
                    self.exit()
                self.refresh_ui()
                return

            if self.state == "difficulty":
                if ch == "1":
                    self.difficulty = "easy"
                elif ch == "2":
                    self.difficulty = "medium"
                elif ch == "3":
                    self.difficulty = "hard"
                else:
                    self.state = "menu"
                self.refresh_diff_view()
                self.refresh_ui()
                return

            if self.state in ("stats", "won", "lost"):
                if event.key == "enter" and self.state in ("won", "lost"):
                    self.start_game()
                else:
                    self.state = "menu"
                self.refresh_ui()
                return

            if self.state not in ("playing",):
                return

            # ----- playing state -----
            if self.animating:
                return

            key = event.key

            if key == "enter":
                self.action_submit()
            elif key in ("backspace", "delete"):
                self.action_delete()
            elif key == "escape":
                self.action_menu()
            elif ch and ch.isalpha() and len(self.current) < WORD_LEN:
                self.current += ch.lower()
                self.message = ""
                self.refresh_ui()

        # -- actions -------------------------------------------------------
        def action_submit(self) -> None:
            if self.state != "playing" or self.animating:
                return
            if len(self.current) != WORD_LEN:
                self.show_message("Not enough letters", "#ff3b30")
                return
            ok, why = self.hard_ok(self.current)
            if not ok:
                self.show_message(why, "#ff3b30")
                return
            self.submit_guess(self.current)

        def action_delete(self) -> None:
            if self.state == "playing" and not self.animating:
                self.current = self.current[:-1]
                self.message = ""
                self.refresh_ui()

        def action_menu(self) -> None:
            if self.state == "playing":
                self.state = "menu"
            elif self.state == "menu":
                self.exit()
            else:
                self.state = "menu"
            self.refresh_ui()

        def action_hint(self) -> None:
            if self.state != "playing" or self.animating:
                return
            self.do_hint()

        def action_undo(self) -> None:
            if self.state != "playing" or self.animating:
                return
            self.do_undo()

        def action_quit(self) -> None:
            self.exit()

        # -- game flow -----------------------------------------------------
        def start_game(self) -> None:
            d = DIFFICULTIES[self.difficulty]
            self.secret = random.choice(WORDS)
            self.tries_allowed = d["tries"]
            self.hints_left = d["hints"]
            self.hard_mode = d["hard"] or self.hard_override
            self.guesses = []
            self.current = ""
            self.used = {}
            self.state = "playing"
            self.message = ""
            self.hints_used = 0
            self.undos_used = 0
            self.clue = ["_"] * WORD_LEN
            self.hinted = set()
            self.animating = False
            self.refresh_ui()

        def hard_ok(self, guess: str):
            if not self.hard_mode or not self.guesses:
                return True, ""
            green_at = {}
            must_have = {}
            for word, marks in self.guesses:
                for i, (c, m) in enumerate(zip(word, marks)):
                    if m == "g":
                        green_at[i] = c
                    if m in ("g", "y"):
                        must_have[c] = must_have.get(c, 0) + 1
            counts = {}
            for c in guess:
                counts[c] = counts.get(c, 0) + 1
            for i, c in enumerate(guess):
                if i in green_at and green_at[i] != c:
                    return False, f"Position {i + 1} must be {green_at[i].upper()}."
            for c, need in must_have.items():
                if counts.get(c, 0) < need:
                    return False, f"Must use {c.upper()} at least {need} time(s)."
            for c in guess:
                if self.used.get(c) == "x":
                    return False, f"{c.upper()} is not in the word."
            return True, ""

        def submit_guess(self, guess: str) -> None:
            marks = score(self.secret, guess)
            self.guesses.append((guess, marks))
            # flip animation, one tile at a time
            self.animating = True
            for c in range(WORD_LEN):
                self.flip_tile(len(self.guesses) - 1, c, guess[c], marks[c])
            self.animating = False
            for ch, m in zip(guess, marks):
                if ch not in self.used or RANK[m] > RANK[self.used[ch]]:
                    self.used[ch] = m
            self.refresh_keyboard()
            if guess == self.secret:
                self.state = "won"
                self.stats.record(True, len(self.guesses), self.hard_mode, self.hints_used, self.undos_used)
                praise = ["Genius!", "Magnificent!", "Splendid!", "Impressive!", "Great!", "Phew!"]
                self.show_message(f"{praise[min(len(self.guesses) - 1, 5)]} Solved in {len(self.guesses)}!", "#6aaa64")
            elif len(self.guesses) == self.tries_allowed:
                self.state = "lost"
                self.stats.record(False, None, self.hard_mode, self.hints_used, self.undos_used)
                self.show_message(f"Out of tries. The word was {self.secret.upper()}.", "#ff3b30")

        async def flip_tile(self, r: int, c: int, letter: str, mark: str) -> None:
            """Wordle-style reveal: blank the tile, then show the colored letter."""
            tile = self.rows[(r, c)]
            tile.set_letter("")                  # blank (the "flip" hides the face)
            await asyncio.sleep(0.12)
            tile.set_letter(letter, mark)        # reveal the letter + color
            await asyncio.sleep(0.08)

        def do_hint(self) -> None:
            if self.hints_left <= 0:
                self.show_message("No hints left.", "#ff3b30")
                return
            avail = [i for i in range(WORD_LEN) if i not in self.hinted]
            if not avail:
                self.show_message("Every position revealed.", "#ff3b30")
                return
            i = random.choice(avail)
            self.hinted.add(i)
            self.hints_left -= 1
            self.hints_used += 1
            self.clue[i] = self.secret[i]
            self.show_message(f"Hint: position {i + 1} is {self.secret[i].upper()}!", "#c9b458")
            self.refresh_clue()

        def do_undo(self) -> None:
            if not self.guesses:
                self.show_message("Nothing to undo.", "#ff3b30")
                return
            if self.undos_used >= 1:
                self.show_message("No undos left this game.", "#ff3b30")
                return
            self.guesses.pop()
            self.undos_used += 1
            self.used = {}
            for word, marks in self.guesses:
                for ch, m in zip(word, marks):
                    if ch not in self.used or RANK[m] > RANK[self.used[ch]]:
                        self.used[ch] = m
            # clear the animated tiles for the undone row
            r = len(self.guesses)
            for c in range(WORD_LEN):
                self.rows[(r, c)].set_letter("")
            self.show_message("Undid last guess.", "#6aaa64")
            self.refresh_keyboard()

        # -- refresh -------------------------------------------------------
        def refresh_ui(self) -> None:
            # toggle views
            view_id = {"menu": "menu", "playing": "game", "stats": "stats-view", "difficulty": "diff-view"}[self.state]
            for vid in ("menu", "game", "stats-view", "diff-view"):
                widget = self.query_one(f"#{vid}")
                widget.remove_class("active")
            self.query_one(f"#{view_id}").add_class("active")

            if self.state == "menu":
                self.refresh_menu()
            elif self.state == "playing":
                self.refresh_game()
            elif self.state == "stats":
                self.refresh_stats()
            elif self.state == "difficulty":
                self.refresh_diff_view()

        def refresh_menu(self) -> None:
            self.query_one("#menu-diff").update(f"Difficulty: {DIFFICULTIES[self.difficulty]['label']}")
            self.query_one("#menu-streak").update(f"Streak: {self.stats.streak}  ·  Best: {self.stats.max_streak}")

        def refresh_game(self) -> None:
            d = DIFFICULTIES[self.difficulty]
            self.query_one("#diff-chip").update(d["label"])
            rate = self.stats.wins * 100 // max(1, self.stats.games)
            self.query_one("#stats-line").update(f"{d['tries']} tries  ·  hints left: {self.hints_left}  ·  win rate {rate}%")
            self.refresh_clue()
            # tiles
            max_r = max(self.tries_allowed, len(self.guesses))
            for r in range(max_r):
                for c in range(WORD_LEN):
                    tile = self.rows[(r, c)]
                    if r < len(self.guesses):
                        word, marks = self.guesses[r]
                        tile.set_letter(word[c], marks[c])
                    elif r == len(self.guesses) and self.state == "playing":
                        tile.set_letter(self.current[c] if c < len(self.current) else "", "")
                    else:
                        tile.set_letter("")
            self.refresh_keyboard()
            if self.message:
                self.show_message(self.message, "#ffffff", temporary=False)
            else:
                self.query_one("#message").update("")

        def refresh_clue(self) -> None:
            self.query_one("#clue").update("Clue: " + " ".join(self.clue))

        def refresh_keyboard(self) -> None:
            for ch, key in self.keys.items():
                key.set_mark(self.used.get(ch))

        def refresh_stats(self) -> None:
            lines = [
                f"Games played : {self.stats.games}",
                f"Games won    : {self.stats.wins}",
                f"Win rate     : {self.stats.wins * 100 // max(1, self.stats.games)}%",
                f"Current streak: {self.stats.streak}   Best streak : {self.stats.max_streak}",
                f"Hard-mode wins: {self.stats.hard_wins}",
                f"Hints used   : {self.stats.total_hints}   Undos used   : {self.stats.total_undos}",
            ]
            # build dist line
            dist = "  ".join(f"{t}:{self.stats.distribution.get(str(t), 0)}" for t in range(1, 9))
            lines.append("")
            lines.append(f"Distribution : {dist}")
            self.query_one("#stats-dist").update("\n".join(lines))

        def refresh_diff_view(self) -> None:
            d = DIFFICULTIES[self.difficulty]
            note = f"Selected: {d['label']}  ·  {d['tries']} tries, {d['hints']} hint{'s' if d['hints'] != 1 else ''}"
            if d["hard"]:
                note += "   ·   hard mode forced"
            self.query_one("#diff-hard-note").update(note)
            # highlight selected button
            for key in ("d-easy", "d-medium", "d-hard"):
                btn = self.query_one(f"#{key}")
                btn.remove_class("-active")
                if key == f"d-{self.difficulty}":
                    btn.add_class("-active")

        def show_message(self, text: str, color: str, temporary: bool = True) -> None:
            msg = self.query_one("#message")
            msg.update(text)
            msg.styles.color = color
            self.message = text

    def run_textual() -> None:
        WordGuessApp().run()


# ---------------------------------------------------------------------------
# Plain text mode
# ---------------------------------------------------------------------------

def play_plain(diff: str, stats: GameStats) -> bool:
    d = DIFFICULTIES[diff]
    secret = random.choice(WORDS)
    used = {}
    guesses = []
    hints_left = d["hints"]
    hinted = set()
    clue = ["_"] * WORD_LEN
    undos_left = 1
    hard = d["hard"]
    tries = 0
    print(f"\nNew game — {d['label']}: {d['tries']} tries, {d['hints']} hint(s).")
    if hard:
        print("Hard mode ON: you must reuse revealed hints in later guesses.")
    while tries < d["tries"]:
        prompt = f"Guess {tries + 1}/{d['tries']} (type 'hint' or 'undo'): "
        try:
            raw = input(prompt).strip().lower()
        except EOFError:
            print()
            return False
        if raw == "hint":
            if hints_left <= 0:
                print("  No hints left.")
                continue
            avail = [i for i in range(WORD_LEN) if i not in hinted]
            if not avail:
                print("  Every position already revealed.")
                continue
            i = random.choice(avail)
            hinted.add(i)
            hints_left -= 1
            stats.total_hints += 1
            clue[i] = secret[i]
            print(f"  Hint: position {i + 1} is {secret[i].upper()}!  Clue: {' '.join(clue)}")
            continue
        if raw == "undo":
            if undos_left <= 0:
                print("  No undos left this game.")
                continue
            if not guesses:
                print("  Nothing to undo.")
                continue
            guesses.pop()
            tries -= 1
            undos_left -= 1
            stats.total_undos += 1
            used = {}
            for word, marks in guesses:
                for c, m in zip(word, marks):
                    if c not in used or RANK[m] > RANK[used[c]]:
                        used[c] = m
            print("  Undid last guess.")
            continue
        guess = raw
        if len(guess) != WORD_LEN or not guess.isalpha():
            print("  Enter exactly 5 letters.")
            continue
        ok = True
        if hard and guesses:
            green_at = {}
            must_have = {}
            for word, marks in guesses:
                for i, (c, m) in enumerate(zip(word, marks)):
                    if m == "g":
                        green_at[i] = c
                    if m in ("g", "y"):
                        must_have[c] = must_have.get(c, 0) + 1
            counts = {}
            for c in guess:
                counts[c] = counts.get(c, 0) + 1
            for i, c in enumerate(guess):
                if i in green_at and green_at[i] != c:
                    ok = False
                    print(f"  Hard mode: position {i + 1} must be {green_at[i].upper()}.")
                    break
            if ok:
                for c, need in must_have.items():
                    if counts.get(c, 0) < need:
                        ok = False
                        print(f"  Hard mode: must use {c.upper()} at least {need} time(s).")
                        break
            if ok:
                for c in guess:
                    if used.get(c) == "x":
                        ok = False
                        print(f"  Hard mode: {c.upper()} is not in the word.")
                        break
        if not ok:
            continue
        tries += 1
        marks = score(secret, guess)
        guesses.append((guess, marks))
        for c, m in zip(guess, marks):
            if c not in used or RANK[m] > RANK[used[c]]:
                used[c] = m
        colors = {"g": "\033[42;30m", "y": "\033[43;30m", "x": "\033[100;97m"}
        reset = "\033[0m"
        bold = "\033[1m"
        print("  " + " ".join(f"{colors[m]}{bold} {g.upper()} {reset}" for g, m in zip(guess, marks)))
        rows = ["qwertyuiop", "asdfghjkl", "zxcvbnm"]
        for i, row in enumerate(rows):
            cells = [
                f"{colors[used[c]]}{bold} {c.upper()} {reset}" if c in used else f"\033[2m {c.upper()} {reset}"
                for c in row
            ]
            print(" " * (i * 2) + "".join(cells))
        if guess == secret:
            praise = ["Genius!", "Magnificent!", "Splendid!", "Impressive!", "Great!", "Phew!"]
            print(f"  {praise[min(tries - 1, 5)]} You got it in {tries}! The word was {secret.upper()}.")
            stats.record(True, tries, hard, d["hints"] - hints_left, 1 - undos_left)
            return True
    print(f"  Out of tries. The word was {secret.upper()}.")
    stats.record(False, None, hard, d["hints"] - hints_left, 1 - undos_left)
    return False


def main_plain() -> None:
    stats = GameStats(STATS_FILE)
    print("WORD GUESS — pick a difficulty:")
    print("  1 Easy   (8 tries, 2 hints)")
    print("  2 Medium (6 tries, 1 hint)")
    print("  3 Hard   (5 tries, hard mode on)")
    choice = input("Choose 1-3 [2]: ").strip()
    diff = {"1": "easy", "2": "medium", "3": "hard"}.get(choice, "medium")
    while True:
        play_plain(diff, stats)
        rate = stats.wins * 100 // max(1, stats.games)
        print(f"Record: {stats.wins} won / {stats.games} played  ·  "
              f"streak {stats.streak} (best {stats.max_streak})  ·  win rate {rate}%")
        try:
            again = input("Play again? (y/n) / (d)ifficulty / (s)tats: ").strip().lower()
        except EOFError:
            break
        if again == "d":
            print("  1 Easy   (8 tries, 2 hints)")
            print("  2 Medium (6 tries, 1 hint)")
            print("  3 Hard   (5 tries, hard mode on)")
            choice = input("Choose 1-3: ").strip()
            diff = {"1": "easy", "2": "medium", "3": "hard"}.get(choice, diff)
        elif again == "s":
            print(f"  Hard-mode wins: {stats.hard_wins}")
            print(f"  Hints used: {stats.total_hints}  Undos used: {stats.total_undos}")
            print("  Distribution:", " ".join(f"{t}:{stats.distribution.get(str(t), 0)}" for t in range(1, 9)))
            again = input("Play again? (y/n): ").strip().lower()
            if again != "y":
                break
        if again != "y":
            break
    print("Thanks for playing!")


def main() -> None:
    if "--plain" in sys.argv[1:]:
        return main_plain()
    if App is None:
        print("Textual is not installed. Run: pip install textual")
        print("Falling back to plain text mode.\n")
        return main_plain()
    run_textual()


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--selftest":
        assert score("crane", "crane") == list("ggggg")
        assert score("candy", "lolly") == list("xxxxg")
        assert score("apple", "paper") == list("yygyx")
        assert score("abbey", "babes") == list("yyggx")
        assert score("allee", "eagle") == list("yyxyg")
        assert score("crane", "error") == list("ygxxx")
        assert all(len(w) == 5 and w.isalpha() for w in WORDS), "bad word in list"
        assert len(WORDS) == len(set(WORDS)), "duplicate words"
        fd, tmp = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        try:
            s = GameStats(tmp)
            s.record(True, 3, False, 1, 0)
            s.record(False, None, False, 0, 0)
            s.record(True, 1, True, 0, 1)
            assert s.games == 3 and s.wins == 2
            assert s.streak == 1 and s.max_streak == 1
            assert s.distribution == {"3": 1, "1": 1}
            assert s.hard_wins == 1 and s.total_hints == 1 and s.total_undos == 1
            s2 = GameStats(tmp)
            assert s2.games == 3 and s2.distribution == {"3": 1, "1": 1}
        finally:
            os.unlink(tmp)
        print(f"selftest ok ({len(WORDS)} words)")
    else:
        main()

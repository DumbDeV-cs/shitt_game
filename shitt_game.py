#!/usr/bin/env python3
"""Word Guess: a colorful Wordle-style game for the terminal.

Guess the secret word in a limited number of tries.
  green  = right letter, right spot
  yellow = right letter, wrong spot
  grey   = letter not in the word

Features:
  * Three difficulties: Easy (8 tries, 2 hints), Medium (6 tries, 1 hint),
    Hard (5 tries, no hints, hard mode on)
  * Optional hard mode: you must reuse revealed hints in later guesses
  * Hints and one undo per game
  * Persistent stats: streak, best streak, win distribution, hard wins
  * Rainbow title, animated tiles, colorful keyboard

Run:  python shitt_game.py          full-screen terminal UI
      python shitt_game.py --plain  simple text mode
      python shitt_game.py --selftest
"""

import base64
import json
import os
import random
import sys
import tempfile
import zlib

try:
    import curses
except ImportError:
    curses = None

# The word list is stored compressed so the answers can't be spoiled by reading this file.
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

# ANSI colors for plain text mode
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"
GREEN = "\033[42;30m"
YELLOW = "\033[43;30m"
GREY = "\033[100;97m"
CYAN = "\033[36m"
MAGENTA = "\033[35m"
RED = "\033[31m"
BLUE = "\033[34m"
RAINBOW = [CYAN, MAGENTA, YELLOW, GREEN, RED]


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


def render(guess: str, marks: list[str]) -> str:
    colors = {"g": GREEN + BOLD, "y": YELLOW + BOLD, "x": GREY + BOLD}
    return " ".join(f"{colors[m]} {c.upper()} {RESET}" for c, m in zip(guess, marks))


def keyboard(used: dict[str, str]) -> str:
    colors = {"g": GREEN + BOLD, "y": YELLOW + BOLD, "x": GREY + BOLD}
    rows = ["qwertyuiop", "asdfghjkl", "zxcvbnm"]
    lines = []
    for i, row in enumerate(rows):
        cells = [
            f"{colors[used[c]]} {c.upper()} {RESET}" if c in used else f"{DIM} {c.upper()} {RESET}"
            for c in row
        ]
        lines.append(" " * (i * 2) + "".join(cells))
    return "\n".join(lines)


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
            pass  # stats are nice-to-have; never crash the game over them

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
# Full-screen curses UI
# ---------------------------------------------------------------------------

class UI:
    def __init__(self, stdscr):
        self.stdscr = stdscr
        curses.curs_set(0)
        curses.start_color()
        curses.use_default_colors()
        self.has_color = curses.COLORS >= 8
        grey_bg = 8 if curses.COLORS >= 16 else curses.COLOR_BLUE
        try:
            curses.init_pair(1, curses.COLOR_BLACK, curses.COLOR_GREEN)   # green tile
            curses.init_pair(2, curses.COLOR_BLACK, curses.COLOR_YELLOW)  # yellow tile
            curses.init_pair(3, curses.COLOR_WHITE, grey_bg)              # grey tile
            curses.init_pair(4, curses.COLOR_CYAN, -1)                    # primary / title
            curses.init_pair(5, curses.COLOR_RED, -1)                     # error / lost
            curses.init_pair(6, curses.COLOR_GREEN, -1)                   # win / praise
            curses.init_pair(7, curses.COLOR_MAGENTA, -1)                 # hints / magic
            curses.init_pair(8, curses.COLOR_BLUE, -1)                    # hidden / dim
            curses.init_pair(9, curses.COLOR_YELLOW, -1)                  # accent
        except curses.error:
            self.has_color = False

        self.stats = GameStats(STATS_FILE)
        self.difficulty = "medium"
        self.hard_override = False
        self.mode = "menu"        # menu | stats | difficulty | playing | won | lost
        self.menu_sel = 0
        self.diff_sel = 0
        self.reset_game()

    # -- colors -----------------------------------------------------------
    def pair(self, n: int) -> int:
        return curses.color_pair(n) if self.has_color else 0

    def tile_attr(self, mark: str, hidden: bool = False) -> int:
        if hidden:
            return self.pair(8) | curses.A_DIM
        base = {"g": 1, "y": 2, "x": 3}.get(mark, 8)
        return self.pair(base) | curses.A_BOLD

    # -- drawing helpers --------------------------------------------------
    def put(self, y: int, text: str, attr: int = 0, x: int | None = None):
        _, w = self.stdscr.getmaxyx()
        if x is None:
            x = max(0, (w - len(text)) // 2)
        try:
            self.stdscr.addstr(y, x, text, attr)
        except curses.error:
            pass  # bottom-right corner raises; harmless

    def put_rainbow(self, y: int, text: str, x: int | None = None):
        _, w = self.stdscr.getmaxyx()
        if x is None:
            x = max(0, (w - len(text)) // 2)
        rainbow = [4, 7, 9, 6, 5]
        cx = x
        for i, ch in enumerate(text):
            if ch == " ":
                cx += 1
                continue
            attr = self.pair(rainbow[i % len(rainbow)]) | curses.A_BOLD
            try:
                self.stdscr.addstr(y, cx, ch, attr)
            except curses.error:
                pass
            cx += 1

    # -- game state -------------------------------------------------------
    def reset_game(self):
        d = DIFFICULTIES[self.difficulty]
        self.secret = random.choice(WORDS)
        self.tries_allowed = d["tries"]
        self.hints_left = d["hints"]
        self.hard_mode = d["hard"] or self.hard_override
        self.guesses = []          # list of (word, marks)
        self.current = ""
        self.used = {}             # letter -> best mark
        self.mode = "playing"
        self.message = ""
        self.msg_attr = 0
        self.hints_used = 0
        self.undos_used = 0
        self.clue = ["_"] * WORD_LEN
        self.hinted = set()

    def hard_ok(self, guess: str):
        """Hard mode: guess must respect every revealed hint so far."""
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
        for i, c in enumerate(guess):
            if i in green_at and green_at[i] != c:
                return False, f"Position {i + 1} must be {green_at[i].upper()}."
        counts = {}
        for c in guess:
            counts[c] = counts.get(c, 0) + 1
        for c, need in must_have.items():
            if counts.get(c, 0) < need:
                return False, f"Must use {c.upper()} at least {need} time(s)."
        for c in guess:
            if self.used.get(c) == "x":
                return False, f"{c.upper()} is not in the word."
        return True, ""

    def submit_guess(self):
        guess = self.current
        if len(guess) != WORD_LEN:
            self.message, self.msg_attr = "Not enough letters", self.pair(5) | curses.A_BOLD
            return
        ok, why = self.hard_ok(guess)
        if not ok:
            self.message, self.msg_attr = why, self.pair(5) | curses.A_BOLD
            return
        marks = score(self.secret, guess)
        self.guesses.append((guess, marks))
        # flip the tiles one by one
        for reveal in range(1, 6):
            self.draw_game(reveal)
            curses.napms(140)
        for ch, m in zip(guess, marks):
            if ch not in self.used or RANK[m] > RANK[self.used[ch]]:
                self.used[ch] = m
        self.current = ""
        if guess == self.secret:
            self.mode = "won"
            self.stats.record(True, len(self.guesses), self.hard_mode, self.hints_used, self.undos_used)
            praise = ["Genius!", "Magnificent!", "Splendid!", "Impressive!", "Great!", "Phew!"]
            self.message = f"{praise[min(len(self.guesses) - 1, 5)]} Solved in {len(self.guesses)}!"
            self.msg_attr = self.pair(6) | curses.A_BOLD
        elif len(self.guesses) == self.tries_allowed:
            self.mode = "lost"
            self.stats.record(False, None, self.hard_mode, self.hints_used, self.undos_used)
            self.message = f"Out of tries. The word was {self.secret.upper()}."
            self.msg_attr = self.pair(5) | curses.A_BOLD

    def do_hint(self):
        if self.hints_left <= 0:
            self.message, self.msg_attr = "No hints left.", self.pair(5) | curses.A_BOLD
            return
        avail = [i for i in range(WORD_LEN) if i not in self.hinted]
        if not avail:
            self.message, self.msg_attr = "Every position already revealed.", self.pair(5) | curses.A_BOLD
            return
        i = random.choice(avail)
        self.hinted.add(i)
        self.hints_left -= 1
        self.hints_used += 1
        self.clue[i] = self.secret[i]
        self.message = f"Hint: position {i + 1} is {self.secret[i].upper()}!"
        self.msg_attr = self.pair(7) | curses.A_BOLD

    def do_undo(self):
        if self.mode != "playing":
            return
        if not self.guesses:
            self.message, self.msg_attr = "Nothing to undo.", self.pair(5) | curses.A_BOLD
            return
        if self.undos_used >= 1:
            self.message, self.msg_attr = "No undos left this game.", self.pair(5) | curses.A_BOLD
            return
        self.guesses.pop()
        self.used = {}
        for word, marks in self.guesses:
            for c, m in zip(word, marks):
                if c not in self.used or RANK[m] > RANK[self.used[c]]:
                    self.used[c] = m
        self.undos_used += 1
        self.message = "Undid last guess."
        self.msg_attr = self.pair(6) | curses.A_BOLD

    # -- screens ----------------------------------------------------------
    def draw_menu(self):
        self.stdscr.erase()
        h, w = self.stdscr.getmaxyx()
        self.put_rainbow(0, "W O R D   G U E S S")
        self.put(2, "Guess the secret word before you run out of tries.", self.pair(8) | curses.A_DIM)
        if self.stats.games:
            rate = self.stats.wins * 100 // max(1, self.stats.games)
            self.put(4, f"Played {self.stats.games}  ·  Won {self.stats.wins} ({rate}%)  ·  "
                        f"Streak {self.stats.streak} (best {self.stats.max_streak})",
                     self.pair(6) | curses.A_BOLD)
        opts = [("1 Play", 0), ("2 Stats", 1), ("3 Difficulty", 2), ("4 Quit", 3)]
        for i, (label, idx) in enumerate(opts):
            attr = self.pair(4) | curses.A_BOLD if idx == self.menu_sel else self.pair(9)
            self.put(7 + i, (">> " if idx == self.menu_sel else "   ") + label, attr)
        d = DIFFICULTIES[self.difficulty]
        self.put(13, f"Difficulty: {d['label']}  ({d['tries']} tries, {d['hints']} hint{'s' if d['hints'] != 1 else ''})",
                 self.pair(7) | curses.A_DIM)
        self.put(14, "Hard mode: " + ("ON" if self.hard_mode else "off"),
                 self.pair(5) if self.hard_mode else self.pair(8) | curses.A_DIM)
        self.put(h - 2, "Arrows to pick  ·  Enter to start  ·  Esc to quit",
                 self.pair(8) | curses.A_DIM)
        self.stdscr.refresh()

    def draw_stats(self):
        self.stdscr.erase()
        h, w = self.stdscr.getmaxyx()
        self.put_rainbow(0, "S T A T S")
        lines = [
            f"Games played : {self.stats.games}",
            f"Games won    : {self.stats.wins}",
            f"Win rate     : {self.stats.wins * 100 // max(1, self.stats.games)}%",
            f"Current streak: {self.stats.streak}   Best streak : {self.stats.max_streak}",
            f"Hard-mode wins: {self.stats.hard_wins}",
            f"Hints used   : {self.stats.total_hints}   Undos used   : {self.stats.total_undos}",
            "",
            "Win distribution:",
        ]
        for i, line in enumerate(lines):
            self.put(2 + i, line, self.pair(9) if i < 6 else 0)
        y = 2 + len(lines)
        for turn in range(1, 9):
            count = self.stats.distribution.get(str(turn), 0)
            bar = "█" * count
            self.put(y, f"  {turn}: {bar}  {count}", self.pair(6) if count else self.pair(8) | curses.A_DIM)
            y += 1
        self.put(h - 2, "Press any key to return", self.pair(8) | curses.A_DIM)
        self.stdscr.refresh()

    def draw_difficulty(self):
        self.stdscr.erase()
        self.put_rainbow(0, "D I F F I C U L T Y")
        self.put(2, "Pick a difficulty:", self.pair(4) | curses.A_BOLD)
        items = list(DIFFICULTIES.items())
        for i, (key, d) in enumerate(items):
            marker = ">> " if key == self.difficulty else "   "
            line = (f"{marker}{key} {d['label']:<8} {d['tries']} tries, "
                    f"{d['hints']} hint{'s' if d['hints'] != 1 else ''}")
            if d["hard"]:
                line += "   ·   hard mode forced"
            self.put(4 + i, line, self.pair(7) | curses.A_BOLD if key == self.difficulty else 0)
        y = 4 + len(items)
        self.put(y, f"Hard-mode override: {'ON' if self.hard_override else 'off'}  (press t to toggle)",
                 self.pair(5) if self.hard_override else self.pair(8) | curses.A_DIM)
        self.put(y + 2, "1/2/3 to pick  ·  Enter to start  ·  Esc to back",
                 self.pair(8) | curses.A_DIM)
        self.stdscr.refresh()

    def draw_game(self, reveal: int = 5):
        self.stdscr.erase()
        h, w = self.stdscr.getmaxyx()
        need_h = 3 + self.tries_allowed * 2 + 10
        if h < need_h or w < 44:
            self.put(0, "Terminal too small", self.pair(5) | curses.A_BOLD)
            self.put(1, f"Please resize to at least 44x{need_h}")
            self.stdscr.refresh()
            return
        self.put_rainbow(0, "W O R D   G U E S S")
        d = DIFFICULTIES[self.difficulty]
        self.put(1, f"{d['label']}  ·  hints left: {self.hints_left}  ·  "
                    f"streak: {self.stats.streak}", self.pair(9) | curses.A_DIM)
        x0 = (w - 29) // 2
        for r in range(self.tries_allowed):
            y = 3 + r * 2
            for c in range(WORD_LEN):
                x = x0 + c * 6
                if r < len(self.guesses):
                    word, marks = self.guesses[r]
                    fresh = r == len(self.guesses) - 1
                    shown = c < reveal if fresh else True
                    ch = word[c].upper() if shown else " "
                    attr = self.tile_attr(marks[c]) if shown else (curses.A_BOLD | curses.A_UNDERLINE)
                    self.put(y, f"  {ch}  ", attr, x)
                elif r == len(self.guesses) and self.mode == "playing" and c < len(self.current):
                    self.put(y, f"  {self.current[c].upper()}  ",
                             curses.A_BOLD | curses.A_UNDERLINE | self.pair(4), x)
                else:
                    if self.clue[c] != "_":
                        self.put(y, f"  {self.clue[c].upper()}  ", self.pair(7) | curses.A_BOLD, x)
                    else:
                        self.put(y, "  _  ", self.pair(8) | curses.A_DIM, x)
        y_clue = 3 + self.tries_allowed * 2
        self.put(y_clue, "Clue: " + " ".join(self.clue), self.pair(7) | curses.A_BOLD, x0)
        self.put(y_clue + 1, self.message, self.msg_attr, x0)

        y_kb = y_clue + 3
        for i, row in enumerate(["qwertyuiop", "asdfghjkl", "zxcvbnm"]):
            x = (w - (len(row) * 4 - 1)) // 2
            for j, ch in enumerate(row):
                attr = self.tile_attr(self.used[ch]) if ch in self.used else self.pair(8) | curses.A_DIM
                self.put(y_kb + i, f" {ch.upper()} ", attr, x + j * 4)

        if self.mode == "playing":
            help_text = "Enter: guess  Bksp: delete  H: hint  U: undo  Esc: menu"
        else:
            help_text = "Enter: play again  Esc: menu"
        self.put(y_kb + 4, help_text, self.pair(8) | curses.A_DIM)
        self.stdscr.refresh()

    # -- main loop --------------------------------------------------------
    ENTER_KEYS = (10, 13, curses.KEY_ENTER)
    BACK_KEYS = (8, 127, curses.KEY_BACKSPACE)

    def run(self):
        while True:
            if self.mode == "menu":
                self.draw_menu()
            elif self.mode == "stats":
                self.draw_stats()
            elif self.mode == "difficulty":
                self.draw_difficulty()
            else:
                self.draw_game()

            key = self.stdscr.getch()
            if key == curses.KEY_RESIZE:
                continue

            if self.mode == "menu":
                if key in (curses.KEY_UP, ord("k")):
                    self.menu_sel = (self.menu_sel - 1) % 4
                elif key in (curses.KEY_DOWN, ord("j")):
                    self.menu_sel = (self.menu_sel + 1) % 4
                elif key in (ord("1"), ord("2"), ord("3"), ord("4")):
                    self.menu_sel = key - ord("1")
                elif key in self.ENTER_KEYS:
                    if self.menu_sel == 0:
                        self.reset_game()
                    elif self.menu_sel == 1:
                        self.mode = "stats"
                    elif self.menu_sel == 2:
                        self.mode = "difficulty"
                    else:
                        return
                elif key == 27:
                    return

            elif self.mode == "stats":
                if key != curses.KEY_RESIZE:
                    self.mode = "menu"

            elif self.mode == "difficulty":
                if key in (ord("1"), ord("2"), ord("3")):
                    self.difficulty = list(DIFFICULTIES)[key - ord("1")]
                elif key in (ord("t"), ord("T")):
                    self.hard_override = not self.hard_override
                elif key in self.ENTER_KEYS:
                    self.reset_game()
                elif key == 27:
                    self.mode = "menu"

            elif self.mode in ("won", "lost"):
                if key in self.ENTER_KEYS:
                    self.reset_game()
                elif key == 27:
                    self.mode = "menu"

            elif self.mode == "playing":
                if key == 27:
                    self.mode = "menu"
                elif key in self.BACK_KEYS:
                    self.current = self.current[:-1]
                    self.message = ""
                elif key in self.ENTER_KEYS:
                    self.submit_guess()
                elif key in (ord("h"), ord("H")):
                    self.do_hint()
                elif key in (ord("u"), ord("U")):
                    self.do_undo()
                elif (97 <= key <= 122 or 65 <= key <= 90) and len(self.current) < WORD_LEN:
                    self.current += chr(key).lower()
                    self.message = ""


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
        # hard mode validation
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
        print("  " + render(guess, marks))
        print(keyboard(used))
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
        stats.games += 0  # no-op; play_plain records via stats.record
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
    try:
        if curses is None:
            raise ImportError("curses not available")
    except ImportError:
        print("The full-screen UI needs curses. On Windows it is built into Python 3.13+.")
        print("Starting plain text mode instead.\n")
        return main_plain()
    os.environ.setdefault("ESCDELAY", "25")  # make Esc respond instantly
    try:
        curses.wrapper(lambda stdscr: UI(stdscr).run())
    except curses.error as e:
        print(f"Could not start the full-screen UI ({e}). Starting plain text mode.\n")
        main_plain()


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
        # stats round-trip
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

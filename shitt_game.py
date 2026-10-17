#!/usr/bin/env python3
"""Word Guess: a Wordle-style game for the terminal.

Guess the secret 5-letter word in 6 tries.
  green  = right letter, right spot
  yellow = right letter, wrong spot
  grey   = letter not in the word (or already used up)

Run:  python wordgame.py
"""

import base64
import random
import sys
import zlib

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

GREEN, YELLOW, GREY, RESET = "\033[42;30m", "\033[43;30m", "\033[100;97m", "\033[0m"
MAX_TRIES = 6


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
    colors = {"g": GREEN, "y": YELLOW, "x": GREY}
    return " ".join(f"{colors[m]} {c.upper()} {RESET}" for c, m in zip(guess, marks))


def keyboard(used: dict[str, str]) -> str:
    colors = {"g": GREEN, "y": YELLOW, "x": GREY}
    rows = ["qwertyuiop", "asdfghjkl", "zxcvbnm"]
    lines = []
    for i, row in enumerate(rows):
        cells = [
            f"{colors[used[c]]} {c.upper()} {RESET}" if c in used else f" {c.upper()} "
            for c in row
        ]
        lines.append(" " * (i * 2) + "".join(cells))
    return "\n".join(lines)


def play() -> bool:
    secret = random.choice(WORDS)
    used: dict[str, str] = {}
    rank = {"x": 0, "y": 1, "g": 2}
    print("\nWORD GUESS: find the 5-letter word in 6 tries.\n")

    tries = 0
    while tries < MAX_TRIES:
        try:
            guess = input(f"Guess {tries + 1}/{MAX_TRIES}: ").strip().lower()
        except EOFError:
            print()
            return False
        if len(guess) != 5 or not guess.isalpha():
            print("  Enter exactly 5 letters.")
            continue
        tries += 1
        marks = score(secret, guess)
        for c, m in zip(guess, marks):
            if c not in used or rank[m] > rank[used[c]]:
                used[c] = m
        print("  " + render(guess, marks))
        print(keyboard(used) + "\n")
        if guess == secret:
            print(f"You got it in {tries}! The word was {secret.upper()}.")
            return True

    print(f"Out of tries. The word was {secret.upper()}.")
    return False


def main() -> None:
    wins = games = 0
    while True:
        games += 1
        wins += play()
        print(f"Record: {wins} won / {games} played")
        try:
            again = input("Play again? (y/n): ").strip().lower()
        except EOFError:
            break
        if again != "y":
            break
    print("THANKS FOR PLAYING!")
#this is a comment

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--selftest":
        assert score("crane", "crane") == list("ggggg")
        assert score("candy", "lolly") == list("xxxxg")
        assert score("apple", "paper") == list("yygyx")
        assert score("abbey", "babes") == list("yyggx")
        assert score("allee", "eagle") == list("yyxyg")
        # Repeated letter in guess, only one in secret: second 'r' must be grey.
        assert score("crane", "error") == list("ygxxx")
        assert all(len(w) == 5 and w.isalpha() for w in WORDS), "bad word in list"
        assert len(WORDS) == len(set(WORDS)), "duplicate words"
        print(f"selftest ok ({len(WORDS)} words)")
    else:
        main()

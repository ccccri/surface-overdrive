"""Word suggestions of the on-screen keyboard: the words the user typed before, then a word list of the system.

The keyboard sends keys and cannot see the text field, so it follows the word being typed by itself (Typing) and
forgets it whenever it can no longer know (a tap elsewhere, an arrow key). A suggestion replaces the letters typed so
far with backspaces. Words typed are counted in a file of the user, so that names and one's own words come first.
"""
import json
import os

SYSTEM_LISTS = ("/usr/share/dict/words",)
LEARN_LIMIT = 4000                 # words kept in the user's file
LETTERS = "abcdefghijklmnopqrstuvwxyzàáâäèéêëìíîïòóôöùúûüçñß'"


class Words:
    def __init__(self, user_file=None, lists=SYSTEM_LISTS):
        self.user_file = user_file
        self.counts = {}
        self._lists = lists
        self._system = None            # {two first letters: [words]}, read at the first question
        self.learning = True           # False: learn() keeps nothing (the app's setting; see app.DEFAULTS)
        if user_file:
            try:
                with open(user_file) as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    self.counts = {str(k): int(v) for k, v in data.items() if isinstance(v, int)}
            except (OSError, ValueError):
                pass

    def _load_system(self):
        self._system = {}
        for path in self._lists:
            try:
                with open(path, encoding="utf-8", errors="ignore") as f:
                    for line in f:
                        w = line.strip()
                        if 2 <= len(w) <= 24 and w.isalpha() and w.islower():
                            self._system.setdefault(w[:2], []).append(w)
            except OSError:
                continue

    def suggest(self, prefix, limit=3):
        """Up to `limit` words that begin with prefix: the user's own by how often they were typed, then the system's,
        the short ones first. Nothing for less than two letters."""
        p = prefix.lower()
        if len(p) < 2:
            return []
        mine = sorted((w for w in self.counts if w.startswith(p) and w != p), key=lambda w: (-self.counts[w], len(w), w))
        out = mine[:limit]
        if len(out) < limit:
            if self._system is None:
                self._load_system()
            rest = sorted((w for w in self._system.get(p[:2], ()) if w.startswith(p) and w != p and w not in out),
                          key=lambda w: (len(w), w))
            out += rest[:limit - len(out)]
        if prefix[:1].isupper():
            out = [w[:1].upper() + w[1:] for w in out]
        return out

    def learn(self, word):
        if not self.learning:
            return
        w = word.lower().strip("'")
        if len(w) < 3 or not all(c in LETTERS for c in w):
            return
        self.counts[w] = self.counts.get(w, 0) + 1

    def save(self):
        if not self.user_file:
            return
        keep = dict(sorted(self.counts.items(), key=lambda kv: -kv[1])[:LEARN_LIMIT])
        try:
            os.makedirs(os.path.dirname(self.user_file), exist_ok=True)
            tmp = self.user_file + ".new"
            with open(tmp, "w") as f:
                json.dump(keep, f)
            os.replace(tmp, self.user_file)
        except OSError:
            pass


class Typing:
    """What the keyboard knows of the text: the word being typed and whether a sentence starts. Each method answers
    with what has to be sent, as a list of ("text", str) and ("back", count)."""

    ENDS = ".!?"

    def __init__(self, words):
        self.words = words
        self.word = ""
        self.sentence_start = True     # the next letter is a capital
        self.last_space = False        # the last thing typed was a space after a word (a second one makes ". ")

    def suggestions(self):
        return self.words.suggest(self.word) if self.word else []

    def text(self, s):
        out = []
        for c in s:
            if c == " " and self.last_space:
                out += [("back", 1), ("text", ". ")]        # two spaces: a full stop
                self.last_space, self.sentence_start = False, True
                continue
            out.append(("text", c))
            if c.lower() in LETTERS and c != "'" or (c == "'" and self.word):
                self.word += c
                self.sentence_start = self.last_space = False
            else:
                if self.word:
                    self.words.learn(self.word)
                self.last_space = c == " " and bool(self.word)
                self.word = ""
                if c in self.ENDS or c == "\n":
                    self.sentence_start = True
                elif c != " ":
                    self.sentence_start = False
        return out

    def backspace(self):
        self.word = self.word[:-1]
        self.last_space = False
        return [("back", 1)]

    def pick(self, suggestion):
        """A suggestion in place of the letters typed so far, with a space after it."""
        out = [("back", len(self.word)), ("text", suggestion + " ")]
        self.words.learn(suggestion)
        self.word, self.last_space, self.sentence_start = "", True, False
        return out

    def forget(self):
        """Something happened that the keyboard cannot follow (an arrow, a shortcut, a tap in the text)."""
        self.word, self.last_space = "", False

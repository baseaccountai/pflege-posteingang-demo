"""Layer 3 of the prompt-injection protection: content goes into prompts as marked data
(F05-AC9, F07-AC8). A text must not be able to close its own markers - "</quelle>" inside a
document would otherwise end the data part, and what follows would read like instructions.
"""

import re


def defuse(text: str, tags: tuple[str, ...]) -> str:
    """ "</abschnitt>" in a text becomes "‹/abschnitt>": still readable, no marker any more."""
    pattern = re.compile(r"</?\s*(" + "|".join(map(re.escape, tags)) + r")\b", re.IGNORECASE)
    return pattern.sub(lambda m: "‹" + m.group(0)[1:], text)

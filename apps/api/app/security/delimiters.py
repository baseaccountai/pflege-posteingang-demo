"""Layer 3 of the prompt-injection protection: content goes into prompts as marked data
(F05-AC9, F07-AC8). A text must not be able to close its own markers - "</quelle>" inside a
document would otherwise end the data part, and what follows would read like instructions.
"""

import re


def defuse(text: str, tags: tuple[str, ...]) -> str:
    """ "</abschnitt>" (also "< /abschnitt>") becomes "‹/abschnitt>": readable, no marker."""
    pattern = re.compile(r"<\s*/?\s*(" + "|".join(map(re.escape, tags)) + r")\b", re.IGNORECASE)
    return pattern.sub(lambda m: "‹" + m.group(0)[1:], text)


def defuse_markers(text: str, markers: tuple[str, ...]) -> str:
    """For fixed text markers like "DOKUMENT>>>": the arrows become "›››"/"‹‹‹"."""
    for marker in markers:
        safe = marker.replace(">", "›").replace("<", "‹")
        text = re.sub(re.escape(marker), safe, text, flags=re.IGNORECASE)
    return text

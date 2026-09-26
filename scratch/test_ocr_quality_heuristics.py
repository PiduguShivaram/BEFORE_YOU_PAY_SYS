import re

tokens = [
    "OTA",
    "C",
    "0dAe",
    "A",
    "0",
    "000",
    "0d/q/ex",
    "S0",
    "00b",
    "Posted",
    "in",
    "r/CarsIndia",
    "reddit",
]


def is_garbage_token(tok: str) -> bool:
    t = tok.strip(".,:;()[]\"'")
    if not t:
        return False
    # If pure digits or standard currency like ₹100, $20, 100.00
    if re.match(r"^[\$€£₹¥]?\d+(?:[.,]\d+)?%?$", t):
        return False
    # Slashes with digits and letters: 0d/q/ex
    if "/" in t or "\\" in t or "|" in t:
        if any(c.isdigit() for c in t) and any(c.isalpha() for c in t):
            return True
        if len(t) > 3 and not re.match(r"^\d{1,4}[/-]\d{1,2}[/-]\d{1,4}$", t):  # not a date
            return True
    # Mixed digits and letters that are not standard (e.g. 0dAe, 00b, S0)
    has_digit = any(c.isdigit() for c in t)
    has_alpha = any(c.isalpha() for c in t)
    if has_digit and has_alpha:
        # allow standard ordinals and units: 1st, 2nd, 3rd, 4th, 5kg, 10ml, 4g, 5g, 3d, etc.
        if re.match(r"^\d+(st|nd|rd|th|kg|g|ml|l|km|m|cm|mm|pcs|nos|pk|hr|hrs|min|sec)$", t, re.I):
            return False
        if re.match(r"^(a4|h4|h7|5g|4g|3d|2d|b2b)$", t, re.I):
            return False
        return True
    # Non-vowel consonant strings length >= 4
    if len(t) >= 4 and not any(c in "aeiouAEIOU" for c in t) and not t.isdigit():
        return True
    # Symbols burst: e.g. ??!!, ---, ===
    if len(t) >= 2 and all(not c.isalnum() for c in t):
        return True
    return False


garbage_count = 0
for t in tokens:
    g = is_garbage_token(t)
    if g:
        garbage_count += 1
    print(f"{t:15} -> garbage: {g}")
print(
    f"Total tokens: {len(tokens)}, Garbage: {garbage_count}, Ratio: {garbage_count / len(tokens):.2f}"
)

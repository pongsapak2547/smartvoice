import re


def has_thai(text: str, min_ratio: float = 0.25) -> bool:
    """Check if text contains enough Thai characters to be considered valid Thai."""
    text = text.strip()
    if not text:
        return False
    thai_chars = len(re.findall(r'[\u0E00-\u0E7F]', text))
    non_space = len(re.findall(r'\S', text))
    if non_space == 0:
        return False
    return (thai_chars / non_space) >= min_ratio

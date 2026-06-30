def truncate(value: str, max_len: int = 80) -> str:
    """Return a single-line, length-limited string safe for logs."""
    text = " ".join(str(value).split())
    if len(text) <= max_len:
        return text
    return f"{text[:max_len]}… ({len(text)} chars)"

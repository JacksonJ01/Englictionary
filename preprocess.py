import re


NOISE_PATTERN = re.compile(r"[^a-z0-9\s'\-]+")
TOKEN_SPLIT_PATTERN = re.compile(r"[^a-z]+")


def normalize_pos(pos: str) -> str:
    normalized = (pos or "").strip().lower()
    tokens = {token for token in TOKEN_SPLIT_PATTERN.split(normalized) if token}

    if "adverb" in tokens or "adv" in tokens:
        return "adverb"
    if "adjective" in tokens or "adj" in tokens or tokens == {"a"}:
        return "adjective"
    if "verb" in tokens or tokens == {"v"}:
        return "verb"
    if "noun" in tokens or tokens == {"n"}:
        return "noun"
    return "other"


def _clean_definition(text: str) -> str:
    lowered = (text or "").strip().lower()
    cleaned = NOISE_PATTERN.sub(" ", lowered)
    return re.sub(r"\s+", " ", cleaned).strip()


def clean_text(df):
    cleaned_df = df.copy()
    cleaned_df["Word"] = cleaned_df["Word"].fillna("").astype(str).str.strip()
    cleaned_df["POS"] = cleaned_df["POS"].fillna("").astype(str).str.strip().str.lower()
    cleaned_df["Definition"] = cleaned_df["Definition"].fillna("").astype(str).map(_clean_definition)
    cleaned_df["pos_group"] = cleaned_df["POS"].map(normalize_pos)
    cleaned_df.attrs.update(df.attrs)
    return cleaned_df

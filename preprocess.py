import re


NOISE_PATTERN = re.compile(r"[^a-z0-9\s'\-]+")


def _clean_definition(text: str) -> str:
    lowered = (text or "").strip().lower()
    cleaned = NOISE_PATTERN.sub(" ", lowered)
    return re.sub(r"\s+", " ", cleaned).strip()


def clean_text(df):
    cleaned_df = df.copy()

    term_column = "Term" if "Term" in cleaned_df.columns else "Word"
    cleaned_df["Term"] = cleaned_df[term_column].fillna("").astype(str).str.strip()
    cleaned_df["Word"] = cleaned_df["Term"]
    cleaned_df["Definition"] = cleaned_df["Definition"].fillna("").astype(str).map(_clean_definition)
    cleaned_df.attrs.update(df.attrs)
    return cleaned_df

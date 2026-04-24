import re

from sklearn.feature_extraction.text import TfidfVectorizer

from config import EMBEDDING_MODEL, MAX_FEATURES


def tokenizer(text):
    return re.findall(r"[a-z]{2,}", text.lower())


def vectorize_tfidf(df):
    vectorizer = TfidfVectorizer(
        tokenizer=tokenizer,
        token_pattern=None,
        lowercase=False,
        max_features=MAX_FEATURES,
    )
    return vectorizer.fit_transform(df["Definition"])


def vectorize_embeddings(df):
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer(EMBEDDING_MODEL)
    return model.encode(df["Definition"].tolist(), show_progress_bar=True)

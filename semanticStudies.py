from pathlib import Path

import pandas as pd
import re

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import MiniBatchKMeans
from sklearn.decomposition import PCA

import plotly.express as px
import umap
from sentence_transformers import SentenceTransformer
# OPTIONAL: only needed if using embeddings
USE_EMBEDDINGS = False

# ----------------------------
# USER SETTINGS (EDIT THESE)
# ----------------------------
FILE_PATH = str(Path(__file__).with_name("csv").joinpath("dictionary.csv"))

DIMENSIONS = 2      # choose 2 or 3
N_CLUSTERS = 20     # adjust based on dataset size
USE_UMAP = False    # better structure, slower

# ----------------------------
# 1. LOAD DATA
# ----------------------------
df = pd.read_csv(FILE_PATH)
source_columns = list(df.columns)
word_column = source_columns[0]
definition_column = source_columns[1] if len(source_columns) > 1 else source_columns[0]

df["Term"] = df[word_column].astype(str).str.strip()
df["Definition"] = df[definition_column].fillna("").astype(str).str.strip()

# ----------------------------
# 3. TOKENIZER
# ----------------------------
def tokenizer(text):
    return re.findall(r"[a-z]{2,}", text.lower())

# ----------------------------
# 4. VECTORIZATION
# ----------------------------
if USE_EMBEDDINGS:
    print("Using embeddings...")
    model = SentenceTransformer('all-MiniLM-L6-v2')
    X = model.encode(df["Definition"].tolist(), show_progress_bar=True)

else:
    print("Using TF-IDF...")
    vectorizer = TfidfVectorizer(
        tokenizer=tokenizer,
        max_features=5000
    )
    X = vectorizer.fit_transform(df["Definition"])

    # Convert sparse → dense for PCA
    X = X.toarray()

# ----------------------------
# 5. CLUSTERING
# ----------------------------
print("Clustering...")
kmeans = MiniBatchKMeans(n_clusters=N_CLUSTERS, random_state=42)
df["cluster"] = kmeans.fit_predict(X)

# ----------------------------
# 6. DIMENSION REDUCTION
# ----------------------------
print(f"Reducing to {DIMENSIONS}D...")

if USE_UMAP:
    reducer = umap.UMAP(n_components=DIMENSIONS, random_state=42)
    coords = reducer.fit_transform(X)

else:
    pca = PCA(n_components=DIMENSIONS)
    coords = pca.fit_transform(X)

# Assign coordinates
df["x"] = coords[:, 0]
df["y"] = coords[:, 1]

if DIMENSIONS == 3:
    df["z"] = coords[:, 2]

# ----------------------------
# 7. VISUALIZATION
# ----------------------------
print("Rendering visualization...")

if DIMENSIONS == 2:
    fig = px.scatter(
        df,
        x="x",
        y="y",
        color=df["cluster"].astype(str),
        hover_data=[column for column in ["Term", "Definition"] if column in df.columns],
        title="Dictionary Semantic Map (2D)"
    )

elif DIMENSIONS == 3:
    fig = px.scatter_3d(
        df,
        x="x",
        y="y",
        z="z",
        color=df["cluster"].astype(str),
        hover_data=[column for column in ["Term", "Definition"] if column in df.columns],
        title="Dictionary Semantic Map (3D)"
    )

fig.show()

# ----------------------------
# 8. SAVE OUTPUT
# ----------------------------
output_file = f"dictionary_visualized_{DIMENSIONS}d.csv"
df.to_csv(output_file, index=False)

print(f"Saved to {output_file}")
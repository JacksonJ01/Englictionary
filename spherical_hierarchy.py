import numpy as np
import pandas as pd
from scipy import sparse
from sklearn.cluster import MiniBatchKMeans
from sklearn.metrics.pairwise import cosine_similarity

from config import RANDOM_STATE


def _to_dense_vector(value):
    if sparse.issparse(value):
        return np.asarray(value.toarray()).ravel()
    return np.asarray(value).ravel()


def _mean_vector(X, row_indices):
    if len(row_indices) == 0:
        raise ValueError("Cannot compute centroid for empty index list")
    return _to_dense_vector(X[row_indices].mean(axis=0))


def _cluster_or_singleton(X_subset, requested_clusters, minimum_cluster_size):
    sample_count = X_subset.shape[0]
    if sample_count <= 1:
        return np.zeros(sample_count, dtype=int), 1

    cluster_limit = max(1, sample_count // max(1, minimum_cluster_size))
    cluster_count = min(requested_clusters, sample_count, max(2, cluster_limit))
    if cluster_count <= 1:
        return np.zeros(sample_count, dtype=int), 1

    model = MiniBatchKMeans(n_clusters=cluster_count, random_state=RANDOM_STATE, n_init="auto")
    return model.fit_predict(X_subset), cluster_count


def _representative_word(df, X, member_indices, centroid_vector):
    if len(member_indices) == 0:
        return ""

    similarities = cosine_similarity(X[member_indices], centroid_vector.reshape(1, -1)).ravel()
    best_position = int(np.argmax(similarities))
    best_index = int(member_indices[best_position])
    word = str(df.at[best_index, "Word"]).strip()
    return word if word else f"word_{best_index}"


def build_spherical_hierarchy(
    df,
    X,
    top_clusters,
    subclusters_per_cluster,
    minimum_subcluster_size,
    secondary_memberships,
):
    sample_count = X.shape[0]
    top_cluster_count = min(max(2, top_clusters), sample_count)

    top_model = MiniBatchKMeans(
        n_clusters=top_cluster_count,
        random_state=RANDOM_STATE,
        n_init="auto",
    )
    top_labels = top_model.fit_predict(X)

    hierarchy_rows = []
    centroid_lookup = {}
    top_id_map = {}

    for top_label in range(top_cluster_count):
        top_node_id = f"T{top_label}"
        top_indices = np.flatnonzero(top_labels == top_label)
        if len(top_indices) == 0:
            continue

        centroid_lookup[top_node_id] = _mean_vector(X, top_indices)
        representative = _representative_word(df, X, top_indices, centroid_lookup[top_node_id])
        top_id_map[top_label] = top_node_id
        hierarchy_rows.append(
            {
                "node_id": top_node_id,
                "parent_id": "ROOT",
                "depth": 0,
                "node_type": "cluster",
                "label": f"{representative}",
                "display_name": f"Cluster {top_label}: {representative}",
                "size": int(len(top_indices)),
                "word_index": pd.NA,
                "top_cluster": top_node_id,
                "subcluster": pd.NA,
            }
        )

    sub_lookup = {}
    for top_label, top_node_id in top_id_map.items():
        top_indices = np.flatnonzero(top_labels == top_label)
        sub_labels, sub_count = _cluster_or_singleton(
            X[top_indices],
            requested_clusters=subclusters_per_cluster,
            minimum_cluster_size=minimum_subcluster_size,
        )

        for sub_label in range(sub_count):
            member_mask = sub_labels == sub_label
            member_indices = top_indices[member_mask]
            if len(member_indices) == 0:
                continue

            sub_node_id = f"{top_node_id}_S{sub_label}"
            sub_lookup[(top_label, sub_label)] = sub_node_id
            centroid_lookup[sub_node_id] = _mean_vector(X, member_indices)
            representative = _representative_word(df, X, member_indices, centroid_lookup[sub_node_id])

            hierarchy_rows.append(
                {
                    "node_id": sub_node_id,
                    "parent_id": top_node_id,
                    "depth": 1,
                    "node_type": "subcluster",
                    "label": f"{representative}",
                    "display_name": f"Subcluster {top_label}.{sub_label}: {representative}",
                    "size": int(len(member_indices)),
                    "word_index": pd.NA,
                    "top_cluster": top_node_id,
                    "subcluster": sub_node_id,
                }
            )

            for row_index in member_indices:
                word_node_id = f"W{int(row_index)}"
                hierarchy_rows.append(
                    {
                        "node_id": word_node_id,
                        "parent_id": sub_node_id,
                        "depth": 2,
                        "node_type": "word",
                        "label": str(df.at[row_index, "Word"]),
                        "display_name": str(df.at[row_index, "Word"]),
                        "size": 1,
                        "word_index": int(row_index),
                        "top_cluster": top_node_id,
                        "subcluster": sub_node_id,
                    }
                )

    hierarchy_df = pd.DataFrame(hierarchy_rows)

    top_centroid_matrix = np.vstack([centroid_lookup[top_id_map[idx]] for idx in sorted(top_id_map.keys())])
    similarities = cosine_similarity(X, top_centroid_matrix)
    requested_secondary = max(0, min(secondary_memberships, top_centroid_matrix.shape[0] - 1))

    secondary_rows = []
    if requested_secondary > 0:
        for row_index in range(similarities.shape[0]):
            primary_label = int(top_labels[row_index])
            sorted_candidates = np.argsort(similarities[row_index])[::-1]
            count = 0
            for candidate_label in sorted_candidates:
                candidate_label = int(candidate_label)
                if candidate_label == primary_label:
                    continue
                secondary_rows.append(
                    {
                        "word_node_id": f"W{row_index}",
                        "primary_cluster_id": top_id_map[primary_label],
                        "secondary_cluster_id": top_id_map[candidate_label],
                        "weight": float(similarities[row_index, candidate_label]),
                    }
                )
                count += 1
                if count >= requested_secondary:
                    break

    secondary_df = pd.DataFrame(secondary_rows)
    return hierarchy_df, secondary_df, centroid_lookup

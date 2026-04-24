import numpy as np
import pandas as pd
from scipy import sparse
from sklearn.decomposition import PCA, TruncatedSVD

import umap

from config import (
    RANDOM_STATE,
    SPHERE_PATCH_RADIUS_SUB,
    SPHERE_PATCH_RADIUS_WORD,
    SPHERE_SUB_RADIUS,
    SPHERE_TOP_RADIUS,
    SPHERE_WORD_RADIUS,
    UMAP_MIN_DIST,
    UMAP_N_NEIGHBORS,
    UMAP_SPREAD,
)


def _reduce_to_3d(matrix):
    sample_count = matrix.shape[0]
    if sample_count <= 1:
        return np.zeros((sample_count, 3), dtype=float)

    if sample_count >= 5:
        reducer = umap.UMAP(
            n_components=3,
            n_neighbors=min(UMAP_N_NEIGHBORS, sample_count - 1),
            min_dist=UMAP_MIN_DIST,
            spread=UMAP_SPREAD,
            random_state=RANDOM_STATE,
        )
        return reducer.fit_transform(matrix)

    if sparse.issparse(matrix):
        reducer = TruncatedSVD(n_components=min(3, sample_count - 1), random_state=RANDOM_STATE)
        reduced = reducer.fit_transform(matrix)
    else:
        reducer = PCA(n_components=min(3, sample_count - 1), random_state=RANDOM_STATE)
        reduced = reducer.fit_transform(np.asarray(matrix))

    if reduced.shape[1] < 3:
        padded = np.zeros((reduced.shape[0], 3), dtype=float)
        padded[:, : reduced.shape[1]] = reduced
        return padded
    return reduced


def _normalize_rows(matrix):
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return matrix / norms


def _reduce_local_to_2d(matrix):
    sample_count = matrix.shape[0]
    if sample_count <= 1:
        return np.zeros((sample_count, 2), dtype=float)

    if sparse.issparse(matrix):
        reducer = TruncatedSVD(n_components=min(2, sample_count - 1), random_state=RANDOM_STATE)
        reduced = reducer.fit_transform(matrix)
    else:
        reducer = PCA(n_components=min(2, sample_count - 1), random_state=RANDOM_STATE)
        reduced = reducer.fit_transform(np.asarray(matrix))

    if reduced.shape[1] < 2:
        padded = np.zeros((reduced.shape[0], 2), dtype=float)
        padded[:, : reduced.shape[1]] = reduced
        return padded
    return reduced


def _tangent_basis(unit_vector):
    reference = np.array([0.0, 0.0, 1.0])
    if abs(float(np.dot(unit_vector, reference))) > 0.95:
        reference = np.array([0.0, 1.0, 0.0])

    basis_1 = np.cross(unit_vector, reference)
    basis_1 /= np.linalg.norm(basis_1)
    basis_2 = np.cross(unit_vector, basis_1)
    basis_2 /= np.linalg.norm(basis_2)
    return basis_1, basis_2


def _local_patch_positions(parent_position, child_vectors, child_radius, patch_radius):
    if len(child_vectors) == 0:
        return np.zeros((0, 3), dtype=float)

    child_matrix = np.vstack(child_vectors)
    reduced = _reduce_local_to_2d(child_matrix)
    if reduced.size == 0:
        reduced = np.zeros((len(child_vectors), 2), dtype=float)

    norms = np.linalg.norm(reduced, axis=1)
    max_norm = float(np.max(norms)) if len(norms) else 1.0
    if max_norm <= 0:
        max_norm = 1.0
    reduced = (reduced / max_norm) * patch_radius

    parent_unit = parent_position / np.linalg.norm(parent_position)
    basis_1, basis_2 = _tangent_basis(parent_unit)

    positions = []
    for offset_1, offset_2 in reduced:
        candidate = parent_unit + basis_1 * float(offset_1) + basis_2 * float(offset_2)
        candidate /= np.linalg.norm(candidate)
        positions.append(candidate * child_radius)
    return np.vstack(positions)


def project_spherical_layout(hierarchy_df, centroid_lookup, X):
    top_nodes = hierarchy_df[hierarchy_df["depth"] == 0].copy()
    top_ids = top_nodes["node_id"].tolist()
    top_centroids = np.vstack([centroid_lookup[node_id] for node_id in top_ids])
    top_reduced = _reduce_to_3d(top_centroids)
    top_positions = _normalize_rows(top_reduced) * SPHERE_TOP_RADIUS

    position_map = {node_id: top_positions[index] for index, node_id in enumerate(top_ids)}

    sub_nodes = hierarchy_df[hierarchy_df["depth"] == 1].copy()
    for top_id in top_ids:
        child_ids = sub_nodes[sub_nodes["parent_id"] == top_id]["node_id"].tolist()
        child_vectors = [centroid_lookup[child_id] for child_id in child_ids]
        if not child_ids:
            continue
        child_positions = _local_patch_positions(
            parent_position=position_map[top_id],
            child_vectors=child_vectors,
            child_radius=SPHERE_SUB_RADIUS,
            patch_radius=SPHERE_PATCH_RADIUS_SUB,
        )
        for child_id, child_position in zip(child_ids, child_positions):
            position_map[child_id] = child_position

    word_nodes = hierarchy_df[hierarchy_df["depth"] == 2].copy()
    for sub_id in sub_nodes["node_id"].tolist():
        child_rows = word_nodes[word_nodes["parent_id"] == sub_id]
        child_ids = child_rows["node_id"].tolist()
        if not child_ids:
            continue

        child_vectors = [np.asarray(X[int(row_index)].toarray()).ravel() if sparse.issparse(X) else np.asarray(X[int(row_index)]) for row_index in child_rows["word_index"].tolist()]
        child_positions = _local_patch_positions(
            parent_position=position_map[sub_id],
            child_vectors=child_vectors,
            child_radius=SPHERE_WORD_RADIUS,
            patch_radius=SPHERE_PATCH_RADIUS_WORD,
        )
        for child_id, child_position in zip(child_ids, child_positions):
            position_map[child_id] = child_position

    coordinate_rows = []
    for _, row in hierarchy_df.iterrows():
        node_id = row["node_id"]
        position = position_map.get(node_id)
        if position is None:
            continue
        coordinate_rows.append(
            {
                "node_id": node_id,
                "parent_id": row["parent_id"],
                "depth": int(row["depth"]),
                "node_type": row["node_type"],
                "label": row["label"],
                "display_name": row.get("display_name", row["label"]),
                "size": int(row["size"]),
                "top_cluster": row["top_cluster"],
                "subcluster": row["subcluster"],
                "word_index": row["word_index"],
                "x": float(position[0]),
                "y": float(position[1]),
                "z": float(position[2]),
            }
        )

    return pd.DataFrame(coordinate_rows)

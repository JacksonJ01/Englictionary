import math

import numpy as np
import pandas as pd

from cluster import cluster_data
from config import (
    SPHERE_CLUSTER_ANGULAR_PADDING,
    SPHERE_CLUSTER_COUNT,
    SPHERE_CLUSTER_MAX_ANGULAR_RADIUS,
    SPHERE_CLUSTER_REPEL_STEPS,
    SPHERE_INCLUDE_DEFINITION_IN_HTML,
    SPHERE_NODE_ANGULAR_SPACING,
)
from reduce_dim import reduce_dimensions


def _normalize_rows(matrix):
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return matrix / norms


def _tangent_basis(unit_vector):
    reference = np.array([0.0, 0.0, 1.0])
    if abs(float(np.dot(unit_vector, reference))) > 0.95:
        reference = np.array([0.0, 1.0, 0.0])

    basis_1 = np.cross(unit_vector, reference)
    basis_1 /= np.linalg.norm(basis_1)
    basis_2 = np.cross(unit_vector, basis_1)
    basis_2 /= np.linalg.norm(basis_2)
    return basis_1, basis_2


def _cluster_patch_radius(cluster_size):
    radius = SPHERE_CLUSTER_ANGULAR_PADDING + SPHERE_NODE_ANGULAR_SPACING * math.sqrt(max(1, cluster_size))
    return min(radius, SPHERE_CLUSTER_MAX_ANGULAR_RADIUS)


def _cluster_members(labels, cluster_count):
    for cluster_id in range(cluster_count):
        indices = np.flatnonzero(labels == cluster_id)
        if len(indices) > 0:
            yield cluster_id, indices


def _repel_centers(center_vectors, angular_radii):
    centers = center_vectors.copy()

    for _ in range(SPHERE_CLUSTER_REPEL_STEPS):
        moved = False
        for i in range(len(centers)):
            for j in range(i + 1, len(centers)):
                dot = float(np.dot(centers[i], centers[j]))
                dot = max(-1.0, min(1.0, dot))
                angle = math.acos(dot)
                target = angular_radii[i] + angular_radii[j]

                if angle >= target:
                    continue

                moved = True
                overlap = target - angle + 1e-4
                direction = centers[i] - centers[j]
                norm = np.linalg.norm(direction)
                if norm < 1e-9:
                    direction = np.array([1.0, 0.0, 0.0])
                    norm = 1.0
                direction /= norm

                centers[i] = centers[i] + direction * (overlap * 0.5)
                centers[j] = centers[j] - direction * (overlap * 0.5)
                centers[i] /= np.linalg.norm(centers[i])
                centers[j] /= np.linalg.norm(centers[j])

        if not moved:
            break

    return centers


def _sunflower_patch(center_vector, count, angular_radius):
    if count <= 0:
        return np.zeros((0, 3), dtype=float)

    basis_1, basis_2 = _tangent_basis(center_vector)
    golden_angle = math.pi * (3.0 - math.sqrt(5.0))

    points = np.zeros((count, 3), dtype=float)
    for i in range(count):
        radial = angular_radius * math.sqrt((i + 0.5) / count)
        theta = i * golden_angle
        offset = basis_1 * (radial * math.cos(theta)) + basis_2 * (radial * math.sin(theta))
        candidate = center_vector + offset
        candidate /= np.linalg.norm(candidate)
        points[i] = candidate
    return points


def build_spherical_surface_points(df, X, use_umap):
    sample_count = X.shape[0]
    requested_clusters = min(max(2, SPHERE_CLUSTER_COUNT), sample_count)
    labels = cluster_data(X, requested_clusters)

    cluster_vectors = []
    cluster_ids = []
    cluster_sizes = []

    for cluster_id, member_indices in _cluster_members(labels, requested_clusters):
        centroid = np.asarray(X[member_indices].mean(axis=0)).ravel()
        cluster_vectors.append(centroid)
        cluster_ids.append(cluster_id)
        cluster_sizes.append(len(member_indices))

    centroid_matrix = np.vstack(cluster_vectors)
    reduced = reduce_dimensions(centroid_matrix, 3, use_umap)
    centers = _normalize_rows(reduced)

    angular_radii = np.array([_cluster_patch_radius(size) for size in cluster_sizes], dtype=float)
    centers = _repel_centers(centers, angular_radii)

    cluster_center_map = {cluster_id: centers[idx] for idx, cluster_id in enumerate(cluster_ids)}
    cluster_radius_map = {cluster_id: angular_radii[idx] for idx, cluster_id in enumerate(cluster_ids)}

    rows = []
    term_column = "Term" if "Term" in df.columns else "Word"
    detail_columns = [column for column in df.attrs.get("detail_columns", ()) if column in df.columns]
    for cluster_id, member_indices in _cluster_members(labels, requested_clusters):
        center = cluster_center_map[cluster_id]
        patch_radius = cluster_radius_map[cluster_id]
        local_points = _sunflower_patch(center, len(member_indices), patch_radius)

        for row_index, point in zip(member_indices, local_points):
            definition = str(df.at[row_index, "Definition"])
            row_payload = {
                "node_id": f"W{int(row_index)}",
                "word": str(df.at[row_index, term_column]),
                "definition": definition if SPHERE_INCLUDE_DEFINITION_IN_HTML else "",
                "cluster": int(cluster_id),
                "x": float(point[0]),
                "y": float(point[1]),
                "z": float(point[2]),
            }
            for column in detail_columns:
                value = df.at[row_index, column]
                row_payload[column] = "" if pd.isna(value) else value
            rows.append(row_payload)

    surface_df = pd.DataFrame(rows)

    surface_df.attrs.update(df.attrs)
    surface_df.attrs["detail_columns"] = tuple(detail_columns)
    return surface_df

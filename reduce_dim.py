import numpy as np
from scipy import sparse
from sklearn.decomposition import PCA, TruncatedSVD

import umap

from config import (
    COORDINATE_SCALE,
    RANDOM_STATE,
    UMAP_MIN_DIST,
    UMAP_N_NEIGHBORS,
    UMAP_SPREAD,
)


def _scale_coordinates(coordinates):
    centered = coordinates - np.mean(coordinates, axis=0, keepdims=True)
    axis_std = np.std(centered, axis=0, keepdims=True)
    axis_std[axis_std == 0] = 1.0
    return (centered / axis_std) * COORDINATE_SCALE


def _pad_coordinates(coordinates, dims):
    if coordinates.shape[1] >= dims:
        return coordinates[:, :dims]

    padding = np.zeros((coordinates.shape[0], dims - coordinates.shape[1]), dtype=coordinates.dtype)
    return np.hstack([coordinates, padding])


def reduce_dimensions(X, dims, use_umap):
    if dims not in (2, 3):
        raise ValueError("DIMENSIONS must be 2 or 3")

    sample_count = X.shape[0]
    feature_count = X.shape[1] if len(X.shape) > 1 else 1
    effective_dims = max(1, min(dims, sample_count, feature_count))

    if sample_count < 2:
        coordinates = np.zeros((sample_count, dims), dtype=float)
        return coordinates

    if use_umap:
        effective_neighbors = max(1, min(UMAP_N_NEIGHBORS, sample_count - 1))
        reducer = umap.UMAP(
            n_components=effective_dims,
            n_neighbors=effective_neighbors,
            min_dist=UMAP_MIN_DIST,
            spread=UMAP_SPREAD,
            random_state=RANDOM_STATE,
        )
        coordinates = reducer.fit_transform(X)
        coordinates = _scale_coordinates(coordinates)
        return _pad_coordinates(coordinates, dims)

    if sparse.issparse(X):
        reducer = TruncatedSVD(n_components=effective_dims, random_state=RANDOM_STATE)
        coordinates = reducer.fit_transform(X)
        coordinates = _scale_coordinates(coordinates)
        return _pad_coordinates(coordinates, dims)

    reducer = PCA(n_components=effective_dims)
    coordinates = reducer.fit_transform(X)
    coordinates = _scale_coordinates(coordinates)
    return _pad_coordinates(coordinates, dims)

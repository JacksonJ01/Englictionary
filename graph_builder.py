from scipy import sparse
from sklearn.decomposition import PCA, TruncatedSVD
from sklearn.neighbors import NearestNeighbors
from sklearn.preprocessing import normalize

from config import GRAPH_SEARCH_DIMS, LARGE_DATA_THRESHOLD, RANDOM_STATE


def _graph_search_space(X):
    if X.shape[0] <= LARGE_DATA_THRESHOLD:
        return X, "cosine", None

    component_count = min(GRAPH_SEARCH_DIMS, X.shape[1] - 1)
    if component_count < 2:
        return X, "cosine", None

    if sparse.issparse(X):
        reducer = TruncatedSVD(n_components=component_count, random_state=RANDOM_STATE)
        reduced = reducer.fit_transform(X)
    else:
        reducer = PCA(n_components=component_count, random_state=RANDOM_STATE)
        reduced = reducer.fit_transform(X)

    return normalize(reduced), "euclidean", "approximate"


def build_knn_graph(X, k):
    sample_count = X.shape[0]
    if sample_count < 2:
        return []

    search_space, metric, similarity_mode = _graph_search_space(X)
    neighbor_count = min(k + 1, sample_count)
    neighbors = NearestNeighbors(n_neighbors=neighbor_count, metric=metric, n_jobs=-1)
    neighbors.fit(search_space)
    distances, indices = neighbors.kneighbors(search_space)

    edge_weights = {}
    for source_index, (row_distances, row_indices) in enumerate(zip(distances, indices)):
        for distance, target_index in zip(row_distances, row_indices):
            if source_index == target_index:
                continue

            if similarity_mode == "approximate":
                similarity = max(0.0, 1.0 - (float(distance) ** 2) / 2.0)
            else:
                similarity = max(0.0, 1.0 - float(distance))

            edge_key = tuple(sorted((int(source_index), int(target_index))))
            previous = edge_weights.get(edge_key)
            if previous is None or similarity > previous:
                edge_weights[edge_key] = similarity

    return [
        (source_index, target_index, weight)
        for (source_index, target_index), weight in sorted(edge_weights.items())
    ]

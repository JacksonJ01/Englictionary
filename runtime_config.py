import math
from pathlib import Path

import pandas as pd


def _clamp(value, minimum, maximum):
    return max(minimum, min(maximum, value))


def _safe_text(value):
    if value is None:
        return ""
    return str(value)


def _resolve_column(columns, candidates):
    lookup = {str(column).strip().lower(): column for column in columns}
    for candidate in candidates:
        match = lookup.get(str(candidate).strip().lower())
        if match is not None:
            return match
    return None


def collect_source_profile(source_file, term_candidates, definition_candidates, column_limit=0):
    source_path = Path(source_file)
    source_df = pd.read_csv(source_path)
    if column_limit:
        source_df = source_df.iloc[:, :column_limit].copy()

    term_column = _resolve_column(source_df.columns, term_candidates) or source_df.columns[0]
    definition_column = _resolve_column(source_df.columns, definition_candidates)
    if definition_column is None:
        definition_column = source_df.columns[1] if len(source_df.columns) > 1 else term_column

    term_series = source_df[term_column].fillna("").map(_safe_text)
    definition_series = source_df[definition_column].fillna("").map(_safe_text)

    term_token_count = int(term_series.str.split().str.len().sum())
    definition_token_count = int(definition_series.str.split().str.len().sum())
    token_count = int(term_token_count + definition_token_count)

    return {
        "row_count": int(len(source_df)),
        "column_count": int(len(source_df.columns)),
        "token_count": token_count,
        "term_token_count": term_token_count,
        "definition_token_count": definition_token_count,
    }


def build_adaptive_settings(config_module, profile):
    rows = max(1, int(profile.get("row_count", 1)))
    cols = max(1, int(profile.get("column_count", 1)))
    tokens = max(rows, int(profile.get("token_count", rows)))

    alpha_clusters = float(getattr(config_module, "ADAPTIVE_CLUSTER_ALPHA", 0.95))
    alpha_neighbors = float(getattr(config_module, "ADAPTIVE_NEIGHBOR_ALPHA", 2.2))
    token_scale = float(getattr(config_module, "ADAPTIVE_TOKEN_SCALE", 1.0))

    token_density = max(1.0, tokens / max(1.0, rows))
    token_factor = max(0.7, min(1.4, (token_density / 8.0) ** 0.25 * token_scale))

    cluster_guess = int(round(math.sqrt(rows) * alpha_clusters * math.log1p(cols) * token_factor))
    n_clusters = _clamp(
        cluster_guess,
        int(getattr(config_module, "ADAPTIVE_MIN_CLUSTERS", 4)),
        int(getattr(config_module, "ADAPTIVE_MAX_CLUSTERS", 120)),
    )
    n_clusters = min(n_clusters, rows)

    k_guess = int(round(math.log2(rows + 1) * alpha_neighbors * token_factor))
    k_neighbors = _clamp(
        k_guess,
        int(getattr(config_module, "ADAPTIVE_MIN_K_NEIGHBORS", 5)),
        int(getattr(config_module, "ADAPTIVE_MAX_K_NEIGHBORS", 50)),
    )
    k_neighbors = min(k_neighbors, max(1, rows - 1))

    umap_guess = int(round((k_neighbors * 1.5) + math.log1p(cols) * 2.0))
    umap_n_neighbors = _clamp(
        umap_guess,
        int(getattr(config_module, "ADAPTIVE_MIN_UMAP_NEIGHBORS", 8)),
        int(getattr(config_module, "ADAPTIVE_MAX_UMAP_NEIGHBORS", 80)),
    )
    umap_n_neighbors = min(umap_n_neighbors, max(2, rows - 1))

    sphere_cluster_guess = int(round(n_clusters * 1.35))
    sphere_cluster_count = _clamp(
        sphere_cluster_guess,
        int(getattr(config_module, "ADAPTIVE_MIN_SPHERE_CLUSTERS", 8)),
        int(getattr(config_module, "ADAPTIVE_MAX_SPHERE_CLUSTERS", 140)),
    )
    sphere_cluster_count = min(sphere_cluster_count, rows)

    repel_guess = int(round(110 + math.sqrt(sphere_cluster_count) * 18))
    sphere_cluster_repel_steps = _clamp(
        repel_guess,
        int(getattr(config_module, "ADAPTIVE_MIN_REPEL_STEPS", 120)),
        int(getattr(config_module, "ADAPTIVE_MAX_REPEL_STEPS", 320)),
    )

    node_spacing = 0.0022 + min(0.0038, 0.00022 * math.sqrt(max(1, rows / max(1, sphere_cluster_count))))

    return {
        "N_CLUSTERS": int(n_clusters),
        "K_NEIGHBORS": int(k_neighbors),
        "UMAP_N_NEIGHBORS": int(umap_n_neighbors),
        "SPHERE_CLUSTER_COUNT": int(sphere_cluster_count),
        "SPHERE_CLUSTER_REPEL_STEPS": int(sphere_cluster_repel_steps),
        "SPHERE_NODE_ANGULAR_SPACING": float(node_spacing),
    }


def apply_adaptive_settings(config_module, source_file, explicit_overrides=None):
    explicit_overrides = dict(explicit_overrides or {})
    profile = collect_source_profile(
        source_file=source_file,
        term_candidates=getattr(config_module, "TERM_COLUMN_CANDIDATES", ("Term", "Word", "term", "word")),
        definition_candidates=getattr(config_module, "DEFINITION_COLUMN_CANDIDATES", ("Definition", "definition")),
        column_limit=int(getattr(config_module, "SOURCE_COLUMN_LIMIT", 0) or 0),
    )

    adaptive_settings = {}
    if bool(getattr(config_module, "ENABLE_ADAPTIVE_CONFIG", True)):
        adaptive_settings = build_adaptive_settings(config_module, profile)

    for key, value in adaptive_settings.items():
        if key in explicit_overrides:
            continue
        setattr(config_module, key, value)

    return {
        "profile": profile,
        "adaptive_settings": adaptive_settings,
    }

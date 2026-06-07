import importlib
from datetime import datetime
from pathlib import Path

import config as config_module
from preprocess import clean_text

MODULES_TO_RELOAD = [
    "data_loader",
    "vectorize",
    "cluster",
    "graph_builder",
    "reduce_dim",
    "spherical_surface_layout",
    "visualize_spherical",
    "visualize",
]


def _set_runtime_config(source_file, overrides=None):
    overrides = overrides or {}
    source_path = Path(source_file)
    config_module.SOURCE_FILE = source_path
    config_module.FILE_PATH = source_path
    for key, value in overrides.items():
        setattr(config_module, key, value)


def _reload_modules():
    reloaded = {}
    for module_name in MODULES_TO_RELOAD:
        module = importlib.import_module(module_name)
        reloaded[module_name] = importlib.reload(module)
    return reloaded


def _build_run_metadata(data_context=None):
    data_context = data_context or {}
    if config_module.VISUALIZATION_MODE == "spherical":
        nodes_file = config_module.SPHERICAL_SURFACE_POINTS_FILE
        edges_file = ""
        plot_file = config_module.SPHERICAL_SURFACE_HTML
    else:
        nodes_file = config_module.NODES_FILE
        edges_file = config_module.EDGES_FILE
        plot_file = config_module.PLOT_2D_FILE if config_module.DIMENSIONS == 2 else config_module.PLOT_3D_FILE

    return {
        "visualization_mode": config_module.VISUALIZATION_MODE,
        "spherical_full_surface": config_module.SPHERE_FULL_SURFACE,
        "file_path": str(config_module.FILE_PATH),
        "use_embeddings": config_module.USE_EMBEDDINGS,
        "dimensions": config_module.DIMENSIONS,
        "use_umap": config_module.USE_UMAP,
        "n_clusters": config_module.N_CLUSTERS,
        "k_neighbors": config_module.K_NEIGHBORS,
        "source_file": str(data_context.get("source_file", config_module.FILE_PATH)),
        "source_row_count": data_context.get("source_row_count", ""),
        "focus_column": data_context.get("focus_column", "Word"),
        "definition_column": data_context.get("definition_column", "Definition"),
        "pos_column": data_context.get("pos_column", ""),
        "detail_columns": list(data_context.get("detail_columns", ())),
        "run_id": data_context.get("run_id", ""),
        "run_timestamp": data_context.get("run_timestamp", ""),
        "plot_file": str(plot_file),
        "nodes_file": str(nodes_file),
        "edges_file": str(edges_file),
    }


def run_from_csv(source_file, overrides=None):
    overrides = overrides or {}
    _set_runtime_config(source_file, overrides)
    modules = _reload_modules()

    data_loader = modules["data_loader"]
    vectorize_module = modules["vectorize"]
    cluster_module = modules["cluster"]
    reduce_dim_module = modules["reduce_dim"]
    spherical_surface_layout = modules["spherical_surface_layout"]
    visualize_spherical = modules["visualize_spherical"]
    visualize_module = modules["visualize"]
    graph_builder = modules["graph_builder"]

    run_started_at = datetime.now()
    run_id = run_started_at.strftime("%Y%m%d_%H%M%S_%f")

    df = data_loader.load_data(Path(source_file))
    data_context = dict(getattr(df, "attrs", {}))
    data_context["source_row_count"] = int(len(df))
    data_context["run_id"] = run_id
    data_context["run_timestamp"] = run_started_at.isoformat(timespec="seconds")

    df = clean_text(df)

    if config_module.USE_EMBEDDINGS:
        X = vectorize_module.vectorize_embeddings(df)
    else:
        X = vectorize_module.vectorize_tfidf(df)

    if config_module.VISUALIZATION_MODE == "spherical":
        config_module.SPHERICAL_SURFACE_POINTS_FILE.parent.mkdir(parents=True, exist_ok=True)
        surface_df = spherical_surface_layout.build_spherical_surface_points(
            df=df,
            X=X,
            use_umap=config_module.USE_UMAP,
        )
        surface_df.to_csv(config_module.SPHERICAL_SURFACE_POINTS_FILE, index=False)
        visualize_spherical.render_spherical_surface(
            surface_df,
            config_module.SPHERICAL_SURFACE_HTML,
            live_reload=bool(getattr(config_module, "LIVE_RELOAD", False)),
        )
        plot_file = config_module.SPHERICAL_SURFACE_HTML
    else:
        edges = graph_builder.build_knn_graph(X, config_module.K_NEIGHBORS)
        labels = cluster_module.cluster_data(X, config_module.N_CLUSTERS)
        coordinates = reduce_dim_module.reduce_dimensions(X, config_module.DIMENSIONS, config_module.USE_UMAP)
        result_df = importlib.import_module("utils").attach_results(df, labels, coordinates)
        config_module.NODES_FILE.parent.mkdir(parents=True, exist_ok=True)
        config_module.EDGES_FILE.parent.mkdir(parents=True, exist_ok=True)
        importlib.import_module("utils").build_nodes_export(result_df).to_csv(config_module.NODES_FILE, index=False)
        importlib.import_module("utils").build_edges_export(edges).to_csv(config_module.EDGES_FILE, index=False)
        if config_module.DIMENSIONS == 2:
            plot_file = visualize_module.plot_2d(result_df, edges=edges)
        else:
            plot_file = visualize_module.plot_3d(result_df, edges=edges)

    return {
        "run_id": run_id,
        "run_timestamp": data_context["run_timestamp"],
        "result_path": str(plot_file),
        "source_file": str(Path(source_file)),
        "source_row_count": data_context["source_row_count"],
        "plot_file": str(plot_file),
        "data_context": data_context,
        "metadata": _build_run_metadata(data_context),
    }

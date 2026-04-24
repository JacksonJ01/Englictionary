import json
from datetime import datetime
import webbrowser

from cluster import cluster_data
from config import (
    DIMENSIONS,
    EDGES_FILE,
    FILE_PATH,
    K_NEIGHBORS,
    N_CLUSTERS,
    NODES_FILE,
    OUTPUT_DIR,
    PLOT_2D_FILE,
    PLOT_3D_FILE,
    RUN_METADATA_FILE,
    SPHERE_FULL_SURFACE,
    SPHERICAL_LAUNCHER_HTML,
    SPHERICAL_OUTPUT_DIR,
    SPHERICAL_SURFACE_HTML,
    SPHERICAL_SURFACE_POINTS_FILE,
    USE_EMBEDDINGS,
    USE_UMAP,
    VISUALIZATION_MODE,
)
from data_loader import load_data
from graph_builder import build_knn_graph
from preprocess import clean_text
from reduce_dim import reduce_dimensions
from spherical_surface_layout import build_spherical_surface_points
from utils import attach_results, build_edges_export, build_nodes_export
from vectorize import vectorize_embeddings, vectorize_tfidf
from visualize import plot_2d, plot_3d
from visualize_spherical import render_spherical_surface
from run_history import archive_current_spherical_outputs, open_launcher


def _current_plot_path():
    if VISUALIZATION_MODE == "spherical":
        return SPHERICAL_SURFACE_HTML
    return PLOT_2D_FILE if DIMENSIONS == 2 else PLOT_3D_FILE


def _mode_output_files():
    if VISUALIZATION_MODE == "spherical":
        return [SPHERICAL_SURFACE_HTML, SPHERICAL_SURFACE_POINTS_FILE]
    return [
        _current_plot_path(),
        NODES_FILE,
        EDGES_FILE,
    ]


def _build_run_metadata(data_context=None):
    data_context = data_context or {}
    if VISUALIZATION_MODE == "spherical":
        nodes_file = SPHERICAL_SURFACE_POINTS_FILE
        edges_file = ""
    else:
        nodes_file = NODES_FILE
        edges_file = EDGES_FILE

    return {
        "visualization_mode": VISUALIZATION_MODE,
        "spherical_full_surface": SPHERE_FULL_SURFACE,
        "file_path": str(FILE_PATH),
        "use_embeddings": USE_EMBEDDINGS,
        "dimensions": DIMENSIONS,
        "use_umap": USE_UMAP,
        "n_clusters": N_CLUSTERS,
        "k_neighbors": K_NEIGHBORS,
        "source_file": str(data_context.get("source_file", FILE_PATH)),
        "source_row_count": data_context.get("source_row_count", ""),
        "focus_column": data_context.get("focus_column", "Word"),
        "definition_column": data_context.get("definition_column", "Definition"),
        "pos_column": data_context.get("pos_column", ""),
        "detail_columns": list(data_context.get("detail_columns", ())),
        "run_id": data_context.get("run_id", ""),
        "run_timestamp": data_context.get("run_timestamp", ""),
        "plot_file": str(_current_plot_path()),
        "nodes_file": str(nodes_file),
        "edges_file": str(edges_file),
    }


def _write_run_metadata(data_context=None):
    RUN_METADATA_FILE.write_text(json.dumps(_build_run_metadata(data_context), indent=2), encoding="utf-8")


def _read_existing_metadata():
    if not RUN_METADATA_FILE.exists():
        return None

    try:
        return json.loads(RUN_METADATA_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _open_existing_outputs(plot_path):
    if VISUALIZATION_MODE == "spherical":
        metadata = _read_existing_metadata()
        launcher_path = open_launcher(current_metadata=metadata)
        print(f"Opened launcher: {launcher_path}")
        if SPHERICAL_SURFACE_POINTS_FILE.exists():
            print(f"Existing spherical points: {SPHERICAL_SURFACE_POINTS_FILE}")
    else:
        import webbrowser

        webbrowser.open(plot_path.resolve().as_uri())
        print(f"Opened existing plot: {plot_path}")
        if NODES_FILE.exists():
            print(f"Existing node data: {NODES_FILE}")
        if EDGES_FILE.exists():
            print(f"Existing edge data: {EDGES_FILE}")


def _csv_data_row_count(file_path):
    try:
        with file_path.open("r", encoding="utf-8", errors="ignore") as handle:
            total_lines = sum(1 for _ in handle)
        return max(0, total_lines - 1)
    except OSError:
        return None


def _existing_outputs_ready(expected_surface_rows=None):
    if not all(path.exists() for path in _mode_output_files()):
        return False

    if VISUALIZATION_MODE == "spherical" and expected_surface_rows is not None:
        cached_rows = _csv_data_row_count(SPHERICAL_SURFACE_POINTS_FILE)
        return cached_rows == expected_surface_rows

    return True


def _prompt_for_existing_outputs(expected_surface_rows=None):
    plot_path = _current_plot_path()
    if not _existing_outputs_ready(expected_surface_rows=expected_surface_rows):
        if VISUALIZATION_MODE == "spherical" and expected_surface_rows is not None:
            cached_rows = _csv_data_row_count(SPHERICAL_SURFACE_POINTS_FILE)
            if cached_rows is not None and cached_rows != expected_surface_rows:
                print(
                    "Existing spherical cache does not match current CSV size "
                    f"(cached={cached_rows}, expected={expected_surface_rows}). Regenerating."
                )
        return False

    metadata = _read_existing_metadata()
    print("Existing processed outputs were found.")
    if VISUALIZATION_MODE == "spherical":
        print(f"Launcher: {SPHERICAL_LAUNCHER_HTML}")
        print(f"Points: {SPHERICAL_SURFACE_POINTS_FILE}")
    else:
        print(f"Plot: {plot_path}")
        print(f"Nodes: {NODES_FILE}")
        print(f"Edges: {EDGES_FILE}")
    if metadata:
        print(
            "Previous settings: "
            f"embeddings={metadata.get('use_embeddings')}, "
            f"dims={metadata.get('dimensions')}, "
            f"umap={metadata.get('use_umap')}, "
            f"clusters={metadata.get('n_clusters')}, "
            f"neighbors={metadata.get('k_neighbors')}"
        )

    while True:
        choice = input(
            "Choose: [O]pen existing, [R]egenerate and overwrite, or [Q]uit: "
        ).strip().lower()
        if choice in {"o", "open"}:
            _open_existing_outputs(plot_path)
            return True
        if choice in {"r", "regenerate"}:
            return False
        if choice in {"q", "quit"}:
            print("No changes made.")
            raise SystemExit(0)

        print("Please enter O, R, or Q.")


def _run_flat_pipeline(df, X):
    print("Building graph...")
    edges = build_knn_graph(X, K_NEIGHBORS)

    print("Clustering...")
    labels = cluster_data(X, N_CLUSTERS)

    print(f"Reducing to {DIMENSIONS}D...")
    coordinates = reduce_dimensions(X, DIMENSIONS, USE_UMAP)
    result_df = attach_results(df, labels, coordinates)

    print("Saving outputs...")
    build_nodes_export(result_df).to_csv(NODES_FILE, index=False)
    build_edges_export(edges).to_csv(EDGES_FILE, index=False)

    print("Rendering visualization...")
    if DIMENSIONS == 2:
        plot_path = plot_2d(result_df, edges=edges)
    else:
        plot_path = plot_3d(result_df, edges=edges)

    print(f"Saved interactive plot to {plot_path}")
    print(f"Saved node data to {NODES_FILE}")
    print(f"Saved edge data to {EDGES_FILE}")


def _run_spherical_pipeline(df, X):
    SPHERICAL_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print("Building full-surface spherical layout...")
    surface_df = build_spherical_surface_points(df=df, X=X, use_umap=USE_UMAP)

    print("Saving spherical surface points...")
    surface_df.to_csv(SPHERICAL_SURFACE_POINTS_FILE, index=False)

    print("Rendering full-surface globe...")
    root_path = render_spherical_surface(surface_df, SPHERICAL_SURFACE_HTML)

    print(f"Saved spherical surface page to {root_path}")
    print(f"Saved spherical points to {SPHERICAL_SURFACE_POINTS_FILE}")


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    if VISUALIZATION_MODE == "spherical":
        archive_current_spherical_outputs()

    run_started_at = datetime.now()
    run_id = run_started_at.strftime("%Y%m%d_%H%M%S_%f")

    print("Loading data...")
    df = load_data(FILE_PATH)
    data_context = dict(getattr(df, "attrs", {}))
    data_context["source_row_count"] = int(len(df))
    data_context["run_id"] = run_id
    data_context["run_timestamp"] = run_started_at.isoformat(timespec="seconds")

    print("Preprocessing...")
    df = clean_text(df)

    print("Vectorizing...")
    if USE_EMBEDDINGS:
        X = vectorize_embeddings(df)
    else:
        X = vectorize_tfidf(df)

    if VISUALIZATION_MODE == "spherical":
        _run_spherical_pipeline(df, X)
        webbrowser.open(SPHERICAL_SURFACE_HTML.resolve().as_uri())
    else:
        _run_flat_pipeline(df, X)

    _write_run_metadata(data_context)


if __name__ == "__main__":
    main()
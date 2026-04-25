import argparse
import json
from datetime import datetime
import time
import webbrowser
from pathlib import Path

import pandas as pd

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
from pipeline_runner import run_from_csv


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


def _is_stale(target_path, source_paths):
    target_path = Path(target_path)
    if not target_path.exists():
        return True

    target_mtime = target_path.stat().st_mtime_ns
    for source_path in source_paths:
        source_path = Path(source_path)
        if source_path.exists() and source_path.stat().st_mtime_ns > target_mtime:
            return True
    return False


def _load_cached_spherical_surface():
    if not SPHERICAL_SURFACE_POINTS_FILE.exists():
        return None

    try:
        surface_df = pd.read_csv(SPHERICAL_SURFACE_POINTS_FILE)
    except OSError:
        return None

    metadata = _read_existing_metadata() or {}
    surface_df.attrs["source_file"] = metadata.get("source_file", FILE_PATH)
    surface_df.attrs["definition_column"] = metadata.get("definition_column", "Definition")
    surface_df.attrs["pos_column"] = metadata.get("pos_column", "")
    surface_df.attrs["detail_columns"] = metadata.get("detail_columns", [])
    surface_df.attrs["source_row_count"] = metadata.get("source_row_count", len(surface_df))
    return surface_df


def _render_cached_spherical_output(live_reload=False):
    surface_df = _load_cached_spherical_surface()
    if surface_df is None:
        return False

    root_path = render_spherical_surface(
        surface_df,
        SPHERICAL_SURFACE_HTML,
        live_reload=bool(live_reload),
    )
    print(f"Re-rendered spherical HTML from cached surface points: {root_path}")
    return True


def _open_plot_file(plot_path):
    webbrowser.open(Path(plot_path).resolve().as_uri())


def _current_visualization_label():
    if VISUALIZATION_MODE == "spherical":
        return f"spherical ({SPHERICAL_SURFACE_HTML})"
    if DIMENSIONS == 2:
        return f"2D ({PLOT_2D_FILE})"
    return f"3D ({PLOT_3D_FILE})"


def _recreate_visualization_menu():
    options = [
        ("current", f"Current visualization: {_current_visualization_label()}"),
        ("spherical", f"Spherical HTML ({SPHERICAL_SURFACE_HTML})"),
        ("2d", f"2D HTML ({PLOT_2D_FILE})"),
        ("3d", f"3D HTML ({PLOT_3D_FILE})"),
        ("back", "Back"),
    ]

    print("Which visualization do you want to recreate?")
    for index, (_, label) in enumerate(options, start=1):
        print(f"{index}) {label}")

    while True:
        choice = input(f"Enter 1-{len(options)}: ").strip().lower()
        if choice in {str(len(options)), "b", "back", "q", "quit", "exit"}:
            return None
        if not choice.isdigit():
            print(f"Please enter a number from 1 to {len(options)}.")
            continue

        selected_index = int(choice) - 1
        if selected_index < 0 or selected_index >= len(options) - 1:
            print(f"Please enter a number from 1 to {len(options)}.")
            continue

        selected_kind, _ = options[selected_index]
        if selected_kind == "current":
            return _current_plot_path()
        return selected_kind


def _recreate_visualization_output(selection):
    if selection is None:
        return False

    if isinstance(selection, Path):
        if selection == SPHERICAL_SURFACE_HTML:
            if _is_stale(SPHERICAL_SURFACE_HTML, [Path(__file__).with_name("visualize_spherical.py"), Path(__file__).with_name("config.py")]):
                if not _render_cached_spherical_output(live_reload=False):
                    print("No cached spherical surface points were found.")
                    return False
            if SPHERICAL_SURFACE_HTML.exists():
                _open_plot_file(SPHERICAL_SURFACE_HTML)
                print(f"Opened existing spherical plot: {SPHERICAL_SURFACE_HTML}")
                if SPHERICAL_SURFACE_POINTS_FILE.exists():
                    print(f"Existing spherical points: {SPHERICAL_SURFACE_POINTS_FILE}")
                return True
            print(f"No cached spherical visualization was found at {SPHERICAL_SURFACE_HTML}.")
            return False

        if selection.exists():
            _open_plot_file(selection)
            print(f"Opened existing plot: {selection}")
            return True

        print(f"No cached visualization was found at {selection}.")
        return False

    if selection == "spherical":
        if _render_cached_spherical_output(live_reload=False):
            _open_plot_file(SPHERICAL_SURFACE_HTML)
            print(f"Opened existing spherical plot: {SPHERICAL_SURFACE_HTML}")
            if SPHERICAL_SURFACE_POINTS_FILE.exists():
                print(f"Existing spherical points: {SPHERICAL_SURFACE_POINTS_FILE}")
            return True
        print("No cached spherical surface points were found.")
        return False

    if selection == "2d":
        if PLOT_2D_FILE.exists():
            _open_plot_file(PLOT_2D_FILE)
            print(f"Opened existing plot: {PLOT_2D_FILE}")
            return True
        print(f"No cached 2D visualization was found at {PLOT_2D_FILE}.")
        return False

    if selection == "3d":
        if PLOT_3D_FILE.exists():
            _open_plot_file(PLOT_3D_FILE)
            print(f"Opened existing plot: {PLOT_3D_FILE}")
            return True
        print(f"No cached 3D visualization was found at {PLOT_3D_FILE}.")
        return False

    return False


def _reuse_existing_output_if_available():
    if VISUALIZATION_MODE == "spherical":
        if SPHERICAL_SURFACE_HTML.exists():
            if _is_stale(SPHERICAL_SURFACE_HTML, [Path(__file__).with_name("visualize_spherical.py"), Path(__file__).with_name("config.py")]):
                if _render_cached_spherical_output(live_reload=False) is False:
                    return False
            _open_plot_file(SPHERICAL_SURFACE_HTML)
            print(f"Opened existing spherical plot: {SPHERICAL_SURFACE_HTML}")
            if SPHERICAL_SURFACE_POINTS_FILE.exists():
                print(f"Existing spherical points: {SPHERICAL_SURFACE_POINTS_FILE}")
            return True

        if _render_cached_spherical_output(live_reload=False):
            _open_plot_file(SPHERICAL_SURFACE_HTML)
            print(f"Opened existing spherical plot: {SPHERICAL_SURFACE_HTML}")
            if SPHERICAL_SURFACE_POINTS_FILE.exists():
                print(f"Existing spherical points: {SPHERICAL_SURFACE_POINTS_FILE}")
            return True

        return False

    plot_path = _current_plot_path()
    if plot_path.exists():
        _open_plot_file(plot_path)
        print(f"Opened existing plot: {plot_path}")
        if NODES_FILE.exists():
            print(f"Existing node data: {NODES_FILE}")
        if EDGES_FILE.exists():
            print(f"Existing edge data: {EDGES_FILE}")
        return True

    return False


def _open_existing_outputs(plot_path):
    return _reuse_existing_output_if_available()


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


def _run_model_pipeline():
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


def _menu_choice():
    print("Choose an action:")
    print("1) Recreate HTML visualization")
    print("2) Run new model")
    print("3) Quit")

    while True:
        choice = input("Enter 1, 2, or 3: ").strip().lower()
        if choice in {"1", "recreate", "html", "visualization"}:
            return "recreate"
        if choice in {"2", "run", "model", "new"}:
            return "model"
        if choice in {"3", "q", "quit", "exit"}:
            return "quit"
        print("Please enter 1, 2, or 3.")


def _watch_paths():
    candidates = [
        Path(__file__),
        Path(__file__).with_name("config.py"),
        Path(__file__).with_name("data_loader.py"),
        Path(__file__).with_name("preprocess.py"),
        Path(__file__).with_name("vectorize.py"),
        Path(__file__).with_name("cluster.py"),
        Path(__file__).with_name("reduce_dim.py"),
        Path(__file__).with_name("spherical_surface_layout.py"),
        Path(__file__).with_name("visualize_spherical.py"),
        Path(FILE_PATH),
    ]
    seen = set()
    paths = []
    for candidate in candidates:
        resolved = Path(candidate).resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        paths.append(resolved)
    return paths


def _snapshot(paths):
    return {str(path): path.stat().st_mtime_ns if path.exists() else None for path in paths}


def _watch_and_rebuild(poll_interval=1.0):
    print("Watch mode enabled. Edit the pipeline or HTML generator files and save to rebuild.")
    watched_paths = _watch_paths()
    last_snapshot = _snapshot(watched_paths)
    first_run = True

    while True:
        result = run_from_csv(FILE_PATH, overrides={"LIVE_RELOAD": True})
        if first_run:
            webbrowser.open(Path(result["result_path"]).resolve().as_uri())
            first_run = False
        print(f"Rebuilt spherical output: {result['result_path']}")

        while True:
            time.sleep(poll_interval)
            current_snapshot = _snapshot(watched_paths)
            if current_snapshot != last_snapshot:
                last_snapshot = current_snapshot
                print("Change detected. Rebuilding...")
                break


def main(argv=None):
    parser = argparse.ArgumentParser(description="Run the Englictionary pipeline.")
    parser.add_argument("--watch", action="store_true", help="Rebuild automatically when source files change.")
    parser.add_argument("--poll-interval", type=float, default=1.0, help="Seconds between file change checks in watch mode.")
    args = parser.parse_args(argv)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    if args.watch:
        _watch_and_rebuild(poll_interval=max(0.25, float(args.poll_interval)))
        return

    action = _menu_choice()
    if action == "quit":
        print("No changes made.")
        return
    if action == "recreate":
        selection = _recreate_visualization_menu()
        if selection is None:
            print("No changes made.")
            return
        _recreate_visualization_output(selection)
        return

    _run_model_pipeline()


if __name__ == "__main__":
    main()
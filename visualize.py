import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import plotly.io as pio
from sklearn.neighbors import NearestNeighbors

from config import (
    CAMERA_EYE_X,
    CAMERA_EYE_Y,
    CAMERA_EYE_Z,
    DISPLAY_DISTANCE_NEIGHBORS,
    DISPLAY_DISTANCE_PASSES,
    DISPLAY_MIN_DISTANCE,
    ENABLE_3D_NODE_SPREAD,
    FIGURE_HEIGHT,
    FIGURE_WIDTH,
    MARKER_OPACITY_3D,
    MARKER_SIZE_3D,
    MAX_DISPLAY_ADJUST_POINTS,
    MAX_EDGE_RENDER,
    PLOT_2D_FILE,
    PLOT_3D_FILE,
    PLOT_AUTO_OPEN,
    PREVIEW_POINT_THRESHOLD,
    RANDOM_STATE,
    SCENE_ASPECTMODE,
)


def _preview_df(df):
    if len(df) <= PREVIEW_POINT_THRESHOLD:
        return df
    return df.sample(n=PREVIEW_POINT_THRESHOLD, random_state=RANDOM_STATE).sort_index()


def _help_panel_html():
    return """
    <aside style="position:fixed;top:20px;right:20px;z-index:9999;max-width:320px;padding:14px 16px;background:rgba(255,255,255,0.94);border:1px solid rgba(0,0,0,0.08);border-radius:12px;box-shadow:0 12px 30px rgba(0,0,0,0.12);font-family:Segoe UI,Arial,sans-serif;color:#1f2937;line-height:1.45;">
        <div style="font-weight:700;font-size:14px;margin-bottom:8px;">Graph Help</div>
        <div style="font-size:13px;">
            <div><strong>Rotate:</strong> click and drag</div>
            <div><strong>Pan:</strong> right-click and drag</div>
            <div><strong>Zoom:</strong> mouse wheel or trackpad pinch</div>
            <div><strong>Inspect:</strong> hover a node for word, definition, and part of speech</div>
            <div><strong>Clusters:</strong> node colors show semantic cluster membership</div>
        </div>
    </aside>
    """


def _hover_columns(df):
    columns = ["Word", "Definition"]
    if "pos_group" in df.columns:
        columns.append("pos_group")

    detail_columns = [
        column
        for column in df.attrs.get("detail_columns", ())
        if column in df.columns and column not in columns
    ]
    columns.extend(detail_columns)
    return columns


def _write_figure(fig, output_path):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    figure_html = pio.to_html(fig, full_html=False, include_plotlyjs=True)
    page_html = f"""<!DOCTYPE html>
<html lang=\"en\">
<head>
    <meta charset=\"utf-8\">
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">
    <title>Semantic Map</title>
    <style>
        body {{ margin: 0; background: #f5f7fb; }}
        .plot-shell {{ min-height: 100vh; padding: 10px; box-sizing: border-box; }}
    </style>
</head>
<body>
    {_help_panel_html()}
    <div class=\"plot-shell\">{figure_html}</div>
</body>
</html>
"""
    output_path.write_text(page_html, encoding="utf-8")
    if PLOT_AUTO_OPEN:
        import webbrowser

        webbrowser.open(output_path.resolve().as_uri())
    return output_path


def _spread_display_nodes_3d(df):
    if not ENABLE_3D_NODE_SPREAD or len(df) > MAX_DISPLAY_ADJUST_POINTS or len(df) < 2:
        return df

    coordinates = df[["x", "y", "z"]].to_numpy(dtype=float).copy()
    neighbor_count = min(DISPLAY_DISTANCE_NEIGHBORS + 1, len(df))

    for _ in range(DISPLAY_DISTANCE_PASSES):
        neighbors = NearestNeighbors(n_neighbors=neighbor_count, metric="euclidean")
        neighbors.fit(coordinates)
        distances, indices = neighbors.kneighbors(coordinates)
        adjustments = np.zeros_like(coordinates)

        for source_index, (row_distances, row_indices) in enumerate(zip(distances, indices)):
            for distance, target_index in zip(row_distances[1:], row_indices[1:]):
                if distance >= DISPLAY_MIN_DISTANCE:
                    continue

                direction = coordinates[source_index] - coordinates[target_index]
                norm = np.linalg.norm(direction)
                if norm < 1e-9:
                    direction = np.array([1.0, 0.0, 0.0])
                    norm = 1.0

                unit_direction = direction / norm
                delta = (DISPLAY_MIN_DISTANCE - float(distance)) / 2.0
                adjustments[source_index] += unit_direction * delta
                adjustments[target_index] -= unit_direction * delta

        coordinates += adjustments

    spread_df = df.copy()
    spread_df[["x", "y", "z"]] = coordinates
    return spread_df


def _edge_segments_2d(df, edges):
    x_values = []
    y_values = []

    for source, target, _weight in edges[:MAX_EDGE_RENDER]:
        x_values.extend([df.at[source, "x"], df.at[target, "x"], None])
        y_values.extend([df.at[source, "y"], df.at[target, "y"], None])

    return go.Scatter(
        x=x_values,
        y=y_values,
        mode="lines",
        line={"color": "rgba(120, 120, 120, 0.18)", "width": 1},
        hoverinfo="skip",
        showlegend=False,
    )


def _edge_segments_3d(df, edges):
    x_values = []
    y_values = []
    z_values = []

    for source, target, _weight in edges[:MAX_EDGE_RENDER]:
        x_values.extend([df.at[source, "x"], df.at[target, "x"], None])
        y_values.extend([df.at[source, "y"], df.at[target, "y"], None])
        z_values.extend([df.at[source, "z"], df.at[target, "z"], None])

    return go.Scatter3d(
        x=x_values,
        y=y_values,
        z=z_values,
        mode="lines",
        line={"color": "rgba(120, 120, 120, 0.14)", "width": 1},
        hoverinfo="skip",
        showlegend=False,
    )


def plot_2d(df, edges=None):
    plot_df = _preview_df(df)
    fig = px.scatter(
        plot_df,
        x="x",
        y="y",
        color=plot_df["cluster"].astype(str),
        hover_data=_hover_columns(plot_df),
        title="Dictionary Semantic Map (2D)",
    )

    if edges and len(plot_df) == len(df):
        fig.add_trace(_edge_segments_2d(df, edges))

    return _write_figure(fig, PLOT_2D_FILE)


def plot_3d(df, edges=None):
    plot_df = _spread_display_nodes_3d(_preview_df(df))
    fig = px.scatter_3d(
        plot_df,
        x="x",
        y="y",
        z="z",
        color=plot_df["cluster"].astype(str),
        hover_data=_hover_columns(plot_df),
        title="Dictionary Semantic Map (3D)",
    )

    fig.update_traces(marker={"size": MARKER_SIZE_3D, "opacity": MARKER_OPACITY_3D})
    fig.update_layout(
        width=FIGURE_WIDTH,
        height=FIGURE_HEIGHT,
        scene={
            "aspectmode": SCENE_ASPECTMODE,
            "camera": {"eye": {"x": CAMERA_EYE_X, "y": CAMERA_EYE_Y, "z": CAMERA_EYE_Z}},
        },
    )

    if edges and len(plot_df) == len(df):
        fig.add_trace(_edge_segments_3d(plot_df, edges))

    return _write_figure(fig, PLOT_3D_FILE)
import json

import numpy as np
import pandas as pd
from sklearn.neighbors import NearestNeighbors


def _json_value(value):
    if pd.isna(value):
        return None
    return value


def _visible_node_payload(row, next_page=None):
    return {
        "node_id": str(row["node_id"]),
        "parent_id": str(row["parent_id"]),
        "depth": int(row["depth"]),
        "node_type": str(row["node_type"]),
        "label": str(row["label"]),
        "display_name": str(_json_value(row.get("display_name", row["label"]))),
        "size": int(row["size"]),
        "top_cluster": str(row["top_cluster"]),
        "subcluster": _json_value(row["subcluster"]),
        "x": float(row["x"]),
        "y": float(row["y"]),
        "z": float(row["z"]),
        "word_index": _json_value(row["word_index"]),
        "next_page": next_page,
    }


def _word_knn_edges(word_rows, X, edge_k):
    if len(word_rows) < 2:
        return []

    indices = word_rows["word_index"].astype(int).tolist()
    matrix = X[indices]
    neighbor_count = min(edge_k + 1, len(indices))
    neighbors = NearestNeighbors(n_neighbors=neighbor_count, metric="cosine", n_jobs=-1)
    neighbors.fit(matrix)
    distances, adjacency = neighbors.kneighbors(matrix)

    node_ids = word_rows["node_id"].tolist()
    edge_weights = {}
    for source_position, (distance_row, neighbor_row) in enumerate(zip(distances, adjacency)):
        source_id = node_ids[source_position]
        for distance, neighbor_position in zip(distance_row[1:], neighbor_row[1:]):
            target_id = node_ids[int(neighbor_position)]
            key = tuple(sorted((source_id, target_id)))
            weight = max(0.0, 1.0 - float(distance))
            previous = edge_weights.get(key)
            if previous is None or weight > previous:
                edge_weights[key] = weight

    return [
        {"source": source, "target": target, "weight": weight, "edge_type": "local"}
        for (source, target), weight in sorted(edge_weights.items())
    ]


def _secondary_edges(visible_node_ids, secondary_df):
    if secondary_df.empty:
        return []

    visible = set(visible_node_ids)
    rows = secondary_df[
        secondary_df["word_node_id"].isin(visible) & secondary_df["secondary_cluster_id"].isin(visible)
    ]
    return [
        {
            "source": row["word_node_id"],
            "target": row["secondary_cluster_id"],
            "weight": float(row["weight"]),
            "edge_type": "secondary",
        }
        for _, row in rows.iterrows()
    ]


def build_spherical_pages(coords_df, secondary_df, X, edge_k, output_dir):
    output_dir.mkdir(parents=True, exist_ok=True)
    pages = []

    top_rows = coords_df[coords_df["depth"] == 0].copy().sort_values("node_id")
    level0_nodes = []
    for _, row in top_rows.iterrows():
        level0_nodes.append(_visible_node_payload(row, next_page=f"sphere_level1_{row['node_id']}.html"))

    level0_page = {
        "page_id": "sphere_level0",
        "title": "Spherical Semantic Globe - Level 0 (Clusters)",
        "breadcrumb": [],
        "nodes": level0_nodes,
        "edges": [],
        "back_page": None,
    }
    pages.append(level0_page)

    sub_rows = coords_df[coords_df["depth"] == 1].copy()
    word_rows = coords_df[coords_df["depth"] == 2].copy()

    for _, top_row in top_rows.iterrows():
        top_id = top_row["node_id"]
        top_node = _visible_node_payload(top_row)

        top_sub_rows = sub_rows[sub_rows["parent_id"] == top_id].copy().sort_values("node_id")
        nodes = [top_node]
        edges = []
        for _, sub_row in top_sub_rows.iterrows():
            sub_node = _visible_node_payload(
                sub_row,
                next_page=f"sphere_level2_{sub_row['node_id']}.html",
            )
            nodes.append(sub_node)
            edges.append(
                {
                    "source": top_id,
                    "target": sub_row["node_id"],
                    "weight": 1.0,
                    "edge_type": "parent",
                }
            )

        page_id = f"sphere_level1_{top_id}"
        pages.append(
            {
                "page_id": page_id,
                "title": f"Spherical Semantic Globe - Level 1 ({top_node['display_name']})",
                "breadcrumb": [("Level 0", "sphere_level0.html")],
                "nodes": nodes,
                "edges": edges,
                "back_page": "sphere_level0.html",
            }
        )

    for _, sub_row in sub_rows.iterrows():
        sub_id = sub_row["node_id"]
        top_id = sub_row["parent_id"]
        top_row = top_rows[top_rows["node_id"] == top_id].iloc[0]
        top_node = _visible_node_payload(top_row)
        sub_node = _visible_node_payload(sub_row)

        sub_word_rows = word_rows[word_rows["parent_id"] == sub_id].copy().sort_values("node_id")
        nodes = [top_node, sub_node]
        for _, word_row in sub_word_rows.iterrows():
            nodes.append(_visible_node_payload(word_row))

        edges = [
            {
                "source": top_id,
                "target": sub_id,
                "weight": 1.0,
                "edge_type": "parent",
            }
        ]
        edges.extend(
            {
                "source": sub_id,
                "target": row["node_id"],
                "weight": 0.7,
                "edge_type": "parent",
            }
            for _, row in sub_word_rows.iterrows()
        )
        edges.extend(_word_knn_edges(sub_word_rows, X, edge_k))
        edges.extend(_secondary_edges([node["node_id"] for node in nodes], secondary_df))

        page_id = f"sphere_level2_{sub_id}"
        pages.append(
            {
                "page_id": page_id,
                "title": f"Spherical Semantic Globe - Level 2 ({sub_node['display_name']})",
                "breadcrumb": [
                    ("Level 0", "sphere_level0.html"),
                    (f"Level 1 {top_node['display_name']}", f"sphere_level1_{top_id}.html"),
                ],
                "nodes": nodes,
                "edges": edges,
                "back_page": f"sphere_level1_{top_id}.html",
            }
        )

    payload_manifest = output_dir / "spherical_pages_manifest.json"
    payload_manifest.write_text(json.dumps(pages, indent=2), encoding="utf-8")
    return pages, payload_manifest

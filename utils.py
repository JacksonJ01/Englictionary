import pandas as pd


def attach_results(df, labels, coordinates):
    result_df = df.copy()
    result_df["cluster"] = labels
    result_df["x"] = coordinates[:, 0]
    result_df["y"] = coordinates[:, 1]

    if coordinates.shape[1] == 3:
        result_df["z"] = coordinates[:, 2]

    result_df.attrs.update(df.attrs)
    return result_df


def build_nodes_export(df):
    term_column = "Term" if "Term" in df.columns else "Word"

    export_df = pd.DataFrame(
        {
            "id": range(len(df)),
            "word": df[term_column],
            "definition": df["Definition"],
            "cluster": df["cluster"],
            "x": df["x"],
            "y": df["y"],
        }
    )

    if "z" in df.columns:
        export_df["z"] = df["z"]

    detail_columns = [
        column
        for column in df.attrs.get("detail_columns", ())
        if column in df.columns and column not in export_df.columns
    ]
    for column in detail_columns:
        export_df[column] = df[column]

    export_df.attrs.update(df.attrs)

    return export_df


def build_edges_export(edges):
    return pd.DataFrame(edges, columns=["source", "target", "weight"])
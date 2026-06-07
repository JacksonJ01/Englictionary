from pathlib import Path

import pandas as pd

import config
import visualize_spherical as vs


surface_path = Path(config.SPHERICAL_SURFACE_POINTS_FILE)
source_path = Path(config.SOURCE_FILE)

surface_df = pd.read_csv(surface_path)
source_df = pd.read_csv(source_path)

if "CORE 2: DOMAIN" in source_df.columns and "CORE 2: DOMAIN" not in surface_df.columns:
    row_numbers = surface_df["node_id"].str.extract(r"W(\d+)")[0].astype(int)
    surface_df["CORE 2: DOMAIN"] = source_df.loc[row_numbers, "CORE 2: DOMAIN"].fillna("").astype(str).to_numpy()

surface_df.attrs["source_row_count"] = int(len(source_df))

standard_columns = {"node_id", "word", "definition", "pos_group", "cluster", "x", "y", "z"}
detail_columns = [column for column in surface_df.columns if column not in standard_columns]
surface_df.attrs["detail_columns"] = tuple(detail_columns)
surface_df.to_csv(surface_path, index=False)

vs.render_spherical_surface(surface_df, config.SPHERICAL_SURFACE_HTML, live_reload=False)

print(surface_path)
print(detail_columns)

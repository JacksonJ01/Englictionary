from pathlib import Path


CSV_DIR = Path(__file__).with_name("csv")
SOURCE_FILE = CSV_DIR / "A+StudyTerms(GF).csv"
FILE_PATH = SOURCE_FILE  # Backward-compatible alias.
SOURCE_COLUMN_LIMIT = 9
OUTPUT_DIR = Path(__file__).with_name("output")
VISUALIZATION_MODE = "spherical"  # flat | spherical
FOCUS_COLUMN = "Term"
DEFINITION_COLUMN = "Definition"
TERM_COLUMN = FOCUS_COLUMN
TERM_COLUMN_CANDIDATES = (
	"Term",
	"Word",
	"term",
	"word",
	"study_term",
	"title",
	"name",
)
DEFINITION_COLUMN_CANDIDATES = (
	"Definition",
	"definition",
	"meaning",
	"explanation",
	"description",
)
USE_EMBEDDINGS = True
DIMENSIONS = 3
USE_UMAP = True
N_CLUSTERS = 120          # ~25 terms/cluster for 3001 rows (adaptive formula output)
K_NEIGHBORS = 35          # log2(3001)*alpha*token_factor — good graph density for 9-col rich context

MAX_FEATURES = 8000       # 77k definition tokens; 8k captures CompTIA technical vocab without noise
EMBEDDING_MODEL = "all-MiniLM-L6-v2"
RANDOM_STATE = 42
PREVIEW_POINT_THRESHOLD = 10000
MAX_EDGE_RENDER = 2000
LARGE_DATA_THRESHOLD = 50000
GRAPH_SEARCH_DIMS = 96    # 384-dim MiniLM vectors; 96 gives better neighbor accuracy at 3k scale

UMAP_N_NEIGHBORS = 57     # k*1.5 + log1p(9)*2 — balances local/global structure at 3k rows
UMAP_MIN_DIST = 0.30      # Tighter cluster separation for topic-dense CompTIA content
UMAP_SPREAD = 2.0

COORDINATE_SCALE = 3.0

ENABLE_3D_NODE_SPREAD = True
DISPLAY_MIN_DISTANCE = 0.15
DISPLAY_DISTANCE_NEIGHBORS = 6
DISPLAY_DISTANCE_PASSES = 2
MAX_DISPLAY_ADJUST_POINTS = 12000

MARKER_SIZE_3D = 2
MARKER_OPACITY_3D = 0.55
FIGURE_WIDTH = 1400
FIGURE_HEIGHT = 1000
SCENE_ASPECTMODE = "cube"
CAMERA_EYE_X = 1.8
CAMERA_EYE_Y = 1.8
CAMERA_EYE_Z = 1.4

PLOT_AUTO_OPEN = True
USE_EXISTING_OUTPUTS = True  # When True, open the last generated outputs instead of rerunning the pipeline.
PLOT_2D_FILE = OUTPUT_DIR / "semantic_map_2d.html"
PLOT_3D_FILE = OUTPUT_DIR / "semantic_map_3d.html"
NODES_FILE = CSV_DIR / "nodes.csv"
EDGES_FILE = CSV_DIR / "edges.csv"
RUN_METADATA_FILE = OUTPUT_DIR / "run_metadata.json"
RUN_HISTORY_FILE = OUTPUT_DIR / "run_history.json"

SPHERICAL_OUTPUT_DIR = OUTPUT_DIR / "spherical"
SPHERICAL_CSV_DIR = SPHERICAL_OUTPUT_DIR / "csv"
SPHERICAL_RUNS_DIR = OUTPUT_DIR / "runs"
SPHERICAL_LAUNCHER_HTML = OUTPUT_DIR / "spherical_launcher.html"
SPHERICAL_ROOT_HTML = SPHERICAL_OUTPUT_DIR / "sphere_level0.html"
SPHERICAL_HIERARCHY_FILE = SPHERICAL_OUTPUT_DIR / "hierarchy_nodes.csv"
SPHERICAL_COORDS_FILE = SPHERICAL_OUTPUT_DIR / "spherical_coords.csv"
SPHERICAL_MEMBERSHIPS_FILE = SPHERICAL_OUTPUT_DIR / "secondary_memberships.csv"
SPHERICAL_SURFACE_POINTS_FILE = SPHERICAL_CSV_DIR / "surface_points.csv"
SPHERICAL_SURFACE_HTML = SPHERICAL_OUTPUT_DIR / "CompTIAA+Study.html"
MAX_RECENT_RUNS = 8

SPHERE_TOP_CLUSTERS = 12
SPHERE_SUBCLUSTERS_PER_CLUSTER = 6
SPHERE_MIN_SUBCLUSTER_SIZE = 30
SPHERE_SECONDARY_MEMBERSHIPS = 2

SPHERE_TOP_RADIUS = 1.0
SPHERE_SUB_RADIUS = 1.08
SPHERE_WORD_RADIUS = 1.16
SPHERE_PATCH_RADIUS_SUB = 0.14
SPHERE_PATCH_RADIUS_WORD = 0.08
SPHERE_LOCAL_EDGE_K = 5

# Full-surface spherical mode settings (all rows on one globe)
SPHERE_FULL_SURFACE = True
SPHERE_CLUSTER_COUNT = 140        # Adaptive output: 140 clusters → ~21 terms/cluster on globe
SPHERE_RENDER_RADIUS = 285.0
SPHERE_POINT_LIFT = 1.012
SPHERE_NODE_PIXEL_SIZE = 2.6
SPHERE_NODE_ANGULAR_SPACING = 0.00322  # Adaptive compute for 3001 nodes / 140 clusters
SPHERE_CLUSTER_ANGULAR_PADDING = 0.022
SPHERE_CLUSTER_MAX_ANGULAR_RADIUS = 0.5
SPHERE_CLUSTER_REPEL_STEPS = 320  # Adaptive max — prevents overlap at 140 clusters
SPHERE_INCLUDE_DEFINITION_IN_HTML = False

# Large payload safeguards for browser stability.
SPHERE_DEFINITION_MAX_POINTS = 25000

# Adaptive config defaults for variable CSV shapes.
ENABLE_ADAPTIVE_CONFIG = True
ADAPTIVE_CLUSTER_ALPHA = 0.95
ADAPTIVE_NEIGHBOR_ALPHA = 2.2
ADAPTIVE_TOKEN_SCALE = 1.0
ADAPTIVE_MIN_CLUSTERS = 4
ADAPTIVE_MAX_CLUSTERS = 150        # Raised: current 3k data hits 120 ceiling; headroom for growth
ADAPTIVE_MIN_K_NEIGHBORS = 5
ADAPTIVE_MAX_K_NEIGHBORS = 50
ADAPTIVE_MIN_UMAP_NEIGHBORS = 8
ADAPTIVE_MAX_UMAP_NEIGHBORS = 80
ADAPTIVE_MIN_SPHERE_CLUSTERS = 8
ADAPTIVE_MAX_SPHERE_CLUSTERS = 175  # Raised proportionally (150 * 1.35 ≈ 202; kept conservative)
ADAPTIVE_MIN_REPEL_STEPS = 120
ADAPTIVE_MAX_REPEL_STEPS = 320

import json
import shutil
import webbrowser
from datetime import datetime
from pathlib import Path

from config import (
    MAX_RECENT_RUNS,
    OUTPUT_DIR,
    RUN_HISTORY_FILE,
    RUN_METADATA_FILE,
    SPHERICAL_LAUNCHER_HTML,
    SPHERICAL_OUTPUT_DIR,
    SPHERICAL_RUNS_DIR,
    SPHERICAL_SURFACE_HTML,
    SPHERICAL_SURFACE_POINTS_FILE,
)
from launcher_ui import open_launcher as open_menu_launcher


def _as_uri(path):
    return Path(path).resolve().as_uri()


def _read_json(path):
    path = Path(path)
    if not path.exists():
        return None

    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _write_json(path, payload):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _timestamp_token(now=None):
    now = now or datetime.now()
    return now.strftime("%Y%m%d_%H%M%S_%f")


def _first_existing_path(*paths):
  for path in paths:
    path = Path(path)
    if path.exists():
      return path
  return Path(paths[0])


def archive_current_spherical_outputs():
  if not SPHERICAL_OUTPUT_DIR.exists():
    return None

  archive_id = _timestamp_token()
  archive_root = SPHERICAL_RUNS_DIR / archive_id
  archive_target = archive_root / "spherical"
  archive_target.parent.mkdir(parents=True, exist_ok=True)
  shutil.copytree(SPHERICAL_OUTPUT_DIR, archive_target, dirs_exist_ok=True)
  if RUN_METADATA_FILE.exists():
    shutil.copy2(RUN_METADATA_FILE, archive_root / "run_metadata.json")
  return archive_root


def _read_run_metadata(run_dir):
  run_dir = Path(run_dir)
  metadata_path = run_dir / "run_metadata.json"
  if not metadata_path.exists():
    metadata_path = run_dir / "spherical" / "run_metadata.json"

  metadata = _read_json(metadata_path)
  if not metadata:
    return None

  plot_path = run_dir / "spherical" / "sphere_surface_all_nodes.html"
  points_path = _first_existing_path(
    run_dir / "spherical" / "csv" / "surface_points.csv",
    run_dir / "spherical" / "surface_points.csv",
  )
  metadata = dict(metadata)
  metadata["archive_dir"] = str(run_dir)
  metadata["plot_file"] = str(plot_path)
  metadata["points_file"] = str(points_path)
  metadata["plot_uri"] = _as_uri(plot_path)
  metadata["points_uri"] = _as_uri(points_path)
  metadata["launcher_uri"] = _as_uri(SPHERICAL_LAUNCHER_HTML)
  metadata["run_label"] = metadata.get("run_id") or run_dir.name
  return metadata


def discover_spherical_runs(current_metadata=None):
    runs = []

    if SPHERICAL_RUNS_DIR.exists():
        for run_dir in sorted(SPHERICAL_RUNS_DIR.iterdir()):
            if not run_dir.is_dir():
                continue
            metadata = _read_run_metadata(run_dir)
            if metadata:
                runs.append(metadata)

    if current_metadata:
        current_metadata = dict(current_metadata)
        current_plot = Path(SPHERICAL_SURFACE_HTML)
        current_points = Path(SPHERICAL_SURFACE_POINTS_FILE)
        current_metadata["archive_dir"] = "current"
        current_metadata["plot_file"] = str(current_plot)
        current_metadata["points_file"] = str(current_points)
        current_metadata["plot_uri"] = _as_uri(current_plot)
        current_metadata["points_uri"] = _as_uri(current_points)
        current_metadata["launcher_uri"] = _as_uri(SPHERICAL_LAUNCHER_HTML)
        current_metadata["run_label"] = current_metadata.get("run_id") or "current"
        runs.append(current_metadata)

    runs.sort(key=lambda item: item.get("run_timestamp", ""), reverse=True)
    return runs[:MAX_RECENT_RUNS]


def render_spherical_launcher(run_records, current_metadata=None):
    current_metadata = current_metadata or {}
    current_plot_uri = _as_uri(SPHERICAL_SURFACE_HTML)
    run_records = list(run_records or [])

    if not run_records and current_metadata:
        current_metadata = dict(current_metadata)
        current_metadata["plot_uri"] = current_plot_uri
        current_metadata["run_label"] = current_metadata.get("run_id") or "current"
        run_records = [current_metadata]

    if not run_records:
        html = """<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Englictionary Launcher</title><style>body{margin:0;font-family:Segoe UI,Arial,sans-serif;background:linear-gradient(135deg,#0f172a,#1e293b);color:#e2e8f0;display:grid;place-items:center;min-height:100vh;} .card{max-width:720px;padding:28px;border-radius:20px;background:rgba(15,23,42,0.88);border:1px solid rgba(148,163,184,0.22);box-shadow:0 20px 50px rgba(0,0,0,0.28);} h1{margin:0 0 10px;font-size:30px;} p{line-height:1.5;color:#cbd5e1;}</style></head><body><div class="card"><h1>Englictionary</h1><p>No spherical runs have been recorded yet. Run the pipeline once to create a launcher history page.</p></div></body></html>"""
        SPHERICAL_LAUNCHER_HTML.parent.mkdir(parents=True, exist_ok=True)
        SPHERICAL_LAUNCHER_HTML.write_text(html, encoding="utf-8")
        return SPHERICAL_LAUNCHER_HTML

    runs_json = json.dumps(run_records)
    launcher_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Englictionary Run Launcher</title>
  <style>
    :root {{
      --bg: #081120;
      --panel: rgba(15, 23, 42, 0.88);
      --panel-border: rgba(148, 163, 184, 0.18);
      --accent: #38bdf8;
      --accent-soft: rgba(56, 189, 248, 0.18);
      --text: #e2e8f0;
      --muted: #94a3b8;
    }}
    body {{
      margin: 0;
      min-height: 100vh;
      font-family: Segoe UI, Arial, sans-serif;
      background: radial-gradient(circle at top left, #1e293b, var(--bg) 58%);
      color: var(--text);
    }}
    .shell {{
      display: grid;
      grid-template-columns: 320px 1fr;
      min-height: 100vh;
    }}
    .sidebar {{
      padding: 20px;
      border-right: 1px solid rgba(148, 163, 184, 0.14);
      background: rgba(2, 6, 23, 0.36);
      backdrop-filter: blur(10px);
    }}
    .title {{ font-size: 30px; font-weight: 800; margin-bottom: 8px; }}
    .subtitle {{ color: var(--muted); font-size: 13px; line-height: 1.45; }}
    .panel {{
      margin-top: 18px;
      padding: 14px;
      border-radius: 16px;
      background: var(--panel);
      border: 1px solid var(--panel-border);
      box-shadow: 0 20px 50px rgba(0, 0, 0, 0.22);
    }}
    .section-title {{
      text-transform: uppercase;
      letter-spacing: 0.08em;
      font-size: 11px;
      color: var(--muted);
      margin-bottom: 8px;
    }}
    .tabs {{ display: grid; gap: 8px; max-height: 42vh; overflow: auto; padding-right: 4px; }}
    .tab {{
      width: 100%;
      text-align: left;
      padding: 11px 12px;
      border-radius: 12px;
      border: 1px solid rgba(148, 163, 184, 0.18);
      background: rgba(15, 23, 42, 0.8);
      color: var(--text);
      cursor: pointer;
      transition: transform 120ms ease, border-color 120ms ease, background 120ms ease;
    }}
    .tab:hover {{ transform: translateY(-1px); border-color: rgba(56, 189, 248, 0.4); }}
    .tab.active {{ background: var(--accent-soft); border-color: rgba(56, 189, 248, 0.55); }}
    .tab-label {{ font-weight: 700; font-size: 13px; }}
    .tab-meta {{ margin-top: 4px; font-size: 12px; color: var(--muted); line-height: 1.35; }}
    .viewer {{
      display: grid;
      grid-template-rows: auto 1fr;
      min-width: 0;
    }}
    .viewer-bar {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      padding: 18px 20px 0 20px;
    }}
    .viewer-title {{ font-size: 18px; font-weight: 700; }}
    .viewer-subtitle {{ color: var(--muted); font-size: 12px; margin-top: 4px; }}
    .viewer-frame-wrap {{ padding: 16px 20px 20px 20px; min-height: 0; }}
    iframe {{ width: 100%; height: calc(100vh - 120px); border: 0; border-radius: 18px; background: white; box-shadow: 0 28px 70px rgba(0, 0, 0, 0.35); }}
    .empty-state {{
      display: grid;
      place-items: center;
      height: calc(100vh - 120px);
      border-radius: 18px;
      background: rgba(15, 23, 42, 0.82);
      border: 1px dashed rgba(148, 163, 184, 0.28);
      color: var(--muted);
      text-align: center;
      padding: 24px;
    }}
    .summary-grid {{ display: grid; gap: 10px; grid-template-columns: repeat(2, minmax(0, 1fr)); margin-top: 12px; }}
    .summary-item {{ padding: 10px 12px; border-radius: 12px; background: rgba(15,23,42,0.72); border: 1px solid rgba(148,163,184,0.16); }}
    .summary-label {{ font-size: 11px; text-transform: uppercase; letter-spacing: 0.08em; color: var(--muted); }}
    .summary-value {{ margin-top: 5px; font-size: 13px; word-break: break-word; }}
    .link {{ color: var(--accent); text-decoration: none; }}
  </style>
</head>
<body>
  <div class="shell">
    <aside class="sidebar">
      <div class="title">Englictionary</div>
      <div class="subtitle">Recent spherical runs are preserved as archived tabs. Select a run to load its static HTML in the viewer on the right.</div>
      <div class="panel">
        <div class="section-title">Runs</div>
        <div id="tabs" class="tabs"></div>
      </div>
      <div class="panel">
        <div class="section-title">Selected run</div>
        <div id="selectedInfo" class="subtitle">Choose a run tab to inspect its settings.</div>
      </div>
    </aside>
    <main class="viewer">
      <div class="viewer-bar">
        <div>
          <div id="viewerTitle" class="viewer-title">Run Viewer</div>
          <div id="viewerSubtitle" class="viewer-subtitle">Static HTML output loaded from disk.</div>
        </div>
        <a id="openInNewTab" class="link" href="#" target="_blank" rel="noopener noreferrer">Open in new tab</a>
      </div>
      <div class="viewer-frame-wrap">
        <iframe id="viewerFrame" src="{current_plot_uri}" title="Englictionary run viewer"></iframe>
      </div>
    </main>
  </div>
  <script>
    const runs = {runs_json};
    const tabs = document.getElementById('tabs');
    const viewerFrame = document.getElementById('viewerFrame');
    const viewerTitle = document.getElementById('viewerTitle');
    const viewerSubtitle = document.getElementById('viewerSubtitle');
    const selectedInfo = document.getElementById('selectedInfo');
    const openInNewTab = document.getElementById('openInNewTab');

    function fmt(value) {{
      return value === null || value === undefined || value === '' ? 'n/a' : String(value);
    }}

    function renderSelected(run) {{
      viewerFrame.src = run.plot_uri;
      viewerTitle.textContent = run.run_label || 'Run Viewer';
      viewerSubtitle.textContent = `${{fmt(run.run_timestamp)}} · ${{fmt(run.source_file)}}`;
      openInNewTab.href = run.plot_uri;
      selectedInfo.innerHTML = [
        `<div class="summary-grid">`,
        `<div class="summary-item"><div class="summary-label">Rows</div><div class="summary-value">${{fmt(run.source_row_count || run.count || run.row_count)}}</div></div>`,
        `<div class="summary-item"><div class="summary-label">Mode</div><div class="summary-value">${{fmt(run.visualization_mode)}}</div></div>`,
        `<div class="summary-item"><div class="summary-label">Embeddings</div><div class="summary-value">${{fmt(run.use_embeddings)}}</div></div>`,
        `<div class="summary-item"><div class="summary-label">UMAP</div><div class="summary-value">${{fmt(run.use_umap)}}</div></div>`,
        `<div class="summary-item"><div class="summary-label">Clusters</div><div class="summary-value">${{fmt(run.n_clusters)}}</div></div>`,
        `<div class="summary-item"><div class="summary-label">Neighbors</div><div class="summary-value">${{fmt(run.k_neighbors)}}</div></div>`,
        `</div>`,
        `<div style="margin-top:12px;">Source: ${{fmt(run.source_file)}}</div>`,
        `<div>Output: ${{fmt(run.plot_file)}}</div>`
      ].join('');
    }}

    function markActive(button) {{
      document.querySelectorAll('.tab').forEach((tab) => tab.classList.remove('active'));
      button.classList.add('active');
    }}

    if (!runs.length) {{
      tabs.innerHTML = '<div class="subtitle">No runs available.</div>';
    }} else {{
      tabs.innerHTML = runs.map((run, index) => `
        <button class="tab ${{index === 0 ? 'active' : ''}}" data-index="${{index}}">
          <div class="tab-label">${{run.run_label || ('Run ' + (index + 1))}}</div>
          <div class="tab-meta">${{fmt(run.run_timestamp)}}<br>${{fmt(run.source_row_count || run.count || run.row_count)}} rows · ${{fmt(run.source_file)}}</div>
        </button>
      `).join('');

      const activate = (index, button) => {{
        const run = runs[index];
        renderSelected(run);
        markActive(button);
      }};

      tabs.querySelectorAll('.tab').forEach((button) => {{
        button.addEventListener('click', () => activate(Number(button.dataset.index), button));
      }});

      const initialButton = tabs.querySelector('.tab');
      if (initialButton) {{
        renderSelected(runs[0]);
        openInNewTab.href = runs[0].plot_uri;
      }}
    }}
  </script>
</body>
</html>
"""
    SPHERICAL_LAUNCHER_HTML.parent.mkdir(parents=True, exist_ok=True)
    SPHERICAL_LAUNCHER_HTML.write_text(launcher_html, encoding="utf-8")
    return SPHERICAL_LAUNCHER_HTML


def persist_run_history(current_metadata=None):
    records = discover_spherical_runs(current_metadata=current_metadata)
    _write_json(RUN_HISTORY_FILE, records)
    return records


def open_launcher(current_metadata=None):
  return open_menu_launcher(current_metadata=current_metadata)

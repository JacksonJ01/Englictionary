import json
import webbrowser
from pathlib import Path

import config as config_module
from config import MAX_RECENT_RUNS, SPHERICAL_LAUNCHER_HTML, SPHERICAL_SURFACE_HTML


def _as_uri(path):
    return Path(path).resolve().as_uri()


def _serializable_value(value):
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (bool, int, float, str)) or value is None:
        return value
    return str(value)


def _config_kind(name, value):
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int) and not isinstance(value, bool):
        return "int"
    if isinstance(value, float):
        return "float"
    return "text"


def _numeric_limits(name, value):
    if isinstance(value, bool):
        return 0, 1, 1

    if isinstance(value, int):
        if name in {"RANDOM_STATE", "DISPLAY_DISTANCE_NEIGHBORS", "SPHERE_LOCAL_EDGE_K"}:
            return 0, max(10, value * 4), 1
        if "COUNT" in name or name.startswith("N_") or name.endswith("SIZE"):
            return 0, max(10, value * 2), 1
        return 0, max(10, value * 2), 1

    if isinstance(value, float):
        if 0.0 <= value <= 1.0 or "OPACITY" in name or "MIN_DIST" in name:
            return 0.0, 1.0, 0.01
        if "RADIUS" in name or "SPREAD" in name:
            return 0.0, max(10.0, value * 2.0), 0.01 if value < 1 else 0.1
        return 0.0, max(10.0, value * 2.0), 0.1

    return None, None, None


def build_config_schema():
    fields = []
    for name in sorted(dir(config_module)):
        if not name.isupper():
            continue
        value = getattr(config_module, name)
        kind = _config_kind(name, value)
        field = {
            "name": name,
            "value": _serializable_value(value),
            "kind": kind,
            "category": (
                "spherical"
                if name.startswith("SPHERE") or name.startswith("SPHERICAL")
                else "output"
                if name.startswith("PLOT") or name.endswith("FILE") or name.endswith("DIR")
                else "pipeline"
            ),
        }
        if kind in {"int", "float"}:
            min_value, max_value, step = _numeric_limits(name, value)
            field.update({"min": min_value, "max": max_value, "step": step})
        fields.append(field)
    return fields


def _run_summary_text(run):
    row_count = run.get("source_row_count") or run.get("count") or run.get("row_count") or "n/a"
    return f"{run.get('run_label', 'Run')} · {run.get('run_timestamp', 'n/a')} · {row_count} rows"


def render_launcher_page(run_records, current_metadata=None):
    current_metadata = current_metadata or {}
    run_records = list(run_records or [])
    config_schema = build_config_schema()

    if not run_records:
        current_plot = _as_uri(SPHERICAL_SURFACE_HTML)
        current_metadata = dict(current_metadata)
        current_metadata.setdefault("plot_uri", current_plot)
        current_metadata.setdefault("run_label", "Current")
        run_records = [current_metadata]

    launcher_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Englictionary Menu</title>
  <style>
    :root {{
      --bg: #07111f;
      --panel: rgba(15, 23, 42, 0.9);
      --panel-2: rgba(2, 6, 23, 0.52);
      --border: rgba(148, 163, 184, 0.18);
      --border-strong: rgba(56, 189, 248, 0.38);
      --text: #e2e8f0;
      --muted: #94a3b8;
      --accent: #38bdf8;
      --accent-soft: rgba(56, 189, 248, 0.16);
      --good: #34d399;
    }}
    body {{
      margin: 0;
      min-height: 100vh;
      font-family: Segoe UI, Arial, sans-serif;
      background:
        radial-gradient(circle at top left, rgba(56, 189, 248, 0.14), transparent 35%),
        radial-gradient(circle at 85% 0%, rgba(99, 102, 241, 0.14), transparent 30%),
        linear-gradient(135deg, #020617, var(--bg) 58%);
      color: var(--text);
    }}
    .shell {{ display: grid; grid-template-columns: 360px 1fr; min-height: 100vh; }}
    .sidebar {{
      padding: 18px;
      border-right: 1px solid rgba(148, 163, 184, 0.12);
      background: rgba(2, 6, 23, 0.34);
      backdrop-filter: blur(12px);
    }}
    .brand {{ font-size: 28px; font-weight: 800; letter-spacing: 0.01em; }}
    .brand-sub {{ margin-top: 6px; color: var(--muted); line-height: 1.45; font-size: 13px; }}
    .tab-strip {{ display: flex; gap: 8px; margin-top: 16px; flex-wrap: wrap; }}
    .tab-btn {{
      padding: 9px 12px;
      border-radius: 999px;
      border: 1px solid rgba(148, 163, 184, 0.18);
      background: rgba(15, 23, 42, 0.72);
      color: var(--text);
      cursor: pointer;
      font-size: 12px;
      font-weight: 700;
    }}
    .tab-btn.active {{ background: var(--accent-soft); border-color: var(--border-strong); }}
    .panel {{
      margin-top: 16px;
      padding: 14px;
      border-radius: 18px;
      background: var(--panel);
      border: 1px solid var(--border);
      box-shadow: 0 24px 50px rgba(0, 0, 0, 0.2);
    }}
    .panel-title {{
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      color: var(--muted);
      margin-bottom: 10px;
    }}
    .source-list, .run-list {{ display: grid; gap: 8px; }}
    .source-card, .run-card {{
      width: 100%;
      text-align: left;
      padding: 12px;
      border-radius: 14px;
      border: 1px solid rgba(148, 163, 184, 0.16);
      background: rgba(15, 23, 42, 0.72);
      color: var(--text);
      cursor: pointer;
    }}
    .source-card.active, .run-card.active {{ border-color: var(--border-strong); background: var(--accent-soft); }}
    .card-title {{ font-size: 13px; font-weight: 800; }}
    .card-meta {{ font-size: 12px; color: var(--muted); line-height: 1.35; margin-top: 4px; }}
    .menu-row {{ display: flex; gap: 8px; flex-wrap: wrap; margin-top: 12px; }}
    .menu-btn {{
      padding: 10px 12px;
      border-radius: 12px;
      border: 1px solid rgba(148, 163, 184, 0.16);
      background: rgba(15, 23, 42, 0.84);
      color: var(--text);
      cursor: pointer;
      font-size: 12px;
      font-weight: 700;
    }}
    .menu-btn.primary {{ background: linear-gradient(135deg, #0ea5e9, #2563eb); border-color: rgba(56, 189, 248, 0.5); }}
    .menu-note {{ margin-top: 10px; color: var(--muted); font-size: 12px; line-height: 1.45; }}
    .main {{ display: grid; grid-template-rows: auto 1fr; min-width: 0; }}
    .header {{
      display: flex; justify-content: space-between; align-items: center; gap: 12px;
      padding: 18px 20px 0 20px;
    }}
    .header-title {{ font-size: 18px; font-weight: 800; }}
    .header-sub {{ font-size: 12px; color: var(--muted); margin-top: 4px; }}
    .content {{ padding: 16px 20px 20px; min-height: 0; }}
    .sphere-stage {{
      position: relative;
      height: calc(100vh - 118px);
      border-radius: 24px;
      overflow: hidden;
      background:
        radial-gradient(circle at 50% 42%, rgba(56, 189, 248, 0.24), rgba(15, 23, 42, 0.88) 28%, rgba(2, 6, 23, 0.98) 60%),
        linear-gradient(180deg, rgba(15, 23, 42, 0.95), rgba(2, 6, 23, 0.98));
      border: 1px solid rgba(148, 163, 184, 0.18);
      box-shadow: 0 28px 70px rgba(0, 0, 0, 0.36);
    }}
    .sphere-stage::before {{
      content: "";
      position: absolute;
      inset: 8% 18%;
      border-radius: 50%;
      border: 1px solid rgba(148, 163, 184, 0.14);
      box-shadow: inset 0 0 90px rgba(56, 189, 248, 0.08);
    }}
    .sphere-stage::after {{
      content: "";
      position: absolute;
      left: 50%; top: 50%; transform: translate(-50%, -50%);
      width: min(58vw, 58vh); height: min(58vw, 58vh);
      border-radius: 50%;
      border: 2px solid rgba(148, 163, 184, 0.2);
      box-shadow: 0 0 0 22px rgba(15, 23, 42, 0.4), inset 0 0 70px rgba(56, 189, 248, 0.06);
    }}
    .vacant-copy {{
      position: absolute; inset: 0; display: grid; place-items: center;
      text-align: center; pointer-events: none; z-index: 2;
      padding: 24px;
    }}
    .vacant-title {{ font-size: 42px; font-weight: 900; letter-spacing: 0.03em; }}
    .vacant-sub {{ margin-top: 10px; font-size: 14px; color: var(--muted); max-width: 520px; line-height: 1.55; }}
    .hidden {{ display: none !important; }}
    .config-browser {{ display: grid; gap: 10px; }}
    .config-nav {{ display: flex; align-items: center; justify-content: space-between; gap: 8px; }}
    .config-name {{ font-size: 16px; font-weight: 800; word-break: break-word; }}
    .arrow-btn {{
      width: 34px; height: 34px; border-radius: 999px; border: 1px solid rgba(148,163,184,0.2);
      background: rgba(15,23,42,0.9); color: var(--text); cursor: pointer; font-size: 18px;
    }}
    .field-meta {{ color: var(--muted); font-size: 12px; line-height: 1.45; }}
    .field-control {{ display: grid; gap: 8px; margin-top: 8px; }}
    .field-input {{ width: 100%; box-sizing: border-box; }}
    input[type="text"], input[type="number"] {{
      width: 100%; box-sizing: border-box; padding: 9px 10px; border-radius: 10px;
      border: 1px solid rgba(148,163,184,0.22); background: rgba(2,6,23,0.46);
      color: var(--text); font-family: inherit; font-size: 12px;
    }}
    input[type="range"] {{ width: 100%; }}
    .toggle-row {{ display: flex; align-items: center; gap: 8px; }}
    .tiny {{ font-size: 11px; color: var(--muted); }}
    .file-chip {{ display: flex; align-items: center; justify-content: space-between; gap: 8px; padding: 10px 12px; border-radius: 12px; background: rgba(15,23,42,0.72); border: 1px solid rgba(148,163,184,0.14); }}
    .file-chip strong {{ display: block; font-size: 13px; }}
    .csv-preview {{ margin-top: 10px; font-size: 12px; color: var(--muted); line-height: 1.45; white-space: pre-wrap; }}
    iframe {{ width: 100%; height: 100%; border: 0; border-radius: 24px; background: #fff; box-shadow: 0 28px 70px rgba(0, 0, 0, 0.26); }}
  </style>
</head>
<body>
  <div class="shell">
    <aside class="sidebar">
      <div class="brand">Englictionary</div>
      <div class="brand-sub">Menu-first launcher with a vacant sphere, CSV import, config browsing, and saved run tabs.</div>

      <div class="tab-strip">
        <button class="tab-btn active" data-view="home">Home</button>
        <button class="tab-btn" data-view="settings">Settings</button>
        <button class="tab-btn" data-view="runs">Runs</button>
      </div>

      <div id="homePanel" class="panel">
        <div class="panel-title">Source menu</div>
        <div class="menu-row">
          <button id="importCsvBtn" class="menu-btn primary" type="button">Import CSV</button>
          <button id="clearCsvBtn" class="menu-btn" type="button">Clear source</button>
        </div>
        <input id="csvInput" type="file" accept=".csv,text/csv" class="hidden">
        <div id="sourceChip" class="file-chip" style="margin-top:12px;">
          <div>
            <strong>Vacant sphere</strong>
            <div class="tiny">No CSV selected yet.</div>
          </div>
        </div>
        <div id="csvPreview" class="csv-preview">Import a CSV to preview its headers and row count here.</div>
      </div>

      <div id="settingsPanel" class="panel hidden">
        <div class="panel-title">Config browser</div>
        <div class="config-browser">
          <div class="config-nav">
            <button id="configPrev" class="arrow-btn" type="button">‹</button>
            <div id="configName" class="config-name"></div>
            <button id="configNext" class="arrow-btn" type="button">›</button>
          </div>
          <div id="configMeta" class="field-meta"></div>
          <div id="configControl" class="field-control"></div>
          <div class="menu-row">
            <button id="savePresetBtn" class="menu-btn primary" type="button">Save preset JSON</button>
            <button id="resetPresetBtn" class="menu-btn" type="button">Reset</button>
          </div>
          <div class="menu-note">These controls edit a browser-side preset for now. The menu is in place so the config can be fed back into the pipeline in the next step.</div>
        </div>
      </div>

      <div id="runsPanel" class="panel hidden">
        <div class="panel-title">Recent runs</div>
        <div id="runList" class="run-list"></div>
      </div>
    </aside>

    <main class="main">
      <div class="header">
        <div>
          <div id="viewerTitle" class="header-title">Vacant Sphere</div>
          <div id="viewerSub" class="header-sub">The sphere starts empty until you choose a CSV or open a saved run.</div>
        </div>
        <a id="openInNewTab" href="#" target="_blank" rel="noopener noreferrer" style="color:var(--accent);text-decoration:none;font-weight:700;">Open current view</a>
      </div>
      <div class="content">
        <div id="homeView" class="sphere-stage">
          <div class="vacant-copy">
            <div>
              <div class="vacant-title">Vacant sphere</div>
              <div class="vacant-sub">Use the menu on the left to import a CSV, browse config values, or switch to a saved run. The sphere will stay empty until a dataset is selected.</div>
            </div>
          </div>
        </div>
        <div id="runView" class="hidden" style="height: calc(100vh - 118px);">
          <iframe id="runFrame" src="{_as_uri(SPHERICAL_SURFACE_HTML)}" title="Englictionary run viewer"></iframe>
        </div>
      </div>
    </main>
  </div>

  <script>
    const runs = {json.dumps(run_records)};
    const configSchema = {json.dumps(config_schema)};
    const tabs = Array.from(document.querySelectorAll('.tab-btn'));
    const panels = {{ home: document.getElementById('homePanel'), settings: document.getElementById('settingsPanel'), runs: document.getElementById('runsPanel') }};
    const homeView = document.getElementById('homeView');
    const runView = document.getElementById('runView');
    const runFrame = document.getElementById('runFrame');
    const viewerTitle = document.getElementById('viewerTitle');
    const viewerSub = document.getElementById('viewerSub');
    const openInNewTab = document.getElementById('openInNewTab');
    const importCsvBtn = document.getElementById('importCsvBtn');
    const clearCsvBtn = document.getElementById('clearCsvBtn');
    const csvInput = document.getElementById('csvInput');
    const sourceChip = document.getElementById('sourceChip');
    const csvPreview = document.getElementById('csvPreview');
    const runList = document.getElementById('runList');
    const configName = document.getElementById('configName');
    const configMeta = document.getElementById('configMeta');
    const configControl = document.getElementById('configControl');
    const configPrev = document.getElementById('configPrev');
    const configNext = document.getElementById('configNext');
    const savePresetBtn = document.getElementById('savePresetBtn');
    const resetPresetBtn = document.getElementById('resetPresetBtn');

    const localStorageKey = 'englictionary.launcher';
    const state = {{
      view: 'home',
      source: null,
      configIndex: 0,
      configOverrides: {{}},
      activeRunIndex: null,
    }};

    function loadState() {{
      try {{
        const stored = JSON.parse(localStorage.getItem(localStorageKey) || '{{}}');
        if (stored && typeof stored === 'object') {{
          if (stored.source) state.source = stored.source;
          if (typeof stored.configIndex === 'number') state.configIndex = stored.configIndex;
          if (stored.configOverrides && typeof stored.configOverrides === 'object') state.configOverrides = stored.configOverrides;
        }}
      }} catch (err) {{
        console.warn(err);
      }}
    }}

    function saveState() {{
      localStorage.setItem(localStorageKey, JSON.stringify({{
        source: state.source,
        configIndex: state.configIndex,
        configOverrides: state.configOverrides,
      }}));
    }}

    function setView(view) {{
      state.view = view;
      tabs.forEach((tab) => tab.classList.toggle('active', tab.dataset.view === view));
      Object.entries(panels).forEach(([name, panel]) => panel.classList.toggle('hidden', name !== view));
      homeView.classList.toggle('hidden', view !== 'home');
      runView.classList.toggle('hidden', view === 'home' || view === 'settings');
      if (view === 'home') {{
        viewerTitle.textContent = 'Vacant Sphere';
        viewerSub.textContent = 'The sphere starts empty until you choose a CSV or open a saved run.';
        openInNewTab.href = '{_as_uri(SPHERICAL_SURFACE_HTML)}';
      }}
      if (view === 'settings') {{
        viewerTitle.textContent = 'Configuration';
        viewerSub.textContent = 'Browse and edit config values with the arrows on the left.';
      }}
      if (view === 'runs') {{
        viewerTitle.textContent = 'Saved Runs';
        viewerSub.textContent = 'Pick a saved run to load its archived HTML in the viewer.';
      }}
    }}

    function renderSourceChip() {{
      if (!state.source) {{
        sourceChip.innerHTML = '<div><strong>Vacant sphere</strong><div class="tiny">No CSV selected yet.</div></div>';
        csvPreview.textContent = 'Import a CSV to preview its headers and row count here.';
        return;
      }}

      const headers = state.source.headers.length ? state.source.headers.join(', ') : 'No headers detected';
      sourceChip.innerHTML = `
        <div>
          <strong>${{state.source.name}}</strong>
          <div class="tiny">${{state.source.rows}} data rows · ${{state.source.headers.length}} columns</div>
        </div>
        <div class="tiny">CSV loaded</div>
      `;
      csvPreview.textContent = `Headers:\n${{headers}}\n\nPreview rows:\n${{state.source.preview.join('\n')}}`;
    }}

    function parseCsvPreview(text) {{
      const lines = String(text || '').replace(/\r/g, '').split('\n').filter((line) => line.trim() !== '');
      const headerLine = lines[0] || '';
      const headers = parseCsvLine(headerLine);
      const preview = lines.slice(1, 4);
      return {{
        headers,
        rows: Math.max(0, lines.length - 1),
        preview,
      }};
    }}

    function parseCsvLine(line) {{
      const values = [];
      let current = '';
      let inQuotes = false;
      for (let i = 0; i < line.length; i += 1) {{
        const char = line[i];
        if (char === '"') {{
          if (inQuotes && line[i + 1] === '"') {{
            current += '"';
            i += 1;
          }} else {{
            inQuotes = !inQuotes;
          }}
          continue;
        }}
        if (char === ',' && !inQuotes) {{
          values.push(current.trim());
          current = '';
          continue;
        }}
        current += char;
      }}
      values.push(current.trim());
      return values;
    }}

    function renderRuns() {{
      if (!runs.length) {{
        runList.innerHTML = '<div class="card-meta">No archived runs yet.</div>';
        return;
      }}
      runList.innerHTML = runs.map((run, index) => `
        <button class="run-card ${{state.activeRunIndex === index ? 'active' : ''}}" data-index="${{index}}">
          <div class="card-title">${{run.run_label || ('Run ' + (index + 1))}}</div>
          <div class="card-meta">${{run.run_timestamp || 'n/a'}}<br>${{run.source_row_count || run.count || run.row_count || 'n/a'}} rows</div>
        </button>
      `).join('');

      runList.querySelectorAll('.run-card').forEach((button) => {{
        button.addEventListener('click', () => {{
          const index = Number(button.dataset.index);
          const run = runs[index];
          state.activeRunIndex = index;
          setView('runs');
          runFrame.src = run.plot_uri;
          viewerTitle.textContent = run.run_label || 'Saved Run';
          viewerSub.textContent = `${{run.run_timestamp || 'n/a'}} · ${{run.source_file || 'saved output'}}`;
          openInNewTab.href = run.plot_uri;
          tabs.forEach((tab) => tab.classList.toggle('active', tab.dataset.view === 'runs'));
          renderRuns();
          saveState();
        }});
      }});
    }}

    function renderConfigField() {{
      if (!configSchema.length) {{
        configName.textContent = 'No config fields found';
        configMeta.textContent = '';
        configControl.innerHTML = '';
        return;
      }}

      const field = configSchema[state.configIndex % configSchema.length];
      const value = Object.prototype.hasOwnProperty.call(state.configOverrides, field.name)
        ? state.configOverrides[field.name]
        : field.value;
      configName.textContent = field.name;
      configMeta.textContent = `Category: ${{field.category}} · Type: ${{field.kind}}`;

      if (field.kind === 'bool') {{
        const checked = String(value).toLowerCase() === 'true';
        configControl.innerHTML = `
          <label class="toggle-row"><input id="cfgBool" type="checkbox" ${{checked ? 'checked' : ''}}> Enable</label>
          <input id="cfgText" class="field-input" type="text" value="${{checked}}">
        `;
        const boolInput = document.getElementById('cfgBool');
        const textInput = document.getElementById('cfgText');
        boolInput.addEventListener('change', () => {{
          state.configOverrides[field.name] = boolInput.checked;
          textInput.value = String(boolInput.checked);
          saveState();
        }});
        textInput.addEventListener('change', () => {{
          const nextValue = String(textInput.value).trim().toLowerCase() === 'true';
          state.configOverrides[field.name] = nextValue;
          boolInput.checked = nextValue;
          saveState();
        }});
        return;
      }}

      if (field.kind === 'int' || field.kind === 'float') {{
        const numericValue = Number(value);
        const minValue = field.min ?? 0;
        const maxValue = field.max ?? Math.max(10, numericValue * 2 || 10);
        const stepValue = field.step ?? (field.kind === 'int' ? 1 : 0.1);
        configControl.innerHTML = `
          <input id="cfgRange" type="range" min="${{minValue}}" max="${{maxValue}}" step="${{stepValue}}" value="${{Number.isFinite(numericValue) ? numericValue : minValue}}">
          <input id="cfgNumber" class="field-input" type="text" value="${{value}}">
        `;
        const rangeInput = document.getElementById('cfgRange');
        const numberInput = document.getElementById('cfgNumber');
        const updateValue = (next) => {{
          state.configOverrides[field.name] = field.kind === 'int' ? Math.round(Number(next)) : Number(next);
          numberInput.value = String(state.configOverrides[field.name]);
          rangeInput.value = String(state.configOverrides[field.name]);
          saveState();
        }};
        rangeInput.addEventListener('input', () => updateValue(rangeInput.value));
        numberInput.addEventListener('change', () => updateValue(numberInput.value));
        return;
      }}

      configControl.innerHTML = `
        <input id="cfgText" class="field-input" type="text" value="${{String(value).replace(/"/g, '&quot;')}}">
      `;
      const textInput = document.getElementById('cfgText');
      textInput.addEventListener('change', () => {{
        state.configOverrides[field.name] = textInput.value;
        saveState();
      }});
    }}

    function exportPreset() {{
      const payload = {{
        configOverrides: state.configOverrides,
        source: state.source,
        savedAt: new Date().toISOString(),
      }};
      const blob = new Blob([JSON.stringify(payload, null, 2)], {{ type: 'application/json' }});
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = 'englictionary_preset.json';
      link.click();
      URL.revokeObjectURL(url);
    }}

    tabs.forEach((tab) => tab.addEventListener('click', () => {{
      setView(tab.dataset.view);
      if (tab.dataset.view === 'runs') {{
        state.activeRunIndex = state.activeRunIndex ?? 0;
        if (runs[state.activeRunIndex]) {{
          runFrame.src = runs[state.activeRunIndex].plot_uri;
          viewerTitle.textContent = runs[state.activeRunIndex].run_label || 'Saved Run';
          viewerSub.textContent = `${{runs[state.activeRunIndex].run_timestamp || 'n/a'}} · ${{runs[state.activeRunIndex].source_file || 'saved output'}}`;
          openInNewTab.href = runs[state.activeRunIndex].plot_uri;
        }}
      }}
      saveState();
    }}));

    importCsvBtn.addEventListener('click', () => csvInput.click());
    csvInput.addEventListener('change', async () => {{
      const file = csvInput.files && csvInput.files[0];
      if (!file) return;
      const text = await file.text();
      const parsed = parseCsvPreview(text);
      state.source = {{
        name: file.name,
        rows: parsed.rows,
        headers: parsed.headers,
        preview: parsed.preview,
      }};
      state.activeRunIndex = null;
      renderSourceChip();
      saveState();
    }});

    clearCsvBtn.addEventListener('click', () => {{
      state.source = null;
      renderSourceChip();
      saveState();
    }});

    configPrev.addEventListener('click', () => {{
      state.configIndex = (state.configIndex - 1 + configSchema.length) % configSchema.length;
      renderConfigField();
      saveState();
    }});
    configNext.addEventListener('click', () => {{
      state.configIndex = (state.configIndex + 1) % configSchema.length;
      renderConfigField();
      saveState();
    }});
    savePresetBtn.addEventListener('click', exportPreset);
    resetPresetBtn.addEventListener('click', () => {{
      state.configOverrides = {{}};
      state.configIndex = 0;
      renderConfigField();
      saveState();
    }});

    loadState();
    renderSourceChip();
    renderRuns();
    renderConfigField();
    setView('home');
    if (state.source) {{
      renderSourceChip();
    }}
  </script>
</body>
</html>
"""
    SPHERICAL_LAUNCHER_HTML.parent.mkdir(parents=True, exist_ok=True)
    SPHERICAL_LAUNCHER_HTML.write_text(launcher_html, encoding="utf-8")
    return SPHERICAL_LAUNCHER_HTML


def open_launcher(current_metadata=None):
    launcher_path = render_launcher_page(
        run_records=discover_spherical_runs(current_metadata=current_metadata),
        current_metadata=current_metadata,
    )
    webbrowser.open(launcher_path.resolve().as_uri())
    return launcher_path

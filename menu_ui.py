import json
from pathlib import Path

import config as config_module


def _config_kind(value):
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
        kind = _config_kind(value)
        field = {
            "name": name,
            "value": value if isinstance(value, (bool, int, float, str)) or value is None else str(value),
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


def render_menu_page(api_base_url):
    config_schema = build_config_schema()
    return f"""<!DOCTYPE html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\">
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">
  <title>Englictionary Menu</title>
  <style>
    :root {{
      --bg: #08111f;
      --panel: rgba(15, 23, 42, 0.9);
      --panel-2: rgba(2, 6, 23, 0.52);
      --border: rgba(148, 163, 184, 0.18);
      --border-strong: rgba(56, 189, 248, 0.38);
      --text: #e2e8f0;
      --muted: #94a3b8;
      --accent: #38bdf8;
      --accent-soft: rgba(56, 189, 248, 0.16);
    }}
    body {{ margin: 0; min-height: 100vh; font-family: Segoe UI, Arial, sans-serif; background: radial-gradient(circle at top left, rgba(56,189,248,0.14), transparent 35%), radial-gradient(circle at 85% 0%, rgba(99,102,241,0.14), transparent 30%), linear-gradient(135deg, #020617, var(--bg) 58%); color: var(--text); }}
    .shell {{ display: grid; grid-template-columns: 390px 1fr; min-height: 100vh; }}
    .sidebar {{ padding: 18px; border-right: 1px solid rgba(148,163,184,0.12); background: rgba(2,6,23,0.34); backdrop-filter: blur(12px); }}
    .brand {{ font-size: 28px; font-weight: 800; }}
    .brand-sub {{ margin-top: 6px; color: var(--muted); line-height: 1.45; font-size: 13px; }}
    .panel {{ margin-top: 16px; padding: 14px; border-radius: 18px; background: var(--panel); border: 1px solid var(--border); box-shadow: 0 24px 50px rgba(0,0,0,0.2); }}
    .panel-title {{ font-size: 11px; text-transform: uppercase; letter-spacing: 0.08em; color: var(--muted); margin-bottom: 10px; }}
    .menu-row {{ display: flex; gap: 8px; flex-wrap: wrap; margin-top: 12px; }}
    .menu-btn {{ padding: 10px 12px; border-radius: 12px; border: 1px solid rgba(148,163,184,0.16); background: rgba(15,23,42,0.84); color: var(--text); cursor: pointer; font-size: 12px; font-weight: 700; }}
    .menu-btn.primary {{ background: linear-gradient(135deg, #0ea5e9, #2563eb); border-color: rgba(56,189,248,0.5); }}
    .menu-btn:disabled {{ opacity: 0.45; cursor: not-allowed; }}
    .source-chip {{ display: flex; align-items: center; justify-content: space-between; gap: 8px; padding: 10px 12px; border-radius: 12px; background: rgba(15,23,42,0.72); border: 1px solid rgba(148,163,184,0.14); }}
    .source-chip strong {{ display: block; font-size: 13px; }}
    .tiny {{ font-size: 11px; color: var(--muted); }}
    .csv-preview {{ margin-top: 10px; font-size: 12px; color: var(--muted); line-height: 1.45; white-space: pre-wrap; }}
    .config-nav {{ display: flex; align-items: center; justify-content: space-between; gap: 8px; }}
    .config-name {{ font-size: 16px; font-weight: 800; word-break: break-word; }}
    .arrow-btn {{ width: 34px; height: 34px; border-radius: 999px; border: 1px solid rgba(148,163,184,0.2); background: rgba(15,23,42,0.9); color: var(--text); cursor: pointer; font-size: 18px; }}
    .field-meta {{ color: var(--muted); font-size: 12px; line-height: 1.45; margin-top: 6px; }}
    .field-control {{ display: grid; gap: 8px; margin-top: 8px; }}
    input[type=\"text\"], input[type=\"number\"] {{ width: 100%; box-sizing: border-box; padding: 9px 10px; border-radius: 10px; border: 1px solid rgba(148,163,184,0.22); background: rgba(2,6,23,0.46); color: var(--text); font-family: inherit; font-size: 12px; }}
    input[type=\"range\"] {{ width: 100%; }}
    .toggle-row {{ display: flex; align-items: center; gap: 8px; }}
    .nav-tabs {{ display: flex; gap: 8px; margin-top: 16px; flex-wrap: wrap; }}
    .nav-tab {{ padding: 9px 12px; border-radius: 999px; border: 1px solid rgba(148,163,184,0.18); background: rgba(15,23,42,0.72); color: var(--text); cursor: pointer; font-size: 12px; font-weight: 700; }}
    .nav-tab.active {{ background: var(--accent-soft); border-color: var(--border-strong); }}
    .status {{ margin-top: 10px; color: var(--muted); font-size: 12px; line-height: 1.45; }}
    .main {{ display: grid; grid-template-rows: auto 1fr; min-width: 0; }}
    .header {{ display: flex; justify-content: space-between; align-items: center; gap: 12px; padding: 18px 20px 0 20px; }}
    .header-title {{ font-size: 18px; font-weight: 800; }}
    .header-sub {{ font-size: 12px; color: var(--muted); margin-top: 4px; }}
    .content {{ padding: 16px 20px 20px; min-height: 0; }}
    .sphere-stage {{ position: relative; height: calc(100vh - 118px); border-radius: 24px; overflow: hidden; background: radial-gradient(circle at 50% 42%, rgba(56,189,248,0.24), rgba(15,23,42,0.88) 28%, rgba(2,6,23,0.98) 60%), linear-gradient(180deg, rgba(15,23,42,0.95), rgba(2,6,23,0.98)); border: 1px solid rgba(148,163,184,0.18); box-shadow: 0 28px 70px rgba(0,0,0,0.36); }}
    .sphere-stage::before {{ content: \"\"; position: absolute; inset: 8% 18%; border-radius: 50%; border: 1px solid rgba(148,163,184,0.14); box-shadow: inset 0 0 90px rgba(56,189,248,0.08); }}
    .vacant-copy {{ position: absolute; inset: 0; display: grid; place-items: center; text-align: center; pointer-events: none; z-index: 2; padding: 24px; }}
    .vacant-title {{ font-size: 42px; font-weight: 900; letter-spacing: 0.03em; }}
    .vacant-sub {{ margin-top: 10px; font-size: 14px; color: var(--muted); max-width: 560px; line-height: 1.55; }}
    .result-frame {{ width: 100%; height: 100%; border: 0; border-radius: 24px; background: #fff; box-shadow: 0 28px 70px rgba(0,0,0,0.26); }}
    .hidden {{ display: none !important; }}
  </style>
</head>
<body>
  <div class=\"shell\">
    <aside class=\"sidebar\">
      <div class=\"brand\">Englictionary</div>
      <div class=\"brand-sub\">Menu-first launcher with CSV import, config controls, and saved processing tabs. Select a CSV, adjust values, then hit Start.</div>

      <div class=\"nav-tabs\">
        <button class=\"nav-tab active\" data-panel=\"home\">Home</button>
        <button class=\"nav-tab\" data-panel=\"settings\">Settings</button>
      </div>

      <div id=\"homePanel\" class=\"panel\">
        <div class=\"panel-title\">Source menu</div>
        <div class=\"menu-row\">
          <label id=\"importCsvBtn\" class=\"menu-btn primary\" for=\"csvInput\">Import CSV</label>
          <button id=\"startBtn\" class=\"menu-btn\" type=\"button\" disabled>Start processing</button>
          <button id=\"clearCsvBtn\" class=\"menu-btn\" type=\"button\">Clear source</button>
        </div>
        <input id=\"csvInput\" type=\"file\" accept=\".csv,text/csv\" style=\"position:fixed;left:-9999px;opacity:0;width:1px;height:1px;\" aria-hidden=\"true\" tabindex=\"-1\">
        <div id=\"sourceChip\" class=\"source-chip\" style=\"margin-top:12px;\">
          <div>
            <strong>No source loaded</strong>
            <div class=\"tiny\">No CSV selected yet.</div>
          </div>
        </div>
        <div id=\"csvPreview\" class=\"csv-preview\">Import a CSV to preview its headers and row count here.</div>
        <div id=\"status\" class=\"status\">The sphere stays vacant until you import a CSV and start processing.</div>
      </div>

      <div id=\"settingsPanel\" class=\"panel hidden\">
        <div class=\"panel-title\">Config browser</div>
        <div class=\"config-nav\">
          <button id=\"configPrev\" class=\"arrow-btn\" type=\"button\">‹</button>
          <div id=\"configName\" class=\"config-name\"></div>
          <button id=\"configNext\" class=\"arrow-btn\" type=\"button\">›</button>
        </div>
        <div id=\"configMeta\" class=\"field-meta\"></div>
        <div id=\"configControl\" class=\"field-control\"></div>
        <div class=\"menu-row\">
          <button id=\"resetPresetBtn\" class=\"menu-btn\" type=\"button\">Reset</button>
        </div>
      </div>
    </aside>

    <main class=\"main\">
      <div class=\"header\">
        <div>
          <div id=\"viewerTitle\" class=\"header-title\">Ready for a CSV</div>
          <div id=\"viewerSub\" class=\"header-sub\">Import a CSV to enable vectorizing and batch processing.</div>
        </div>
        <a id=\"openInNewTab\" href=\"#\" target=\"_blank\" rel=\"noopener noreferrer\" style=\"color:var(--accent);text-decoration:none;font-weight:700;\">Open current view</a>
      </div>
      <div class=\"content\">
        <div id=\"homeView\" class=\"sphere-stage\">
          <div class=\"vacant-copy\">
            <div>
              <div class=\"vacant-title\">Ready to import</div>
              <div class=\"vacant-sub\">The sphere remains empty until you import a CSV and click Start processing. The loaded dataset will then be vectorized and rendered here.</div>
            </div>
          </div>
        </div>
        <iframe id=\"resultFrame\" class=\"result-frame hidden\" title=\"Englictionary result view\"></iframe>
      </div>
    </main>
  </div>

  <script>
    const apiBaseUrl = {json.dumps(api_base_url)};
    const configSchema = {json.dumps(config_schema)};
    const panels = Array.from(document.querySelectorAll('.nav-tab'));
    const homePanel = document.getElementById('homePanel');
    const settingsPanel = document.getElementById('settingsPanel');
    const homeView = document.getElementById('homeView');
    const resultFrame = document.getElementById('resultFrame');
    const viewerTitle = document.getElementById('viewerTitle');
    const viewerSub = document.getElementById('viewerSub');
    const openInNewTab = document.getElementById('openInNewTab');
    const importCsvBtn = document.getElementById('importCsvBtn');
    const startBtn = document.getElementById('startBtn');
    const clearCsvBtn = document.getElementById('clearCsvBtn');
    const csvInput = document.getElementById('csvInput');
    const sourceChip = document.getElementById('sourceChip');
    const csvPreview = document.getElementById('csvPreview');
    const statusBox = document.getElementById('status');
    const configName = document.getElementById('configName');
    const configMeta = document.getElementById('configMeta');
    const configControl = document.getElementById('configControl');
    const configPrev = document.getElementById('configPrev');
    const configNext = document.getElementById('configNext');
    const resetPresetBtn = document.getElementById('resetPresetBtn');

    let selectedFile = null;
    const state = {{ configIndex: 0, configOverrides: {{}} }};

    function setStatus(message) {{
      statusBox.textContent = message;
    }}

    function setActivePanel(panelName) {{
      panels.forEach((button) => button.classList.toggle('active', button.dataset.panel === panelName));
      homePanel.classList.toggle('hidden', panelName !== 'home');
      settingsPanel.classList.toggle('hidden', panelName !== 'settings');
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

    async function previewCsv(file) {{
      const text = await file.text();
      const lines = String(text || '').replace(/\r/g, '').split('\n').filter((line) => line.trim() !== '');
      const headers = parseCsvLine(lines[0] || '');
      const preview = lines.slice(1, 4);
      sourceChip.innerHTML = `
        <div>
          <strong>${{file.name}}</strong>
          <div class="tiny">${{Math.max(0, lines.length - 1)}} data rows · ${{headers.length}} columns</div>
        </div>
        <div class="tiny">CSV loaded</div>
      `;
      csvPreview.textContent = `Headers:\n${{headers.join(', ') || 'None'}}\n\nPreview rows:\n${{preview.join('\n') || 'No preview rows'}}`;
      setStatus('CSV loaded. Adjust settings if needed, then click Start processing.');
    }}

    function renderConfigField() {{
      if (!configSchema.length) return;
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
          <input id="cfgText" type="text" value="${{checked}}">
        `;
        const boolInput = document.getElementById('cfgBool');
        const textInput = document.getElementById('cfgText');
        boolInput.addEventListener('change', () => {{
          const nextValue = boolInput.checked;
          state.configOverrides[field.name] = nextValue;
          textInput.value = String(nextValue);
        }});
        textInput.addEventListener('change', () => {{
          const nextValue = String(textInput.value).trim().toLowerCase() === 'true';
          state.configOverrides[field.name] = nextValue;
          boolInput.checked = nextValue;
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
          <input id="cfgNumber" type="text" value="${{value}}">
        `;
        const rangeInput = document.getElementById('cfgRange');
        const numberInput = document.getElementById('cfgNumber');
        const updateValue = (next) => {{
          const parsed = field.kind === 'int' ? Math.round(Number(next)) : Number(next);
          state.configOverrides[field.name] = Number.isFinite(parsed) ? parsed : value;
          rangeInput.value = String(state.configOverrides[field.name]);
          numberInput.value = String(state.configOverrides[field.name]);
        }};
        rangeInput.addEventListener('input', () => updateValue(rangeInput.value));
        numberInput.addEventListener('change', () => updateValue(numberInput.value));
        return;
      }}

      configControl.innerHTML = `<input id="cfgText" type="text" value="${{String(value).replace(/"/g, '&quot;')}}">`;
      const textInput = document.getElementById('cfgText');
      textInput.addEventListener('change', () => {{
        state.configOverrides[field.name] = textInput.value;
      }});
    }}

    async function startProcessing() {{
      if (!selectedFile) {{
        setStatus('Select a CSV first.');
        return;
      }}
      startBtn.disabled = true;
      setStatus('Processing selected CSV...');
      const formData = new FormData();
      formData.append('source_csv', selectedFile, selectedFile.name);
      formData.append('config_overrides', JSON.stringify(state.configOverrides));
      const response = await fetch(`${{apiBaseUrl}}/start`, {{ method: 'POST', body: formData }});
      if (!response.ok) {{
        startBtn.disabled = false;
        setStatus('Processing failed.');
        return;
      }}
      const payload = await response.json();
      resultFrame.src = payload.result_url;
      resultFrame.classList.remove('hidden');
      homeView.classList.add('hidden');
      viewerTitle.textContent = payload.title || 'Processed Sphere';
      viewerSub.textContent = payload.message || 'Loaded processed output.';
      openInNewTab.href = payload.result_url;
      setStatus('Processing complete.');
      startBtn.disabled = false;
    }}

    panels.forEach((button) => button.addEventListener('click', () => setActivePanel(button.dataset.panel)));
    csvInput.addEventListener('change', async () => {{
      const file = csvInput.files && csvInput.files[0];
      if (!file) return;
      selectedFile = file;
      csvPreview.textContent = 'Loading preview...';
      startBtn.disabled = false;
      setStatus('CSV loaded. Adjust settings if needed, then click Start processing.');
      try {{
        await previewCsv(file);
      }} catch (error) {{
        sourceChip.innerHTML = `
          <div>
            <strong>${{file.name}}</strong>
            <div class="tiny">Selected file</div>
          </div>
          <div class="tiny">Ready</div>
        `;
        csvPreview.textContent = 'File selected, but a preview could not be generated.';
        setStatus('CSV loaded. Preview unavailable, but it can still be processed.');
      }}
    }});
    startBtn.addEventListener('click', startProcessing);
    clearCsvBtn.addEventListener('click', () => {{
      selectedFile = null;
      csvInput.value = '';
      startBtn.disabled = true;
      sourceChip.innerHTML = '<div><strong>No source loaded</strong><div class="tiny">No CSV selected yet.</div></div>';
      csvPreview.textContent = 'Import a CSV to preview its headers and row count here.';
      setStatus('CSV cleared.');
    }});
    configPrev.addEventListener('click', () => {{ state.configIndex = (state.configIndex - 1 + configSchema.length) % configSchema.length; renderConfigField(); }});
    configNext.addEventListener('click', () => {{ state.configIndex = (state.configIndex + 1) % configSchema.length; renderConfigField(); }});
    resetPresetBtn.addEventListener('click', () => {{ state.configOverrides = {{}}; state.configIndex = 0; renderConfigField(); }});
    document.addEventListener('keydown', (event) => {{
      if (event.key === 'Enter' && !startBtn.disabled) {{
        startProcessing();
      }}
    }});

    renderConfigField();
    setActivePanel('home');
    setStatus('The sphere stays vacant until you import a CSV and click Start processing.');
  </script>
</body>
</html>"""

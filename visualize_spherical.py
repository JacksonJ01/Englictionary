import json
from pathlib import Path

import pandas as pd

from config import FILE_PATH, PLOT_AUTO_OPEN, SPHERE_NODE_PIXEL_SIZE, SPHERE_RENDER_RADIUS
from config import SPHERE_DEFINITION_MAX_POINTS, SPHERE_POINT_LIFT


PALETTE = [
    "#1d4ed8",
    "#0f766e",
    "#b45309",
    "#7c3aed",
    "#be123c",
    "#0e7490",
    "#65a30d",
    "#c2410c",
    "#4f46e5",
    "#0369a1",
    "#9333ea",
    "#15803d",
    "#b91c1c",
    "#0ea5e9",
    "#15803d",
    "#a16207",
]


def _color_for_cluster(cluster_id):
    return PALETTE[int(cluster_id) % len(PALETTE)]


def _hex_to_rgb(color):
    color = color.lstrip("#")
    return tuple(int(color[i : i + 2], 16) for i in (0, 2, 4))


def _row_number_from_node_id(node_id):
    node_text = str(node_id)
    if node_text.startswith("W"):
        node_text = node_text[1:]

    try:
        return int(node_text) + 1
    except ValueError:
        return node_id


def _load_definition_lookup(source_file=None, definition_column=None):
  source_path = Path(source_file) if source_file else FILE_PATH
  if not source_path.exists():
    return {}

  source_df = None
  for encoding in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
    try:
      source_df = pd.read_csv(source_path, encoding=encoding)
      break
    except Exception:
      continue

  if source_df is None:
    return {}

  if definition_column:
    definition_column = next(
      (
        column
        for column in source_df.columns
        if str(column).strip().lower() == str(definition_column).strip().lower()
      ),
      None,
    )
  else:
    definition_column = None
    for column in source_df.columns:
      if str(column).strip().lower() == "definition":
        definition_column = column
        break

  if definition_column is None:
    return {}

  lookup = {}
  for idx, definition in enumerate(source_df[definition_column].fillna("")):
    lookup[idx + 1] = str(definition)
  return lookup


def _detail_columns(surface_df):
  return [column for column in surface_df.attrs.get("detail_columns", ()) if column in surface_df.columns]


def _build_render_payload(surface_df, definition_lookup=None):
    points = []
    colors = []
    include_definitions = len(surface_df) <= SPHERE_DEFINITION_MAX_POINTS or bool(definition_lookup)
    metadata = []
    total_rows = int(len(surface_df))
    detail_columns = _detail_columns(surface_df)
    has_pos_column = bool(str(surface_df.attrs.get("pos_column", "")).strip())

    cluster_counts = {
        int(cluster_id): int(count)
        for cluster_id, count in surface_df["cluster"].value_counts().to_dict().items()
    }
    cluster_names = {cluster_id: f"Cluster {cluster_id}" for cluster_id in cluster_counts}
    cluster_positions = {cluster_id: 0 for cluster_id in cluster_counts}
    cluster_summary = [
        {
            "cluster": cluster_id,
            "name": cluster_names[cluster_id],
            "count": cluster_counts[cluster_id],
            "color": _color_for_cluster(cluster_id),
        }
        for cluster_id in sorted(cluster_counts)
    ]

    point_radius = SPHERE_RENDER_RADIUS * SPHERE_POINT_LIFT
    for _, row in surface_df.iterrows():
        cluster_id = int(row["cluster"])
        cluster_positions[cluster_id] += 1
        row_number = _row_number_from_node_id(row.get("node_id", ""))

        x = float(row["x"]) * point_radius
        y = float(row["y"]) * point_radius
        z = float(row["z"]) * point_radius
        points.extend([x, y, z])

        r, g, b = _hex_to_rgb(_color_for_cluster(cluster_id))
        colors.extend([r / 255.0, g / 255.0, b / 255.0])

        raw_row_definition = row.get("definition", "")
        row_definition = "" if pd.isna(raw_row_definition) else str(raw_row_definition)
        if not row_definition and definition_lookup and isinstance(row_number, int):
            row_definition = definition_lookup.get(row_number, "")

        detail_fields = []
        for column in detail_columns:
          value = row.get(column, "")
          if pd.isna(value):
            value = ""
          value_text = str(value).strip()
          if value_text:
            detail_fields.append({"label": str(column), "value": value_text})

        metadata.append(
            {
                "word": str(row["word"]),
            "definition": row_definition if include_definitions else "",
                "cluster": cluster_id,
                "cluster_name": cluster_names[cluster_id],
                "cluster_count": cluster_counts[cluster_id],
                "cluster_row_number": cluster_positions[cluster_id],
                "pos_group": str(row["pos_group"]),
            "row_number": row_number,
            "details": detail_fields,
            }
        )

    return {
        "points": points,
        "colors": colors,
        "metadata": metadata,
        "cluster_summary": cluster_summary,
        "definitions_enabled": include_definitions,
        "detail_columns": detail_columns,
        "has_pos_column": has_pos_column,
        "point_size": float(SPHERE_NODE_PIXEL_SIZE),
        "radius": float(SPHERE_RENDER_RADIUS),
        "count": total_rows,
    }


def _cluster_drilldown_html(payload):
    payload_json = json.dumps(payload)
    return (
      "<!DOCTYPE html><html lang=\"en\"><head>"
      "<meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
      "<title>Cluster Drilldown</title>"
      "<style>"
      "body{margin:0;overflow:hidden;background:#f5f7fb;}"
      "#canvas{width:100vw;height:100vh;display:block;}"
      "#hud{position:fixed;left:16px;top:16px;z-index:1000;background:rgba(255,255,255,0.96);"
      "border:1px solid rgba(0,0,0,0.1);border-radius:12px;box-shadow:0 10px 24px rgba(0,0,0,0.16);"
      "padding:12px;font-family:Segoe UI,Arial,sans-serif;font-size:12px;width:330px;max-height:calc(100vh - 32px);overflow:auto;}"
      "#legend{margin-top:8px;}"
      ".row{display:flex;align-items:center;justify-content:space-between;gap:8px;margin-top:4px;padding:3px 5px;border-radius:6px;cursor:pointer;}"
      ".row:hover{background:rgba(15,23,42,0.08);}"
      ".row.active{background:rgba(30,64,175,0.14);outline:1px solid rgba(30,64,175,0.3);}"
      ".sw{width:10px;height:10px;border-radius:999px;border:1px solid rgba(0,0,0,0.25);margin-right:6px;display:inline-block;}"
      "#tip{position:fixed;right:16px;top:16px;z-index:1001;display:none;max-width:400px;padding:8px 10px;background:rgba(17,24,39,0.92);"
      "color:#fff;border-radius:8px;font-family:Segoe UI,Arial,sans-serif;font-size:12px;line-height:1.35;}"
      "</style></head><body>"
      "<div id=\"hud\">"
      "<div style=\"font-weight:700;\">Cluster Drilldown Sphere</div>"
      "<div style=\"margin-top:4px;\">Cluster: <b id=\"clusterId\"></b></div>"
      "<div>Nodes: <b id=\"nodeCount\"></b></div>"
      "<div style=\"margin-top:8px;\">Layout mode</div>"
      "<select id=\"layoutMode\" style=\"width:100%;margin-top:4px;padding:4px;border-radius:6px;border:1px solid rgba(0,0,0,0.2)\">"
      "<option value=\"sparse\">Sparse (current distribution)</option>"
      "<option value=\"even\">Even spacing</option>"
      "</select>"
      "<div style=\"margin-top:8px;\">Subcluster legend</div>"
      "<div id=\"legend\"></div></div>"
      "<div id=\"tip\"></div><canvas id=\"canvas\"></canvas>"
      "<script>(async function(){"
      "const payload="
      + payload_json
      + ";"
      "document.getElementById('clusterId').textContent=payload.cluster;"
      "document.getElementById('nodeCount').textContent=payload.nodes.length;"
      "const legend=document.getElementById('legend');const layoutMode=document.getElementById('layoutMode');const tip=document.getElementById('tip');"
      "async function ensureThree(){if(window.THREE)return true;const urls=['https://unpkg.com/three@0.160.0/build/three.min.js','https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.min.js','https://cdnjs.cloudflare.com/ajax/libs/three.js/r160/three.min.js'];"
      "for(const url of urls){const ok=await new Promise((resolve)=>{const s=document.createElement('script');s.src=url;s.async=true;s.onload=()=>resolve(true);s.onerror=()=>resolve(false);document.head.appendChild(s);});if(ok&&window.THREE)return true;}return false;}"
      "if(!(await ensureThree()))return;"
      "const subclusterKey=(n)=>String(n.pos_group||'other');const groups=new Map();"
      "for(let i=0;i<payload.nodes.length;i+=1){const k=subclusterKey(payload.nodes[i]);if(!groups.has(k))groups.set(k,[]);groups.get(k).push(i);}"
      "const groupEntries=Array.from(groups.entries()).sort((a,b)=>b[1].length-a[1].length);"
      "const palette=['#1d4ed8','#0f766e','#b45309','#7c3aed','#be123c','#0e7490','#65a30d','#c2410c','#4f46e5','#0369a1'];"
      "const colorByGroup=new Map(groupEntries.map((g,i)=>[g[0],palette[i%palette.length]]));let activeGroup=groupEntries.length?groupEntries[0][0]:null;"
      "legend.innerHTML=groupEntries.map(([n,idxs])=>'<div class=\"row\" data-group=\"'+n+'\"><span><span class=\"sw\" style=\"background:'+colorByGroup.get(n)+'\"></span>'+n+'</span><span>'+idxs.length+'</span></div>').join('');"
      "const canvas=document.getElementById('canvas');const renderer=new THREE.WebGLRenderer({canvas,antialias:true});renderer.setPixelRatio(window.devicePixelRatio||1);renderer.setSize(window.innerWidth,window.innerHeight);"
      "const scene=new THREE.Scene();scene.background=new THREE.Color(0xf5f7fb);const camera=new THREE.PerspectiveCamera(58,window.innerWidth/window.innerHeight,0.1,20000);let yaw=0,pitch=0,distance=payload.radius*2.6;let dragging=false,lastX=0,lastY=0;"
      "scene.add(new THREE.AmbientLight(0xffffff,0.78));const dir=new THREE.DirectionalLight(0xffffff,0.7);dir.position.set(payload.radius*1.6,payload.radius*2.0,payload.radius*1.2);scene.add(dir);"
      "const globe=new THREE.Mesh(new THREE.SphereGeometry(payload.radius,64,64),new THREE.MeshPhongMaterial({color:0x4f7ea8,emissive:0x0d2238,shininess:16,transparent:true,opacity:0.55}));scene.add(globe);"
      "const axisHelper=new THREE.AxesHelper(payload.radius*1.3);const ac=axisHelper.geometry.getAttribute('color');ac.setXYZ(0,0.50,0.10,0.10);ac.setXYZ(1,0.50,0.10,0.10);ac.setXYZ(2,0.07,0.38,0.16);ac.setXYZ(3,0.07,0.38,0.16);ac.setXYZ(4,0.12,0.25,0.60);ac.setXYZ(5,0.12,0.25,0.60);ac.needsUpdate=true;scene.add(axisHelper);"
      "const sparse=new Float32Array(payload.nodes.length*3);const even=new Float32Array(payload.nodes.length*3);const cols=new Float32Array(payload.nodes.length*3);"
      "for(let i=0;i<payload.nodes.length;i+=1){const n=payload.nodes[i];const norm=Math.sqrt(n.x*n.x+n.y*n.y+n.z*n.z)||1;const r=payload.radius*1.012;sparse[i*3]=(n.x/norm)*r;sparse[i*3+1]=(n.y/norm)*r;sparse[i*3+2]=(n.z/norm)*r;const c=new THREE.Color(colorByGroup.get(subclusterKey(n))||'#0f172a');cols[i*3]=c.r;cols[i*3+1]=c.g;cols[i*3+2]=c.b;}"
      "function basis(v){let ref={x:0,y:0,z:1};if(Math.abs(v.x*ref.x+v.y*ref.y+v.z*ref.z)>0.95)ref={x:0,y:1,z:0};const b1=new THREE.Vector3(v.y*ref.z-v.z*ref.y,v.z*ref.x-v.x*ref.z,v.x*ref.y-v.y*ref.x).normalize();const b2=new THREE.Vector3().crossVectors(new THREE.Vector3(v.x,v.y,v.z),b1).normalize();return[b1,b2];}"
      "for(const [name,idxs] of groupEntries){let cx=0,cy=0,cz=0;for(const idx of idxs){cx+=sparse[idx*3];cy+=sparse[idx*3+1];cz+=sparse[idx*3+2];}const v=new THREE.Vector3(cx,cy,cz).normalize();const bb=basis(v);const b1=bb[0],b2=bb[1];const golden=Math.PI*(3-Math.sqrt(5));const maxRadius=Math.min(0.45,0.02+0.0035*Math.sqrt(idxs.length));for(let i=0;i<idxs.length;i+=1){const idx=idxs[i];const radial=maxRadius*Math.sqrt((i+0.5)/idxs.length);const theta=i*golden;const ox=b1.x*radial*Math.cos(theta)+b2.x*radial*Math.sin(theta);const oy=b1.y*radial*Math.cos(theta)+b2.y*radial*Math.sin(theta);const oz=b1.z*radial*Math.cos(theta)+b2.z*radial*Math.sin(theta);const p=new THREE.Vector3(v.x+ox,v.y+oy,v.z+oz).normalize().multiplyScalar(payload.radius*1.012);even[idx*3]=p.x;even[idx*3+1]=p.y;even[idx*3+2]=p.z;}}"
      "const geom=new THREE.BufferGeometry();geom.setAttribute('position',new THREE.Float32BufferAttribute(sparse,3));geom.setAttribute('color',new THREE.Float32BufferAttribute(cols,3));const pointCloud=new THREE.Points(geom,new THREE.PointsMaterial({size:3,vertexColors:true,transparent:true,opacity:0.97,depthWrite:false,sizeAttenuation:false}));scene.add(pointCloud);"
      "let lineOverlay=null;function clearLines(){if(!lineOverlay)return;scene.remove(lineOverlay);lineOverlay.geometry.dispose();lineOverlay.material.dispose();lineOverlay=null;}"
      "function rebuildLines(name){clearLines();const idxs=groups.get(name)||[];if(idxs.length<2)return;const maxNodes=400;const stride=Math.max(1,Math.ceil(idxs.length/maxNodes));const sampled=[];for(let i=0;i<idxs.length;i+=stride)sampled.push(idxs[i]);const pos=geom.getAttribute('position').array;const vecs=sampled.map((idx)=>{const x=pos[idx*3],y=pos[idx*3+1],z=pos[idx*3+2];const n=Math.sqrt(x*x+y*y+z*z)||1;return{idx,x:x/n,y:y/n,z:z/n};});const edges=new Set();for(let i=0;i<vecs.length;i++){let best=-1,bestSim=-Infinity;for(let j=0;j<vecs.length;j++){if(i===j)continue;const sim=vecs[i].x*vecs[j].x+vecs[i].y*vecs[j].y+vecs[i].z*vecs[j].z;if(sim>bestSim){bestSim=sim;best=j;}}if(best>=0){const a=Math.min(i,best),b=Math.max(i,best);edges.add(a+'-'+b);}}const lv=[];for(const key of edges){const ab=key.split('-').map(Number);const pa=vecs[ab[0]].idx,pb=vecs[ab[1]].idx;lv.push(pos[pa*3],pos[pa*3+1],pos[pa*3+2],pos[pb*3],pos[pb*3+1],pos[pb*3+2]);}const lg=new THREE.BufferGeometry();lg.setAttribute('position',new THREE.Float32BufferAttribute(lv,3));const lm=new THREE.LineBasicMaterial({color:new THREE.Color(colorByGroup.get(name)||'#0f172a'),transparent:true,opacity:0.35,depthWrite:false});lineOverlay=new THREE.LineSegments(lg,lm);scene.add(lineOverlay);}"
      "function applyLayout(mode){const src=mode==='even'?even:sparse;geom.setAttribute('position',new THREE.Float32BufferAttribute(src,3));geom.attributes.position.needsUpdate=true;rebuildLines(activeGroup);}"
      "legend.addEventListener('click',(evt)=>{const row=evt.target.closest('.row');if(!row)return;activeGroup=row.dataset.group;legend.querySelectorAll('.row').forEach((r)=>r.classList.toggle('active',r.dataset.group===activeGroup));rebuildLines(activeGroup);});legend.querySelectorAll('.row').forEach((r)=>r.classList.toggle('active',r.dataset.group===activeGroup));"
      "layoutMode.addEventListener('change',()=>applyLayout(layoutMode.value));applyLayout('sparse');"
      "const raycaster=new THREE.Raycaster();raycaster.params.Points.threshold=4.0;const mouse=new THREE.Vector2();function setMouse(evt){const rect=renderer.domElement.getBoundingClientRect();mouse.x=((evt.clientX-rect.left)/rect.width)*2-1;mouse.y=-((evt.clientY-rect.top)/rect.height)*2+1;}"
      "renderer.domElement.addEventListener('mousemove',(evt)=>{setMouse(evt);raycaster.setFromCamera(mouse,camera);const hits=raycaster.intersectObject(pointCloud);if(!hits.length){tip.style.display='none';return;}const idx=hits[0].index;const info=payload.nodes[idx];tip.innerHTML='<b>'+info.word+'</b><br>row: '+info.row_number+'<br>subcluster: '+(info.pos_group||'other')+(info.definition?'<br>'+String(info.definition).slice(0,220):'');tip.style.display='block';});"
      "renderer.domElement.addEventListener('mousedown',(evt)=>{dragging=true;lastX=evt.clientX;lastY=evt.clientY;});window.addEventListener('mouseup',()=>{dragging=false;});window.addEventListener('mousemove',(evt)=>{if(!dragging)return;const dx=evt.clientX-lastX,dy=evt.clientY-lastY;lastX=evt.clientX;lastY=evt.clientY;yaw-=dx*0.0038;pitch-=dy*0.0038;pitch=Math.max(-1.35,Math.min(1.35,pitch));});"
      "renderer.domElement.addEventListener('wheel',(evt)=>{evt.preventDefault();distance*=evt.deltaY>0?0.94:1.06;distance=Math.max(payload.radius*1.1,Math.min(payload.radius*8.0,distance));},{passive:false});"
      "window.addEventListener('resize',()=>{camera.aspect=window.innerWidth/window.innerHeight;camera.updateProjectionMatrix();renderer.setSize(window.innerWidth,window.innerHeight);});"
      "(function animate(){requestAnimationFrame(animate);camera.position.x=distance*Math.cos(pitch)*Math.sin(yaw);camera.position.y=distance*Math.sin(pitch);camera.position.z=distance*Math.cos(pitch)*Math.cos(yaw);camera.lookAt(0,0,0);renderer.render(scene,camera);})();"
      "})();<\\/script></body></html>"
    )


def _write_cluster_drilldown_pages(surface_df, output_dir, definition_lookup=None):
    drilldown_dir = output_dir / "clusters"
    drilldown_dir.mkdir(parents=True, exist_ok=True)

    mapping = {}
    detail_columns = _detail_columns(surface_df)
    for cluster_id, cluster_df in surface_df.groupby("cluster", sort=True):
        cluster_id_int = int(cluster_id)
        nodes = []
        for row in cluster_df.itertuples(index=False):
            row_number = _row_number_from_node_id(getattr(row, "node_id", ""))
            definition = getattr(row, "definition", "")
            definition_text = "" if pd.isna(definition) else str(definition)
            if not definition_text and definition_lookup and isinstance(row_number, int):
                definition_text = definition_lookup.get(row_number, "")

            detail_fields = []
            for column in detail_columns:
                value = getattr(row, column, "")
                if pd.isna(value):
                    value = ""
                value_text = str(value).strip()
                if value_text:
                    detail_fields.append({"label": str(column), "value": value_text})

            nodes.append(
                {
                    "x": float(getattr(row, "x")),
                    "y": float(getattr(row, "y")),
                    "z": float(getattr(row, "z")),
                    "word": str(getattr(row, "word")),
                    "pos_group": str(getattr(row, "pos_group")),
                    "row_number": row_number,
                    "definition": definition_text,
                    "details": detail_fields,
                }
            )

        cluster_payload = {
            "cluster": cluster_id_int,
            "radius": float(SPHERE_RENDER_RADIUS),
            "nodes": nodes,
        }

        file_name = f"cluster_{cluster_id_int}.html"
        file_path = drilldown_dir / file_name
        file_path.write_text(_cluster_drilldown_html(cluster_payload), encoding="utf-8")
        mapping[cluster_id_int] = file_path.resolve().as_uri()

    return mapping


def _html(payload):
    payload_json = json.dumps(payload)
    return f"""<!DOCTYPE html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\">
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">
  <title>Spherical Semantic Surface</title>
  <style>
    body {{ margin: 0; overflow: hidden; background: #f5f7fb; }}
    #viewport {{ width: 100vw; height: 100vh; display: block; }}
    #hud {{
      position: fixed; left: 18px; top: 18px; z-index: 1000;
      background: rgba(255,255,255,0.95); border: 1px solid rgba(0,0,0,0.08);
      border-radius: 12px; box-shadow: 0 10px 26px rgba(0,0,0,0.14);
      padding: 12px 14px; font-family: Segoe UI, Arial, sans-serif; font-size: 13px;
      max-width: 420px;
    }}
    #tooltip {{
      position: fixed; display: none; z-index: 1001;
      max-width: 420px; padding: 8px 10px; background: rgba(17, 24, 39, 0.92);
      color: #fff; border-radius: 8px; font-family: Segoe UI, Arial, sans-serif;
      font-size: 12px; line-height: 1.35;
    }}
    #status {{
      position: fixed; right: 18px; bottom: 18px; z-index: 1002;
      padding: 8px 10px; background: rgba(15,23,42,0.9); color: #fff;
      border-radius: 8px; font-family: Segoe UI, Arial, sans-serif; font-size: 12px;
      display: none;
    }}
    #controlsPanel {{
      position: fixed; right: 18px; top: 18px; z-index: 1003;
      background: rgba(255,255,255,0.95); border: 1px solid rgba(0,0,0,0.08);
      border-radius: 12px; box-shadow: 0 10px 26px rgba(0,0,0,0.14);
      padding: 10px 12px; font-family: Segoe UI, Arial, sans-serif; font-size: 12px;
      min-width: 230px;
    }}
    .controls-title {{ font-weight: 700; margin-bottom: 6px; }}
    .control-row {{ display: flex; align-items: center; gap: 8px; margin-top: 6px; }}
    #legendList {{
      margin-top: 8px;
      max-height: 260px;
      overflow-y: auto;
      padding-right: 4px;
    }}
    #legendSearch {{
      width: 100%;
      box-sizing: border-box;
      margin-top: 8px;
      padding: 7px 8px;
      border-radius: 8px;
      border: 1px solid rgba(15,23,42,0.18);
      font-family: Segoe UI, Arial, sans-serif;
      font-size: 12px;
      outline: none;
    }}
    #legendSearch:focus {{
      border-color: rgba(30,64,175,0.6);
      box-shadow: 0 0 0 2px rgba(30,64,175,0.12);
    }}
    #legendInfo {{
      margin-top: 6px;
      font-size: 11px;
      color: #334155;
      opacity: 0.9;
    }}
    #clusterDrilldownBar {{
      margin-top: 8px;
      display: none;
    }}
    #clusterDrilldownBack {{
      width: 100%;
      box-sizing: border-box;
      padding: 7px 8px;
      border-radius: 8px;
      border: 1px solid rgba(15,23,42,0.18);
      background: #fff;
      color: #0f172a;
      font-family: Segoe UI, Arial, sans-serif;
      font-size: 12px;
      cursor: pointer;
    }}
    #clusterDrilldownBack:hover {{
      background: rgba(15,23,42,0.05);
    }}
    .legend-row {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 10px;
      margin-top: 4px;
      font-size: 12px;
      cursor: pointer;
      border-radius: 6px;
      padding: 2px 4px;
    }}
    .legend-row:hover {{
      background: rgba(15,23,42,0.07);
    }}
    .legend-row.active {{
      background: rgba(30,64,175,0.14);
      outline: 1px solid rgba(30,64,175,0.3);
    }}
    .legend-left {{
      display: flex;
      align-items: center;
      gap: 6px;
      min-width: 0;
    }}
    .legend-swatch {{
      width: 10px;
      height: 10px;
      border-radius: 999px;
      border: 1px solid rgba(0,0,0,0.25);
      flex: 0 0 auto;
    }}
    .legend-name {{
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }}
    .legend-count {{ color: #0f172a; opacity: 0.8; }}
  </style>
</head>
<body>
  <div id=\"hud\">
    <div style=\"font-weight:700;margin-bottom:6px;\">Spherical Semantic Surface (All Nodes)</div>
    <div>Rows plotted: <b>{payload['count']}</b></div>
    <div style=\"margin-top:4px;\">Drag to rotate, hover or click nodes for details, wheel to zoom.</div>
    <div id=\"detailHint\" style=\"margin-top:4px;color:#334155;\"></div>
    <div id="clusterDrilldownBar">
      <button id="clusterDrilldownBack" type="button">Back to all clusters</button>
    </div>
    <input id="legendSearch" type="text" placeholder="Search words in legend...">
    <div id="legendInfo"></div>
    <div style=\"margin-top:8px;font-weight:600;color:#0f172a;\">Cluster Legend</div>
    <div id=\"legendList\"></div>
  </div>
  <div id=\"controlsPanel\">
    <div class=\"controls-title\">Mouse Controls</div>
    <label class=\"control-row\"><input id=\"invertHorizontal\" type=\"checkbox\">Invert left-right drag</label>
    <label class=\"control-row\"><input id=\"invertVertical\" type=\"checkbox\">Invert up-down drag</label>
    <label class=\"control-row\"><input id=\"invertZoom\" type=\"checkbox\">Invert zoom scroll</label>
  </div>
  <div id=\"tooltip\"></div>
  <div id=\"status\"></div>
  <canvas id=\"viewport\"></canvas>
  <script>
  (async function() {{
    const payload = {payload_json};
    const statusBox = document.getElementById('status');
    const tooltip = document.getElementById('tooltip');
    const detailHint = document.getElementById('detailHint');
    const legendList = document.getElementById('legendList');
    const legendSearchInput = document.getElementById('legendSearch');
    const legendInfo = document.getElementById('legendInfo');
    const clusterDrilldownBar = document.getElementById('clusterDrilldownBar');
    const clusterDrilldownBack = document.getElementById('clusterDrilldownBack');
    const invertHorizontalCheckbox = document.getElementById('invertHorizontal');
    const invertVerticalCheckbox = document.getElementById('invertVertical');
    const invertZoomCheckbox = document.getElementById('invertZoom');

    const searchableText = payload.metadata.map((m) => {{
      const word = String(m.word || '').toLowerCase();
      const definition = String(m.definition || '').toLowerCase();
      return `${{word}} ${{definition}}`.trim();
    }});
    const clusterIndicesById = new Map();
    for (let i = 0; i < payload.metadata.length; i += 1) {{
      const clusterId = payload.metadata[i].cluster;
      if (!clusterIndicesById.has(clusterId)) {{
        clusterIndicesById.set(clusterId, []);
      }}
      clusterIndicesById.get(clusterId).push(i);
    }}
    let activeClusterId = null;

    function escapeHtml(value) {{
      return String(value)
        .replaceAll('&', '&amp;')
        .replaceAll('<', '&lt;')
        .replaceAll('>', '&gt;')
        .replaceAll('"', '&quot;')
        .replaceAll("'", '&#39;');
    }}

    function updateDrilldownControls() {{
      const isClusterDrilldown = activeClusterId !== null;
      clusterDrilldownBar.style.display = isClusterDrilldown ? 'block' : 'none';
      legendSearchInput.placeholder = isClusterDrilldown
        ? 'Search words in this cluster...'
        : 'Search words in legend...';
    }}

    function resetClusterDrilldown() {{
      activeClusterId = null;
      pinnedIndex = null;
      tooltip.style.display = 'none';
      updateDrilldownControls();
      renderLegendList(legendSearchInput.value);
    }}

    function enterClusterDrilldown(clusterId) {{
      activeClusterId = clusterId;
      pinnedIndex = null;
      tooltip.style.display = 'none';
      focusCluster(clusterId);
      updateDrilldownControls();
      renderLegendList(legendSearchInput.value);
    }}

    function renderLegendList(rawQuery) {{
      const query = String(rawQuery || '').trim().toLowerCase();
      if (activeClusterId !== null) {{
        const clusterInfo = payload.cluster_summary.find((item) => item.cluster === activeClusterId);
        const clusterIndices = clusterIndicesById.get(activeClusterId) || [];
        const matches = [];
        for (const metaIndex of clusterIndices) {{
          if (query && !searchableText[metaIndex].includes(query)) {{
            continue;
          }}
          matches.push(metaIndex);
        }}

        legendList.innerHTML = matches.map((metaIndex) => {{
          const info = payload.metadata[metaIndex];
          const definitionSnippet = info.definition ? `<div style="margin-top:2px;color:#475569;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:180px;">${{escapeHtml(String(info.definition).slice(0, 60))}}</div>` : '';
          return `<div class="legend-row" data-kind="word" data-meta-index="${{metaIndex}}" data-cluster="${{info.cluster}}">` +
            `<div class="legend-left">` +
              `<span class="legend-swatch" style="background:${{payload.cluster_summary.find((c) => c.cluster === info.cluster)?.color || '#0f172a'}}"></span>` +
              `<div style="min-width:0;">` +
                `<div class="legend-name">${{escapeHtml(info.word)}}</div>` +
                `${{definitionSnippet}}` +
              `</div>` +
            `</div>` +
            `<span class="legend-count">C${{info.cluster}}</span>` +
          `</div>`;
        }}).join('');

        const clipped = matches.length > 140 ? ' (showing first 140)' : '';
        legendInfo.textContent = `${{clusterInfo ? clusterInfo.name : `Cluster ${{activeClusterId}}`}} • ${{matches.length}} words${{clipped}}`;
        return;
      }}

      if (!query) {{
        legendList.innerHTML = payload.cluster_summary.map((item) =>
          `<div class="legend-row" data-kind="cluster" data-cluster="${{item.cluster}}" data-drilldown-file="${{item.drilldown_file || ''}}">` +
            `<div class="legend-left">` +
              `<span class="legend-swatch" style="background:${{item.color}}"></span>` +
              `<span class="legend-name">${{escapeHtml(item.name)}}</span>` +
            `</div>` +
            `<span class="legend-count">${{item.count}}</span>` +
          `</div>`
        ).join('');
        legendInfo.textContent = `${{payload.cluster_summary.length}} clusters`;
        return;
      }}

      const maxResults = 140;
      const matches = [];
      let totalMatches = 0;
      for (let i = 0; i < searchableText.length; i += 1) {{
        if (!searchableText[i].includes(query)) {{
          continue;
        }}
        totalMatches += 1;
        if (matches.length < maxResults) {{
          matches.push(i);
        }}
      }}

      legendList.innerHTML = matches.map((metaIndex) => {{
        const info = payload.metadata[metaIndex];
        const definitionSnippet = info.definition ? `<div style="margin-top:2px;color:#475569;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:180px;">${{escapeHtml(String(info.definition).slice(0, 60))}}</div>` : '';
        return `<div class="legend-row" data-kind="word" data-meta-index="${{metaIndex}}" data-cluster="${{info.cluster}}">` +
          `<div class="legend-left">` +
            `<span class="legend-swatch" style="background:${{payload.cluster_summary.find((c) => c.cluster === info.cluster)?.color || '#0f172a'}}"></span>` +
            `<div style="min-width:0;">` +
              `<div class="legend-name">${{escapeHtml(info.word)}}</div>` +
              `${{definitionSnippet}}` +
            `</div>` +
          `</div>` +
          `<span class="legend-count">C${{info.cluster}}</span>` +
        `</div>`;
      }}).join('');

      const clipped = totalMatches > maxResults ? ` (showing first ${{maxResults}})` : '';
      legendInfo.textContent = `${{totalMatches}} word matches${{clipped}}`;
    }}

    renderLegendList('');
    updateDrilldownControls();

    function showStatus(msg) {{
      statusBox.textContent = msg;
      statusBox.style.display = 'block';
    }}

    async function ensureThree() {{
      if (window.THREE) return true;
      const urls = [
        'https://unpkg.com/three@0.160.0/build/three.min.js',
        'https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.min.js',
        'https://cdnjs.cloudflare.com/ajax/libs/three.js/r160/three.min.js'
      ];
      for (const url of urls) {{
        const ok = await new Promise((resolve) => {{
          const s = document.createElement('script');
          s.src = url; s.async = true;
          s.onload = () => resolve(true);
          s.onerror = () => resolve(false);
          document.head.appendChild(s);
        }});
        if (ok && window.THREE) return true;
      }}
      return false;
    }}

    if (!(await ensureThree())) {{
      showStatus('Three.js failed to load from CDN(s).');
      return;
    }}

    try {{
      const canvas = document.getElementById('viewport');
      const renderer = new THREE.WebGLRenderer({{ canvas, antialias: true }});
      renderer.setPixelRatio(window.devicePixelRatio || 1);
      renderer.setSize(window.innerWidth, window.innerHeight);

      const scene = new THREE.Scene();
      scene.background = new THREE.Color(0xf5f7fb);

      const camera = new THREE.PerspectiveCamera(58, window.innerWidth / window.innerHeight, 0.1, 20000);
      let yaw = 0;
      let pitch = 0;
      let distance = payload.radius * 3.1;
      let dragging = false;
      let movedDuringDrag = false;
      let lastX = 0;
      let lastY = 0;
      let pinnedIndex = null;
      let invertHorizontal = false;
      let invertVertical = false;
      let invertZoom = true;

      scene.add(new THREE.AmbientLight(0xffffff, 0.76));
      const dir = new THREE.DirectionalLight(0xffffff, 0.72);
      dir.position.set(payload.radius * 1.6, payload.radius * 2.0, payload.radius * 1.3);
      scene.add(dir);

      const globe = new THREE.Mesh(
        new THREE.SphereGeometry(payload.radius, 84, 84),
        new THREE.MeshPhongMaterial({{
          color: 0x4f7ea8,
          emissive: 0x0d2238,
          shininess: 16,
          transparent: true,
          opacity: 0.56,
        }})
      );
      scene.add(globe);

      const globeWire = new THREE.Mesh(
        new THREE.SphereGeometry(payload.radius * 1.002, 42, 32),
        new THREE.MeshBasicMaterial({{ color: 0xd6e5f5, wireframe: true, transparent: true, opacity: 0.12 }})
      );
      scene.add(globeWire);

      // Orientation guides (X=red, Y=green, Z=blue).
      const axisHelper = new THREE.AxesHelper(payload.radius * 1.4);
      const axisColors = axisHelper.geometry.getAttribute('color');
      // Darker axis tones for better readability on light background.
      axisColors.setXYZ(0, 0.50, 0.10, 0.10);
      axisColors.setXYZ(1, 0.50, 0.10, 0.10);
      axisColors.setXYZ(2, 0.07, 0.38, 0.16);
      axisColors.setXYZ(3, 0.07, 0.38, 0.16);
      axisColors.setXYZ(4, 0.12, 0.25, 0.60);
      axisColors.setXYZ(5, 0.12, 0.25, 0.60);
      axisColors.needsUpdate = true;
      axisHelper.material.transparent = true;
      axisHelper.material.opacity = 0.98;
      axisHelper.renderOrder = 1;
      scene.add(axisHelper);

      const geom = new THREE.BufferGeometry();
      geom.setAttribute('position', new THREE.Float32BufferAttribute(payload.points, 3));
      geom.setAttribute('color', new THREE.Float32BufferAttribute(payload.colors, 3));

      const pointMaterial = new THREE.PointsMaterial({{
        size: payload.point_size,
        vertexColors: true,
        transparent: true,
        opacity: 0.97,
        depthWrite: false,
        sizeAttenuation: false,
      }});

      const pointCloud = new THREE.Points(geom, pointMaterial);
      pointCloud.renderOrder = 3;
      scene.add(pointCloud);

      const raycaster = new THREE.Raycaster();
      raycaster.params.Points.threshold = Math.max(3.2, payload.point_size * 2.6);
      const mouse = new THREE.Vector2();
      const clusterFocusVectors = new Map();
      const clusterPointIndices = new Map();
      const clusterColorById = new Map(payload.cluster_summary.map((c) => [c.cluster, c.color]));
      let clusterRelationshipLines = null;
      let focusTween = null;

      for (let i = 0; i < payload.metadata.length; i += 1) {{
        const info = payload.metadata[i];
        const clusterId = info.cluster;
        let accum = clusterFocusVectors.get(clusterId);
        if (!accum) {{
          accum = {{ x: 0, y: 0, z: 0, count: 0 }};
          clusterFocusVectors.set(clusterId, accum);
        }}
        accum.x += payload.points[i * 3 + 0];
        accum.y += payload.points[i * 3 + 1];
        accum.z += payload.points[i * 3 + 2];
        accum.count += 1;

        if (!clusterPointIndices.has(clusterId)) {{
          clusterPointIndices.set(clusterId, []);
        }}
        clusterPointIndices.get(clusterId).push(i);
      }}

      function shortestAngleDelta(fromAngle, toAngle) {{
        let delta = toAngle - fromAngle;
        while (delta > Math.PI) delta -= Math.PI * 2;
        while (delta < -Math.PI) delta += Math.PI * 2;
        return delta;
      }}

      function easeInOutQuad(t) {{
        return t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2;
      }}

      function clearClusterRelationshipOverlay() {{
        if (!clusterRelationshipLines) {{
          return;
        }}
        scene.remove(clusterRelationshipLines);
        clusterRelationshipLines.geometry.dispose();
        clusterRelationshipLines.material.dispose();
        clusterRelationshipLines = null;
      }}

      function buildClusterRelationshipOverlay(clusterId) {{
        clearClusterRelationshipOverlay();
        const pointIndices = clusterPointIndices.get(clusterId) || [];
        if (pointIndices.length < 2) {{
          showStatus(`Cluster ${{clusterId}}: not enough points for relationship links.`);
          return;
        }}

        const maxNodes = 700;
        const targetNeighbors = 2;
        const stride = Math.max(1, Math.ceil(pointIndices.length / maxNodes));
        const sampledIndices = [];
        for (let i = 0; i < pointIndices.length; i += stride) {{
          sampledIndices.push(pointIndices[i]);
        }}

        const vectors = sampledIndices.map((pointIdx) => {{
          const x = payload.points[pointIdx * 3 + 0];
          const y = payload.points[pointIdx * 3 + 1];
          const z = payload.points[pointIdx * 3 + 2];
          const norm = Math.sqrt(x * x + y * y + z * z) || 1;
          return {{ pointIdx, x: x / norm, y: y / norm, z: z / norm }};
        }});

        const edgeKeys = new Set();
        for (let i = 0; i < vectors.length; i += 1) {{
          const base = vectors[i];
          const nearest = [];

          for (let j = 0; j < vectors.length; j += 1) {{
            if (i === j) continue;
            const candidate = vectors[j];
            const similarity = base.x * candidate.x + base.y * candidate.y + base.z * candidate.z;

            if (nearest.length < targetNeighbors) {{
              nearest.push({{ j, similarity }});
              nearest.sort((a, b) => b.similarity - a.similarity);
            }} else if (similarity > nearest[targetNeighbors - 1].similarity) {{
              nearest[targetNeighbors - 1] = {{ j, similarity }};
              nearest.sort((a, b) => b.similarity - a.similarity);
            }}
          }}

          for (const n of nearest) {{
            const a = Math.min(i, n.j);
            const b = Math.max(i, n.j);
            edgeKeys.add(`${{a}}-${{b}}`);
          }}
        }}

        const lineVertices = [];
        for (const key of edgeKeys) {{
          const [aText, bText] = key.split('-');
          const aIdx = Number(aText);
          const bIdx = Number(bText);
          const pa = vectors[aIdx].pointIdx;
          const pb = vectors[bIdx].pointIdx;

          lineVertices.push(
            payload.points[pa * 3 + 0], payload.points[pa * 3 + 1], payload.points[pa * 3 + 2],
            payload.points[pb * 3 + 0], payload.points[pb * 3 + 1], payload.points[pb * 3 + 2]
          );
        }}

        const lineGeometry = new THREE.BufferGeometry();
        lineGeometry.setAttribute('position', new THREE.Float32BufferAttribute(lineVertices, 3));

        const lineMaterial = new THREE.LineBasicMaterial({{
          color: new THREE.Color(clusterColorById.get(clusterId) || '#0f172a'),
          transparent: true,
          opacity: 0.32,
          depthWrite: false,
        }});

        clusterRelationshipLines = new THREE.LineSegments(lineGeometry, lineMaterial);
        clusterRelationshipLines.renderOrder = 2;
        scene.add(clusterRelationshipLines);
        showStatus(`Cluster ${{clusterId}} relationships: ${{lineVertices.length / 6}} links across ${{sampledIndices.length}} sampled nodes.`);
      }}

      function setMouse(evt) {{
        const rect = renderer.domElement.getBoundingClientRect();
        mouse.x = ((evt.clientX - rect.left) / rect.width) * 2 - 1;
        mouse.y = -((evt.clientY - rect.top) / rect.height) * 2 + 1;
      }}

      function renderInfo(info, pinned) {{
        return `<b>${{info.word}}</b>` +
          `<br>cluster number: ${{info.cluster}}` +
          `<br>cluster node count: ${{info.cluster_count}}` +
          `<br>global row: ${{info.row_number}} of ${{payload.count}}` +
          `<br>cluster row: ${{info.cluster_row_number}} of ${{info.cluster_count}}` +
          `<br>pos: ${{info.pos_group}}` +
          (info.definition ? `<br>${{String(info.definition).slice(0, 220)}}` : '') +
          (pinned ? '<br><span style="opacity:0.8">click empty space to clear</span>' : '');
      }}

      function showTooltip(evt, info, pinned) {{
        tooltip.innerHTML = renderInfo(info, pinned);
        tooltip.style.display = 'block';
        tooltip.style.left = (evt.clientX + 14) + 'px';
        tooltip.style.top = (evt.clientY + 14) + 'px';
      }}

      function setTooltipFromMetadata(info) {{
        tooltip.innerHTML = renderInfo(info, true);
        tooltip.style.display = 'block';
        tooltip.style.left = '24px';
        tooltip.style.top = '120px';
      }}

      function focusCluster(clusterId) {{
        const accum = clusterFocusVectors.get(clusterId);
        if (!accum || accum.count === 0) {{
          return;
        }}

        const vx = accum.x / accum.count;
        const vy = accum.y / accum.count;
        const vz = accum.z / accum.count;
        const vlen = Math.sqrt(vx * vx + vy * vy + vz * vz) || 1;
        const nx = vx / vlen;
        const ny = vy / vlen;
        const nz = vz / vlen;

        const targetYaw = Math.atan2(nx, nz);
        const targetPitch = Math.asin(Math.max(-1, Math.min(1, ny)));
        const targetDistance = payload.radius * 2.4;

        focusTween = {{
          startAtMs: performance.now(),
          durationMs: 700,
          fromYaw: yaw,
          fromPitch: pitch,
          fromDistance: distance,
          yawDelta: shortestAngleDelta(yaw, targetYaw),
          targetPitch,
          targetDistance,
        }};

        activeClusterId = clusterId;
        buildClusterRelationshipOverlay(clusterId);

        legendList.querySelectorAll('.legend-row').forEach((el) => {{
          el.classList.toggle('active', Number(el.dataset.cluster) === clusterId);
        }});
      }}

      function hideTooltip() {{
        if (pinnedIndex !== null) {{
          return;
        }}
        tooltip.style.display = 'none';
      }}

      function pickPoint(evt) {{
        setMouse(evt);
        raycaster.setFromCamera(mouse, camera);
        const hits = raycaster.intersectObject(pointCloud);
        if (!hits.length) {{
          return null;
        }}
        return hits[0].index;
      }}

      function onHover(evt) {{
        if (dragging || pinnedIndex !== null) {{
          return;
        }}

        const idx = pickPoint(evt);
        if (idx === null) {{
          hideTooltip();
          renderer.domElement.style.cursor = 'grab';
          return;
        }}

        showTooltip(evt, payload.metadata[idx], false);
        renderer.domElement.style.cursor = 'pointer';
      }}

      function onClick(evt) {{
        if (movedDuringDrag) {{
          movedDuringDrag = false;
          return;
        }}

        const idx = pickPoint(evt);
        if (idx === null) {{
          pinnedIndex = null;
          tooltip.style.display = 'none';
          renderer.domElement.style.cursor = 'grab';
          return;
        }}

        pinnedIndex = idx;
        showTooltip(evt, payload.metadata[idx], true);
        renderer.domElement.style.cursor = 'pointer';
      }}

      renderer.domElement.addEventListener('mousedown', (evt) => {{
        dragging = true;
        movedDuringDrag = false;
        focusTween = null;
        lastX = evt.clientX;
        lastY = evt.clientY;
        renderer.domElement.style.cursor = 'grabbing';
      }});

      window.addEventListener('mouseup', () => {{
        dragging = false;
        if (pinnedIndex === null) {{
          renderer.domElement.style.cursor = 'grab';
        }}
      }});

      window.addEventListener('mousemove', (evt) => {{
        if (!dragging) return;
        const dx = evt.clientX - lastX;
        const dy = evt.clientY - lastY;
        if (Math.abs(dx) > 1 || Math.abs(dy) > 1) {{
          movedDuringDrag = true;
        }}
        lastX = evt.clientX;
        lastY = evt.clientY;
        const horizontalSign = invertHorizontal ? 1 : -1;
        const verticalSign = invertVertical ? -1 : 1;
        yaw += dx * 0.0038 * horizontalSign;
        pitch += dy * 0.0038 * verticalSign;
        pitch = Math.max(-1.35, Math.min(1.35, pitch));
      }});

      renderer.domElement.addEventListener('wheel', (evt) => {{
        evt.preventDefault();
        const zoomOutFactor = invertZoom ? 0.94 : 1.06;
        const zoomInFactor = invertZoom ? 1.06 : 0.94;
        distance *= evt.deltaY > 0 ? zoomOutFactor : zoomInFactor;
        distance = Math.max(payload.radius * 1.15, Math.min(payload.radius * 9.0, distance));
      }}, {{ passive: false }});

      detailHint.textContent = payload.definitions_enabled
        ? 'Definitions are shown in node details.'
        : 'Definitions are omitted at this scale, but word, cluster, and part of speech remain available for every node.';

      invertHorizontalCheckbox.checked = false;
      invertVerticalCheckbox.checked = false;
      invertZoomCheckbox.checked = true;
      invertHorizontalCheckbox.addEventListener('change', () => {{
        invertHorizontal = invertHorizontalCheckbox.checked;
      }});
      invertVerticalCheckbox.addEventListener('change', () => {{
        invertVertical = invertVerticalCheckbox.checked;
      }});
      invertZoomCheckbox.addEventListener('change', () => {{
        invertZoom = invertZoomCheckbox.checked;
      }});
      legendSearchInput.addEventListener('input', () => {{
        renderLegendList(legendSearchInput.value);
      }});

      legendList.addEventListener('click', (evt) => {{
        const row = evt.target.closest('.legend-row');
        if (!row) {{
          return;
        }}

        const rowKind = row.dataset.kind;
        if (rowKind === 'word') {{
          const metaIndex = Number(row.dataset.metaIndex);
          const clusterId = Number(row.dataset.cluster);
          if (!Number.isNaN(metaIndex) && payload.metadata[metaIndex]) {{
            pinnedIndex = metaIndex;
            setTooltipFromMetadata(payload.metadata[metaIndex]);
          }}
          if (!Number.isNaN(clusterId)) {{
            focusCluster(clusterId);
          }}
          return;
        }}

        const clusterId = Number(row.dataset.cluster);
        if (Number.isNaN(clusterId)) {{
          return;
        }}

        focusCluster(clusterId);
        pinnedIndex = null;
        tooltip.style.display = 'none';
      }});

      legendList.addEventListener('dblclick', (evt) => {{
        const row = evt.target.closest('.legend-row');
        if (!row || row.dataset.kind !== 'cluster') {{
          return;
        }}

        const clusterId = Number(row.dataset.cluster);
        if (Number.isNaN(clusterId)) {{
          return;
        }}
        enterClusterDrilldown(clusterId);
      }});

      clusterDrilldownBack.addEventListener('click', () => {{
        resetClusterDrilldown();
      }});

      renderer.domElement.addEventListener('mousemove', onHover);
      renderer.domElement.addEventListener('click', onClick);
      renderer.domElement.addEventListener('mouseleave', () => {{
        hideTooltip();
        renderer.domElement.style.cursor = dragging ? 'grabbing' : (pinnedIndex === null ? 'grab' : 'pointer');
      }});

      function onResize() {{
        camera.aspect = window.innerWidth / window.innerHeight;
        camera.updateProjectionMatrix();
        renderer.setSize(window.innerWidth, window.innerHeight);
      }}
      window.addEventListener('resize', onResize);

      renderer.domElement.style.cursor = 'grab';
      (function animate(nowMs) {{
        requestAnimationFrame(animate);

        if (focusTween) {{
          const elapsed = nowMs - focusTween.startAtMs;
          const progress = Math.max(0, Math.min(1, elapsed / focusTween.durationMs));
          const eased = easeInOutQuad(progress);
          yaw = focusTween.fromYaw + focusTween.yawDelta * eased;
          pitch = focusTween.fromPitch + (focusTween.targetPitch - focusTween.fromPitch) * eased;
          distance = focusTween.fromDistance + (focusTween.targetDistance - focusTween.fromDistance) * eased;
          if (progress >= 1) {{
            focusTween = null;
          }}
        }}

        camera.position.x = distance * Math.cos(pitch) * Math.sin(yaw);
        camera.position.y = distance * Math.sin(pitch);
        camera.position.z = distance * Math.cos(pitch) * Math.cos(yaw);
        camera.lookAt(0, 0, 0);
        renderer.render(scene, camera);
      }})();
    }} catch (err) {{
      showStatus('Renderer error: ' + (err && err.message ? err.message : err));
      console.error(err);
    }}
  }})();
  </script>
</body>
</html>
"""


def render_spherical_surface(surface_df, output_html_path):
    output_html_path.parent.mkdir(parents=True, exist_ok=True)
    definition_lookup = _load_definition_lookup(
        source_file=surface_df.attrs.get("source_file"),
        definition_column=surface_df.attrs.get("definition_column"),
    )
    payload = _build_render_payload(surface_df, definition_lookup=definition_lookup)
    drilldown_files = _write_cluster_drilldown_pages(
        surface_df=surface_df,
        output_dir=output_html_path.parent,
        definition_lookup=definition_lookup,
    )
    for item in payload.get("cluster_summary", []):
        item["drilldown_file"] = drilldown_files.get(int(item.get("cluster", -1)), "")

    output_html_path.write_text(_html(payload), encoding="utf-8")

    return output_html_path

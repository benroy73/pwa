# -*- coding: utf-8 -*-
import os
import webbrowser

def calculate_box_volume_and_cutlist(
    main_w, base_width, main_h, main_d, ext_w=4.250, ext_d=3.000, thickness=0.625,
    ADD_BOX_L_EXTENSION=True, ext_offset_pct=1.0, polyfill_boost=1.14,
    route_depth=0.250, route_coverage=0.50, speaker_cutout_dia=3.000,
    use_metric=False, generate_3d_html=True, html_filename="speaker_box_3d.html",
    auto_open_browser=True
):
    """
    Calculates speaker box interior volumes, outputs a Title Case cutlist,
    and builds a standalone 3D Web Browser blueprint with dynamic polyfill labeling,
    integer-rounded metric cut list values, adjustable extension box width, and tunable panel placement.
    """
    # Enforce offset bounds between 0.0 (closed) and 1.0 (fully open)
    ext_offset_pct = max(0.0, min(1.0, ext_offset_pct))

    # Unit Conversions and Labels
    unit_label = "mm" if use_metric else '"'
    vol_unit_label = "cu cm" if use_metric else "cu in"
    scale = 25.4 if use_metric else 1.0  # Inches to Millimeters scaling multiplier

    # Overhang margin
    overhang = 0.500 * scale

    # Scale variables according to selected measurement system
    w_main = main_w * scale
    w_ext = ext_w * scale
    h_main = main_h * scale
    d_main = main_d * scale
    d_ext = ext_d * scale
    t = thickness * scale
    w_target_base = base_width * scale
    d_route = route_depth * scale

    # 1. Enforce Joint Geometry & Relational Constraints
    rear_panel_width = (w_main + w_ext) - t
    ext_top_cap_max_w = w_ext
    main_front_baffle_w = w_main - (2 * t)

    right_side_depth = d_main
    ext_left_side_depth = d_ext - (2 * t)
    main_left_side_depth = d_main - ext_left_side_depth - t

    # Dynamic extension width based on slider/offset percentage
    ext_active_w = ext_top_cap_max_w * ext_offset_pct
    ext_top_cap_w = ext_active_w
    ext_front_baffle_w = ext_active_w

    # 2. Calculate Standard Interior Cubic Space Volume
    main_int_w = main_front_baffle_w
    main_int_h = h_main - (2 * t)
    main_int_d = d_main - (2 * t)
    main_vol_raw = main_int_w * main_int_h * main_int_d

    if ADD_BOX_L_EXTENSION and ext_offset_pct > 0:
        ext_int_w = ext_front_baffle_w - t if ext_front_baffle_w >= t else 0
        ext_int_d = ext_left_side_depth
        ext_vol_raw = ext_int_w * main_int_h * ext_int_d
        max_footprint_depth = max(d_main, d_ext)

        sa_caps = 2 * ((main_int_w * main_int_d) + (ext_int_w * ext_int_d))
        sa_walls = main_int_h * (main_int_w + right_side_depth + ext_front_baffle_w + ext_left_side_depth + main_left_side_depth)
        total_interior_sa = sa_caps + sa_walls
    else:
        ext_vol_raw = 0
        max_footprint_depth = d_main
        total_interior_sa = 2 * ((main_int_w * main_int_d) + (main_int_w * main_int_h) + (main_int_d * main_int_h))

    # Volume Metrics Matrix
    base_physical_vol = main_vol_raw + ext_vol_raw
    routed_added_vol = total_interior_sa * d_route * route_coverage
    vol_to_liters = 0.001 if use_metric else 0.0163871

    liters_raw = base_physical_vol * vol_to_liters
    liters_polyfill = liters_raw * polyfill_boost
    liters_routed = (base_physical_vol + routed_added_vol) * vol_to_liters
    liters_combined = liters_routed * polyfill_boost

    polyfill_pct = int(round((polyfill_boost - 1.0) * 100))

    # 3. Compile Cut List
    uniform_panel_height = h_main - (2 * t)

    cutlist = {
        "Base Board":                   {"qty": 1, "width": w_target_base, "height": max_footprint_depth, "board_w": t},
        "Main Top Cap (Lid)":           {"qty": 1, "width": w_main, "height": d_main, "board_w": t},
        "Rear Panel":                   {"qty": 1, "width": rear_panel_width, "height": uniform_panel_height, "board_w": t},
        "Main Front Baffle":            {"qty": 1, "width": main_front_baffle_w, "height": uniform_panel_height, "board_w": t},
        "Right Side Panel":             {"qty": 1, "width": right_side_depth, "height": uniform_panel_height, "board_w": t},
    }

    if ADD_BOX_L_EXTENSION and ext_offset_pct > 0:
        cutlist["Extension Top Cap"]      = {"qty": 1, "width": ext_top_cap_w, "height": d_ext, "board_w": t}
        cutlist["Extension Front Baffle"] = {"qty": 1, "width": ext_front_baffle_w, "height": uniform_panel_height, "board_w": t}
        cutlist["Extension Left Side"]    = {"qty": 1, "width": ext_left_side_depth, "height": uniform_panel_height, "board_w": t}
        cutlist["Main Left Side Panel"]   = {"qty": 1, "width": main_left_side_depth, "height": uniform_panel_height, "board_w": t}
    else:
        cutlist["Extension Left Side (Closed Alignment)"] = {"qty": 1, "width": ext_left_side_depth, "height": uniform_panel_height, "board_w": t}
        cutlist["Main Left Side Panel"]                   = {"qty": 1, "width": main_left_side_depth, "height": uniform_panel_height, "board_w": t}

    # 4. Build Terminal & HTML Report Text Buffer
    box_type = f"MODULAR L-SHAPED MODE ({int(ext_offset_pct*100)}% TUNED EXTENSION)" if ADD_BOX_L_EXTENSION else "STANDALONE MODE (EXTENSION CLOSED)"
    sa_unit = "sq cm" if use_metric else "sq in"
    display_sa = total_interior_sa / 100.0 if use_metric else total_interior_sa

    report_lines = []
    report_lines.append("=====================================================")
    report_lines.append(f"📐 BOX DESIGN PROFILE: {box_type}")
    report_lines.append(f"🧱 Material Thickness: {thickness:.3f}\" (Inches Input)")
    report_lines.append(f"🔊 Speaker Hole Cutout: {speaker_cutout_dia:.3f}\" Diameter")
    report_lines.append("=====================================================")
    report_lines.append("📦 BASE GEOMETRIC SPECIFICATIONS:")
    report_lines.append(f"  Main Core Airspace:  {main_vol_raw:.3f} {vol_unit_label}")
    if ADD_BOX_L_EXTENSION:
        report_lines.append(f"  Pocket Airspace:     {ext_vol_raw:.3f} {vol_unit_label}")
    report_lines.append(f"  Total Surface Area:  {display_sa:.3f} {sa_unit}")
    report_lines.append("-----------------------------------------------------")
    report_lines.append("🔊 ACOUSTIC AIRSPACE CAPACITIES MATRIX:")
    report_lines.append(f"  Plain Raw Enclosure:        👉 {liters_raw:.3f} Liters")
    report_lines.append(f"  + Polyfill Fluff Only:      👉 {liters_polyfill:.3f} Liters (+{polyfill_pct}% apparent space)")
    report_lines.append(f"  + Routed Pockets Only:      👉 {liters_routed:.3f} Liters ({route_depth:.3f}\" deep @ {int(route_coverage*100)}% area)")
    report_lines.append(f"  + COMBINED BOTH METHODS:    👉 {liters_combined:.3f} Liters (Maximum Efficiency)")
    report_lines.append("=====================================================\n")

    report_lines.append("-------------------------------------------------------------------------")
    report_lines.append(f"🪚 REQUIRED MDF CUT LIST (Width x Height in {unit_label.upper()})")
    report_lines.append("-------------------------------------------------------------------------")
    fmt = "4.0f" if use_metric else "6.3f"
    for panel, dims in cutlist.items():
        w_val = round(dims['width']) if use_metric else dims['width']
        h_val = round(dims['height']) if use_metric else dims['height']
        w_str = f"{w_val:{fmt}}{unit_label}"
        h_str = f"{h_val:{fmt}}{unit_label}"
        cutout_note = f" (Includes {speaker_cutout_dia:.3f}\" Center Cutout)" if panel == "Main Front Baffle" else ""
        report_lines.append(f"  [ ] Qty: {dims['qty']}  |  {w_str}  x  {h_str}  --> {panel}{cutout_note}")
    report_lines.append("================================================-------------------------")

    report_output_text = "\n".join(report_lines)
    print(report_output_text + "\n")

    # 5. Build and Export Standalone 3D Blueprint
    if generate_3d_html:
        base_w = base_width / scale
        base_d = max_footprint_depth / scale
        th = thickness
        oh = overhang / scale

        m_w = main_w / scale
        m_h = main_h / scale
        m_d = main_d / scale

        r_w = rear_panel_width / scale
        m_baffle_w = main_front_baffle_w / scale
        r_depth = right_side_depth / scale

        ext_cap_w = ext_top_cap_w / scale
        ext_baffle_w = ext_front_baffle_w / scale
        ext_left_d = ext_left_side_depth / scale
        main_left_d = main_left_side_depth / scale
        e_d = ext_d / scale

        wall_h = m_h - (2 * th)
        hole_radius = (speaker_cutout_dia / scale) / 2.0

        main_x_start = base_w - oh - m_w
        ext_x_start = main_x_start - ext_cap_w

        panels = [
            ("Base Board", base_w, th, base_d, 0, 0, 0, 0x8B5A2B, base_w, base_d, False),
            ("Right Side Panel", th, wall_h, r_depth, base_w - oh - th, th, 0, 0x3B82F6, r_depth, wall_h, False),
            ("Main Front Baffle", m_baffle_w, wall_h, th, main_x_start + th, th, m_d - th, 0x2563EB, m_baffle_w, wall_h, True),
            ("Main Left Side Panel", th, wall_h, main_left_d, main_x_start, th, m_d - main_left_d, 0x6D28D9, main_left_d, wall_h, False),
            ("Main Top Cap", m_w, th, m_d, main_x_start, m_h - th, 0, 0x1E3A8A, m_w, m_d, False),
            ("Rear Panel", r_w, wall_h, th, (base_w - oh - th) - r_w, th, 0, 0x1D4ED8, r_w, wall_h, False),
        ]

        if ADD_BOX_L_EXTENSION and ext_offset_pct > 0:
            panels.extend([
                ("Extension Left Side", th, wall_h, ext_left_d, ext_x_start, th, th, 0x8B5CF6, ext_left_d, wall_h, False),
                ("Extension Front Baffle", ext_baffle_w, wall_h, th, ext_x_start, th, e_d - th, 0x7C3AED, ext_baffle_w, wall_h, False),
                ("Extension Top Cap", ext_cap_w, th, e_d, ext_x_start, m_h - th, 0, 0x5B21B6, ext_cap_w, e_d, False),
            ])
        else:
            panels.extend([
                ("Extension Left Side", th, wall_h, ext_left_d, main_x_start, th, th, 0x8B5CF6, ext_left_d, wall_h, False)
            ])

        js_panel_list = []
        for name, w, h, d, px, py, pz, col, lbl_w, lbl_h, is_baffle in panels:
            is_baffle_str = "true" if is_baffle else "false"
            lbl_w_disp = lbl_w * scale
            lbl_h_disp = lbl_h * scale
            js_panel_list.append(
                f'        addPanel("{name}", {w:.3f}, {h:.3f}, {d:.3f}, {px:.3f}, {py:.3f}, {pz:.3f}, {hex(col)}, {lbl_w_disp:.3f}, {lbl_h_disp:.3f}, {is_baffle_str});'
            )
        js_panels_code = "\n".join(js_panel_list)

        disp_base_w = f"{base_width * scale:.0f}" if use_metric else f"{base_width:.3f}"
        disp_main_w = f"{main_w * scale:.0f}" if use_metric else f"{main_w:.3f}"
        disp_main_h = f"{main_h * scale:.0f}" if use_metric else f"{main_h:.3f}"
        disp_main_d = f"{main_d * scale:.0f}" if use_metric else f"{main_d:.3f}"
        disp_thick  = f"{thickness * scale:.0f}" if use_metric else f"{thickness:.3f}"

        js_unit_label = '\\"' if unit_label == '"' else unit_label

        html_template = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Interactive 3D Speaker Blueprint</title>
    <style>
        body { margin: 0; padding: 0; background-color: #121212; overflow: hidden; font-family: system-ui, sans-serif; }
        #info-panel { position: absolute; top: 15px; left: 15px; background: rgba(0,0,0,0.85); padding: 15px; border-radius: 8px; border: 1px solid #333; color: #fff; max-width: 320px; z-index: 10; }
        h3 { margin: 0 0 10px 0; color: #00adb5; font-size: 14px; text-transform: uppercase; }
        p { margin: 4px 0; font-size: 12px; color: #ccc; }
        .control-group { margin-top: 10px; border-top: 1px solid #444; padding-top: 8px; }
        label { font-size: 12px; color: #fff; display: block; margin-bottom: 4px; cursor: pointer; }
        input[type=range] { width: 100%; cursor: pointer; }
        #controls-hint { position: absolute; bottom: 15px; left: 50%; transform: translateX(-50%); background: rgba(0,0,0,0.7); padding: 8px 15px; border-radius: 20px; font-size: 12px; color: #fff; border: 1px solid #555; pointer-events: none; z-index: 10; }

        .panel-label {
            position: absolute;
            background: rgba(0, 0, 0, 0.75);
            color: #00fff2;
            padding: 3px 8px;
            border-radius: 4px;
            border: 1px solid #00fff2;
            font-size: 11px;
            font-weight: bold;
            pointer-events: none;
            white-space: nowrap;
            transform: translate(-50%, -50%);
            transition: opacity 0.1s ease;
        }

        #report-overlay {
            display: block;
            position: absolute;
            top: 15px;
            right: 15px;
            width: 480px;
            max-height: 85vh;
            background: rgba(10, 15, 25, 0.92);
            border: 1px solid #00adb5;
            border-radius: 8px;
            padding: 15px;
            color: #00fff2;
            font-family: 'Courier New', Courier, monospace;
            font-size: 12px;
            white-space: pre;
            overflow-y: auto;
            z-index: 20;
            box-shadow: 0px 4px 20px rgba(0, 0, 0, 0.8);
        }
    </style>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/controls/OrbitControls.js"></script>
</head>
<body>
    <div id="info-panel">
        <h3>Blueprint Configuration</h3>
        <p>Base Width: __DISP_BASE_W____LABEL_UNIT__</p>
        <p>Main Box: __DISP_MAIN_W____LABEL_UNIT__ W x __DISP_MAIN_H____LABEL_UNIT__ H x __DISP_MAIN_D____LABEL_UNIT__ D</p>
        <p>MDF Thickness: __DISP_THICK____LABEL_UNIT__</p>
        <p>Raw Enclosure: __RAW_VOL_LITERS__ L</p>

        <div class="control-group">
            <label for="opacity-slider">Panel Transparency: <span id="opacity-val">80%</span></label>
            <input type="range" id="opacity-slider" min="0.1" max="1.0" step="0.05" value="0.8">
        </div>
        <div class="control-group">
            <label><input type="checkbox" id="toggle-labels" checked> Show Panel Text Labels</label>
            <label><input type="checkbox" id="toggle-cutlist" checked> Show Full Cut List Report</label>
        </div>
    </div>
    
    <div id="controls-hint">🖱️ Left Click + Drag to Rotate | Right Click + Drag to Pan | Scroll to Zoom</div>
    <div id="label-container"></div>
    <div id="report-overlay">__REPORT_TEXT__</div>

    <script>
        const scene = new THREE.Scene(); scene.background = new THREE.Color(0x121212);
        const camera = new THREE.PerspectiveCamera(45, window.innerWidth / window.innerHeight, 0.1, 1000);
        const renderer = new THREE.WebGLRenderer({ antialias: true });
        renderer.setSize(window.innerWidth, window.innerHeight); renderer.shadowMap.enabled = true;
        document.body.appendChild(renderer.domElement);
        const controls = new THREE.OrbitControls(camera, renderer.domElement); controls.enableDamping = true;

        scene.add(new THREE.AmbientLight(0xffffff, 0.7));
        const light = new THREE.DirectionalLight(0xffffff, 0.8); light.position.set(20, 40, 20); light.castShadow = true; scene.add(light);
        scene.add(new THREE.GridHelper(30, 30, 0x444444, 0x222222));

        const panelMaterials = [];
        const labelElements = [];
        const useMetric = __USE_METRIC__;
        const unitSuffix = "__JS_UNIT__";
        const cutoutRadius = __HOLE_RADIUS__;

        function createBaffleGeometry(w, h, d, holeRadius) {
            const shape = new THREE.Shape();
            const hw = w / 2;
            const hh = h / 2;

            shape.moveTo(-hw, -hh);
            shape.lineTo(hw, -hh);
            shape.lineTo(hw, hh);
            shape.lineTo(-hw, hh);
            shape.lineTo(-hw, -hh);

            const holePath = new THREE.Path();
            holePath.absarc(0, 0, holeRadius, 0, Math.PI * 2, true);
            shape.holes.push(holePath);

            const extrudeSettings = { steps: 1, depth: d, bevelEnabled: false };
            return new THREE.ExtrudeGeometry(shape, extrudeSettings);
        }

        function addPanel(name, w, h, d, x, y, z, color, lblW, lblH, isBaffle) {
            let geo = isBaffle ? createBaffleGeometry(w, h, d, cutoutRadius) : new THREE.BoxGeometry(w, h, d);
            const mat = new THREE.MeshStandardMaterial({ color: color, roughness: 0.4, transparent: true, opacity: 0.8 });
            panelMaterials.push(mat);

            const mesh = new THREE.Mesh(geo, mat);
            const centerX = x + w / 2;
            const centerY = y + h / 2;
            const centerZ = z + d / 2;

            if (isBaffle) {
                mesh.position.set(centerX, centerY, z);
            } else {
                mesh.position.set(centerX, centerY, centerZ);
            }

            mesh.castShadow = true;
            mesh.receiveShadow = true;

            const edges = new THREE.LineSegments(new THREE.EdgesGeometry(geo), new THREE.LineBasicMaterial({ color: 0xffffff, linewidth: 1 }));
            mesh.add(edges);
            scene.add(mesh);

            const labelDiv = document.createElement('div');
            labelDiv.className = 'panel-label';
            const formattedW = useMetric ? Math.round(lblW) : lblW.toFixed(3);
            const formattedH = useMetric ? Math.round(lblH) : lblH.toFixed(3);
            labelDiv.innerText = `${name} (${formattedW}${unitSuffix} x ${formattedH}${unitSuffix})`;
            document.getElementById('label-container').appendChild(labelDiv);
            labelElements.push({ element: labelDiv, pos: new THREE.Vector3(centerX, centerY, centerZ) });
        }

__JS_PANELS__

        document.getElementById('opacity-slider').addEventListener('input', (e) => {
            const val = parseFloat(e.target.value);
            document.getElementById('opacity-val').innerText = Math.round(val * 100) + '%';
            panelMaterials.forEach(m => m.opacity = val);
        });

        const labelsToggle = document.getElementById('toggle-labels');
        labelsToggle.addEventListener('change', (e) => {
            const display = e.target.checked ? 'block' : 'none';
            labelElements.forEach(l => l.element.style.display = display);
        });

        const cutlistToggle = document.getElementById('toggle-cutlist');
        const reportOverlay = document.getElementById('report-overlay');
        cutlistToggle.addEventListener('change', (e) => {
            reportOverlay.style.display = e.target.checked ? 'block' : 'none';
        });

        camera.position.set(__CAM_X__, __CAM_Y__, __CAM_Z__);
        controls.target.set(__TARGET_X__, __TARGET_Y__, __TARGET_Z__); 
        controls.update();

        function updateLabels() {
            if (!labelsToggle.checked) return;
            const tempV = new THREE.Vector3();
            labelElements.forEach(labelObj => {
                tempV.copy(labelObj.pos);
                tempV.project(camera);

                if (tempV.z > 1) {
                    labelObj.element.style.opacity = 0;
                    return;
                }

                const x = (tempV.x *  .5 + .5) * window.innerWidth;
                const y = (tempV.y * -.5 + .5) * window.innerHeight;
                labelObj.element.style.left = `${x}px`;
                labelObj.element.style.top = `${y}px`;
                labelObj.element.style.opacity = 1;
            });
        }

        function animate() {
            requestAnimationFrame(animate);
            controls.update();
            updateLabels();
            renderer.render(scene, camera);
        }
        animate();

        window.addEventListener('resize', () => {
            camera.aspect = window.innerWidth/window.innerHeight;
            camera.updateProjectionMatrix();
            renderer.setSize(window.innerWidth, window.innerHeight);
        });
    </script>
</body>
</html>"""

        html_content = html_template \
            .replace("__DISP_BASE_W__", disp_base_w) \
            .replace("__DISP_MAIN_W__", disp_main_w) \
            .replace("__DISP_MAIN_H__", disp_main_h) \
            .replace("__DISP_MAIN_D__", disp_main_d) \
            .replace("__DISP_THICK__", disp_thick) \
            .replace("__RAW_VOL_LITERS__", f"{liters_raw:.3f}") \
            .replace("__LABEL_UNIT__", unit_label) \
            .replace("__JS_UNIT__", js_unit_label) \
            .replace("__USE_METRIC__", "true" if use_metric else "false") \
            .replace("__HOLE_RADIUS__", f"{hole_radius:.4f}") \
            .replace("__JS_PANELS__", js_panels_code) \
            .replace("__REPORT_TEXT__", report_output_text) \
            .replace("__CAM_X__", f"{main_w * 1.8:.3f}") \
            .replace("__CAM_Y__", f"{main_h * 2.2:.3f}") \
            .replace("__CAM_Z__", f"{main_d * 2.8:.3f}") \
            .replace("__TARGET_X__", f"{base_width / 2:.3f}") \
            .replace("__TARGET_Y__", f"{main_h / 2:.3f}") \
            .replace("__TARGET_Z__", f"{main_d / 2:.3f}")

        abs_html_path = os.path.abspath(html_filename)
        with open(abs_html_path, "w", encoding="utf-8") as f:
            f.write(html_content)
        print(f"🎉 Standalone interactive 3D Web File saved as: '{abs_html_path}'\n")

        if auto_open_browser:
            webbrowser.open(f"file://{abs_html_path}")


# ==========================================
# 🛠 YOUR DATA CONFIGURATION
# ==========================================
BOARD_THICKNESS    = 0.625

BASE_WIDTH         = 10.750

MAIN_BOX_DEPTH     = 5.000
MAIN_BOX_WIDTH     = 5.500
MAIN_BOX_HEIGHT    = 5.500
SPEAKER_CUTOUT_DIA = 3.000

EXTENSION_BOX_WIDTH = 4.250  # Width of the extension pocket
EXTENSION_BOX_DEPTH = 3.000  # Depth of the extension pocket

# Global Configuration Toggles
ADD_BOX_L_EXTENSION  = True
EXTENSION_OFFSET_PCT = 1.0  # 1.0 = Fully extended (max vol), 0.0 = Flush with main panel (min vol)
USE_METRIC           = False

# Acoustic Tuning Coefficients
POLYFILL_EFFICIENCY  = 1.14
ROUTER_POCKET_DEPTH  = 0.250
ROUTER_COVERAGE_PCT  = 0.50

if __name__ == "__main__":
    calculate_box_volume_and_cutlist(
        main_w=MAIN_BOX_WIDTH, base_width=BASE_WIDTH, main_h=MAIN_BOX_HEIGHT, main_d=MAIN_BOX_DEPTH,
        ext_w=EXTENSION_BOX_WIDTH, ext_d=EXTENSION_BOX_DEPTH, thickness=BOARD_THICKNESS,
        ADD_BOX_L_EXTENSION=ADD_BOX_L_EXTENSION, ext_offset_pct=EXTENSION_OFFSET_PCT,
        polyfill_boost=POLYFILL_EFFICIENCY, route_depth=ROUTER_POCKET_DEPTH, route_coverage=ROUTER_COVERAGE_PCT,
        speaker_cutout_dia=SPEAKER_CUTOUT_DIA,
        use_metric=USE_METRIC, generate_3d_html=True, auto_open_browser=True
    )

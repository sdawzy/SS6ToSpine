# SS6-To-Spine Toolkit

A Python toolkit for extracting, previewing, validating, and converting **SpriteStudio 6 / SS6Player for Unity** character animations from Unity AssetBundles into **Spine 4.2 JSON**.

The project includes both a command-line interface and a Windows desktop GUI. Its current high-fidelity export path uses **frame-swapped baked mesh attachments**, which reproduces the evaluated SS6 animation geometry closely while avoiding differences in transform interpolation between SS6 and Spine.

> **Project status:** experimental, but usable for the tested SS6 character bundles. The frame-swap exporter is currently the recommended export path.

---

## Features

- Extract SS6 animation data directly from Unity AssetBundles.
- Export textures, cell maps, part definitions, and raw animation data.
- Preview SS6 animations in Python before exporting.
- Render every animation in a character bundle to PNG frames and GIF previews.
- Export multiple animations into a single Spine 4.2 JSON project.
- Preserve per-frame visual geometry through baked mesh attachment switching.
- Cross-frame and cross-animation mesh deduplication.
- Optional animation downsampling for smaller exports.
- Include/exclude animation filtering with regular expressions.
- Diagnostic tools for comparing exported Spine geometry against the Python runtime.
- Windows desktop GUI for the most common workflows.

---

## Requirements

- Python 3.9 or newer
- Windows is recommended for the included `.bat` launchers
- Spine 4.2 for importing the generated JSON

Python dependencies:

```text
UnityPy
Pillow
NumPy
OpenCV-Python
```

Install them with:

```powershell
py -m pip install UnityPy pillow numpy opencv-python
```

On Windows, you can also double-click:

```text
install_dependencies.bat
```

---

## Quick Start

### Desktop GUI

The easiest way to use the toolkit is the desktop interface.

Double-click:

```text
run_gui.bat
```

or launch it manually:

```powershell
py -m ss6runtime.gui
```

Typical workflow:

1. Select a Unity AssetBundle.
2. Choose an output directory.
3. Click **Scan animations**.
4. Verify the detected setup animation.
5. Keep the default deduplication settings for the first export.
6. Click **Export all animations to Spine**.
7. Import the generated `.json` file into Spine 4.2.

---

## Recommended Spine Export

The recommended exporter is the optimized frame-swap exporter.

```powershell
py -m ss6runtime bundle-to-spine-frame-swap-all bundle.bin -o spine_output
```

The generated directory contains files similar to:

```text
spine_output/
├── bundle.json
├── bundle.atlas
├── textures/
├── spine_export_report.json
└── _extracted/
```

Import the generated JSON into Spine while keeping the `.atlas` file and `textures/` directory beside it.

### Choose the setup animation

The exporter automatically prefers animations such as `stand`, `idle`, or `ready` when available.

To choose one explicitly:

```powershell
py -m ss6runtime bundle-to-spine-frame-swap-all bundle.bin -o spine_output --setup-animation stand --setup-frame 0
```

### Filter animations

Export only selected animations:

```powershell
py -m ss6runtime bundle-to-spine-frame-swap-all bundle.bin -o spine_output --include "stand|move|attack|damage"
```

Exclude selected animations:

```powershell
py -m ss6runtime bundle-to-spine-frame-swap-all bundle.bin -o spine_output --exclude "victory|effect"
```

Both options accept regular expressions and can be used together.

---

## Output Optimization

The optimized exporter supports several ways to reduce JSON size.

### Geometry deduplication

Geometry is deduplicated across both frames and animations.

Default tolerance:

```text
0.0001 Spine units
```

Use a stricter tolerance:

```powershell
py -m ss6runtime bundle-to-spine-frame-swap-all bundle.bin -o spine_output --dedupe-tolerance 0.00001
```

Use more aggressive deduplication:

```powershell
py -m ss6runtime bundle-to-spine-frame-swap-all bundle.bin -o spine_output --dedupe-tolerance 0.001
```

Disable deduplication completely:

```powershell
py -m ss6runtime bundle-to-spine-frame-swap-all bundle.bin -o spine_output --no-dedupe
```

### Lower export frame rate

Keep the original animation duration while using fewer baked samples:

```powershell
py -m ss6runtime bundle-to-spine-frame-swap-all bundle.bin -o spine_output --export-fps 15
```

Other useful values include `20`, `12`, and `10`.

### Frame stepping

Export every second source frame:

```powershell
py -m ss6runtime bundle-to-spine-frame-swap-all bundle.bin -o spine_output --frame-step 2
```

`--frame-step` takes precedence over `--export-fps`.

For best fidelity, start with the original frame rate and only downsample after verifying the result.

---

## Extracting Raw SS6 Data

Extract the main character data from a bundle:

```powershell
py -m ss6runtime extract-bundle bundle.bin -o extracted
```

This produces:

```text
extracted/
├── textures/
├── animation_raw.json
├── cellmap.json
├── parts_raw.json
└── extract_manifest.json
```

Extract every animation:

```powershell
py -m ss6runtime extract-bundle bundle.bin -o extracted --all-animations
```

Additional raw animation files will be written under:

```text
extracted/animations/
```

---

## Python Preview Renderer

Before exporting to Spine, you can render the SS6 animation directly with the Python runtime.

### Preview one frame

```powershell
py -m ss6runtime preview --parts-raw extracted\parts_raw.json --animation-raw extracted\animation_raw.json --cellmap extracted\cellmap.json --texture-dir extracted\textures --frame 0 --mode native2d --coordinate-mode yup -o frame0.png
```

### Preview a complete animation

```powershell
py -m ss6runtime preview-animation --parts-raw extracted\parts_raw.json --animation-raw extracted\animation_raw.json --cellmap extracted\cellmap.json --texture-dir extracted\textures --mode native2d --coordinate-mode yup -o preview_animation
```

This creates PNG frames and, by default, a GIF preview.

### Render every animation in a bundle

```powershell
py -m ss6runtime render-all-animations bundle.bin -o rendered_20080
```

The command also creates an HTML gallery for quickly reviewing all animations.

---

## Batch Testing

Test many bundles in one directory:

```powershell
py -m ss6runtime batch-test bundles -o batch_results --pattern "bundle_unit_*"
```

To render every animation for every bundle:

```powershell
py -m ss6runtime batch-test bundles -o batch_results --pattern "bundle_unit_*" --all-animations
```

For a faster first pass:

```powershell
py -m ss6runtime batch-test bundles -o batch_results_quick --pattern "bundle_unit_*" --all-animations --max-frames 6 --scale 1 --no-gif
```

The batch tester writes JSON, CSV, and HTML reports.

---

## Validation

The frame-swap validator compares the geometry selected by the generated Spine animation against the Python SS6 runtime at every sampled frame.

Example:

```powershell
py -m ss6runtime validate-spine-frame-swap --spine-json spine_output\bundle.json --spine-dir spine_output --animation victory --part-filter "hand|arm" -o validation_victory
```

The validation report includes:

```text
max_vertex_error
visibility_mismatches
region_mismatches
worst
```

A result close to:

```text
max_vertex_error = 0
visibility_mismatches = 0
region_mismatches = 0
```

means the exported sampled geometry matches the Python runtime at the validated frames.

---

## Export Modes

Several experimental exporters are included because they were useful during development.

| Exporter | Purpose | Status |
|---|---|---|
| `bundle-to-spine-frame-swap-all` | All animations, optimized baked frame-swap export | **Recommended** |
| `bundle-to-spine-frame-swap` | One animation, baked frame-swap export | Stable baseline |
| `bundle-to-spine-static` | Static setup pose | Useful for debugging |
| `bundle-to-spine-animated` | Bone/timeline-based experimental export | Experimental |
| `bundle-to-spine-baked` | Deform-based baked experiment | Experimental |

The frame-swap exporter is currently preferred because it most closely reproduces the Python renderer for the tested assets.

---

## How the Frame-Swap Exporter Works

SS6 and Spine do not use identical animation semantics. Reconstructing the original SS6 hierarchy directly in Spine can produce differences in transform interpolation, reflection handling, shear, and mesh deformation.

The current exporter therefore uses a fidelity-first approach:

```text
SS6 AssetBundle
      ↓
UnityPy extraction
      ↓
Python SS6 runtime evaluation
      ↓
Final per-frame world geometry
      ↓
Baked Spine mesh attachments
      ↓
Stepped attachment timelines
```

Each visible SS6 part becomes a Spine slot attached to a single root bone. The evaluated geometry for each sampled frame is stored as a mesh attachment, and the animation switches attachments at the corresponding frame times.

This produces larger files than a traditional skeletal rig, but avoids many differences between SS6 and Spine transform systems.

---

## Project Layout

```text
ss6runtime/
├── __main__.py       # CLI entry point
├── runtime.py        # SS6 animation evaluation
├── extractor.py      # Unity/SS6 AssetBundle extraction
├── preview.py        # Python renderer
├── spine_export.py   # Spine exporters
├── validate_spine.py # Export validation
├── batch.py          # Batch workflows
└── gui.py            # Tkinter desktop interface

run_gui.py
run_gui.bat
install_dependencies.bat
```

---

## GUI Notes

The GUI is implemented with Tkinter and does not require an additional UI framework.

The main tabs are:

- **Spine export** — configure and run the optimized exporter.
- **Python previews** — render selected or all animations.
- **Animations** — inspect animations detected in the bundle.

Long-running extraction and rendering operations run in worker threads so the interface remains responsive.

---

## Known Limitations

- The project targets SS6 / SS6Player-for-Unity style data and is not a general Unity animation converter.
- AssetBundle layouts may differ between games or SS6Player versions.
- The hidden-status interpretation is based on the tested asset format and may require adjustment for other SS6 projects.
- The recommended exporter prioritizes visual fidelity over editability. The generated Spine project is not equivalent to the original SS6 rig.
- Frame-swap exports can become large for characters with many long animations.
- Lower export frame rates reduce output size but can reduce animation fidelity.
- Third-party Spine previewers may not behave exactly like the official Spine editor/runtime.

---

## Troubleshooting

### No SpriteStudio6 data found

The bundle may not contain SS6 `MonoBehaviour` objects, or its serialized layout may differ from the currently supported format.

Use the extraction/inspection commands first and check the generated manifest.

### Character is missing textures

Verify that the generated `.atlas` and `textures/` directory remain next to the exported JSON.

### Mesh textures appear vertically inverted

Try the mesh V-flip option in the GUI or the corresponding CLI flag:

```text
--mesh-v-flip
```

### Export is too large

Try, in order:

1. keep deduplication enabled;
2. increase `--dedupe-tolerance` slightly;
3. export at 15 or 20 FPS;
4. use `--frame-step 2` for a more aggressive reduction.

Always verify the resulting animation visually after changing compression settings.

---

## Development

Run the CLI help:

```powershell
py -m ss6runtime --help
```

Run the GUI directly:

```powershell
py -m ss6runtime.gui
```

The codebase intentionally keeps extraction, runtime evaluation, rendering, exporting, and validation in separate modules so each stage can be tested independently.

Contributions that improve compatibility with additional SS6Player versions, reduce frame-swap output size, or reconstruct a compact editable Spine rig are particularly useful.

---

## Legal Notice

This project is an independent interoperability and asset-processing tool. It is not affiliated with SpriteStudio, Esoteric Software, Unity Technologies, or any game developer or publisher.

Use it only with assets you are authorized to access, modify, or convert. Game assets, character artwork, textures, animations, and other bundled content remain the property of their respective rights holders.

---

## License

No software license is currently included in this archive.

If you plan to publish this project as open source, add an appropriate license file (for example MIT, Apache-2.0, or another license that matches your intended terms) before distributing the repository.

## License

This project is licensed under the [MIT License](LICENSE).

You are free to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the software, subject to the terms of the MIT License.


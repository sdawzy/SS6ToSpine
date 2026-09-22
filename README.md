# ss6python_runtime v0.3

v0.3 focuses on two errors shared by all v0.2 previews:

1. animation/runtime coordinates are treated as **Y-up** by default;
2. `Status.Flags & 0x20000000` is provisionally interpreted as the SS6 hidden bit.

The hidden interpretation is intentionally reversible with `--show-hidden`.

## Install

```powershell
py -m pip install pillow numpy opencv-python
```

## Recommended comparison

```powershell
py -m ss6runtime preview-compare --parts-raw parts_raw.json --animation-raw animation_raw.json --cellmap cellmap.json --texture-dir textures --frame 0 -o preview_compare_v03
```

The comparison now contains:

1. `native2d_zxy_yup` — recommended candidate, hidden parts removed
2. `native2d_zxy_yup_showhidden` — same transform but hidden parts retained
3. `flat2d_zxy_yup`
4. `unity3d_zxy_yup`
5. `native2d_zxy_ydown`
6. `flat3d_zxy_yup`

## Single recommended preview

```powershell
py -m ss6runtime preview --parts-raw parts_raw.json --animation-raw animation_raw.json --cellmap cellmap.json --texture-dir textures --frame 0 --mode native2d --coordinate-mode yup -o preview_v03_native2d.png
```

## Show hidden parts for diagnosis

```powershell
py -m ss6runtime preview --parts-raw parts_raw.json --animation-raw animation_raw.json --cellmap cellmap.json --texture-dir textures --frame 0 --mode native2d --coordinate-mode yup --show-hidden -o preview_v03_native2d_showhidden.png
```

## Why Y-up?

The v0.2 comparison showed that `native2d + final Y flip` was the only candidate with a broadly correct upright orientation. v0.3 therefore makes Y-up consistent at both levels:

- animation/world coordinates;
- Cell local geometry around the Cell Pivot.

Previously only the final canvas projection was flipped, while Cell-local geometry still used Y-down coordinates.

## Why hide bit 0x20000000?

In this asset the auxiliary `kirann_2`, `circle`, `circle_1`, and `flash` states use flags such as `0x60ffffff`, while ordinary visible parts commonly use `0x40...`. The shared difference is `0x20000000`.

This is still marked provisional until the exact SS6Player enum is recovered, so `--show-hidden` remains available.

## Remaining likely issues

If the main body is still structurally wrong after v0.3, the next target is no longer Euler order. It will be the SS6Player attribute-evaluation semantics, especially:

- exact Status flag meanings;
- whether planarization uses Rotation X/Y before or after hierarchy composition;
- mesh bind-space semantics;
- any runtime correction applied after parent matrices.


## Render the whole animation as PNG frames + GIF

Recommended next step, using the current best candidate:

```powershell
py -m ss6runtime preview-animation --parts-raw parts_raw.json --animation-raw animation_raw.json --cellmap cellmap.json --texture-dir textures --mode native2d --coordinate-mode yup -o preview_anim_v04
```

This generates:

```text
preview_anim_v04\frame_000.png
preview_anim_v04\frame_001.png
...
preview_anim_v04\preview.gif
```

You can also limit the number of frames during testing:

```powershell
py -m ss6runtime preview-animation --parts-raw parts_raw.json --animation-raw animation_raw.json --cellmap cellmap.json --texture-dir textures --mode native2d --coordinate-mode yup --max-frames 6 -o preview_anim_test
```


# v0.5: one-command AssetBundle extractor

v0.5 can now generate all four inputs needed by the Python runtime in one command:

```text
textures/
animation_raw.json
cellmap.json
parts_raw.json
```

It also writes `extract_manifest.json`, which records which SS6 Root, DataAnimation, DataCellMap, and animation were selected.

## Install

```powershell
py -m pip install UnityPy pillow numpy opencv-python
```

## Typical use

```powershell
py -m ss6runtime extract-bundle bundle_unit_00048_bc -o extracted_00048
```

The output is:

```text
extracted_00048/
  textures/
    ...
  animation_raw.json
  cellmap.json
  parts_raw.json
  extract_manifest.json
```

The extractor prefers the SS6 Root with the largest `TableControlParts` count and a referenced `*_mot` DataAnimation, while avoiding obvious effect and `da_sp` roots.

If the automatically selected animation is not the one you want:

```powershell
py -m ss6runtime extract-bundle bundle_unit_00048_bc -o extracted_00048 --animation-name mot_stand
```

or:

```powershell
py -m ss6runtime extract-bundle bundle_unit_00048_bc -o extracted_00048 --animation-index 0
```

If a bundle contains several character DataAnimation objects and auto-selection picks the wrong one:

```powershell
py -m ss6runtime extract-bundle your_bundle -o extracted_character --data-animation da_00048_BC_mot
```

After extraction, preview immediately with:

```powershell
py -m ss6runtime preview-compare --parts-raw extracted_00048\parts_raw.json --animation-raw extracted_00048\animation_raw.json --cellmap extracted_00048\cellmap.json --texture-dir extracted_00048\textures --frame 0 -o extracted_00048\preview_compare
```

The generated `cellmap.json` now records the exact `texture_file` for each cell map when the Texture2D PPtr can be resolved, so the preview renderer no longer has to guess atlas filenames in the normal case.


# v0.6 rendering performance

v0.6 significantly speeds up preview rendering.

Main changes:

- JSON/runtime/cellmap/textures are loaded once per animation, not once per frame.
- `cv2.warpAffine` works only on the destination triangle's bounding box instead of the full canvas.
- alpha blending is restricted to the same small ROI.
- PNG compression defaults to `1` for much faster writes.
- GIF generation can be disabled during iteration.

Fast animation preview:

```powershell
py -m ss6runtime preview-animation --parts-raw extracted_00048\parts_raw.json --animation-raw extracted_00048\animation_raw.json --cellmap extracted_00048\cellmap.json --texture-dir extracted_00048\textures --mode native2d --coordinate-mode yup --no-gif --png-compression 1 -o extracted_00048\preview_fast
```

If you only need visual diagnosis, scale 1 is substantially faster than scale 2:

```powershell
py -m ss6runtime preview-animation --parts-raw extracted_00048\parts_raw.json --animation-raw extracted_00048\animation_raw.json --cellmap extracted_00048\cellmap.json --texture-dir extracted_00048\textures --mode native2d --coordinate-mode yup --scale 1 --no-gif --png-compression 1 -o extracted_00048\preview_fast
```

After the result looks correct, generate the GIF once:

```powershell
py -m ss6runtime preview-animation --parts-raw extracted_00048\parts_raw.json --animation-raw extracted_00048\animation_raw.json --cellmap extracted_00048\cellmap.json --texture-dir extracted_00048\textures --mode native2d --coordinate-mode yup --scale 2 --png-compression 1 -o extracted_00048\preview_final
```


# v0.7: batch testing and all-animation rendering

## 1. Render every animation for one character

```powershell
py -m ss6runtime render-all-animations bundle_unit_20080_bc.bin -o rendered_20080
```

This automatically:

- finds the main SS6 `DataAnimation`;
- exports shared `textures`, `parts_raw.json`, and `cellmap.json`;
- exports every animation into `animations\XX_name\animation_raw.json`;
- renders every animation;
- creates a `preview.gif` for each animation;
- creates `all_animations_report.json`;
- creates `all_animations_report.html` as a visual gallery.

For faster testing without GIFs:

```powershell
py -m ss6runtime render-all-animations bundle_unit_20080_bc.bin -o rendered_20080_fast --scale 1 --no-gif
```

Only render animations whose names match a regular expression:

```powershell
py -m ss6runtime render-all-animations bundle_unit_20080_bc.bin -o rendered_20080 --animation-filter "stand|idle|attack"
```

Limit every animation to the first 6 frames:

```powershell
py -m ss6runtime render-all-animations bundle_unit_20080_bc.bin -o rendered_20080_test --max-frames 6
```

## 2. Extract all animations without rendering them

```powershell
py -m ss6runtime extract-bundle bundle_unit_20080_bc.bin -o extracted_20080 --all-animations
```

This creates:

```text
extracted_20080/
  textures/
  parts_raw.json
  cellmap.json
  animation_raw.json
  animations/
    00_animation_name/
      animation_raw.json
    01_animation_name/
      animation_raw.json
    ...
  extract_manifest.json
```

## 3. Batch-test a whole folder of bundles

Put bundles in one directory, for example:

```text
bundles/
  bundle_unit_00048_bc
  bundle_unit_20080_bc.bin
  bundle_unit_XXXXX_bc
```

Then run:

```powershell
py -m ss6runtime batch-test bundles -o batch_results
```

For every bundle the tool automatically:

- extracts the selected main animation;
- exports `textures`, `animation_raw.json`, `cellmap.json`, and `parts_raw.json`;
- renders `frame0.png`;
- renders the selected animation;
- generates `preview.gif`;
- records failures without stopping the rest of the batch.

The batch output contains:

```text
batch_results/
  000_bundle_name/
  001_bundle_name/
  ...
  batch_report.json
  batch_report.csv
  batch_report.html
```

Open `batch_report.html` in a browser for a visual gallery of all tested characters.

If the input directory contains unrelated files, use a glob pattern:

```powershell
py -m ss6runtime batch-test bundles -o batch_results --pattern "bundle_unit_*"
```

## 4. Batch-test and render every animation for every character

This is the most comprehensive mode and can take significantly longer:

```powershell
py -m ss6runtime batch-test bundles -o batch_results_all --pattern "bundle_unit_*" --all-animations
```

For a quick scan:

```powershell
py -m ss6runtime batch-test bundles -o batch_results_quick --pattern "bundle_unit_*" --all-animations --max-frames 6 --scale 1 --no-gif
```


# v0.8: automatic camera framing

Many SS6 characters are authored high in the 320x320 canvas. Previous versions placed the runtime origin at the exact canvas center, which could clip the top of the head while leaving a large empty area below.

v0.8 enables automatic framing by default.

For a whole animation it:

1. renders all frames on a larger temporary canvas;
2. computes the union of visible pixels across the entire animation;
3. computes ONE fixed camera translation for the whole clip;
4. crops back to the original animation canvas.

Because the same translation is used for every frame, auto framing does not introduce per-frame camera jitter.

## Normal usage

No extra option is necessary:

```powershell
py -m ss6runtime preview-animation --parts-raw extracted_20080\parts_raw.json --animation-raw extracted_20080\animation_raw.json --cellmap extracted_20080\cellmap.json --texture-dir extracted_20080\textures --mode native2d --coordinate-mode yup -o extracted_20080\preview_anim
```

`render-all-animations` also uses auto framing automatically:

```powershell
py -m ss6runtime render-all-animations bundle_unit_20080_bc.bin -o rendered_20080
```

## Disable automatic framing

```powershell
py -m ss6runtime preview-animation --parts-raw extracted_20080\parts_raw.json --animation-raw extracted_20080\animation_raw.json --cellmap extracted_20080\cellmap.json --texture-dir extracted_20080\textures --mode native2d --coordinate-mode yup --no-auto-frame -o extracted_20080\preview_original_camera
```

## Manual camera adjustment

Positive `--offset-y` moves the SS6 origin downward on screen before auto-framing/manual rendering:

```powershell
py -m ss6runtime preview-animation --parts-raw extracted_20080\parts_raw.json --animation-raw extracted_20080\animation_raw.json --cellmap extracted_20080\cellmap.json --texture-dir extracted_20080\textures --mode native2d --coordinate-mode yup --offset-y 20 -o extracted_20080\preview_shifted
```

Likewise:

```text
--offset-x 20
--offset-x -20
--offset-y 20
--offset-y -20
```

can be used for unusual characters.


# v0.9: auto-frame blank-output fix

v0.8 had a coordinate bug in the final crop step. The character bounding-box center was
measured in the enlarged SOURCE canvas, but was then mixed with an additional source-to-target
center translation. This could move the crop window completely away from the character and
produce an empty transparent image.

v0.9 fixes this by directly cropping the enlarged source canvas around the union bounding-box
center.

Recommended command:

```powershell
py -m ss6runtime preview-animation --parts-raw extracted_20080\parts_raw.json --animation-raw extracted_20080\animation_raw.json --cellmap extracted_20080\cellmap.json --texture-dir extracted_20080\textures --mode native2d --coordinate-mode yup -o extracted_20080\preview_anim_v09
```

All-animation rendering uses the same fixed auto-framing logic:

```powershell
py -m ss6runtime render-all-animations bundle_unit_20080_bc.bin -o rendered_20080_v09
```


# v0.10: Spine 4.2 static exporter

v0.10 adds the first Spine exporter.

It deliberately exports a **static setup pose first**. The source frame is evaluated by the
already-tested Python runtime (`native2d`, Y-up). Animation timelines will be added after the
static import is visually validated.

## Export from an already extracted character

```powershell
py -m ss6runtime export-spine-static --parts-raw extracted_20080\parts_raw.json --animation-raw extracted_20080\animation_raw.json --cellmap extracted_20080\cellmap.json --texture-dir extracted_20080\textures --frame 0 --name unit_20080 -o spine_20080
```

Output:

```text
spine_20080/
  unit_20080.json
  unit_20080.atlas
  textures/
    ...
  spine_export_report.json
```

Import `unit_20080.json` into Spine 4.2 and keep the generated `.atlas` beside it.

## One-command bundle -> Spine static export

```powershell
py -m ss6runtime bundle-to-spine-static bundle_unit_20080_bc.bin -o spine_20080
```

Choose another source animation/setup frame:

```powershell
py -m ss6runtime bundle-to-spine-static bundle_unit_20080_bc.bin -o spine_20080_stand --animation-name mot_stand --frame 0
```

## Export model

The exporter uses one flat Spine bone per SS6 Part, all parented directly to `root`.

This is intentional. The Python runtime has already evaluated the SS6 hierarchy correctly.
Flattening prevents Spine's transform inheritance rules from changing the validated world pose.

The converter does **not** throw away affine shear: each evaluated 2D matrix is represented
exactly using Spine `rotation`, `scaleX`, `scaleY`, and `shearY`.

### Ordinary sprites

Ordinary cells remain Spine `region` attachments.

Their local offset is computed from the SS6 Cell Pivot.

### SS6 weighted meshes

For this static exporter, weighted SS6 meshes are CPU-skinned at the selected frame and then
written as Spine **unweighted mesh** attachments.

This preserves the selected static shape. True Spine weighted-mesh bindings will be added in
the later animation exporter.

## Mesh UV troubleshooting

The exporter currently writes SS6 `TableRateUV` values directly as Spine region UVs.

If a mesh texture looks vertically inverted, retry with:

```powershell
py -m ss6runtime export-spine-static --parts-raw extracted_20080\parts_raw.json --animation-raw extracted_20080\animation_raw.json --cellmap extracted_20080\cellmap.json --texture-dir extracted_20080\textures --frame 0 --name unit_20080 --mesh-v-flip -o spine_20080_vflip
```

Do not use `--mesh-v-flip` unless mesh textures actually appear vertically inverted.


# v0.11: Spine import fix

v0.10 emitted `"animations": {}` for static exports. Spine's JSON importer rejects a file
with no animations and reports:

```text
No animations were found in the Spine JSON.
```

v0.11 always emits a minimal placeholder animation named `setup`:

```json
"animations": {
  "setup": {
    "bones": {
      "root": {
        "rotate": [
          { "time": 0.0, "value": 0.0 }
        ]
      }
    }
  }
}
```

This animation does not visually alter the exported setup pose. It only ensures that Spine
recognizes the file as importable animation data.

Normal static export command remains unchanged:

```powershell
py -m ss6runtime export-spine-static --parts-raw extracted_20080\parts_raw.json --animation-raw extracted_20080\animation_raw.json --cellmap extracted_20080\cellmap.json --texture-dir extracted_20080\textures --frame 0 --name unit_20080 -o spine_20080
```


# v0.12: first Spine animation exporter

v0.12 adds the first actual Spine animation exporter.

It builds on the already validated static exporter:

- flat setup bones (one per SS6 part, all parented to `root`);
- the selected setup pose from `setup_frame`;
- a real animation timeline generated by evaluating every SS6 frame through the Python runtime.

## Export animation from extracted files

```powershell
py -m ss6runtime export-spine-animated --parts-raw extracted_20080\parts_raw.json --animation-raw extracted_20080\animation_raw.json --cellmap extracted_20080\cellmap.json --texture-dir extracted_20080\textures --setup-frame 0 --name unit_20080 -o spine_anim_20080
```

## One-command bundle -> Spine animation export

```powershell
py -m ss6runtime bundle-to-spine-animated bundle_unit_20080_bc.bin -o spine_anim_20080
```

Choose another source animation:

```powershell
py -m ss6runtime bundle-to-spine-animated bundle_unit_20080_bc.bin -o spine_anim_20080_attack --animation-name mot_action_01 --setup-frame 0
```

## What v0.12 exports

- setup pose bones
- region attachments
- mesh attachments baked from the setup frame
- bone translate / rotate / scale / shear timelines
- slot attachment switching
- slot color timelines for opacity / hidden-state toggling
- setup placeholder animation

## Current limitation

True mesh deformation timelines are **not** emitted yet.

So if a character relies heavily on animated weighted meshes, the imported Spine animation will
usually be partially correct:

- rigid parts and region-swaps should animate;
- mesh parts may keep the setup-frame shape while following the animated flat bone transform.

This is the expected v0.12 limitation and the next target for improvement.


# v0.13: animation transform semantics fix

v0.12 wrote evaluated bone transforms as absolute animation values. Spine animation transform
keys are relative to the setup pose, so this caused a correct setup pose to become displaced
when the animation started.

v0.13 changes the timelines to:

```text
translate = frame position - setup position
rotate    = frame rotation - setup rotation
scale     = frame scale / setup scale
shear     = frame shear - setup shear
```

It also fixes two Spine JSON field names:

```text
rotate key:  angle    (not value)
draw order:  draworder (not drawOrder)
```

Rotation and shear deltas are unwrapped across frames to avoid artificial +/-360 degree jumps.

Recommended test:

```powershell
py -m ss6runtime bundle-to-spine-animated bundle_unit_20080_bc.bin -o spine_anim_20080_v13 --animation-name mot_stand --setup-frame 0
```

Compare the imported Spine `mot_stand` animation against the Python `preview.gif`.

Current remaining known limitation: weighted mesh vertex animation/deform is still static at the
setup frame. Rigid region parts should now follow the runtime pose much more closely.


# v0.14: baked Spine mesh deform timelines

v0.14 adds mesh deformation to the animated Spine exporter.

The Python runtime already computes the final skinned SS6 mesh vertices for each frame. Rather
than reconstructing native Spine bone weights immediately, v0.14 converts those world-space
vertices back into the animated flat Spine bone's local coordinate system and writes the
difference from the setup mesh vertices as a Spine `deform` timeline.

For an unweighted Spine mesh:

```text
deform delta = current local vertex - setup local vertex
```

This keeps the existing flat-bone strategy while allowing hair, clothing, bust, wings, skirts,
and other SS6 weighted meshes to change shape over time.

Recommended test:

```powershell
py -m ss6runtime bundle-to-spine-animated bundle_unit_20080_bc.bin -o spine_anim_20080_stand_v14 --animation-name mot_stand --setup-frame 0
```

Attack:

```powershell
py -m ss6runtime bundle-to-spine-animated bundle_unit_20080_bc.bin -o spine_anim_20080_attack_v14 --animation-name mot_attack_02 --setup-frame 0
```

Move:

```powershell
py -m ss6runtime bundle-to-spine-animated bundle_unit_20080_bc.bin -o spine_anim_20080_move_v14 --animation-name mot_move --setup-frame 0
```

`spine_export_report.json` now reports:

```text
mesh_animation_supported
mesh_animation_mode
deform_timelines
deform_keyframes
```

The mesh animation mode is `baked-unweighted-deform`: it reproduces the evaluated SS6 mesh
shape frame-by-frame but does not yet reconstruct the original SS6 bone weights inside Spine.


# v0.15: signed-reflection transforms + sparse timelines

The warning from the Spine preview tool (`531 timelines`, dense per-frame keys) exposed that the
previous exporter created four transform timelines for nearly every SS6 part whether or not the
channel changed.

v0.15 changes two important things.

## 1. Reflection decomposition

Previously an affine reflection was commonly represented as:

```text
scaleY = positive
shearY ~= 180 degrees
```

That reproduces a static matrix, but is a poor animation representation.

v0.15 represents reflections using a signed scale:

```text
scaleY = negative
shearY ~= 0 degrees
```

The world matrix is mathematically identical, but interpolation is substantially more stable for
SS6 characters that use 180-degree Y flips.

## 2. Sparse timelines

The exporter now:

- omits translate if it is zero for the whole animation;
- omits rotate if it is zero for the whole animation;
- omits scale if it stays at 1,1;
- omits shear if it stays at 0,0;
- removes linearly redundant intermediate samples;
- does not emit a frame-0 attachment key when the setup attachment is already correct;
- does not emit a frame-0 color key when the setup color is already correct.

This should greatly reduce timeline/key counts.

## 3. Transform self-check

`spine_export_report.json` now includes:

```text
transform_selfcheck.max_matrix_error
bone_timelines
bone_keyframes
slot_timelines
slot_keyframes
```

`max_matrix_error` should normally be close to floating-point zero. A large value means the
Spine setup + timeline transform representation itself does not reconstruct the Python runtime
pose and should be investigated before looking at mesh deformation.

Recommended tests:

```powershell
py -m ss6runtime bundle-to-spine-animated bundle_unit_20080_bc.bin -o spine_anim_20080_attack_v15 --animation-name mot_attack_02 --setup-frame 0
```

```powershell
py -m ss6runtime bundle-to-spine-animated bundle_unit_20080_bc.bin -o spine_anim_20080_move_v15 --animation-name mot_move --setup-frame 0
```


# v0.16: fidelity-first baked visual exporter

The rig-style exporter can reconstruct the Python affine matrices numerically, but Spine still
has to interpret hundreds of independent transform timelines. v0.16 adds a second export mode
that bypasses that problem entirely.

Every visible SS6 part is converted to an unweighted mesh attached directly to the single
Spine `root` bone. The Python runtime's FINAL evaluated world vertices are baked into Spine
deform timelines.

This means the exported animation no longer depends on:

- SS6 hierarchy reconstruction
- bone rotation decomposition
- negative-scale interpolation
- shear interpolation
- 100+ animated Spine bones

Instead it is essentially:

```text
1 root bone
~30 visual slots
~30 baked mesh/deform timelines
```

## Recommended attack test

```powershell
py -m ss6runtime bundle-to-spine-baked bundle_unit_20080_bc.bin -o spine_baked_20080_attack --animation-name mot_attack_02 --setup-frame 0
```

## Recommended move test

```powershell
py -m ss6runtime bundle-to-spine-baked bundle_unit_20080_bc.bin -o spine_baked_20080_move --animation-name mot_move --setup-frame 0
```

## Exact 30 FPS sampled playback

If interpolation between SS6 samples still looks undesirable, use stepped deform/color keys:

```powershell
py -m ss6runtime bundle-to-spine-baked bundle_unit_20080_bc.bin -o spine_baked_20080_attack_stepped --animation-name mot_attack_02 --setup-frame 0 --stepped
```

This mode is intended first as a fidelity baseline. It is less editable as a character rig than
the bone-based exporter, but if its output visually matches the Python preview then we have
proved that the remaining discrepancy is in Spine transform reconstruction rather than the SS6
runtime evaluator itself.


# v0.17: per-frame baked attachment switching

v0.16 proved that the current Spine import/preview path is not applying the generated deform
timelines: once all motion depended only on deform, the character became completely static.

v0.17 therefore removes deform from the fidelity baseline entirely.

For each visual SS6 part and each sampled animation frame:

1. Python runtime evaluates the final world geometry.
2. That geometry is saved as a separate unweighted Spine mesh attachment.
3. A stepped Spine attachment timeline switches to the matching baked mesh at 30 FPS.

There are:

- no animated bones;
- no deform timelines;
- only one root bone;
- stepped attachment switching and optional slot-color/draw-order timelines.

This is intentionally larger on disk, but uses the simplest Spine animation feature that the
previous imports have already shown to work.

## Attack

```powershell
py -m ss6runtime bundle-to-spine-frame-swap bundle_unit_20080_bc.bin -o spine_frameswap_20080_attack --animation-name mot_attack_02 --setup-frame 0
```

## Move

```powershell
py -m ss6runtime bundle-to-spine-frame-swap bundle_unit_20080_bc.bin -o spine_frameswap_20080_move --animation-name mot_move --setup-frame 0
```

## Stand

```powershell
py -m ss6runtime bundle-to-spine-frame-swap bundle_unit_20080_bc.bin -o spine_frameswap_20080_stand --animation-name mot_stand --setup-frame 0
```

The exporter deduplicates identical sampled geometry by default. Disable this only for debugging:

```powershell
py -m ss6runtime bundle-to-spine-frame-swap bundle_unit_20080_bc.bin -o spine_frameswap_debug --animation-name mot_attack_02 --no-dedupe
```

If this mode animates correctly, then the SS6 evaluator, atlas mapping, and final geometry are
confirmed. We can then optimize back toward a compact Spine rig from this known-good baseline.


# v0.18: one-click export of all animations into one Spine project

v0.18 extends the proven v0.17 frame-swap baked-mesh exporter to the whole SS6 character.

It extracts the selected main `DataAnimation` once, evaluates every animation through the
Python runtime, and writes all animations into one Spine 4.2 JSON.

All animations share:

- one root bone;
- one slot set;
- one atlas;
- one texture directory;
- one default skin;
- cross-animation attachment deduplication.

## Basic usage

```powershell
py -m ss6runtime bundle-to-spine-frame-swap-all bundle_unit_20080_bc.bin -o spine_20080_all
```

The output contains:

```text
spine_20080_all/
  bundle_unit_20080_bc.json
  bundle_unit_20080_bc.atlas
  textures/
  spine_export_report.json
  _extracted/
```

Import the JSON into Spine. The animation list should contain `setup` plus all selected SS6
animations such as stand, move, attacks, damage, victory, etc.

## Choose the setup pose

By default the exporter prefers `mot_stand`, `stand`, `idle`, `mot_ready`, or `ready`.

To explicitly use `mot_stand` frame 0:

```powershell
py -m ss6runtime bundle-to-spine-frame-swap-all bundle_unit_20080_bc.bin -o spine_20080_all --setup-animation mot_stand --setup-frame 0
```

## Include only some animations

`--include` accepts a regular expression:

```powershell
py -m ss6runtime bundle-to-spine-frame-swap-all bundle_unit_20080_bc.bin -o spine_20080_combat --include "stand|move|attack|damage"
```

## Exclude animations

```powershell
py -m ss6runtime bundle-to-spine-frame-swap-all bundle_unit_20080_bc.bin -o spine_20080_no_victory --exclude "victory|effect"
```

You can combine include and exclude:

```powershell
py -m ss6runtime bundle-to-spine-frame-swap-all bundle_unit_20080_bc.bin -o spine_20080_filtered --include "mot_" --exclude "damage"
```

## Cross-animation dedupe

Identical geometry is reused across animations by default.

For debugging only, disable it with:

```powershell
py -m ss6runtime bundle-to-spine-frame-swap-all bundle_unit_20080_bc.bin -o spine_20080_all_nodedupe --no-dedupe
```

## Report

`spine_export_report.json` contains:

```text
setup_animation
setup_frame
animations_exported
animation_names
mesh_attachments
slots
animations[]
```

Each entry under `animations[]` reports frame count, FPS, duration, attachment timeline/key
counts, color keys, and draw-order keys.


# v0.19: preserve the final sampled frame

v0.18 placed the final sampled attachment key at:

```text
(frame_count - 1) / fps
```

Spine uses the time of the latest key to determine the animation duration. This meant the final
sampled pose had effectively zero display time before a looping animation jumped back to frame 0.

This is subtle for cyclic stand/move animations, but visible in one-shot animations such as
victory where the last hand/arm pose is distinct.

v0.19 adds a harmless root rotation duration marker:

```text
time = 0             angle = 0
time = frame_count/fps  angle = 0
```

It does not change the character geometry. It only makes the animation duration match the Python
preview, so the last sampled frame remains visible for one complete frame interval.

The normal all-animation command is unchanged:

```powershell
py -m ss6runtime bundle-to-spine-frame-swap-all bundle_unit_20080_bc.bin -o spine_20080_all_v19
```

To test victory only:

```powershell
py -m ss6runtime bundle-to-spine-frame-swap-all bundle_unit_20080_bc.bin -o spine_20080_victory_v19 --include "victory"
```

`spine_export_report.json` now reports the duration as:

```text
frame_count / fps
```

and includes `terminal_hold: true`.


# v0.20: fix terminal hold in the all-animation exporter

v0.19 correctly described the intended final-frame duration fix, but that patch only reached
the single-animation frame-swap exporter. The combined
`bundle-to-spine-frame-swap-all` implementation was still using:

```text
duration = (frame_count - 1) / fps
```

and did not add the final root duration marker.

v0.20 fixes the combined exporter itself.

For every exported animation:

```text
last attachment sample = (frame_count - 1) / fps
animation duration      = frame_count / fps
```

A no-op root rotation key is added at `frame_count/fps`, so the final sampled pose remains visible
for one full frame interval.

For example, a 40-frame 30 FPS victory animation now reports:

```text
duration = 1.333333
terminal_hold = true
```

instead of:

```text
duration = 1.3
```

Normal command:

```powershell
py -m ss6runtime bundle-to-spine-frame-swap-all bundle_unit_20080_bc.bin -o spine_20080_all_v20
```


# v0.21: frame-by-frame Spine geometry validator

v0.21 adds a validator specifically for the frame-swap exporter.

It compares, at every exact SS6 sample time:

```text
Python runtime final world geometry
vs
the Spine attachment selected by the exported attachment timeline
```

It verifies:

- visibility;
- active atlas region/cell;
- selected Spine attachment;
- vertex count;
- every exported vertex coordinate.

For a v0.20/v0.21 combined export directory:

```powershell
py -m ss6runtime validate-spine-frame-swap --spine-json spine_20080_all_v20\bundle_unit_20080_bc.json --spine-dir spine_20080_all_v20 --animation victory --part-filter "hand|arm" -o victory_validation
```

To inspect all parts:

```powershell
py -m ss6runtime validate-spine-frame-swap --spine-json spine_20080_all_v20\bundle_unit_20080_bc.json --spine-dir spine_20080_all_v20 --animation victory -o victory_validation_all
```

Outputs:

```text
victory_validation/
  validation_report.json
  part_summary.csv
  frame_details.csv
```

The most important fields are:

```text
max_vertex_error
visibility_mismatches
region_mismatches
worst
```

If all three mismatch measures are effectively zero, the exported sampled geometry is identical
to the Python runtime. In that case any remaining visual difference must come from playback
timing between samples, draw order, atlas rendering, or the external Spine previewer rather than
the SS6-to-geometry conversion.


# v0.22: fix one-frame attachment lag from timestamp rounding

The victory validator showed that frame 5 was still using the frame-4 hand attachment.

At 30 FPS:

```text
frame 5 exact time = 5 / 30 = 0.166666666...
old 6-digit key    = 0.166667
```

So an exact 30 FPS sample could occur just before the rounded key time.

v0.22 uses 9 decimal places consistently for all frame-swap timestamps and uses the same
timestamp function in the validator.

Re-export:

```powershell
py -m ss6runtime bundle-to-spine-frame-swap-all bundle_unit_20080_bc.bin -o spine_20080_all_v22
```

Validate the affected hand/arm parts:

```powershell
py -m ss6runtime validate-spine-frame-swap --spine-json spine_20080_all_v22\bundle_unit_20080_bc.json --spine-dir spine_20080_all_v22 --animation victory --part-filter "hand|arm" -o victory_validation_v22
```

The previous frame-5 region mismatch should disappear.


# v0.24: optimized v0.22 frame-swap export

v0.24 is deliberately based on v0.22, keeping the proven frame-swap behavior and adding output
compression/optimization only.

## 1. Stronger attachment deduplication

Deduplication now works across frames AND across animations. Vertex positions are quantized before
comparison, allowing visually negligible differences to reuse one attachment.

Default tolerance:

```text
0.0001 Spine units
```

Use a stricter tolerance:

```powershell
py -m ss6runtime bundle-to-spine-frame-swap-all bundle_unit_20080_bc.bin -o spine_v24_strict --dedupe-tolerance 0.00001
```

Use exact-ish dedupe:

```powershell
py -m ss6runtime bundle-to-spine-frame-swap-all bundle_unit_20080_bc.bin -o spine_v24_exact --dedupe-tolerance 0
```

Use more aggressive dedupe:

```powershell
py -m ss6runtime bundle-to-spine-frame-swap-all bundle_unit_20080_bc.bin -o spine_v24_small --dedupe-tolerance 0.001
```

`spine_export_report.json` reports `dedupe_hits`.

## 2. Sparse color timelines

Hidden parts are already controlled by attachment switching, so hidden frames no longer force
`color = alpha 0` keys.

If a slot is fully opaque whenever it is visible, no color timeline is emitted at all.

## 3. Sparse draw-order timelines

Changes caused only by currently hidden slots are ignored. A draw-order key is emitted only if
the ordering of visible parts actually changes.

## 4. Optional export frame rate / frame skipping

Original 30 FPS:

```powershell
py -m ss6runtime bundle-to-spine-frame-swap-all bundle_unit_20080_bc.bin -o spine_v24_30fps
```

15 FPS:

```powershell
py -m ss6runtime bundle-to-spine-frame-swap-all bundle_unit_20080_bc.bin -o spine_v24_15fps --export-fps 15
```

10 FPS:

```powershell
py -m ss6runtime bundle-to-spine-frame-swap-all bundle_unit_20080_bc.bin -o spine_v24_10fps --export-fps 10
```

Or explicitly keep every second source frame:

```powershell
py -m ss6runtime bundle-to-spine-frame-swap-all bundle_unit_20080_bc.bin -o spine_v24_step2 --frame-step 2
```

`--frame-step` takes precedence over `--export-fps`.

The animation duration remains the original SS6 duration; only the number of baked samples is
reduced.

## 5. Compact JSON

The Spine JSON itself is now written without indentation/extra whitespace. The human-readable
`spine_export_report.json` remains formatted.


# v0.25: desktop GUI

v0.25 adds a Tkinter desktop interface around the optimized v0.24 exporter.

No additional GUI framework is required: Tkinter ships with normal Windows Python installations.

## Start the GUI

Double-click:

```text
run_gui.bat
```

or run:

```powershell
py -m ss6runtime.gui
```

If dependencies are not installed yet, double-click:

```text
install_dependencies.bat
```

## GUI features

### Character bundle

- Browse for a bundle.
- Choose an output directory.
- Scan the bundle and list all animations.
- Automatically suggest stand/idle/ready as the setup animation when available.
- Open the output folder directly.

### Spine export

The GUI exposes the v0.24 optimized all-animation exporter:

- setup animation
- setup frame
- include / exclude regex
- geometry deduplication
- dedupe tolerance
- export FPS
- frame step
- mesh V flip
- hidden-part inclusion

The main button exports all selected animations into one Spine JSON.

### Python previews

The preview tab can render all or regex-filtered animations using the validated Python runtime:

- scale
- maximum frames
- optional GIF creation
- automatic Y-up framing

Outputs are written under:

```text
<output>\python_previews\
```

### Animations tab

After scanning, the GUI shows the animation list and selected DataAnimation metadata.

### Background execution

Extraction, exporting, and preview rendering run in worker threads so the UI remains responsive.
The bottom log panel displays reports and errors.

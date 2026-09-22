
from __future__ import annotations
from pathlib import Path
import json, csv, html, re, traceback
from typing import List, Dict, Optional

from .extractor import extract_bundle
from .preview import render_frame, render_animation

def _safe_name(s):
    s=re.sub(r'[<>:"/\\|?*]+',"_",str(s))
    return s.strip(" .") or "unnamed"

def _write_reports(rows, out_dir):
    out=Path(out_dir)
    # JSON
    (out/"batch_report.json").write_text(
        json.dumps(rows,ensure_ascii=False,indent=2),encoding="utf-8"
    )
    # CSV
    fields=[
        "bundle","status","character_dir","data_animation","selected_animation",
        "animation_count","part_count","texture_count","frame0","preview_gif","error"
    ]
    with open(out/"batch_report.csv","w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow({k:r.get(k,"") for k in fields})

    # Simple HTML gallery/report.
    cards=[]
    for r in rows:
        name=html.escape(str(r.get("bundle","")))
        status=html.escape(str(r.get("status","")))
        err=html.escape(str(r.get("error","") or ""))
        frame0=r.get("frame0")
        gif=r.get("preview_gif")
        img_html=""
        if frame0:
            rel=Path(frame0)
            try: rel=rel.relative_to(out)
            except: pass
            img_html+=f'<div><img src="{html.escape(rel.as_posix())}" loading="lazy"></div>'
        if gif:
            rel=Path(gif)
            try: rel=rel.relative_to(out)
            except: pass
            img_html+=f'<div><img src="{html.escape(rel.as_posix())}" loading="lazy"></div>'
        cards.append(f"""
        <section class="card">
          <h2>{name}</h2>
          <p><b>Status:</b> {status}</p>
          <p><b>DataAnimation:</b> {html.escape(str(r.get("data_animation","")))}</p>
          <p><b>Selected animation:</b> {html.escape(str(r.get("selected_animation","")))}</p>
          <p><b>Animations:</b> {html.escape(str(r.get("animation_count","")))}, <b>Parts:</b> {html.escape(str(r.get("part_count","")))}</p>
          {img_html}
          <pre>{err}</pre>
        </section>
        """)
    page=f"""<!doctype html>
<html><head><meta charset="utf-8"><title>SS6 Batch Report</title>
<style>
body{{font-family:Arial,sans-serif;background:#202124;color:#eee;margin:20px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(340px,1fr));gap:16px}}
.card{{background:#2b2d31;padding:14px;border-radius:10px}}
img{{max-width:100%;height:auto;background:#111;border-radius:6px;margin:6px 0}}
pre{{white-space:pre-wrap;color:#ffb4b4}}
</style></head><body><h1>SS6 Batch Test Report</h1><div class="grid">{''.join(cards)}</div></body></html>"""
    (out/"batch_report.html").write_text(page,encoding="utf-8")

def render_all_animations(bundle_path, output_dir, mode="native2d", coordinate_mode="yup",
                          scale=1.0, make_gif=True, max_frames=None,
                          animation_filter=None, data_animation=None,
                          png_compression=1,auto_frame=True,padding=16.0,
                          offset_x=0.0,offset_y=0.0):
    out=Path(output_dir)
    out.mkdir(parents=True,exist_ok=True)

    manifest=extract_bundle(
        bundle_path,out,
        data_animation=data_animation,
        all_animations=True
    )

    parts=out/"parts_raw.json"
    cellmap=out/"cellmap.json"
    textures=out/"textures"
    outputs=[]
    filt=re.compile(animation_filter,re.I) if animation_filter else None

    for item in manifest.get("all_animation_outputs",[]):
        if filt and not filt.search(item["name"]):
            continue
        raw=out/item["animation_raw"]
        anim_dir=out/item["dir"]
        preview_dir=anim_dir/"preview"
        try:
            rep=render_animation(
                parts,raw,cellmap,textures,preview_dir,
                mode=mode,coordinate_mode=coordinate_mode,scale=scale,
                make_gif=make_gif,max_frames=max_frames,
                png_compression=png_compression,auto_frame=auto_frame,padding=padding,
                offset_x=offset_x,offset_y=offset_y
            )
            outputs.append({
                "index":item["index"],"name":item["name"],
                "status":"ok","preview_dir":str(preview_dir),
                "gif":rep.get("gif"),"frames":rep.get("frames")
            })
        except Exception as e:
            outputs.append({
                "index":item["index"],"name":item["name"],
                "status":"error","error":str(e)
            })

    summary={
        "bundle":str(bundle_path),
        "data_animation":manifest.get("selected_data_animation"),
        "animation_count_total":len(manifest.get("available_animations",[])),
        "animation_count_rendered":len(outputs),
        "animations":outputs
    }
    (out/"all_animations_report.json").write_text(
        json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8"
    )

    # HTML gallery for all animations.
    cards=[]
    for a in outputs:
        gif=a.get("gif")
        ghtml=""
        if gif:
            gp=Path(gif)
            try: gp=gp.relative_to(out)
            except: pass
            ghtml=f'<img src="{html.escape(gp.as_posix())}" loading="lazy">'
        cards.append(f"""<section class="card"><h2>{a["index"]:02d} - {html.escape(a["name"])}</h2>
        <p>{html.escape(a.get("status",""))}</p>{ghtml}<pre>{html.escape(a.get("error","") or "")}</pre></section>""")
    page=f"""<!doctype html><html><head><meta charset="utf-8"><title>All animations</title>
<style>body{{font-family:Arial;background:#202124;color:#eee;margin:20px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:16px}}
.card{{background:#2b2d31;padding:12px;border-radius:10px}}
img{{max-width:100%;background:#111}}</style></head>
<body><h1>{html.escape(Path(bundle_path).name)} - All Animations</h1><div class="grid">{''.join(cards)}</div></body></html>"""
    (out/"all_animations_report.html").write_text(page,encoding="utf-8")
    return summary

def batch_test(input_dir, output_dir, pattern="*", mode="native2d", coordinate_mode="yup",
               scale=1.0, make_gif=True, max_frames=None, render_all=False,
               data_animation=None, png_compression=1,auto_frame=True,padding=16.0,
               offset_x=0.0,offset_y=0.0):
    inp=Path(input_dir)
    out=Path(output_dir)
    out.mkdir(parents=True,exist_ok=True)

    files=sorted([p for p in inp.glob(pattern) if p.is_file()])
    rows=[]

    for idx,bundle in enumerate(files):
        char_dir=out/f"{idx:03d}_{_safe_name(bundle.stem)}"
        row={
            "bundle":bundle.name,
            "status":"running",
            "character_dir":str(char_dir),
            "error":""
        }
        try:
            manifest=extract_bundle(
                bundle,char_dir,
                data_animation=data_animation,
                all_animations=render_all
            )
            row["data_animation"]=(manifest.get("selected_data_animation") or {}).get("name","")
            row["selected_animation"]=(manifest.get("selected_animation") or {}).get("name","")
            row["animation_count"]=len(manifest.get("available_animations",[]))
            row["part_count"]=manifest.get("part_count",0)
            row["texture_count"]=manifest.get("texture_count",0)

            frame0=char_dir/"frame0.png"
            render_frame(
                char_dir/"parts_raw.json",char_dir/"animation_raw.json",
                char_dir/"cellmap.json",char_dir/"textures",frame0,
                frame=0,mode=mode,coordinate_mode=coordinate_mode,
                scale=scale,png_compression=png_compression,auto_frame=auto_frame,
                padding=padding,offset_x=offset_x,offset_y=offset_y
            )
            row["frame0"]=str(frame0)

            selected_preview=char_dir/"selected_animation_preview"
            rep=render_animation(
                char_dir/"parts_raw.json",char_dir/"animation_raw.json",
                char_dir/"cellmap.json",char_dir/"textures",selected_preview,
                mode=mode,coordinate_mode=coordinate_mode,scale=scale,
                make_gif=make_gif,max_frames=max_frames,
                png_compression=png_compression,auto_frame=auto_frame,padding=padding,
                offset_x=offset_x,offset_y=offset_y
            )
            row["preview_gif"]=rep.get("gif") or ""

            if render_all:
                # Use already-extracted raw files instead of extracting bundle again.
                all_rows=[]
                for item in manifest.get("all_animation_outputs",[]):
                    raw=char_dir/item["animation_raw"]
                    adir=char_dir/item["dir"]/"preview"
                    try:
                        ar=render_animation(
                            char_dir/"parts_raw.json",raw,char_dir/"cellmap.json",
                            char_dir/"textures",adir,
                            mode=mode,coordinate_mode=coordinate_mode,scale=scale,
                            make_gif=make_gif,max_frames=max_frames,
                            png_compression=png_compression,auto_frame=auto_frame,padding=padding,
                            offset_x=offset_x,offset_y=offset_y
                        )
                        all_rows.append({"index":item["index"],"name":item["name"],"status":"ok","gif":ar.get("gif")})
                    except Exception as ae:
                        all_rows.append({"index":item["index"],"name":item["name"],"status":"error","error":str(ae)})
                (char_dir/"all_animations_report.json").write_text(
                    json.dumps(all_rows,ensure_ascii=False,indent=2),encoding="utf-8"
                )

            row["status"]="ok"
        except Exception as e:
            row["status"]="error"
            row["error"]=traceback.format_exc()

        rows.append(row)
        _write_reports(rows,out)

    return {"input_dir":str(inp),"output_dir":str(out),"bundles":len(files),
            "ok":sum(r["status"]=="ok" for r in rows),
            "errors":sum(r["status"]=="error" for r in rows),
            "report_html":str(out/"batch_report.html")}

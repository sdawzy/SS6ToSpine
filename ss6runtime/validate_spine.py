
from __future__ import annotations
from pathlib import Path
import json, re, csv, math
from typing import Any

from .runtime import Runtime
from .spine_export import _load, _parse_maps, _build_regions, _part_key_to_cell, _part_visible, _part_world_geometry, _frame_time

def _timeline_value_at(keys, t, field="name", default=None):
    """Spine attachment/color timelines are stepped in the frame-swap exporter."""
    value=default
    for k in keys or []:
        if float(k.get("time",0.0)) <= t + 1e-9:
            if field in k:
                value=k[field]
            elif field=="name":
                value=None
        else:
            break
    return value

def _slot_setup_map(doc):
    out={}
    for s in doc.get("slots",[]) or []:
        out[s["name"]]={
            "attachment":s.get("attachment"),
            "color":s.get("color","ffffffff")
        }
    return out

def _skin_attachment_map(doc):
    skins=doc.get("skins",[]) or []
    for skin in skins:
        if skin.get("name")=="default":
            return skin.get("attachments",{}) or {}
    if skins:
        return skins[0].get("attachments",{}) or {}
    return {}

def _alpha_from_hex(color):
    if not color:
        return 1.0
    color=str(color)
    if len(color)>=8:
        try:return int(color[-2:],16)/255.0
        except:return 1.0
    return 1.0

def _max_vertex_error(expected, actual):
    if expected is None or actual is None:
        return None
    if len(expected)!=len(actual):
        return math.inf
    if not expected:
        return 0.0
    return max(abs(float(a)-float(b)) for a,b in zip(expected,actual))

def _find_animation_raw_from_spine_dir(spine_dir, animation_name):
    spine_dir=Path(spine_dir)
    extracted=spine_dir/"_extracted"
    manifest_path=extracted/"extract_manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(
            f"Could not find {manifest_path}. Use explicit --parts-raw/--animation-raw/--cellmap instead."
        )
    manifest=json.load(open(manifest_path,"r",encoding="utf-8"))
    for item in manifest.get("all_animation_outputs",[]) or []:
        if str(item.get("name"))==str(animation_name):
            return (
                extracted/"parts_raw.json",
                extracted/item["animation_raw"],
                extracted/"cellmap.json"
            )
    raise RuntimeError(
        f"Animation {animation_name!r} not found in extract_manifest.json. "
        f"Available: {[x.get('name') for x in manifest.get('all_animation_outputs',[])]}"
    )

def validate_frame_swap(spine_json_path, animation_name,
                        parts_raw_path=None, animation_raw_path=None, cellmap_path=None,
                        spine_dir=None, part_filter=None, output_dir=None,
                        show_hidden=False):
    spine_json_path=Path(spine_json_path)
    doc=json.load(open(spine_json_path,"r",encoding="utf-8"))

    if spine_dir and (parts_raw_path is None or animation_raw_path is None or cellmap_path is None):
        parts_raw_path,animation_raw_path,cellmap_path=_find_animation_raw_from_spine_dir(spine_dir,animation_name)

    if not (parts_raw_path and animation_raw_path and cellmap_path):
        raise RuntimeError("Need either --spine-dir or explicit --parts-raw/--animation-raw/--cellmap.")

    rt=Runtime.from_files(parts_raw_path,animation_raw_path)
    maps=_parse_maps(_load(cellmap_path))
    regions=_build_regions(maps)

    anim=(doc.get("animations",{}) or {}).get(animation_name)
    if anim is None:
        raise RuntimeError(
            f"Animation {animation_name!r} not found in Spine JSON. "
            f"Available: {list((doc.get('animations',{}) or {}).keys())}"
        )

    setup_slots=_slot_setup_map(doc)
    skin_atts=_skin_attachment_map(doc)
    slot_tls=anim.get("slots",{}) or {}

    regex=re.compile(part_filter,re.I) if part_filter else None
    frames=[]
    per_part={}
    fps=float(max(rt.fps,1.0))

    for fi in range(int(rt.frame_count)):
        t=_frame_time(fi,fps)
        state=rt.evaluate_frame(fi,"native2d","zxy")
        by_name={str(p["name"]):p for p in state["parts"]}

        for slot_name,setup in setup_slots.items():
            if regex and not regex.search(slot_name):
                continue
            p=by_name.get(slot_name)
            if p is None:
                continue

            tl=slot_tls.get(slot_name,{}) or {}
            spine_attachment=_timeline_value_at(
                tl.get("attachment",[]),t,"name",setup.get("attachment")
            )
            spine_color=_timeline_value_at(
                tl.get("color",[]),t,"color",setup.get("color","ffffffff")
            )
            spine_visible=(spine_attachment is not None and _alpha_from_hex(spine_color)>0.001)

            cell_key=_part_key_to_cell(p)
            expected_visible=_part_visible(p,regions,show_hidden=show_hidden)
            expected_vertices=None
            expected_region=None
            if cell_key is not None and cell_key in regions and expected_visible:
                region_name,cell,_=regions[cell_key]
                expected_region=region_name
                expected_vertices,_,_=_part_world_geometry(p,cell,mesh_v_flip=False)

            actual_att=None
            actual_vertices=None
            actual_region=None
            if spine_attachment is not None:
                actual_att=(skin_atts.get(slot_name,{}) or {}).get(spine_attachment)
                if isinstance(actual_att,dict):
                    actual_vertices=actual_att.get("vertices")
                    actual_region=actual_att.get("path")

            err=_max_vertex_error(expected_vertices,actual_vertices) if (expected_visible and spine_visible) else None
            region_match=(expected_region==actual_region) if (expected_visible and spine_visible) else None
            visible_match=(bool(expected_visible)==bool(spine_visible))

            row={
                "frame":fi,
                "time":round(t,6),
                "part":slot_name,
                "expected_visible":bool(expected_visible),
                "spine_visible":bool(spine_visible),
                "visible_match":visible_match,
                "expected_region":expected_region,
                "spine_region":actual_region,
                "region_match":region_match,
                "spine_attachment":spine_attachment,
                "expected_vertex_count":(len(expected_vertices)//2 if expected_vertices else 0),
                "spine_vertex_count":(len(actual_vertices)//2 if actual_vertices else 0),
                "max_vertex_error":err,
            }
            frames.append(row)
            per_part.setdefault(slot_name,[]).append(row)

    summary_parts=[]
    for part,rows in per_part.items():
        finite=[r["max_vertex_error"] for r in rows if isinstance(r["max_vertex_error"],(int,float)) and math.isfinite(r["max_vertex_error"])]
        mism_vis=[r for r in rows if not r["visible_match"]]
        mism_reg=[r for r in rows if r["region_match"] is False]
        worst=None
        if finite:
            maxerr=max(finite)
            worst=next(r for r in rows if r["max_vertex_error"]==maxerr)
        else:
            maxerr=None
        summary_parts.append({
            "part":part,
            "max_vertex_error":maxerr,
            "worst_frame":worst["frame"] if worst else None,
            "visibility_mismatches":len(mism_vis),
            "region_mismatches":len(mism_reg),
            "frames_checked":len(rows)
        })

    def rank_key(x):
        e=x["max_vertex_error"]
        return (
            x["visibility_mismatches"]+x["region_mismatches"]>0,
            (e if isinstance(e,(int,float)) and math.isfinite(e) else -1.0)
        )
    summary_parts.sort(key=rank_key,reverse=True)

    max_global=0.0
    worst_global=None
    for r in frames:
        e=r["max_vertex_error"]
        if isinstance(e,(int,float)) and math.isfinite(e) and e>max_global:
            max_global=e
            worst_global=r

    report={
        "spine_json":str(spine_json_path),
        "animation":animation_name,
        "runtime_frames":int(rt.frame_count),
        "fps":float(rt.fps),
        "part_filter":part_filter,
        "max_vertex_error":max_global,
        "worst":worst_global,
        "visibility_mismatches":sum(1 for r in frames if not r["visible_match"]),
        "region_mismatches":sum(1 for r in frames if r["region_match"] is False),
        "parts":summary_parts,
        "diagnosis":(
            "Geometry/attachment selection matches Python runtime at sampled frames."
            if max_global<1e-5
               and not any(not r["visible_match"] for r in frames)
               and not any(r["region_match"] is False for r in frames)
            else
            "Mismatch detected. Inspect the worst frame/part rows."
        )
    }

    if output_dir:
        out=Path(output_dir)
        out.mkdir(parents=True,exist_ok=True)
        (out/"validation_report.json").write_text(
            json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8"
        )
        with open(out/"frame_details.csv","w",encoding="utf-8-sig",newline="") as f:
            fields=[
                "frame","time","part","expected_visible","spine_visible","visible_match",
                "expected_region","spine_region","region_match","spine_attachment",
                "expected_vertex_count","spine_vertex_count","max_vertex_error"
            ]
            w=csv.DictWriter(f,fieldnames=fields)
            w.writeheader()
            w.writerows(frames)
        with open(out/"part_summary.csv","w",encoding="utf-8-sig",newline="") as f:
            fields=["part","max_vertex_error","worst_frame","visibility_mismatches","region_mismatches","frames_checked"]
            w=csv.DictWriter(f,fieldnames=fields)
            w.writeheader()
            w.writerows(summary_parts)

    return report

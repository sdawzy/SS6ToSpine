
from __future__ import annotations
from pathlib import Path
import json, re
from typing import Any, Dict, List, Optional

def _plain(v):
    if isinstance(v,dict):
        return {str(k):_plain(x) for k,x in v.items()}
    if isinstance(v,(list,tuple)):
        return [_plain(x) for x in v]
    if hasattr(v,"path_id") or hasattr(v,"file_id"):
        return {"m_FileID":int(getattr(v,"file_id",0)),"m_PathID":int(getattr(v,"path_id",0))}
    if isinstance(v,(str,int,float,bool)) or v is None:
        return v
    try:return float(v)
    except Exception:return str(v)

def _safe(s):
    s=re.sub(r'[<>:"/\\|?*]+',"_",str(s))
    return s.strip(" .") or "unnamed"

def _script_name(obj,tree):
    try:
        data=obj.read()
        p=getattr(data,"m_Script",None)
        if p:
            s=p.read()
            for k in ("m_ClassName","m_Name","name"):
                v=getattr(s,k,None)
                if v:return str(v)
    except Exception:
        pass
    if isinstance(tree,dict):
        for k in ("m_ScriptName","m_ClassName","ScriptName","ClassName"):
            if tree.get(k):return str(tree[k])
    return ""

def _pid(v):
    if isinstance(v,dict):
        for k in ("m_PathID","path_id","PathID"):
            if k in v:
                try:return int(v[k])
                except:pass
    try:return int(getattr(v,"path_id",0))
    except:return 0

def _find_obj(env,pid):
    pid=int(pid)
    for o in env.objects:
        if int(o.path_id)==pid:return o
    return None

def _obj_name(obj):
    if obj is None:return ""
    try:
        d=obj.read()
        return str(getattr(d,"m_Name","") or getattr(d,"name","") or "")
    except:return ""

def _read_tree(obj):
    return _plain(obj.read_typetree())

def _load_ss6(bundle):
    import UnityPy
    env=UnityPy.load(str(bundle))
    entries=[]
    for o in env.objects:
        if o.type.name!="MonoBehaviour":continue
        try:t=_read_tree(o)
        except:continue
        script=_script_name(o,t)
        if "SpriteStudio6" not in script:continue
        entries.append({"obj":o,"path_id":int(o.path_id),"name":str(t.get("m_Name","") or ""),"script":script,"tree":t})
    if not entries:
        raise RuntimeError("No SpriteStudio6 MonoBehaviour found in bundle.")
    return env,entries

def _resolve_pptr(env,v):
    pid=_pid(v)
    if not pid:return None
    o=_find_obj(env,pid)
    return {"path_id":pid,"type":o.type.name if o else None,"name":_obj_name(o)} if o else {"path_id":pid,"type":None,"name":None}

def _root_candidates(env,entries):
    rows=[]
    for e in entries:
        if e["script"]!="Script_SpriteStudio6_Root":continue
        t=e["tree"]
        da=_resolve_pptr(env,t.get("DataAnimation"))
        dc=_resolve_pptr(env,t.get("DataCellMap"))
        control=len(t.get("TableControlParts",[]) or [])
        name=(da or {}).get("name") or ""
        score=control*100
        low=name.lower()
        if "_mot" in low:score+=50000
        if "effect" in low:score-=50000
        if "_sp_" in low or low.startswith("da_sp"):score-=5000
        rows.append({
            "entry":e,"score":score,"control_parts":control,
            "data_animation":da,"data_cellmap":dc,
            "table_information_play":t.get("TableInformationPlay",[]) or []
        })
    return sorted(rows,key=lambda x:x["score"],reverse=True)

def _find_animation_entry(entries,path_id=None,name=None):
    c=[e for e in entries if e["script"]=="Script_SpriteStudio6_DataAnimation"]
    if path_id:
        for e in c:
            if e["path_id"]==int(path_id):return e
    if name:
        for e in c:
            if e["name"]==name:return e
    return None

def _find_cellmap_entry(entries,path_id=None,name=None):
    c=[e for e in entries if e["script"]=="Script_SpriteStudio6_DataCellMap"]
    if path_id:
        for e in c:
            if e["path_id"]==int(path_id):return e
    if name:
        for e in c:
            if e["name"]==name:return e
    return None

def _fallback_animation(entries):
    c=[e for e in entries if e["script"]=="Script_SpriteStudio6_DataAnimation"]
    if not c:raise RuntimeError("No SS6 DataAnimation found.")
    def score(e):
        t=e["tree"]; name=e["name"].lower()
        s=len(t.get("TableParts",[]) or [])*100+len(t.get("TableAnimation",[]) or [])
        if "_mot" in name:s+=50000
        if "effect" in name:s-=50000
        if "_sp_" in name or name.startswith("da_sp"):s-=5000
        return s
    return max(c,key=score)

def _fallback_cellmap(entries):
    c=[e for e in entries if e["script"]=="Script_SpriteStudio6_DataCellMap"]
    if not c:raise RuntimeError("No SS6 DataCellMap found.")
    return max(c,key=lambda e:len(e["tree"].get("TableCellMap",[]) or []))

def _anim_name(a,i):
    if isinstance(a,dict):
        return str(a.get("Name",a.get("NameAnimation",f"animation_{i}")))
    return f"animation_{i}"

def _select_animation(tree,name=None,index=None,preferred=None):
    arr=tree.get("TableAnimation",[]) or []
    if not arr:raise RuntimeError("Selected DataAnimation has no TableAnimation.")
    if index is not None:
        if index<0 or index>=len(arr):raise RuntimeError(f"Animation index out of range: {index}; count={len(arr)}")
        return int(index),arr[int(index)]
    if name:
        for i,a in enumerate(arr):
            if _anim_name(a,i)==name:return i,a
        raise RuntimeError(f"Animation not found: {name}; available={[ _anim_name(a,i) for i,a in enumerate(arr) ]}")
    if preferred:
        for i,a in enumerate(arr):
            if _anim_name(a,i)==preferred:return i,a
    # Prefer stand/idle/ready for cross-character testing when present, otherwise first.
    names=[_anim_name(a,i) for i,a in enumerate(arr)]
    for key in ("mot_stand","stand","idle","mot_ready","ready","mot_action_01"):
        for i,n in enumerate(names):
            if n.lower()==key:return i,arr[i]
    return 0,arr[0]

def _parse_initial_animation(root_tree):
    info=root_tree.get("TableInformationPlay",[]) or []
    for row in info:
        if not isinstance(row,dict):continue
        for k in ("NameAnimation","AnimationName","Name"):
            v=row.get(k)
            if isinstance(v,str) and v:return v
    return None

def _texture_export(env,out_dir):
    out=Path(out_dir);out.mkdir(parents=True,exist_ok=True)
    rows=[]
    used={}
    for o in env.objects:
        if o.type.name!="Texture2D":continue
        try:
            tex=o.read()
            name=str(getattr(tex,"m_Name","") or getattr(tex,"name","") or f"texture_{o.path_id}")
            base=_safe(name)
            fn=base+".png"
            if fn.lower() in used:
                fn=f"{base}_{o.path_id}.png"
            used[fn.lower()]=1
            img=tex.image
            img.save(out/fn)
            rows.append({"path_id":int(o.path_id),"name":name,"file":fn,"width":img.width,"height":img.height})
        except Exception as ex:
            rows.append({"path_id":int(o.path_id),"error":str(ex)})
    return rows

def _resolve_texture_file(texture_ref,texture_manifest):
    pid=_pid(texture_ref)
    if pid:
        for t in texture_manifest:
            if t.get("path_id")==pid and t.get("file"):return t["file"]
    return None

def _parse_cellmaps(tree,texture_manifest):
    maps=[]
    for mi,cm in enumerate(tree.get("TableCellMap",[]) or []):
        if not isinstance(cm,dict):continue
        texref=cm.get("Texture",cm.get("Texture2D",cm.get("DataTexture",{})))
        texfile=_resolve_texture_file(texref,texture_manifest)
        cells=[]
        for ci,c in enumerate(cm.get("TableCell",[]) or []):
            if not isinstance(c,dict):continue
            rect=c.get("Rectangle",{}) or {}
            pivot=c.get("Pivot",{}) or {}
            mesh=c.get("Mesh",{}) or {}
            name=str(c.get("Name",f"cell_{mi}_{ci}"))
            cells.append({
                "index":ci,
                "name":name,
                "plain_name":re.sub(r"\[[^\]]+\]$","",name),
                "x":float(rect.get("x",0)),"y":float(rect.get("y",0)),
                "width":float(rect.get("width",0)),"height":float(rect.get("height",0)),
                "pivot":{"x":float(pivot.get("x",0)),"y":float(pivot.get("y",0))},
                "mesh":{
                    "coordinates":_plain(mesh.get("TableCoordinate",mesh.get("TableVertex",[])) or []),
                    "indices":_plain(mesh.get("TableIndexVertex",[]) or [])
                }
            })
        maps.append({
            "index":mi,
            "name":str(cm.get("Name",f"cellmap_{mi}")),
            "size":_plain(cm.get("SizeOriginal",cm.get("SizeTexture",{}))),
            "texture_ref":_plain(texref),
            "texture_file":texfile,
            "cells":cells
        })
    return maps

def extract_bundle(bundle_path,out_dir,animation_name=None,animation_index=None,data_animation=None,root_path_id=None,all_animations=False):
    out=Path(out_dir);out.mkdir(parents=True,exist_ok=True)
    env,entries=_load_ss6(bundle_path)
    roots=_root_candidates(env,entries)

    selected_root=None
    if root_path_id is not None:
        for r in roots:
            if r["entry"]["path_id"]==int(root_path_id):selected_root=r;break
        if selected_root is None:raise RuntimeError(f"SS6 Root path id not found: {root_path_id}")
    elif data_animation:
        for r in roots:
            if (r.get("data_animation") or {}).get("name")==data_animation:
                selected_root=r;break
    elif roots:
        selected_root=roots[0]

    da=None;dc=None
    if selected_root:
        dainfo=selected_root.get("data_animation") or {}
        dcinfo=selected_root.get("data_cellmap") or {}
        da=_find_animation_entry(entries,dainfo.get("path_id"),data_animation or dainfo.get("name"))
        dc=_find_cellmap_entry(entries,dcinfo.get("path_id"),dcinfo.get("name"))
    if da is None:
        if data_animation:
            da=_find_animation_entry(entries,name=data_animation)
            if da is None:raise RuntimeError(f"DataAnimation not found: {data_animation}")
        else:
            da=_fallback_animation(entries)
    if dc is None:dc=_fallback_cellmap(entries)

    preferred=_parse_initial_animation(selected_root["entry"]["tree"]) if selected_root else None
    ai,a=_select_animation(da["tree"],animation_name,animation_index,preferred)
    aname=_anim_name(a,ai)

    textures=_texture_export(env,out/"textures")
    maps=_parse_cellmaps(dc["tree"],textures)

    parts_payload={
        "source":{"path_id":da["path_id"],"name":da["name"],"script":da["script"],"version":da["tree"].get("Version")},
        "CatalogParts":_plain(da["tree"].get("CatalogParts",{})),
        "TableParts":_plain(da["tree"].get("TableParts",[])),
        "TableAnimationPartsSetup":_plain(da["tree"].get("TableAnimationPartsSetup",[]))
    }
    (out/"parts_raw.json").write_text(json.dumps(parts_payload,ensure_ascii=False,indent=2),encoding="utf-8")
    (out/"animation_raw.json").write_text(json.dumps(_plain(a),ensure_ascii=False,indent=2),encoding="utf-8")

    all_animation_outputs=[]
    if all_animations:
        adir=out/"animations"
        adir.mkdir(parents=True,exist_ok=True)
        for j,aa in enumerate(da["tree"].get("TableAnimation",[]) or []):
            nm=_anim_name(aa,j)
            safe_nm=_safe(nm)
            sub=adir/f"{j:02d}_{safe_nm}"
            sub.mkdir(parents=True,exist_ok=True)
            raw_path=sub/"animation_raw.json"
            raw_path.write_text(json.dumps(_plain(aa),ensure_ascii=False,indent=2),encoding="utf-8")
            all_animation_outputs.append({
                "index":j,
                "name":nm,
                "dir":str(sub.relative_to(out)),
                "animation_raw":str(raw_path.relative_to(out))
            })

    (out/"cellmap.json").write_text(json.dumps({
        "source":{"path_id":dc["path_id"],"name":dc["name"],"script":dc["script"]},
        "maps":maps
    },ensure_ascii=False,indent=2),encoding="utf-8")

    available=[{"index":i,"name":_anim_name(x,i)} for i,x in enumerate(da["tree"].get("TableAnimation",[]) or [])]
    manifest={
        "bundle":str(bundle_path),
        "selected_root":{
            "path_id":selected_root["entry"]["path_id"],
            "control_parts":selected_root["control_parts"],
            "data_animation":selected_root.get("data_animation"),
            "data_cellmap":selected_root.get("data_cellmap")
        } if selected_root else None,
        "selected_data_animation":{"path_id":da["path_id"],"name":da["name"],"version":da["tree"].get("Version")},
        "selected_data_cellmap":{"path_id":dc["path_id"],"name":dc["name"]},
        "selected_animation":{"index":ai,"name":aname},
        "available_animations":available,
        "all_animation_outputs":all_animation_outputs,
        "part_count":len(da["tree"].get("TableParts",[]) or []),
        "cellmap_count":len(maps),
        "texture_count":len([x for x in textures if x.get("file")]),
        "textures":textures,
        "root_candidates":[{
            "path_id":r["entry"]["path_id"],
            "score":r["score"],
            "control_parts":r["control_parts"],
            "data_animation":r.get("data_animation"),
            "data_cellmap":r.get("data_cellmap")
        } for r in roots]
    }
    (out/"extract_manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8")
    return manifest


from __future__ import annotations
from dataclasses import dataclass, asdict
from pathlib import Path
import json, math
from typing import Any, Dict, List, Tuple, Optional

MASK_FRAME = 0x7FFF

def load_json(path):
    return json.load(open(path, "r", encoding="utf-8"))

def flatten_codes(container: dict) -> List[int]:
    out=[]
    for g in (container or {}).get("TableCodeValue", []) or []:
        if isinstance(g, dict):
            out.extend(int(x) for x in (g.get("TableCode",[]) or []))
    return out

def decode_events(container: dict, frame_count: Optional[int]=None):
    """
    SS6 CPE-style packed key table.
    Observed encoding in this asset:
        low 15 bits  -> frame number
        upper bits   -> TableValue index
    A trailing code whose frame is the valid-end sentinel and which does not
    reference a new value is ignored.
    """
    if not isinstance(container, dict):
        return []
    values = container.get("TableValue", []) or []
    if not values:
        return []

    codes = flatten_codes(container)
    if not codes:
        return [(0, values[0])] if len(values)==1 else list(enumerate(values))

    events=[]
    for seq_i, code in enumerate(codes):
        frame = int(code) & MASK_FRAME
        value_index = int(code) >> 15

        # Sentinels commonly appear as a final raw frame number, eg 13.
        if frame_count is not None and frame >= frame_count:
            continue

        if 0 <= value_index < len(values):
            value = values[value_index]
        elif seq_i < len(values):
            # fallback for unusual packing
            value = values[seq_i]
        else:
            continue
        events.append((frame, value))

    # Keep last value for duplicate frame records.
    merged={}
    for f,v in events:
        merged[int(f)] = v
    return sorted(merged.items())

def sample_hold(events, frame, default):
    if not events:
        return default
    cur=events[0][1]
    for f,v in events:
        if f > frame:
            break
        cur=v
    return cur

# ---------- matrix helpers ----------
# 2D affine = (a,b,c,d,tx,ty), mapping:
# x' = a*x + b*y + tx
# y' = c*x + d*y + ty

def a_identity():
    return (1.0,0.0,0.0,1.0,0.0,0.0)

def a_mul(P,L):
    a,b,c,d,tx,ty=P
    e,f,g,h,ux,uy=L
    return (
        a*e+b*g, a*f+b*h,
        c*e+d*g, c*f+d*h,
        a*ux+b*uy+tx, c*ux+d*uy+ty
    )

def a_local(x,y,rz_deg,sx,sy):
    r=math.radians(rz_deg)
    co,si=math.cos(r),math.sin(r)
    return (co*sx,-si*sy,si*sx,co*sy,x,y)

def a_point(M,p):
    a,b,c,d,tx,ty=M
    x,y=p
    return (a*x+b*y+tx,c*x+d*y+ty)

def a_decompose(M):
    a,b,c,d,tx,ty=M
    sx=math.hypot(a,c)
    if sx < 1e-12:
        sx=1e-12
    det=a*d-b*c
    sy=det/sx
    rot=math.degrees(math.atan2(c,a))
    return {"x":tx,"y":ty,"rotation":rot,"scale_x":sx,"scale_y":sy}

def m4_identity():
    return [[1.,0.,0.,0.],[0.,1.,0.,0.],[0.,0.,1.,0.],[0.,0.,0.,1.]]

def m4_mul(A,B):
    return [[sum(A[i][k]*B[k][j] for k in range(4)) for j in range(4)] for i in range(4)]

def m4_t(x,y,z):
    M=m4_identity();M[0][3]=x;M[1][3]=y;M[2][3]=z;return M
def m4_s(x,y,z):
    M=m4_identity();M[0][0]=x;M[1][1]=y;M[2][2]=z;return M
def m4_rx(r):
    c,s=math.cos(r),math.sin(r)
    return [[1,0,0,0],[0,c,-s,0],[0,s,c,0],[0,0,0,1]]
def m4_ry(r):
    c,s=math.cos(r),math.sin(r)
    return [[c,0,s,0],[0,1,0,0],[-s,0,c,0],[0,0,0,1]]
def m4_rz(r):
    c,s=math.cos(r),math.sin(r)
    return [[c,-s,0,0],[s,c,0,0],[0,0,1,0],[0,0,0,1]]

def m4_euler(x,y,z,order="zxy"):
    R=m4_identity()
    funcs={"x":m4_rx,"y":m4_ry,"z":m4_rz}
    vals={"x":math.radians(x),"y":math.radians(y),"z":math.radians(z)}
    # listed order is application order
    for axis in order:
        R=m4_mul(funcs[axis](vals[axis]), R)
    return R

def m4_local(pos,rot,scale,order="zxy"):
    return m4_mul(
        m4_t(float(pos.get("x",0)),float(pos.get("y",0)),float(pos.get("z",0))),
        m4_mul(
            m4_euler(float(rot.get("x",0)),float(rot.get("y",0)),float(rot.get("z",0)),order),
            m4_s(float(scale.get("x",1)),float(scale.get("y",1)),1.0)
        )
    )

def m4_point(M,p):
    x,y,z=p
    v=[x,y,z,1.0]
    q=[sum(M[i][j]*v[j] for j in range(4)) for i in range(4)]
    return (q[0],q[1],q[2])

def m4_project_xy(M):
    return (M[0][0],M[0][1],M[1][0],M[1][1],M[0][3],M[1][3])

class Runtime:
    def __init__(self, parts_raw: dict, animation_raw: dict):
        self.parts_raw=parts_raw
        self.animation_raw=animation_raw
        self.parts=parts_raw.get("TableParts",[]) or []
        self.catalog=parts_raw.get("CatalogParts",{}) or {}
        self.anim_parts=animation_raw.get("TableParts",[]) or []
        self.frame_count=int(animation_raw.get("CountFrame", animation_raw.get("CountFrameValid", 1)) or 1)
        self.fps=float(animation_raw.get("FramePerSecond",30) or 30)

        self.id_to_index={}
        self.name_to_index={}
        for i,p in enumerate(self.parts):
            pid=int(p.get("ID",i))
            self.id_to_index[pid]=i
            self.name_to_index[str(p.get("Name",f"part_{i}"))]=i

        self.bone_catalog=[int(x) for x in (self.catalog.get("TableIDPartsBone",[]) or [])]

        self.tracks=[]
        attrs=[
            "Status","Cell","Position","Rotation","Scaling","ScalingLocal",
            "RateOpacity","Priority","PartsColor","VertexCorrection","OffsetPivot",
            "PositionAnchor","SizeForce","PositionTexture","RotationTexture",
            "ScalingTexture","RadiusCollision","UserData","Instance","Effect","Deform"
        ]
        for i in range(len(self.parts)):
            ap=self.anim_parts[i] if i<len(self.anim_parts) else {}
            self.tracks.append({
                a:decode_events(ap.get(a,{}), self.frame_count)
                for a in attrs
            })

    @classmethod
    def from_files(cls, parts_raw_path, animation_raw_path):
        return cls(load_json(parts_raw_path),load_json(animation_raw_path))

    def state(self,i,frame):
        t=self.tracks[i]
        p=self.parts[i]
        status=sample_hold(t["Status"],frame,{"Flags":0})
        flags=int(status.get("Flags",0)) if isinstance(status,dict) else 0
        return {
            "index":i,
            "id":int(p.get("ID",i)),
            "name":p.get("Name",f"part_{i}"),
            "parent_id":int(p.get("IDParent",-1)),
            "feature":int(p.get("Feature",0)),
            "status":status,
            "status_flags":flags,
            "hidden_provisional":bool(flags & 0x20000000),
            "cell":sample_hold(t["Cell"],frame,None),
            "position":sample_hold(t["Position"],frame,{"x":0.0,"y":0.0,"z":0.0}),
            "rotation":sample_hold(t["Rotation"],frame,{"x":0.0,"y":0.0,"z":0.0}),
            "scaling":sample_hold(t["Scaling"],frame,{"x":1.0,"y":1.0}),
            "scaling_local":sample_hold(t["ScalingLocal"],frame,{"x":1.0,"y":1.0}),
            "opacity":sample_hold(t["RateOpacity"],frame,1.0),
            "priority":sample_hold(t["Priority"],frame,0),
            "offset_pivot":sample_hold(t["OffsetPivot"],frame,{"x":0.0,"y":0.0}),
            "position_anchor":sample_hold(t["PositionAnchor"],frame,{"x":0.0,"y":0.0}),
            "size_force":sample_hold(t["SizeForce"],frame,{"x":0.0,"y":0.0}),
        }

    def _local_native2d(self,s):
        p=s["position"];r=s["rotation"];sc=s["scaling"]
        sx=float(sc.get("x",1));sy=float(sc.get("y",1))
        # In SpriteStudio animation space, X/Y rotations of 180 degrees act as flips
        # after planarization. Crucially, we leave animation-space Y and Z sign native.
        rx=float(r.get("x",0));ry=float(r.get("y",0))
        if abs((rx % 360.0)-180.0)<1e-4: sy=-sy
        if abs((ry % 360.0)-180.0)<1e-4: sx=-sx
        return a_local(float(p.get("x",0)),float(p.get("y",0)),float(r.get("z",0)),sx,sy)

    def evaluate_frame(self,frame,mode="native2d",euler_order="zxy"):
        frame=max(0,min(int(frame),self.frame_count-1))
        states=[self.state(i,frame) for i in range(len(self.parts))]
        world={}
        visiting=set()

        if mode in ("native2d","flat2d"):
            def solve2(i):
                if i in world:return world[i]
                if i in visiting:return a_identity()
                visiting.add(i)
                L=self._local_native2d(states[i])
                pid=states[i]["parent_id"]
                if mode=="flat2d" or pid not in self.id_to_index:
                    W=L
                else:
                    W=a_mul(solve2(self.id_to_index[pid]),L)
                visiting.remove(i);world[i]=W
                return W
            for i in range(len(states)):solve2(i)

        elif mode in ("unity3d","flat3d"):
            def solve3(i):
                if i in world:return world[i]
                if i in visiting:return m4_identity()
                visiting.add(i)
                s=states[i]
                L=m4_local(s["position"],s["rotation"],s["scaling"],euler_order)
                pid=s["parent_id"]
                if mode=="flat3d" or pid not in self.id_to_index:
                    W=L
                else:
                    W=m4_mul(solve3(self.id_to_index[pid]),L)
                visiting.remove(i);world[i]=W
                return W
            for i in range(len(states)):solve3(i)
        else:
            raise ValueError("mode must be native2d, flat2d, unity3d, or flat3d")

        out_parts=[]
        for i,s in enumerate(states):
            row=dict(s)
            if mode.endswith("2d"):
                row["world_affine"]=list(world[i])
                row["world"]=a_decompose(world[i])
            else:
                row["world_matrix4"]=world[i]
                row["world"]=a_decompose(m4_project_xy(world[i]))

            # weighted mesh evaluation
            mesh=self.parts[i].get("Mesh",{}) or {}
            table_vertex=mesh.get("TableVertex",[]) or []
            if int(s["feature"])==11 and table_vertex:
                verts=[]
                for vi,v in enumerate(table_vertex):
                    accum=[0.0,0.0,0.0]
                    weight_sum=0.0
                    refs=[]
                    for bw in (v.get("TableBone",[]) or []):
                        bi=int(bw.get("Index",-1))
                        w=float(bw.get("Weight",0.0))
                        off=bw.get("CoordinateOffset",{}) or {}
                        if bi<0 or bi>=len(self.bone_catalog):
                            continue
                        part_id=self.bone_catalog[bi]
                        if part_id not in self.id_to_index:
                            continue
                        pi=self.id_to_index[part_id]
                        if mode.endswith("2d"):
                            q=a_point(world[pi],(float(off.get("x",0)),float(off.get("y",0))))
                            q=(q[0],q[1],float(off.get("z",0)))
                        else:
                            q=m4_point(world[pi],(float(off.get("x",0)),float(off.get("y",0)),float(off.get("z",0))))
                        accum[0]+=w*q[0];accum[1]+=w*q[1];accum[2]+=w*q[2]
                        weight_sum+=w
                        refs.append({"bone_catalog_index":bi,"part_id":part_id,
                                     "part_name":self.parts[pi].get("Name"),"weight":w})
                    verts.append({
                        "index":vi,
                        "x":accum[0],"y":accum[1],"z":accum[2],
                        "weight_sum":weight_sum,
                        "bones":refs
                    })
                row["skinned_mesh"]={
                    "vertices":verts,
                    "uv":mesh.get("TableRateUV",[]) or [],
                    "triangles":mesh.get("TableIndexVertex",[]) or [],
                    "count_vertex_deform":mesh.get("CountVertexDeform",0)
                }
            out_parts.append(row)

        return {
            "animation":self.animation_raw.get("Name","animation"),
            "frame":frame,
            "time":frame/self.fps,
            "fps":self.fps,
            "frame_count":self.frame_count,
            "mode":mode,
            "euler_order":euler_order if "3d" in mode else None,
            "parts":out_parts
        }

    def dump_frames(self,out_path,mode="native2d",euler_order="zxy",frames=None):
        if frames is None:
            frames=range(self.frame_count)
        doc={
            "runtime":"ss6python_runtime_v01",
            "mode":mode,
            "euler_order":euler_order if "3d" in mode else None,
            "animation":self.animation_raw.get("Name","animation"),
            "fps":self.fps,
            "frame_count":self.frame_count,
            "frames":[self.evaluate_frame(f,mode,euler_order) for f in frames]
        }
        Path(out_path).write_text(json.dumps(doc,ensure_ascii=False,indent=2),encoding="utf-8")
        return doc

def inspect_runtime(rt: Runtime):
    features={}
    for p in rt.parts:
        f=int(p.get("Feature",0));features[f]=features.get(f,0)+1
    track_counts={}
    for attr in rt.tracks[0].keys() if rt.tracks else []:
        track_counts[attr]=sum(1 for t in rt.tracks if t[attr])
    weighted=[]
    for i,p in enumerate(rt.parts):
        mesh=p.get("Mesh",{}) or {}
        if int(p.get("Feature",0))==11:
            weighted.append({
                "index":i,"name":p.get("Name"),
                "vertices":len(mesh.get("TableVertex",[]) or []),
                "triangles":len(mesh.get("TableIndexVertex",[]) or [])//3
            })
    return {
        "animation":rt.animation_raw.get("Name"),
        "fps":rt.fps,
        "frame_count":rt.frame_count,
        "parts":len(rt.parts),
        "features":features,
        "track_counts":track_counts,
        "bone_catalog_size":len(rt.bone_catalog),
        "weighted_mesh_parts":weighted
    }


from __future__ import annotations
from pathlib import Path
import json, math
import numpy as np
import cv2
from PIL import Image, ImageDraw
from .runtime import Runtime

def _load(path):
    return json.load(open(path,"r",encoding="utf-8"))

def _maps_from_cellmap(doc):
    if isinstance(doc,dict) and isinstance(doc.get("maps"),list):
        return doc["maps"]
    raw=doc.get("TableCellMap",[]) if isinstance(doc,dict) else []
    maps=[]
    for mi,cm in enumerate(raw or []):
        cells=[]
        for ci,c in enumerate((cm or {}).get("TableCell",[]) or []):
            rect=(c or {}).get("Rectangle",{}) or {}
            pivot=(c or {}).get("Pivot",{}) or {}
            mesh=(c or {}).get("Mesh",{}) or {}
            cells.append({
                "index":ci,
                "name":(c or {}).get("Name",f"cell_{mi}_{ci}"),
                "plain_name":(c or {}).get("Name",f"cell_{mi}_{ci}").split("[")[0],
                "x":float(rect.get("x",0)),
                "y":float(rect.get("y",0)),
                "width":float(rect.get("width",0)),
                "height":float(rect.get("height",0)),
                "pivot":{"x":float(pivot.get("x",0)),"y":float(pivot.get("y",0))},
                "mesh":{
                    "coordinates":mesh.get("TableCoordinate",[]) or [],
                    "indices":mesh.get("TableIndexVertex",[]) or []
                }
            })
        maps.append({"index":mi,"name":cm.get("Name",f"cellmap_{mi}"),"cells":cells})
    return maps

def _texture_candidates(texture_dir):
    return sorted([p for p in Path(texture_dir).glob("*.png") if p.is_file()])

def _choose_textures(maps,texture_dir,explicit=None):
    explicit=explicit or {}
    pngs=_texture_candidates(texture_dir)
    if not pngs:
        raise FileNotFoundError(f"No PNG textures found in: {texture_dir}")
    out={}
    for mi,m in enumerate(maps):
        if mi in explicit and explicit[mi]:
            p=Path(explicit[mi])
            if not p.exists(): raise FileNotFoundError(p)
            out[mi]=p; continue
        tf=m.get("texture_file") if isinstance(m,dict) else None
        if tf:
            p=Path(texture_dir)/tf
            if p.exists():
                out[mi]=p; continue
        hits=[p for p in pngs if p.stem.endswith(f"_{mi}")]
        if not hits:
            nm=str(m.get("name","")).lower()
            hits=[p for p in pngs if nm and nm in p.stem.lower()]
        if not hits and mi<len(pngs): hits=[pngs[mi]]
        if not hits: raise RuntimeError(f"Could not choose texture for cellmap {mi}")
        out[mi]=hits[0]
    return out

def _read_rgba(path):
    im=cv2.imread(str(path),cv2.IMREAD_UNCHANGED)
    if im is None: raise RuntimeError(f"Failed to read image: {path}")
    if im.ndim==2: im=cv2.cvtColor(im,cv2.COLOR_GRAY2BGRA)
    elif im.shape[2]==3: im=cv2.cvtColor(im,cv2.COLOR_BGR2BGRA)
    return im

def _alpha_over_roi(dst_roi,src_roi):
    sa=src_roi[:,:,3:4].astype(np.float32)/255.0
    if not np.any(sa>0): return
    da=dst_roi[:,:,3:4].astype(np.float32)/255.0
    outa=sa+da*(1-sa)
    srgb=src_roi[:,:,:3].astype(np.float32)
    drgb=dst_roi[:,:,:3].astype(np.float32)
    denom=np.maximum(outa,1e-8)
    outrgb=(srgb*sa+drgb*da*(1-sa))/denom
    dst_roi[:,:,:3]=np.clip(outrgb,0,255).astype(np.uint8)
    dst_roi[:,:,3]=np.clip(outa[:,:,0]*255,0,255).astype(np.uint8)

def _warp_triangle_roi(canvas,atlas,src_tri,dst_tri,opacity=1.0):
    src=np.asarray(src_tri,dtype=np.float32)
    dst=np.asarray(dst_tri,dtype=np.float32)
    H,W=canvas.shape[:2]

    # Destination bounding box, clipped to canvas.
    minx=max(0,int(math.floor(float(dst[:,0].min())))-1)
    maxx=min(W,int(math.ceil(float(dst[:,0].max())))+2)
    miny=max(0,int(math.floor(float(dst[:,1].min())))-1)
    maxy=min(H,int(math.ceil(float(dst[:,1].max())))+2)
    if maxx<=minx or maxy<=miny:
        return

    # Translate destination triangle into ROI-local coordinates.
    dlocal=dst.copy()
    dlocal[:,0]-=minx
    dlocal[:,1]-=miny

    M=cv2.getAffineTransform(src,dlocal)
    rw,rh=maxx-minx,maxy-miny
    warped=cv2.warpAffine(
        atlas,M,(rw,rh),
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(0,0,0,0)
    )

    mask=np.zeros((rh,rw),dtype=np.uint8)
    cv2.fillConvexPoly(mask,np.round(dlocal).astype(np.int32),255)
    alpha=warped[:,:,3].astype(np.float32)
    alpha*=mask.astype(np.float32)/255.0
    if opacity!=1.0: alpha*=float(opacity)
    warped[:,:,3]=np.clip(alpha,0,255).astype(np.uint8)

    roi=canvas[miny:maxy,minx:maxx]
    _alpha_over_roi(roi,warped)

def _cell_lookup(maps):
    out={}
    for mi,m in enumerate(maps):
        for ci,c in enumerate(m.get("cells",[]) or []):
            out[(mi,ci)]=c
    return out

def _world_point(part,x,y):
    if "world_affine" in part:
        a,b,c,d,tx,ty=part["world_affine"]
        return (a*x+b*y+tx,c*x+d*y+ty)
    w=part.get("world",{})
    r=math.radians(float(w.get("rotation",0)))
    sx=float(w.get("scale_x",1));sy=float(w.get("scale_y",1))
    co,si=math.cos(r),math.sin(r)
    return (float(w.get("x",0))+co*sx*x-si*sy*y,
            float(w.get("y",0))+si*sx*x+co*sy*y)

def _to_canvas(pt,cx,cy,coordinate_mode="yup"):
    x,y=pt
    return (cx+x,cy-y if coordinate_mode=="yup" else cy+y)

class PreviewContext:
    def __init__(self,parts_raw_path,animation_raw_path,cellmap_path,texture_dir,
                 texture0=None,texture1=None,canvas_w=None,canvas_h=None,scale=2.0,
                 work_factor=1.0):
        self.rt=Runtime.from_files(parts_raw_path,animation_raw_path)
        self.maps=_maps_from_cellmap(_load(cellmap_path))
        self.lookup=_cell_lookup(self.maps)
        self.texture_paths=_choose_textures(self.maps,texture_dir,{0:texture0,1:texture1})
        self.atlases={mi:_read_rgba(p) for mi,p in self.texture_paths.items()}
        ar=self.rt.animation_raw
        self.cw=int(canvas_w or ar.get("SizeCanvasX",320) or 320)
        self.ch=int(canvas_h or ar.get("SizeCanvasY",320) or 320)
        self.scale=float(scale)
        self.work_factor=float(work_factor)
        self.W=max(1,int(round(self.cw*self.scale*self.work_factor)))
        self.H=max(1,int(round(self.ch*self.scale*self.work_factor)))
        self.cx,self.cy=self.W/2.0,self.H/2.0

    def render(self,frame=0,mode="native2d",euler_order="zxy",coordinate_mode="yup",
               show_hidden=False,draw_mesh_wire=False,offset_x=0.0,offset_y=0.0):
        result=self.rt.evaluate_frame(frame,mode,euler_order)
        canvas=np.zeros((self.H,self.W,4),dtype=np.uint8)
        cx=self.cx+float(offset_x)*self.scale
        cy=self.cy+float(offset_y)*self.scale
        parts=sorted(result["parts"],key=lambda p:(int(p.get("priority",0) or 0),int(p.get("index",0))))
        wire=[]

        for p in parts:
            if (not show_hidden) and bool(p.get("hidden_provisional",False)):
                continue
            cell=p.get("cell")
            if not isinstance(cell,dict): continue
            mi=int(cell.get("IndexCellMap",-1));ci=int(cell.get("IndexCell",-1))
            c=self.lookup.get((mi,ci))
            if c is None or mi not in self.atlases: continue

            atlas=self.atlases[mi]
            rx=float(c.get("x",0));ry=float(c.get("y",0))
            rw=float(c.get("width",0));rh=float(c.get("height",0))
            piv=c.get("pivot",{}) or {}
            px=float(piv.get("x",rw/2));py=float(piv.get("y",rh/2))
            opacity=float(p.get("opacity",1.0) if isinstance(p.get("opacity",1.0),(int,float)) else 1.0)

            mesh=p.get("skinned_mesh")
            if isinstance(mesh,dict) and mesh.get("vertices") and mesh.get("triangles"):
                verts=mesh["vertices"];uvs=mesh.get("uv",[]) or [];inds=mesh["triangles"]
                if len(uvs)>=len(verts):
                    for k in range(0,len(inds)-2,3):
                        ids=[int(inds[k]),int(inds[k+1]),int(inds[k+2])]
                        if max(ids)>=len(verts) or max(ids)>=len(uvs): continue
                        src=[];dst=[]
                        for vi in ids:
                            uv=uvs[vi]
                            src.append((rx+float(uv.get("x",0))*rw,ry+float(uv.get("y",0))*rh))
                            q=(float(verts[vi]["x"]),float(verts[vi]["y"]))
                            dst.append(_to_canvas((q[0]*self.scale,q[1]*self.scale),cx,cy,coordinate_mode))
                        _warp_triangle_roi(canvas,atlas,src,dst,opacity)
                        if draw_mesh_wire: wire.append(dst)
                continue

            src4=[(rx,ry),(rx+rw,ry),(rx+rw,ry+rh),(rx,ry+rh)]
            if coordinate_mode=="yup":
                loc4=[(-px,py),(rw-px,py),(rw-px,py-rh),(-px,py-rh)]
            else:
                loc4=[(-px,-py),(rw-px,-py),(rw-px,rh-py),(-px,rh-py)]
            dst4=[]
            for q in loc4:
                wq=_world_point(p,q[0],q[1])
                dst4.append(_to_canvas((wq[0]*self.scale,wq[1]*self.scale),cx,cy,coordinate_mode))
            _warp_triangle_roi(canvas,atlas,[src4[0],src4[1],src4[2]],[dst4[0],dst4[1],dst4[2]],opacity)
            _warp_triangle_roi(canvas,atlas,[src4[0],src4[2],src4[3]],[dst4[0],dst4[2],dst4[3]],opacity)

        if draw_mesh_wire and wire:
            rgba=cv2.cvtColor(canvas,cv2.COLOR_BGRA2RGBA)
            pil=Image.fromarray(rgba)
            d=ImageDraw.Draw(pil)
            for tri in wire:
                pts=[tuple(map(float,x)) for x in tri]
                d.line([pts[0],pts[1],pts[2],pts[0]],fill=(255,255,255,180),width=1)
            canvas=cv2.cvtColor(np.array(pil),cv2.COLOR_RGBA2BGRA)

        return canvas

def save_png(path,canvas,compression=1):
    Path(path).parent.mkdir(parents=True,exist_ok=True)
    cv2.imwrite(str(path),canvas,[cv2.IMWRITE_PNG_COMPRESSION,int(compression)])


def _alpha_bbox(canvas):
    a=canvas[:,:,3]
    ys,xs=np.nonzero(a>0)
    if len(xs)==0:
        return None
    return (int(xs.min()),int(ys.min()),int(xs.max())+1,int(ys.max())+1)

def _crop_source_center(src,target_w,target_h,center_x,center_y):
    """
    Crop a target-sized window from `src`, centered at the supplied SOURCE-space point.
    Areas outside src are transparent. This avoids mixing source-space and target-space
    translations, which caused the v0.8 auto-frame blank-output bug.
    """
    out=np.zeros((target_h,target_w,4),dtype=np.uint8)
    sh,sw=src.shape[:2]

    left=int(round(float(center_x)-target_w/2.0))
    top=int(round(float(center_y)-target_h/2.0))
    right=left+target_w
    bottom=top+target_h

    sx0=max(0,left)
    sy0=max(0,top)
    sx1=min(sw,right)
    sy1=min(sh,bottom)
    if sx1<=sx0 or sy1<=sy0:
        return out

    dx0=sx0-left
    dy0=sy0-top
    w=sx1-sx0
    h=sy1-sy0
    out[dy0:dy0+h,dx0:dx0+w]=src[sy0:sy1,sx0:sx1]
    return out

def _frame_union_bbox(canvases):
    boxes=[_alpha_bbox(c) for c in canvases]
    boxes=[b for b in boxes if b is not None]
    if not boxes:return None
    return (min(b[0] for b in boxes),min(b[1] for b in boxes),
            max(b[2] for b in boxes),max(b[3] for b in boxes))

def render_frame(parts_raw_path,animation_raw_path,cellmap_path,texture_dir,output_path,
                 frame=0,mode="native2d",euler_order="zxy",canvas_w=None,canvas_h=None,
                 scale=2.0,coordinate_mode="yup",draw_mesh_wire=False,
                 texture0=None,texture1=None,show_hidden=False,png_compression=1,
                 auto_frame=True,padding=16,offset_x=0.0,offset_y=0.0):
    if auto_frame:
        ctx=PreviewContext(parts_raw_path,animation_raw_path,cellmap_path,texture_dir,
                           texture0,texture1,canvas_w,canvas_h,scale,work_factor=2.5)
        large=ctx.render(frame,mode,euler_order,coordinate_mode,show_hidden,draw_mesh_wire,
                         offset_x=offset_x,offset_y=offset_y)
        bbox=_alpha_bbox(large)
        target_w=max(1,int(round(ctx.cw*scale))); target_h=max(1,int(round(ctx.ch*scale)))
        if bbox:
            x0,y0,x1,y1=bbox
            content_cx=(x0+x1)/2.0
            content_cy=(y0+y1)/2.0
            canvas=_crop_source_center(large,target_w,target_h,content_cx,content_cy)
        else:
            canvas=np.zeros((target_h,target_w,4),dtype=np.uint8)
    else:
        ctx=PreviewContext(parts_raw_path,animation_raw_path,cellmap_path,texture_dir,
                           texture0,texture1,canvas_w,canvas_h,scale)
        canvas=ctx.render(frame,mode,euler_order,coordinate_mode,show_hidden,draw_mesh_wire,
                          offset_x=offset_x,offset_y=offset_y)
        target_w,target_h=ctx.W,ctx.H
    save_png(output_path,canvas,png_compression)
    return {"output":str(output_path),"frame":frame,"mode":mode,"canvas":[target_w,target_h],
            "auto_frame":auto_frame,"offset_x":offset_x,"offset_y":offset_y}

def render_animation(parts_raw_path,animation_raw_path,cellmap_path,texture_dir,output_dir,
                     mode="native2d",euler_order="zxy",coordinate_mode="yup",scale=2.0,
                     texture0=None,texture1=None,show_hidden=False,gif_name="preview.gif",
                     max_frames=None,make_gif=True,png_compression=1,
                     auto_frame=True,padding=16,offset_x=0.0,offset_y=0.0):
    out=Path(output_dir);out.mkdir(parents=True,exist_ok=True)

    work_factor=2.5 if auto_frame else 1.0
    ctx=PreviewContext(parts_raw_path,animation_raw_path,cellmap_path,texture_dir,
                       texture0,texture1,scale=scale,work_factor=work_factor)
    total=int(ctx.rt.frame_count)
    if max_frames is not None: total=min(total,int(max_frames))

    # Render all frames once on the large working canvas.
    raw_frames=[]
    for frame in range(total):
        raw_frames.append(ctx.render(frame,mode,euler_order,coordinate_mode,show_hidden,False,
                                     offset_x=offset_x,offset_y=offset_y))

    target_w=max(1,int(round(ctx.cw*scale)))
    target_h=max(1,int(round(ctx.ch*scale)))

    crop_cx=ctx.W/2.0
    crop_cy=ctx.H/2.0
    union=None
    if auto_frame:
        union=_frame_union_bbox(raw_frames)
        if union:
            x0,y0,x1,y1=union
            crop_cx=(x0+x1)/2.0
            crop_cy=(y0+y1)/2.0

            # Padding is currently diagnostic metadata only: v0.9 performs translation-only
            # auto-framing and never rescales the character. If the union is larger than the
            # target canvas, centering still preserves the maximum possible visible area.

    pngs=[]
    for frame,large in enumerate(raw_frames):
        canvas=_crop_source_center(large,target_w,target_h,crop_cx,crop_cy) if auto_frame else large
        op=out/f"frame_{frame:03d}.png"
        save_png(op,canvas,png_compression)
        pngs.append(op)

    gif_path=None
    if make_gif and pngs:
        ims=[Image.open(p).convert("RGBA") for p in pngs]
        duration=int(round(1000.0/max(ctx.rt.fps,1.0)))
        gif_path=out/gif_name
        ims[0].save(gif_path,save_all=True,append_images=ims[1:],loop=0,duration=duration,disposal=2)

    report={
        "output_dir":str(out),"gif":str(gif_path) if gif_path else None,"frames":len(pngs),
        "mode":mode,"coordinate_mode":coordinate_mode,"auto_frame":auto_frame,
        "union_bbox":union,"crop_center_source_pixels":[crop_cx,crop_cy],
        "manual_offset":[offset_x,offset_y]
    }
    (out/"animation_report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    return report

def render_compare(parts_raw_path,animation_raw_path,cellmap_path,texture_dir,output_dir,
                   frame=0,scale=2.0,texture0=None,texture1=None):
    out=Path(output_dir);out.mkdir(parents=True,exist_ok=True)
    ctx=PreviewContext(parts_raw_path,animation_raw_path,cellmap_path,texture_dir,texture0,texture1,scale=scale)
    specs=[
        ("native2d","zxy","yup",False),
        ("native2d","zxy","yup",True),
        ("flat2d","zxy","yup",False),
        ("unity3d","zxy","yup",False),
        ("native2d","zxy","ydown",False),
        ("flat3d","zxy","yup",False),
    ]
    images=[]
    for mode,order,coord,showhidden in specs:
        tag=f"{mode}_{order}_{coord}" + ("_showhidden" if showhidden else "")
        canvas=ctx.render(frame,mode,order,coord,showhidden,False)
        op=out/f"frame_{frame:03d}_{tag}.png"
        save_png(op,canvas,1)
        rgba=cv2.cvtColor(canvas,cv2.COLOR_BGRA2RGBA)
        images.append((tag,Image.fromarray(rgba)))

    cellw=max(im.width for _,im in images);cellh=max(im.height for _,im in images)
    labelh=28;cols=3;rows=(len(images)+cols-1)//cols
    sheet=Image.new("RGBA",(cols*cellw,rows*(cellh+labelh)),(40,40,40,255))
    draw=ImageDraw.Draw(sheet)
    for i,(tag,im) in enumerate(images):
        x=(i%cols)*cellw;y=(i//cols)*(cellh+labelh)
        sheet.alpha_composite(im,(x,y+labelh));draw.text((x+6,y+6),tag,fill=(255,255,255,255))
    sp=out/f"frame_{frame:03d}_comparison.png";sheet.save(sp,compress_level=1)
    return {"comparison":str(sp)}

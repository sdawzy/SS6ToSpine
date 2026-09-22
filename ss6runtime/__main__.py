
import argparse, json
from pathlib import Path
from .runtime import Runtime, inspect_runtime
from .preview import render_frame, render_compare, render_animation
from .extractor import extract_bundle
from .batch import batch_test, render_all_animations
from .spine_export import export_spine_static, export_spine_animated, export_spine_baked, export_spine_frame_swap, export_spine_frame_swap_all, bundle_to_spine_static, bundle_to_spine_animated, bundle_to_spine_baked, bundle_to_spine_frame_swap, bundle_to_spine_frame_swap_all
from .validate_spine import validate_frame_swap

def main():
    ap=argparse.ArgumentParser(prog="ss6runtime")
    sub=ap.add_subparsers(dest="cmd",required=True)

    p=sub.add_parser("inspect")
    p.add_argument("--parts-raw",required=True)
    p.add_argument("--animation-raw",required=True)
    p.add_argument("-o","--output")

    p=sub.add_parser("evaluate")
    p.add_argument("--parts-raw",required=True)
    p.add_argument("--animation-raw",required=True)
    p.add_argument("--frame",type=int,default=0)
    p.add_argument("--mode",choices=["native2d","flat2d","unity3d","flat3d"],default="native2d")
    p.add_argument("--order",choices=["zxy","zyx","xyz","xzy","yxz","yzx"],default="zxy")
    p.add_argument("-o","--output",required=True)

    p=sub.add_parser("dump-animation")
    p.add_argument("--parts-raw",required=True)
    p.add_argument("--animation-raw",required=True)
    p.add_argument("--mode",choices=["native2d","flat2d","unity3d","flat3d"],default="native2d")
    p.add_argument("--order",choices=["zxy","zyx","xyz","xzy","yxz","yzx"],default="zxy")
    p.add_argument("-o","--output",required=True)

    p=sub.add_parser("compare-modes")
    p.add_argument("--parts-raw",required=True)
    p.add_argument("--animation-raw",required=True)
    p.add_argument("--frame",type=int,default=0)
    p.add_argument("-o","--output-dir",required=True)


    p=sub.add_parser("preview")
    p.add_argument("--parts-raw",required=True)
    p.add_argument("--animation-raw",required=True)
    p.add_argument("--cellmap",required=True)
    p.add_argument("--texture-dir",required=True)
    p.add_argument("--texture0")
    p.add_argument("--texture1")
    p.add_argument("--frame",type=int,default=0)
    p.add_argument("--mode",choices=["native2d","flat2d","unity3d","flat3d"],default="native2d")
    p.add_argument("--order",choices=["zxy","zyx","xyz","xzy","yxz","yzx"],default="zxy")
    p.add_argument("--scale",type=float,default=2.0)
    p.add_argument("--coordinate-mode",choices=["yup","ydown"],default="yup")
    p.add_argument("--show-hidden",action="store_true")
    p.add_argument("--mesh-wire",action="store_true")
    p.add_argument("--png-compression",type=int,default=1)
    p.add_argument("--no-auto-frame",action="store_true")
    p.add_argument("--padding",type=float,default=16.0)
    p.add_argument("--offset-x",type=float,default=0.0)
    p.add_argument("--offset-y",type=float,default=0.0)
    p.add_argument("-o","--output",required=True)

    p=sub.add_parser("preview-compare")
    p.add_argument("--parts-raw",required=True)
    p.add_argument("--animation-raw",required=True)
    p.add_argument("--cellmap",required=True)
    p.add_argument("--texture-dir",required=True)
    p.add_argument("--texture0")
    p.add_argument("--texture1")
    p.add_argument("--frame",type=int,default=0)
    p.add_argument("--scale",type=float,default=2.0)
    p.add_argument("-o","--output-dir",required=True)


    p=sub.add_parser("preview-animation")
    p.add_argument("--parts-raw",required=True)
    p.add_argument("--animation-raw",required=True)
    p.add_argument("--cellmap",required=True)
    p.add_argument("--texture-dir",required=True)
    p.add_argument("--texture0")
    p.add_argument("--texture1")
    p.add_argument("--mode",choices=["native2d","flat2d","unity3d","flat3d"],default="native2d")
    p.add_argument("--order",choices=["zxy","zyx","xyz","xzy","yxz","yzx"],default="zxy")
    p.add_argument("--coordinate-mode",choices=["yup","ydown"],default="yup")
    p.add_argument("--show-hidden",action="store_true")
    p.add_argument("--scale",type=float,default=2.0)
    p.add_argument("--max-frames",type=int)
    p.add_argument("--no-gif",action="store_true")
    p.add_argument("--png-compression",type=int,default=1)
    p.add_argument("--no-auto-frame",action="store_true")
    p.add_argument("--padding",type=float,default=16.0)
    p.add_argument("--offset-x",type=float,default=0.0)
    p.add_argument("--offset-y",type=float,default=0.0)
    p.add_argument("-o","--output-dir",required=True)


    p=sub.add_parser("extract-bundle")
    p.add_argument("bundle")
    p.add_argument("-o","--output-dir",required=True)
    p.add_argument("--animation-name")
    p.add_argument("--animation-index",type=int)
    p.add_argument("--data-animation")
    p.add_argument("--root-path-id",type=int)
    p.add_argument("--all-animations",action="store_true")


    p=sub.add_parser("render-all-animations")
    p.add_argument("bundle")
    p.add_argument("-o","--output-dir",required=True)
    p.add_argument("--data-animation")
    p.add_argument("--animation-filter")
    p.add_argument("--mode",choices=["native2d","flat2d","unity3d","flat3d"],default="native2d")
    p.add_argument("--coordinate-mode",choices=["yup","ydown"],default="yup")
    p.add_argument("--scale",type=float,default=1.0)
    p.add_argument("--max-frames",type=int)
    p.add_argument("--no-gif",action="store_true")
    p.add_argument("--png-compression",type=int,default=1)
    p.add_argument("--no-auto-frame",action="store_true")
    p.add_argument("--padding",type=float,default=16.0)
    p.add_argument("--offset-x",type=float,default=0.0)
    p.add_argument("--offset-y",type=float,default=0.0)

    p=sub.add_parser("batch-test")
    p.add_argument("input_dir")
    p.add_argument("-o","--output-dir",required=True)
    p.add_argument("--pattern",default="*")
    p.add_argument("--data-animation")
    p.add_argument("--mode",choices=["native2d","flat2d","unity3d","flat3d"],default="native2d")
    p.add_argument("--coordinate-mode",choices=["yup","ydown"],default="yup")
    p.add_argument("--scale",type=float,default=1.0)
    p.add_argument("--max-frames",type=int)
    p.add_argument("--no-gif",action="store_true")
    p.add_argument("--all-animations",action="store_true")
    p.add_argument("--png-compression",type=int,default=1)
    p.add_argument("--no-auto-frame",action="store_true")
    p.add_argument("--padding",type=float,default=16.0)
    p.add_argument("--offset-x",type=float,default=0.0)
    p.add_argument("--offset-y",type=float,default=0.0)


    p=sub.add_parser("export-spine-static")
    p.add_argument("--parts-raw",required=True)
    p.add_argument("--animation-raw",required=True)
    p.add_argument("--cellmap",required=True)
    p.add_argument("--texture-dir",required=True)
    p.add_argument("--frame",type=int,default=0)
    p.add_argument("--name")
    p.add_argument("--mesh-v-flip",action="store_true")
    p.add_argument("--show-hidden",action="store_true")
    p.add_argument("-o","--output-dir",required=True)

    p=sub.add_parser("bundle-to-spine-static")
    p.add_argument("bundle")
    p.add_argument("-o","--output-dir",required=True)
    p.add_argument("--frame",type=int,default=0)
    p.add_argument("--name")
    p.add_argument("--animation-name")
    p.add_argument("--animation-index",type=int)
    p.add_argument("--data-animation")
    p.add_argument("--root-path-id",type=int)
    p.add_argument("--mesh-v-flip",action="store_true")
    p.add_argument("--show-hidden",action="store_true")


    p=sub.add_parser("export-spine-animated")
    p.add_argument("--parts-raw",required=True)
    p.add_argument("--animation-raw",required=True)
    p.add_argument("--cellmap",required=True)
    p.add_argument("--texture-dir",required=True)
    p.add_argument("--setup-frame",type=int,default=0)
    p.add_argument("--name")
    p.add_argument("--mesh-v-flip",action="store_true")
    p.add_argument("--show-hidden",action="store_true")
    p.add_argument("-o","--output-dir",required=True)

    p=sub.add_parser("bundle-to-spine-animated")
    p.add_argument("bundle")
    p.add_argument("-o","--output-dir",required=True)
    p.add_argument("--setup-frame",type=int,default=0)
    p.add_argument("--name")
    p.add_argument("--animation-name")
    p.add_argument("--animation-index",type=int)
    p.add_argument("--data-animation")
    p.add_argument("--root-path-id",type=int)
    p.add_argument("--mesh-v-flip",action="store_true")
    p.add_argument("--show-hidden",action="store_true")


    p=sub.add_parser("export-spine-baked")
    p.add_argument("--parts-raw",required=True)
    p.add_argument("--animation-raw",required=True)
    p.add_argument("--cellmap",required=True)
    p.add_argument("--texture-dir",required=True)
    p.add_argument("--setup-frame",type=int,default=0)
    p.add_argument("--name")
    p.add_argument("--mesh-v-flip",action="store_true")
    p.add_argument("--show-hidden",action="store_true")
    p.add_argument("--stepped",action="store_true")
    p.add_argument("-o","--output-dir",required=True)

    p=sub.add_parser("bundle-to-spine-baked")
    p.add_argument("bundle")
    p.add_argument("-o","--output-dir",required=True)
    p.add_argument("--setup-frame",type=int,default=0)
    p.add_argument("--name")
    p.add_argument("--animation-name")
    p.add_argument("--animation-index",type=int)
    p.add_argument("--data-animation")
    p.add_argument("--root-path-id",type=int)
    p.add_argument("--mesh-v-flip",action="store_true")
    p.add_argument("--show-hidden",action="store_true")
    p.add_argument("--stepped",action="store_true")


    p=sub.add_parser("export-spine-frame-swap")
    p.add_argument("--parts-raw",required=True)
    p.add_argument("--animation-raw",required=True)
    p.add_argument("--cellmap",required=True)
    p.add_argument("--texture-dir",required=True)
    p.add_argument("--setup-frame",type=int,default=0)
    p.add_argument("--name")
    p.add_argument("--mesh-v-flip",action="store_true")
    p.add_argument("--show-hidden",action="store_true")
    p.add_argument("--no-dedupe",action="store_true")
    p.add_argument("-o","--output-dir",required=True)

    p=sub.add_parser("bundle-to-spine-frame-swap")
    p.add_argument("bundle")
    p.add_argument("-o","--output-dir",required=True)
    p.add_argument("--setup-frame",type=int,default=0)
    p.add_argument("--name")
    p.add_argument("--animation-name")
    p.add_argument("--animation-index",type=int)
    p.add_argument("--data-animation")
    p.add_argument("--root-path-id",type=int)
    p.add_argument("--mesh-v-flip",action="store_true")
    p.add_argument("--show-hidden",action="store_true")
    p.add_argument("--no-dedupe",action="store_true")


    p=sub.add_parser("bundle-to-spine-frame-swap-all")
    p.add_argument("bundle")
    p.add_argument("-o","--output-dir",required=True)
    p.add_argument("--setup-animation")
    p.add_argument("--setup-frame",type=int,default=0)
    p.add_argument("--name")
    p.add_argument("--include")
    p.add_argument("--exclude")
    p.add_argument("--data-animation")
    p.add_argument("--root-path-id",type=int)
    p.add_argument("--mesh-v-flip",action="store_true")
    p.add_argument("--show-hidden",action="store_true")
    p.add_argument("--no-dedupe",action="store_true")
    p.add_argument("--dedupe-tolerance",type=float,default=1e-4)
    p.add_argument("--export-fps",type=float)
    p.add_argument("--frame-step",type=int)


    p=sub.add_parser("validate-spine-frame-swap")
    p.add_argument("--spine-json",required=True)
    p.add_argument("--animation",required=True)
    p.add_argument("--spine-dir")
    p.add_argument("--parts-raw")
    p.add_argument("--animation-raw")
    p.add_argument("--cellmap")
    p.add_argument("--part-filter")
    p.add_argument("--show-hidden",action="store_true")
    p.add_argument("-o","--output-dir",required=True)

    args=ap.parse_args()





    if args.cmd=="validate-spine-frame-swap":
        r=validate_frame_swap(
            args.spine_json,args.animation,
            parts_raw_path=args.parts_raw,
            animation_raw_path=args.animation_raw,
            cellmap_path=args.cellmap,
            spine_dir=args.spine_dir,
            part_filter=args.part_filter,
            output_dir=args.output_dir,
            show_hidden=args.show_hidden
        )
        print(json.dumps(r,ensure_ascii=False,indent=2))
        return
    if args.cmd=="bundle-to-spine-frame-swap-all":
        r=bundle_to_spine_frame_swap_all(
            args.bundle,args.output_dir,
            setup_animation_name=args.setup_animation,
            setup_frame=args.setup_frame,
            name=args.name,
            include=args.include,
            exclude=args.exclude,
            data_animation=args.data_animation,
            root_path_id=args.root_path_id,
            mesh_v_flip=args.mesh_v_flip,
            show_hidden=args.show_hidden,
            dedupe=not args.no_dedupe,
            dedupe_tolerance=args.dedupe_tolerance,
            export_fps=args.export_fps,
            frame_step=args.frame_step
        )
        print(json.dumps(r,ensure_ascii=False,indent=2))
        return
    if args.cmd=="export-spine-frame-swap":
        r=export_spine_frame_swap(args.parts_raw,args.animation_raw,args.cellmap,args.texture_dir,args.output_dir,
                                  setup_frame=args.setup_frame,name=args.name,mesh_v_flip=args.mesh_v_flip,
                                  show_hidden=args.show_hidden,dedupe=not args.no_dedupe)
        print(json.dumps(r,ensure_ascii=False,indent=2))
        return
    if args.cmd=="bundle-to-spine-frame-swap":
        r=bundle_to_spine_frame_swap(args.bundle,args.output_dir,setup_frame=args.setup_frame,name=args.name,
                                     animation_name=args.animation_name,animation_index=args.animation_index,
                                     data_animation=args.data_animation,root_path_id=args.root_path_id,
                                     mesh_v_flip=args.mesh_v_flip,show_hidden=args.show_hidden,
                                     dedupe=not args.no_dedupe)
        print(json.dumps(r,ensure_ascii=False,indent=2))
        return
    if args.cmd=="export-spine-baked":
        r=export_spine_baked(args.parts_raw,args.animation_raw,args.cellmap,args.texture_dir,args.output_dir,
                             setup_frame=args.setup_frame,name=args.name,mesh_v_flip=args.mesh_v_flip,
                             show_hidden=args.show_hidden,stepped=args.stepped)
        print(json.dumps(r,ensure_ascii=False,indent=2))
        return
    if args.cmd=="bundle-to-spine-baked":
        r=bundle_to_spine_baked(args.bundle,args.output_dir,setup_frame=args.setup_frame,name=args.name,
                                animation_name=args.animation_name,animation_index=args.animation_index,
                                data_animation=args.data_animation,root_path_id=args.root_path_id,
                                mesh_v_flip=args.mesh_v_flip,show_hidden=args.show_hidden,
                                stepped=args.stepped)
        print(json.dumps(r,ensure_ascii=False,indent=2))
        return
    if args.cmd=="export-spine-animated":
        r=export_spine_animated(args.parts_raw,args.animation_raw,args.cellmap,args.texture_dir,args.output_dir,
                                setup_frame=args.setup_frame,name=args.name,mesh_v_flip=args.mesh_v_flip,
                                show_hidden=args.show_hidden)
        print(json.dumps(r,ensure_ascii=False,indent=2))
        return
    if args.cmd=="bundle-to-spine-animated":
        r=bundle_to_spine_animated(args.bundle,args.output_dir,setup_frame=args.setup_frame,name=args.name,
                                   animation_name=args.animation_name,animation_index=args.animation_index,
                                   data_animation=args.data_animation,root_path_id=args.root_path_id,
                                   mesh_v_flip=args.mesh_v_flip,show_hidden=args.show_hidden)
        print(json.dumps(r,ensure_ascii=False,indent=2))
        return
    if args.cmd=="export-spine-static":
        r=export_spine_static(args.parts_raw,args.animation_raw,args.cellmap,args.texture_dir,args.output_dir,
                              frame=args.frame,name=args.name,mesh_v_flip=args.mesh_v_flip,
                              show_hidden=args.show_hidden)
        print(json.dumps(r,ensure_ascii=False,indent=2))
        return
    if args.cmd=="bundle-to-spine-static":
        r=bundle_to_spine_static(args.bundle,args.output_dir,frame=args.frame,name=args.name,
                                 animation_name=args.animation_name,animation_index=args.animation_index,
                                 data_animation=args.data_animation,root_path_id=args.root_path_id,
                                 mesh_v_flip=args.mesh_v_flip,show_hidden=args.show_hidden)
        print(json.dumps(r,ensure_ascii=False,indent=2))
        return
    if args.cmd=="extract-bundle":
        r=extract_bundle(args.bundle,args.output_dir,args.animation_name,args.animation_index,args.data_animation,args.root_path_id,args.all_animations)
        print(json.dumps(r,ensure_ascii=False,indent=2))
        return
    if args.cmd=="render-all-animations":
        r=render_all_animations(args.bundle,args.output_dir,mode=args.mode,coordinate_mode=args.coordinate_mode,
                                scale=args.scale,make_gif=not args.no_gif,max_frames=args.max_frames,
                                animation_filter=args.animation_filter,data_animation=args.data_animation,
                                png_compression=args.png_compression,auto_frame=not args.no_auto_frame,
                                padding=args.padding,offset_x=args.offset_x,offset_y=args.offset_y)
        print(json.dumps(r,ensure_ascii=False,indent=2))
        return
    if args.cmd=="batch-test":
        r=batch_test(args.input_dir,args.output_dir,pattern=args.pattern,mode=args.mode,
                     coordinate_mode=args.coordinate_mode,scale=args.scale,make_gif=not args.no_gif,
                     max_frames=args.max_frames,render_all=args.all_animations,
                     data_animation=args.data_animation,png_compression=args.png_compression,
                     auto_frame=not args.no_auto_frame,padding=args.padding,
                     offset_x=args.offset_x,offset_y=args.offset_y)
        print(json.dumps(r,ensure_ascii=False,indent=2))
        return

    rt=Runtime.from_files(args.parts_raw,args.animation_raw)

    if args.cmd=="inspect":
        r=inspect_runtime(rt)
        txt=json.dumps(r,ensure_ascii=False,indent=2)
        if args.output: Path(args.output).write_text(txt,encoding="utf-8")
        print(txt)
    elif args.cmd=="evaluate":
        r=rt.evaluate_frame(args.frame,args.mode,args.order)
        Path(args.output).write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding="utf-8")
        print(args.output)
    elif args.cmd=="dump-animation":
        rt.dump_frames(args.output,args.mode,args.order)
        print(args.output)
    elif args.cmd=="compare-modes":
        out=Path(args.output_dir);out.mkdir(parents=True,exist_ok=True)
        specs=[("native2d","zxy"),("flat2d","zxy"),
               ("unity3d","zxy"),("unity3d","zyx"),("unity3d","xyz"),
               ("flat3d","zxy")]
        for mode,order in specs:
            r=rt.evaluate_frame(args.frame,mode,order)
            fn=out/f"frame_{args.frame:03d}_{mode}_{order}.json"
            fn.write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding="utf-8")
            print(fn)
    elif args.cmd=="preview":
        r=render_frame(args.parts_raw,args.animation_raw,args.cellmap,args.texture_dir,args.output,
                       frame=args.frame,mode=args.mode,euler_order=args.order,scale=args.scale,
                       coordinate_mode=args.coordinate_mode,draw_mesh_wire=args.mesh_wire,
                       texture0=args.texture0,texture1=args.texture1,show_hidden=args.show_hidden,
                       png_compression=args.png_compression,auto_frame=not args.no_auto_frame,
                       padding=args.padding,offset_x=args.offset_x,offset_y=args.offset_y)
        print(json.dumps(r,ensure_ascii=False,indent=2))
    elif args.cmd=="preview-compare":
        r=render_compare(args.parts_raw,args.animation_raw,args.cellmap,args.texture_dir,args.output_dir,
                         frame=args.frame,scale=args.scale,texture0=args.texture0,texture1=args.texture1)
        print(json.dumps(r,ensure_ascii=False,indent=2))
    else:
        r=render_animation(args.parts_raw,args.animation_raw,args.cellmap,args.texture_dir,args.output_dir,
                           mode=args.mode,euler_order=args.order,coordinate_mode=args.coordinate_mode,
                           scale=args.scale,texture0=args.texture0,texture1=args.texture1,
                           show_hidden=args.show_hidden,max_frames=args.max_frames,make_gif=not args.no_gif,
                           png_compression=args.png_compression,auto_frame=not args.no_auto_frame,
                           padding=args.padding,offset_x=args.offset_x,offset_y=args.offset_y)
        print(json.dumps(r,ensure_ascii=False,indent=2))

if __name__=="__main__":
    main()

"""Fixed ComfyUI Core graphs for object scenes, motif patterns and proof sheets.

Generation uses existing generate.py tasks. This helper only composes supplied
images through Core nodes; it does not infer masks, lighting or art acceptance.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import sys
import uuid

from PIL import Image
from image_edit_tools import file_record, load_image, new_directory, save_json
import generate


def positive(value, name, minimum=1, maximum=4096):
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        raise ValueError(f"{name} must be integer {minimum}..{maximum}")
    return value


def rgb_color(value):
    if not isinstance(value, str) or len(value) != 7 or value[0] != '#':
        raise ValueError("background must be #RRGGBB")
    try:
        return int(value[1:], 16)
    except ValueError as exc:
        raise ValueError("background must be #RRGGBB") from exc


def check_image(path, transparent=False):
    image = load_image(path)
    if image.width * image.height > 16_777_216:
        raise ValueError("Input image exceeds 16 megapixels")
    alpha = image.getchannel('A')
    if not alpha.getbbox():
        raise ValueError("Fully transparent image cannot be placed")
    if transparent and alpha.getextrema()[0] == 255:
        raise ValueError("Object/motif requires transparency; run existing remove-bg first")
    return image


class Graph:
    def __init__(self):
        self.nodes = {}

    def add(self, kind, **inputs):
        node = str(len(self.nodes) + 1)
        self.nodes[node] = {'class_type': kind, 'inputs': inputs}
        return [node, 0]

    def canvas(self, width, height, background):
        return self.add('EmptyImage', width=width, height=height, batch_size=1, color=rgb_color(background))

    def object(self, filename, source_size, target_box, bbox):
        loaded = self.add('LoadImage', image=filename)
        x, y, right, bottom = bbox
        w, h = right-x, bottom-y
        cropped = self.add('ImageCrop', image=loaded, x=x, y=y, width=w, height=h)
        mask = self.add('InvertMask', mask=[loaded[0], 1])
        mask = self.add('CropMask', mask=mask, x=x, y=y, width=w, height=h)
        scale = min(target_box[0]/w, target_box[1]/h)
        tw, th = max(1, round(w*scale)), max(1, round(h*scale))
        resized = self.add('ImageScale', image=cropped, upscale_method='lanczos', width=tw, height=th, crop='disabled')
        mask = self.add('MaskToImage', mask=mask)
        mask = self.add('ImageScale', image=mask, upscale_method='bilinear', width=tw, height=th, crop='disabled')
        mask = self.add('ImageToMask', image=mask, channel='red')
        return resized, mask, (tw, th)

    def paste(self, destination, source, mask, x, y):
        return self.add('ImageCompositeMasked', destination=destination, source=source, mask=mask,
                        x=x, y=y, resize_source=False)


def build_graph(mode, filenames, images, *, background_filename=None, background_size=None,
                x=0, y=0, width=512, height=512, cell=256, columns=3, padding=24,
                rows=3, color='#f5f0e5', title='', caption='', canvas_width=None, canvas_height=None):
    if not filenames or len(filenames) != len(images) or len(images) > 16:
        raise ValueError("Requires 1..16 matching images")
    graph = Graph()
    placements = []
    if mode == 'scene':
        if len(images) != 1 or background_filename is None or background_size is None:
            raise ValueError("scene needs one object and one opaque background")
        positive(width, 'width');positive(height, 'height')
        positive(x, 'x', 0);positive(y, 'y', 0)
        destination = graph.add('LoadImage', image=background_filename)
        if canvas_width is not None or canvas_height is not None:
            if canvas_width is None or canvas_height is None:raise ValueError('Both canvas dimensions are required')
            positive(canvas_width,'canvas_width',64);positive(canvas_height,'canvas_height',64)
            background_size=(canvas_width,canvas_height)
            if x+width>canvas_width or y+height>canvas_height:raise ValueError('Object box exceeds output canvas')
            destination=graph.add('ImageScale',image=destination,upscale_method='lanczos',width=canvas_width,height=canvas_height,crop='center')
        if x+width > background_size[0] or y+height > background_size[1]:
            raise ValueError("Object box exceeds background; no implicit cropping")
        source, mask, fitted = graph.object(filenames[0], images[0].size, (width,height), images[0].getchannel('A').getbbox())
        px, py = x+(width-fitted[0])//2, y+(height-fitted[1])//2
        destination = graph.paste(destination, source, mask, px, py)
        placements.append({'input': 0, 'box': [px,py,*fitted]})
        output_size = background_size
    elif mode in {'sheet','pattern'}:
        positive(cell,'cell',64,512);positive(columns,'columns',1,8);positive(padding,'padding',0,cell//3)
        if mode=='pattern':
            if len(images)!=1:raise ValueError("pattern repeats one approved motif only")
            positive(rows,'rows',1,8)
            sequence=[0]*(rows*columns)
        else:
            sequence=list(range(len(images)));rows=math.ceil(len(sequence)/columns)
        output_size=(cell*columns,cell*rows)
        destination=graph.canvas(*output_size,color)
        objects={}
        for index in set(sequence):
            objects[index]=graph.object(filenames[index],images[index].size,(cell-2*padding,cell-2*padding),images[index].getchannel('A').getbbox())
        for n,index in enumerate(sequence):
            source,mask,fitted=objects[index]
            px=(n%columns)*cell+(cell-fitted[0])//2
            py=(n//columns)*cell+(cell-fitted[1])//2
            destination=graph.paste(destination,source,mask,px,py)
            placements.append({'input':index,'box':[px,py,*fitted]})
    else:
        raise ValueError("Unknown fixed graph mode")
    for text, position, font_size in [(title,'top',5.0),(caption,'bottom',2.8)]:
        if text:
            if len(text)>200 or any(ord(c)>126 or (ord(c)<32 and c!='\n') for c in text):
                raise ValueError("Core TextOverlay currently supports printable ASCII titles only; use external typography for Chinese")
            destination=graph.add('TextOverlay',images=destination,text=text,font_size=font_size,color='#203b38',
                                  position=position,align='center',outline=False)
    output = graph.add('SaveImage',images=destination,filename_prefix='design_'+mode)
    return graph.nodes, output[0], output_size, placements


def run(args):
    url=generate.resolve_comfy_url(args.comfy_url, args.config)
    generate.validate_timeout(args.timeout)
    records=[file_record(p) for p in args.images]
    images=[check_image(p, True) for p in args.images]
    bg=None
    if args.command=='scene':
        records.append(file_record(args.background))
        bg=check_image(args.background)
        if bg.getchannel('A').getextrema()!=(255,255):
            raise ValueError("Background must be opaque; helper output is opaque RGB")
    if any(file_record(r['path'])!=r for r in records):raise ValueError('Input changed during validation')
    # Validate all plan values and required Core schemas BEFORE any upload/queue.
    placeholders=[f'input-{n}.png' for n in range(len(images))]
    options=dict(background_filename='background.png' if bg else None,background_size=bg.size if bg else None,
                 x=args.x,y=args.y,width=args.width,height=args.height,cell=args.cell,columns=args.columns,
                 padding=args.padding,rows=args.rows,color=args.color,title=args.title,caption=args.caption,
                 canvas_width=args.canvas_width,canvas_height=args.canvas_height)
    graph,output_id,size,placements=build_graph(args.command,placeholders,images,**options)
    info=generate._fetch_comfy_object_info(url)
    # LoadImage enum reflects current uploads, so check its schema existence but not placeholder filenames.
    missing, _ = generate.check_image_graph_against_object_info(graph,info)
    if missing:raise RuntimeError('Missing ComfyUI Core nodes: '+', '.join(missing))
    for node in graph.values():
        required=info[node['class_type']].get('input',{}).get('required',{})
        if not isinstance(required,dict) or set(required)-set(node['inputs']):
            raise RuntimeError('Incompatible Core schema: '+node['class_type'])
    out=new_directory(args.output_dir)
    save_json(out/'request.json',{'mode':args.command,'inputs':records,'parameters':options,'output_dimensions':list(size),
                                 'limitations':['Opaque RGB output','No automatic relighting or contact shadow','ASCII Core titles only',
                                                'Patterns repeat one motif; not seamless texture generation']})
    try:
        names=[]
        for index,path in enumerate(args.images+([args.background] if bg else [])):
            # Unique upload names prevent another request overwriting a registered input.
            copy=out/f'input-{index}-{uuid.uuid4().hex}.png'
            load_image(path).save(copy)
            names.append(generate.upload_image(str(copy),comfy_url=url))
        if any(file_record(r['path'])!=r for r in records):raise ValueError('Input changed before queue')
        options['background_filename']=names[-1] if bg else None
        graph,output_id,size,placements=build_graph(args.command,names[:len(images)],images,**options)
        save_json(out/'graph.json',graph)
        history=generate.submit_and_wait(graph,timeout=args.timeout,comfy_url=url)
        save_json(out/'history.json',history)
        paths=generate.download_outputs(history,str(out),node_ids=[output_id],comfy_url=url,allow_overwrite=False)
        if len(paths)!=1:raise RuntimeError('Expected exactly one scene/proof output')
        with Image.open(paths[0]) as output:
            if output.size!=tuple(size):raise RuntimeError('Comfy output dimensions differ from fixed graph')
        report={'schema_version':1,'kind':'comfyui_core_design','mode':args.command,'status':'candidate',
                'inputs':records,'output':file_record(paths[0]),'dimensions':list(size),'placements':placements,
                'graph_sha256':hashlib.sha256(json.dumps(graph,sort_keys=True).encode()).hexdigest(),
                'acceptance':'pending human review','model_generation':False}
        save_json(out/'manifest.json',report)
        return report
    except Exception as exc:
        save_json(out/'failure.json',{'error':str(exc),'automatic_retry':False,'queue_may_still_run':True})
        raise


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='command',required=True)
    for mode in ('scene','sheet','pattern'):
        p=sub.add_parser(mode)
        p.add_argument('--images',nargs='+',required=True)
        p.add_argument('--background',required=mode=='scene')
        p.add_argument('--output-dir',required=True)
        p.add_argument('--comfy-url');p.add_argument('--config');p.add_argument('--timeout',type=float,default=180)
        p.add_argument('--x',type=int,default=0);p.add_argument('--y',type=int,default=0)
        p.add_argument('--width',type=int,default=512);p.add_argument('--height',type=int,default=512)
        p.add_argument('--canvas-width',type=int);p.add_argument('--canvas-height',type=int)
        p.add_argument('--cell',type=int,default=256);p.add_argument('--columns',type=int,default=3)
        p.add_argument('--rows',type=int,default=3);p.add_argument('--padding',type=int,default=24)
        p.add_argument('--color',default='#f5f0e5');p.add_argument('--title',default='');p.add_argument('--caption',default='')
    args=parser.parse_args(argv)
    try:report=run(args)
    except (ValueError,OSError,RuntimeError) as exc:
        print(f'Error: {exc}',file=sys.stderr);return 2
    print(json.dumps(report,ensure_ascii=False));return 0


if __name__=='__main__':raise SystemExit(main())

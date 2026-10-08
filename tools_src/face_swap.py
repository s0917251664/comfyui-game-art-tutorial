"""Queue a fixed server-side ComfyUI video workflow; no client media processing."""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import uuid
from urllib.parse import urlparse
# 只拿 HTTP client:import generate 會連帶載入 image_graphs,從 repo 執行時印出誤導的 device_config 提醒。
from comfyui_pipeline import client as comfy_client
from comfyui_face_swap_video.contracts import (SOURCE_COMMIT, CORE_HASHES, MODEL_HASHES, record, checked,
                                              LOAD_NODE, REACTOR_NODE, SOURCE_TYPE, LEGACY_NODE_NAMES)
REQUIRED_NODES=(LOAD_NODE,REACTOR_NODE,'ReActorFaceSwap')

def parse_range(value):
    try:
        start,end=map(float,value.split(':'))
    except (ValueError,TypeError):
        raise argparse.ArgumentTypeError('Range requires START:END seconds')
    if not math.isfinite(start) or not math.isfinite(end) or not 0<=start<end<=60:
        raise argparse.ArgumentTypeError('Range must satisfy 0 <= START < END <= 60')
    return start,end

def build_graph(video,source,start,end,ranges,face_index,batch_size,on_unchanged,audio,prefix):
    return {
        '1':{'class_type':LOAD_NODE,'inputs':{'video_path':str(video),'reference_path':str(source)}},
        '2':{'class_type':REACTOR_NODE,'inputs':{'source':['1',0],
             'start':start,'end':end,'edit_ranges':json.dumps(ranges),'face_index':face_index,
             'batch_size':batch_size,'on_unchanged':on_unchanged,'audio':audio,'output_prefix':prefix}}
    }

def build_ui_workflow(graph):
    """Visual counterpart of the same fixed API graph, loadable in ComfyUI."""
    first=graph['1']['inputs']; second=graph['2']['inputs']
    widgets=[second[k] for k in ('start','end','edit_ranges','face_index','batch_size',
                                 'on_unchanged','audio','output_prefix')]
    return {'last_node_id':2,'last_link_id':1,'version':0.4,
            'nodes':[
                {'id':1,'type':LOAD_NODE,'pos':[80,100],'size':[420,160],
                 'flags':{},'order':0,'mode':0,'inputs':[],
                 'outputs':[{'name':'source','type':SOURCE_TYPE,'links':[1],'slot_index':0}],
                 'properties':{'Node name for S&R':LOAD_NODE},
                 'widgets_values':[first['video_path'],first['reference_path']]},
                {'id':2,'type':REACTOR_NODE,'pos':[580,100],'size':[440,430],
                 'flags':{},'order':1,'mode':0,
                 'inputs':[{'name':'source','type':SOURCE_TYPE,'link':1}],
                 'outputs':[],'properties':{'Node name for S&R':REACTOR_NODE},
                 'widgets_values':widgets}],
            'links':[[1,1,0,2,0,SOURCE_TYPE]], 'groups':[], 'config':{}, 'extra':{}}

def check_live_nodes(schema):
    """Require the current node names in the live schema."""
    stale=[n for n in (LOAD_NODE,REACTOR_NODE) if n not in schema and LEGACY_NODE_NAMES[n] in schema]
    if stale:
        # The deployed package (hash-checked first) defines the new names, so a schema with
        # only the legacy ones means ComfyUI is still running the code loaded before deploy.
        raise ValueError('ComfyUI still has the pre-deploy face-swap nodes loaded (legacy names only); '
                         'restart ComfyUI before preflight: '+','.join(stale))
    if any(n not in schema for n in REQUIRED_NODES):
        raise ValueError('Missing ComfyUI nodes: '+','.join(n for n in REQUIRED_NODES if n not in schema))

def preflight(config_path):
    path=Path(config_path).resolve(strict=True)
    config=json.loads(path.read_text(encoding='utf-8-sig'))
    url=config['comfyui_url'].rstrip('/')
    parsed=urlparse(url)
    if parsed.scheme!='http' or parsed.hostname not in ('127.0.0.1','localhost','::1'):
        raise ValueError('This local tool requires a loopback ComfyUI URL')
    root=Path(config['comfyui_path'])
    if not root.is_absolute(): root=path.parent/root
    node_root=root/'custom_nodes/ComfyUI-ReActor'
    commit=subprocess.run(['git','-C',str(node_root),'rev-parse','HEAD'],check=True,
                          capture_output=True,text=True).stdout.strip()
    if commit!=SOURCE_COMMIT:
        raise ValueError('Unsupported ReActor commit; verify integration before updating')
    subprocess.run(['git','-C',str(node_root),'diff','--exit-code','HEAD','--'],
                   check=True,capture_output=True)
    core=[checked(node_root/'reactor_core',n,h) for n,h in CORE_HASHES.items()]
    models=[checked(root/'models/insightface',n.replace('buffalo_l/','models/buffalo_l/'),h)
            for n,h in MODEL_HASHES.items()]
    for name in ('2d106det.onnx','1k3d68.onnx','genderage.onnx'):
        models.append(record(root/'models/insightface/models/buffalo_l'/name))
    for name in ('config.json','model.safetensors','preprocessor_config.json'):
        models.append(record(root/'models/nsfw_detector/vit-base-nsfw-detector'/name))
    if not list((root/'models/facerestore_models').glob('*.onnx')):
        raise ValueError('ReActor requires a provisioned restorer to prevent automatic schema-time downloads')
    package_files=[]
    for name in ('__init__.py','contracts.py','media.py','nodes.py'):
        expected=record(Path(__file__).parent/'comfyui_face_swap_video'/name)['sha256']
        package_files.append(checked(root/'custom_nodes/comfyui-face-swap-video',name,expected))
    schema=comfy_client._fetch_comfy_object_info(url)
    check_live_nodes(schema)
    fields=schema['ReActorFaceSwap']['input']['required']
    if 'inswapper_128.onnx' not in fields['swap_model'][0] or 'none' not in fields['face_restore_model'][0]:
        raise ValueError('Required ReActor model/options unavailable')
    template=build_graph('input.mkv','source.png',0,-1,[(0,1)],0,4,'error','preserve','face_swap/preflight')
    for node in template.values():
        spec=schema[node['class_type']]['input']
        if set(spec.get('required',{}))-set(node['inputs']):
            raise ValueError('Node schema changed; required inputs missing')
    fingerprint=hashlib.sha256(json.dumps({n:schema[n] for n in REQUIRED_NODES},
                                         sort_keys=True).encode()).hexdigest()
    return url, {'backend':'comfyui_reactor','comfyui_url':url,'node_commit':commit,
                 'server_package':package_files, 'core_files':core,'models':models,'node_schema_fingerprint':fingerprint,
                 'processing_location':'ComfyUI server','model_provider':'See ComfyUI execution log; not asserted by client'}


def run(args,url,provenance):
    dest=Path(args.output_dir).resolve()
    if dest.exists(): raise FileExistsError(f'Use a new output directory: {dest}')
    video=Path(args.video).resolve(strict=True)
    source=Path(args.source_image).resolve(strict=True)
    if not args.edit_range: raise ValueError('Explicit edit ranges required')
    if not math.isfinite(args.start) or not 0<=args.start<60:
        raise ValueError('Start must be a finite timeline time')
    if args.end is not None and (not math.isfinite(args.end) or not args.start<args.end<=60):
        raise ValueError('End must be after start and at most 60 seconds')
    bounds=args.end if args.end is not None else 60
    for pair in args.edit_range:
        if len(pair)!=2 or not all(math.isfinite(v) for v in pair) or not args.start<=pair[0]<pair[1]<=bounds:
            raise ValueError('Edit ranges must lie within clip bounds')
    for left,right in zip(sorted(args.edit_range),sorted(args.edit_range)[1:]):
        if left[1]>right[0]: raise ValueError('Edit ranges must not overlap')
    if not 1<=args.batch_size<=8 or not 0<=args.face_index<=7:
        raise ValueError('Batch size must be 1–8; face index 0–7')
    if any(p.is_relative_to(dest) for p in (video,source)):
        raise ValueError('Output directory must not contain inputs')
    graph=build_graph(video,source,args.start,args.end if args.end is not None else -1,
          args.edit_range,args.face_index,args.batch_size,args.on_unchanged,args.audio,
          'face_swap/'+uuid.uuid4().hex)
    dest.parent.mkdir(parents=True,exist_ok=True)
    stage=Path(tempfile.mkdtemp(prefix='.'+dest.name+'-',dir=dest.parent))
    try:
        (stage/'workflow_api.json').write_text(json.dumps(graph,indent=2),encoding='utf-8')
        (stage/'workflow_ui.json').write_text(json.dumps(build_ui_workflow(graph),indent=2),encoding='utf-8')
        history=comfy_client.submit_and_wait(graph,comfy_url=url,timeout=args.timeout)
        (stage/'history.json').write_text(json.dumps(history,ensure_ascii=False,indent=2),encoding='utf-8')
        # The UI previews only the video. Treat server sidecars as downloadable
        # file descriptors without changing the recorded native history.
        downloadable=dict(history)
        downloadable['outputs']=dict(history['outputs'])
        node_output=dict(history['outputs']['2'])
        node_output['images']=list(node_output.get('images',[]))+list(node_output.get('files',[]))
        downloadable['outputs']['2']=node_output
        paths=comfy_client.download_outputs(downloadable,output_dir=str(stage),node_ids=['2'],comfy_url=url,allow_overwrite=False)
        required={'candidate.mp4','candidate.mp4.json','frames.json','comparison.jpg'}
        if {Path(p).name for p in paths}!=required:
            raise ValueError('Server output contract failed')
        manifest=json.loads((stage/'candidate.mp4.json').read_text(encoding='utf-8'))
        if manifest.get('processing_location')!='ComfyUI server':
            raise ValueError('Server processing provenance missing')
        if record(stage/'candidate.mp4')['sha256']!=manifest['output']['sha256']:
            raise ValueError('Downloaded video hash mismatch')
        receipt={'prompt_id':history['_prompt_id'],'server_manifest':'candidate.mp4.json',
                 'preflight':provenance,'client_source':record(__file__),'output_dir':str(dest)}
        (stage/'receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
        if dest.exists(): raise FileExistsError(str(dest))
        os.rename(stage,dest)
        return {'output_dir':str(dest),'prompt_id':history['_prompt_id'],
                'technical_status':manifest['technical_status'],'counts':manifest['counts'],'actual':manifest['actual']}
    finally:
        if stage.exists(): shutil.rmtree(stage)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('command', choices=('preflight', 'swap'))
    p.add_argument('--config', required=True)
    p.add_argument('--video'); p.add_argument('--source-image')
    p.add_argument('--output-dir')
    p.add_argument('--start', type=float, default=0)
    p.add_argument('--end', type=float)
    p.add_argument('--edit-range', type=parse_range, action='append', default=[])
    p.add_argument('--face-index', type=int, default=0, help='Per-frame large-to-small face index; no identity tracking')
    p.add_argument('--batch-size', type=int, default=4)
    p.add_argument('--timeout', type=float, default=600)
    p.add_argument('--on-unchanged', choices=('error','preserve'), default='error')
    p.add_argument('--audio', choices=('preserve','drop'), default='preserve')
    args = p.parse_args()
    if not math.isfinite(args.timeout) or not 1<=args.timeout<=3600:
        p.error('Timeout must be 1–3600 seconds')
    if args.command == 'swap' and not all((args.video,args.source_image,args.output_dir)):
        p.error('swap requires --video, --source-image, --output-dir')
    url, provenance = preflight(args.config)
    result = provenance if args.command == 'preflight' else run(args,url,provenance)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, RuntimeError) as exc:
        print(f'face_swap: {exc}', file=sys.stderr)
        sys.exit(1)

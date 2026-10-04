"""ComfyUI nodes for the complete local video face-swap pipeline."""
import argparse
import json
import math
import os
from pathlib import Path
import subprocess

import folder_paths
import nodes as comfy_nodes
import comfy.model_management as model_management
import numpy as np
import torch
from PIL import Image

from . import media
from .contracts import SOURCE_COMMIT, CORE_HASHES, MODEL_HASHES, checked, record


def installation_provenance():
    root=Path(folder_paths.base_path)
    reactor=root/'custom_nodes/ComfyUI-ReActor'
    commit=subprocess.run(['git','-C',str(reactor),'rev-parse','HEAD'],
                          capture_output=True,text=True,check=True).stdout.strip()
    if commit!=SOURCE_COMMIT:
        raise ValueError('Unsupported ReActor commit')
    subprocess.run(['git','-C',str(reactor),'diff','--exit-code','HEAD','--'],
                   capture_output=True,check=True)
    files=[checked(reactor/'reactor_core',n,h) for n,h in CORE_HASHES.items()]
    models=[checked(root/'models/insightface',n.replace('buffalo_l/','models/buffalo_l/'),h)
            for n,h in MODEL_HASHES.items()]
    for name in ('2d106det.onnx','1k3d68.onnx','genderage.onnx'):
        models.append(record(root/'models/insightface/models/buffalo_l'/name))
    for name in ('config.json','model.safetensors','preprocessor_config.json'):
        models.append(record(root/'models/nsfw_detector/vit-base-nsfw-detector'/name))
    if not list((root/'models/facerestore_models').glob('*.onnx')):
        raise ValueError('Provision a face restorer to prevent upstream auto-download')
    if 'ReActorFaceSwap' not in comfy_nodes.NODE_CLASS_MAPPINGS:
        raise ValueError('Official ReActorFaceSwap node unavailable')
    return {'node_commit':commit,'core_files':files,'models':models,
            'server_package':[record(Path(__file__).parent/n) for n in
                              ('__init__.py','contracts.py','media.py','nodes.py')],
            'processing_location':'ComfyUI server','server_pid':os.getpid()}


class ReActorEngine:
    """Call the registered official node in-process; never load its models ourselves."""
    def __init__(self,reference,face_index):
        self.node=comfy_nodes.NODE_CLASS_MAPPINGS['ReActorFaceSwap']()
        with Image.open(reference) as im:
            self.source=torch.from_numpy(np.array(im.convert('RGB')).astype(np.float32)/255.)[None]
        self.face_index=face_index
        self.jobs=[]

    def check_cancelled(self):
        model_management.throw_exception_if_processing_interrupted()

    def process(self,images,fps,directory):
        self.check_cancelled()
        batch=torch.from_numpy(np.stack([im[:,:,::-1].copy() for im in images]).astype(np.float32)/255.)
        with torch.inference_mode():
            upstream=self.node.execute(enabled=True,input_image=batch,source_image=self.source,
                    swap_model='inswapper_128.onnx',facedetection='retinaface_resnet50',
                    face_restore_model='none',face_restore_visibility=1.,codeformer_weight=.5,
                    detect_gender_input='no',detect_gender_source='no',
                    input_faces_index=str(self.face_index),source_faces_index='0',console_log_level=1)
        result=upstream[0]
        self.check_cancelled()
        if (result.shape!=batch.shape or not torch.isfinite(result).all() or
                upstream[2].shape!=batch.shape or
                not torch.equal(upstream[2].detach().cpu(),batch)):
            raise ValueError('ReActor filtered/partial batch or invalid output; refusing publish')
        outputs=[np.clip(im.detach().cpu().numpy()*255.,0,255).astype(np.uint8)[:,:,::-1].copy()
                 for im in result]
        self.jobs.append({'batch':len(self.jobs),'frames':len(images),
                          'node':'ReActorFaceSwap','function':'execute','location':'ComfyUI server'})
        return outputs


class SteveLoadFaceSwapVideo:
    @classmethod
    def INPUT_TYPES(cls):
        return {'required':{'video_path':('STRING',{'default':''}),
                            'reference_path':('STRING',{'default':''})}}
    RETURN_TYPES=('STEVE_FACE_SWAP_SOURCE',)
    RETURN_NAMES=('source',)
    FUNCTION='load'
    CATEGORY='Steve/Video'

    @classmethod
    def IS_CHANGED(cls,video_path,reference_path):
        return (record(video_path)['sha256'],record(reference_path)['sha256'])

    def load(self,video_path,reference_path):
        paths=[]
        for value in (video_path,reference_path):
            p=Path(value)
            if not p.is_absolute():
                raise ValueError('Source paths must be absolute local server paths')
            p=p.resolve(strict=True)
            if not p.is_file(): raise ValueError('Source must be a file')
            paths.append(p)
        meta=media.inspect_video(paths[0])
        with Image.open(paths[1]) as im:
            if max(im.size)>4096: raise ValueError('Reference longest side must be <=4096')
            im.verify()
        return ({'video':str(paths[0]),'reference':str(paths[1]),'metadata':meta},)


class SteveReActorVideo:
    @classmethod
    def INPUT_TYPES(cls):
        return {'required':{
            'source':('STEVE_FACE_SWAP_SOURCE',),
            'start':('FLOAT',{'default':0.,'min':0.,'max':60.}),
            'end':('FLOAT',{'default':-1.,'min':-1.,'max':60.}),
            'edit_ranges':('STRING',{'default':'[[0, 1]]','multiline':True}),
            'face_index':('INT',{'default':0,'min':0,'max':7}),
            'batch_size':('INT',{'default':4,'min':1,'max':8}),
            'on_unchanged':(['error','preserve'],),
            'audio':(['preserve','drop'],),
            'output_prefix':('STRING',{'default':'face_swap/candidate-v1'})}}
    RETURN_TYPES=()
    FUNCTION='execute'
    OUTPUT_NODE=True
    CATEGORY='Steve/Video'

    @classmethod
    def IS_CHANGED(cls,**kwargs):
        return float('nan')

    def execute(self,source,start,end,edit_ranges,face_index,batch_size,on_unchanged,audio,output_prefix):
        model_management.throw_exception_if_processing_interrupted()
        prefix=Path(output_prefix)
        if prefix.is_absolute() or '..' in prefix.parts or not prefix.parts:
            raise ValueError('Output prefix must stay within ComfyUI output')
        out_root=Path(folder_paths.get_output_directory()).resolve()
        dest=(out_root/prefix).resolve()
        if dest==out_root or not dest.is_relative_to(out_root):
            raise ValueError('Output prefix escapes ComfyUI output')
        ranges=json.loads(edit_ranges)
        if not isinstance(ranges,list): raise ValueError('Edit ranges require JSON list')
        validated=[]
        for pair in ranges:
            if not isinstance(pair,list) or len(pair)!=2:
                raise ValueError('Each range requires [START, END]')
            validated.append(media.parse_range(f'{pair[0]}:{pair[1]}'))
        if not math.isfinite(end) or end < 0 and end!=-1:
            raise ValueError('End must be -1 (entire video) or a valid timeline time')
        provenance=installation_provenance()
        args=argparse.Namespace(video=source['video'],source_image=source['reference'],
                 output_dir=str(dest),start=start,end=None if end==-1 else end,
                 edit_range=validated,face_index=face_index,batch_size=batch_size,
                 on_unchanged=on_unchanged,audio=audio)
        if on_unchanged not in ('error','preserve') or audio not in ('preserve','drop'):
            raise ValueError('Unsupported unchanged/audio policy')
        engine=ReActorEngine(source['reference'],face_index)
        manifest=media.render(args,engine,provenance)
        subfolder=dest.relative_to(out_root).as_posix()
        def item(name): return {'filename':name,'subfolder':subfolder,'type':'output'}
        # Match Core PreviewVideo's UI contract; JSON sidecars are not images.
        return {'ui':{'images':[item('candidate.mp4')],'animated':(True,),
                      'files':[item(n) for n in ('comparison.jpg','candidate.mp4.json','frames.json')],
                      'text':[json.dumps({'actual':manifest['actual'],'counts':manifest['counts'],
                                        'warnings':manifest['warnings'],'server_pid':os.getpid()})]}}


NODE_CLASS_MAPPINGS={'SteveLoadFaceSwapVideo':SteveLoadFaceSwapVideo,'SteveReActorVideo':SteveReActorVideo}
NODE_DISPLAY_NAME_MAPPINGS={'SteveLoadFaceSwapVideo':'Steve · Read Video and Face Reference',
                           'SteveReActorVideo':'Steve · ReActor Video + Audio Output'}

"""Reframe an already-authored scene and render final/diagnostic evidence."""
import argparse
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parent
p=argparse.ArgumentParser()
p.add_argument("--diagnostic", action="store_true")
args=p.parse_args(sys.argv[sys.argv.index("--")+1:])
scene=bpy.context.scene
stem=Path(bpy.data.filepath).stem
scene.render.threads=4
scene.cycles.samples=24 if args.diagnostic else 64
scene.render.resolution_x=720 if args.diagnostic else 1100
scene.render.resolution_y=520 if args.diagnostic else 760
if args.diagnostic:
    scene.camera.location=(-7.2,-8.4,6.7)
    scene.camera.rotation_euler=(Vector((0,.3,1.0))-scene.camera.location).to_track_quat('-Z','Y').to_euler()
    scene.camera.data.lens=44
    bpy.data.objects['Left wall'].hide_render=True
    scene.render.filepath=str(ROOT/'evidence'/(stem+'_side.png'))
else:
    scene.render.filepath=str(ROOT/'renders'/(stem+'.png'))
    bpy.context.preferences.filepaths.save_version=0
    bpy.ops.wm.save_as_mainfile(filepath=bpy.data.filepath)
    path=ROOT/'evidence'/(stem+'.json')
    data=json.loads(path.read_text())
    data['render_file']=scene.render.filepath
    data['resolution']=[scene.render.resolution_x,scene.render.resolution_y]
    data['preview']=False
    path.write_text(json.dumps(data,indent=2)+'\n')
bpy.ops.render.render(write_still=True)
print('EVIDENCE_RENDERED',scene.render.filepath)

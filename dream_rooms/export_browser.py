"""Export a saved room to GLB, baking procedural base colors for the browser.

Works on a loaded scene copy and does not overwrite its editable .blend source.
"""
import argparse
import json
import math
import sys
from pathlib import Path

import bpy

ROOT = Path(__file__).resolve().parent
p = argparse.ArgumentParser()
p.add_argument("--room", type=int, required=True)
args = p.parse_args(sys.argv[sys.argv.index("--") + 1:])
labels = {1: "simple", 2: "comfort", 3: "studio", 4: "dream"}
stem = f"{args.room:02d}_{labels[args.room]}"
output = ROOT / "viewer" / "models" / (stem + ".glb")
bake_dir = ROOT / "evidence" / "baked_colors" / stem
bake_dir.mkdir(parents=True, exist_ok=True)
allowed = {"Architecture", "Furniture", "Textiles", "Plants", "Decor"}
objects = [o for o in bpy.context.scene.objects if o.type in {"MESH", "CURVE"}
           and any(c.name in allowed for c in o.users_collection)]
materials = {m for o in objects for m in o.data.materials if m}
scene = bpy.context.scene
scene.render.engine = "CYCLES"
scene.cycles.device = "CPU"
scene.cycles.samples = 1
scene.render.threads_mode = "FIXED"
scene.render.threads = 4
scene.render.bake.use_clear = True
scene.render.bake.margin = 8
baked = []
copies = {}

for index, original in enumerate(sorted(materials, key=lambda m: m.name)):
    mat = original.copy()
    mat.name = original.name + " [browser]"
    copies[original] = mat
    if not mat.use_nodes:
        continue
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    bsdf = nodes.get("Principled BSDF")
    if not bsdf:
        continue
    color = bsdf.inputs["Base Color"]
    # Direct image textures, including the cropped window reference, export natively.
    if color.is_linked and color.links[0].from_node.type != "TEX_IMAGE":
        source = color.links[0].from_socket
        bake_mat = mat.copy()
        bake_nodes, bake_links = bake_mat.node_tree.nodes, bake_mat.node_tree.links
        bake_bsdf = bake_nodes.get("Principled BSDF")
        output_node = next(n for n in bake_nodes if n.type == "OUTPUT_MATERIAL")
        for link in list(output_node.inputs["Surface"].links): bake_links.remove(link)
        emission = bake_nodes.new("ShaderNodeEmission")
        bake_links.new(bake_bsdf.inputs["Base Color"].links[0].from_socket, emission.inputs["Color"])
        bake_links.new(emission.outputs[0], output_node.inputs["Surface"])
        image = bpy.data.images.new("Baked " + original.name, width=256, height=256, alpha=False)
        target_node = bake_nodes.new("ShaderNodeTexImage")
        target_node.image = image
        bake_nodes.active = target_node
        bpy.ops.object.select_all(action="DESELECT")
        bpy.ops.mesh.primitive_plane_add(size=2, location=(0, 0, 12))
        plane = bpy.context.object
        plane.name = "Temporary albedo bake plane"
        plane.data.materials.append(bake_mat)
        bpy.context.view_layer.objects.active = plane
        bpy.ops.object.bake(type="EMIT")
        image.filepath_raw = str(bake_dir / f"{index:02d}.png")
        image.file_format = "PNG"
        image.save()
        image.pack()
        bpy.data.objects.remove(plane, do_unlink=True)
        bpy.data.materials.remove(bake_mat)
        for link in list(color.links): links.remove(link)
        image_node = nodes.new("ShaderNodeTexImage")
        image_node.image = image
        links.new(image_node.outputs["Color"], color)
        baked.append(original.name)
    # Browser geometry retains modeled detail; procedural micro-bump is not exported.
    for link in list(bsdf.inputs["Normal"].links): links.remove(link)

for obj in objects:
    for slot in obj.material_slots:
        if slot.material in copies: slot.material = copies[slot.material]
    obj["inspection_group"] = next((c.name for c in obj.users_collection if c.name in allowed), "Room")

# The exporter supports meshes; convert modeled wires/stems in the working copy.
bpy.ops.object.select_all(action="DESELECT")
curves = [o for o in objects if o.type == "CURVE"]
if curves:
    for obj in curves: obj.select_set(True)
    bpy.context.view_layer.objects.active = curves[0]
    bpy.ops.object.convert(target="MESH")

bpy.ops.object.select_all(action="DESELECT")
objects = [o for o in scene.objects if o.type == "MESH"
           and any(c.name in allowed for c in o.users_collection)]
for obj in objects: obj.select_set(True)
bpy.context.view_layer.objects.active = objects[0]
bpy.ops.export_scene.gltf(filepath=str(output), export_format="GLB", use_selection=True,
                         export_apply=True, export_yup=True, export_materials="EXPORT",
                         export_extras=True, export_cameras=False, export_lights=False,
                         export_animations=False)
assert output.is_file() and output.stat().st_size > 1000
manifest = {"room": labels[args.room], "file": str(output), "bytes": output.stat().st_size,
            "authored_objects": len(objects), "baked_color_materials": baked,
            "omitted": ["Presentation ground", "render cameras", "Blender light rig", "procedural micro-bump"],
            "material_note": "Base-color procedural textures baked on a canonical UV plane; browser lighting differs from Cycles.",
            "window_note": "Distant greenery is a cropped-reference backdrop, not modeled vegetation outside the room."}
(ROOT / "evidence" / (stem + "_export.json")).write_text(json.dumps(manifest, indent=2) + "\n")
print("BROWSER_EXPORT " + json.dumps(manifest), flush=True)

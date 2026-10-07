"""Procedurally author four editable dream-room dioramas from the reference.

Run: ./blender -b --factory-startup --python dream_rooms/build_rooms.py -- --room 1
All meshes, materials, lighting and cameras are authored locally; no asset APIs.
"""

import argparse
import json
import math
import random
import sys
from pathlib import Path

import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parent
parser = argparse.ArgumentParser()
parser.add_argument("--room", type=int, choices=(1, 2, 3, 4), required=True)
parser.add_argument("--preview", action="store_true")
parser.add_argument("--samples", type=int, default=64)
args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
LEVEL = args.room
LABELS = {1: "Simple", 2: "Comfort", 3: "Studio", 4: "Dream"}
rng = random.Random(1100 + LEVEL)
bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete(use_global=False)
for old in list(bpy.data.collections):
    if old.name != "Collection":
        bpy.data.collections.remove(old)
collections = {}
for name in ("Architecture", "Furniture", "Textiles", "Plants", "Decor", "Lighting", "Presentation"):
    col = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(col)
    collections[name] = col
ACTIVE = "Architecture"


def group(name):
    global ACTIVE
    ACTIVE = name


def register(obj, name, mat=None):
    obj.name = name
    for col in list(obj.users_collection):
        col.objects.unlink(obj)
    collections[ACTIVE].objects.link(obj)
    if mat:
        obj.data.materials.append(mat)
    obj["authored_for"] = LABELS[LEVEL]
    return obj


def smooth(obj):
    if obj.type == "MESH":
        for p in obj.data.polygons:
            p.use_smooth = True
    return obj


def material(name, color, rough=.5, metallic=0, transmission=0, emission=0):
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = (*color, 1)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (*color, 1)
    bsdf.inputs["Roughness"].default_value = rough
    bsdf.inputs["Metallic"].default_value = metallic
    bsdf.inputs["Transmission Weight"].default_value = transmission
    if emission:
        bsdf.inputs["Emission Color"].default_value = (*color, 1)
        bsdf.inputs["Emission Strength"].default_value = emission
    return mat


def textured(name, color, kind="fabric"):
    mat = material(name, color, .52 if kind == "wood" else .85)
    n, l = mat.node_tree.nodes, mat.node_tree.links
    bsdf = n.get("Principled BSDF")
    tex = n.new("ShaderNodeTexCoord")
    mapping = n.new("ShaderNodeMapping")
    l.new(tex.outputs["Generated"], mapping.inputs["Vector"])
    noise = n.new("ShaderNodeTexNoise")
    if kind == "wood":
        mapping.inputs["Scale"].default_value = (1.2, 28, 8)
        noise.inputs["Scale"].default_value = 3.2
        noise.inputs["Detail"].default_value = 3
        ramp = n.new("ShaderNodeValToRGB")
        ramp.color_ramp.elements[0].position = .2
        ramp.color_ramp.elements[0].color = (*(c * .62 for c in color), 1)
        ramp.color_ramp.elements[1].position = .8
        ramp.color_ramp.elements[1].color = (*(min(c * 1.5, 1) for c in color), 1)
        l.new(noise.outputs["Fac"], ramp.inputs["Fac"])
        l.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
    else:
        noise.inputs["Scale"].default_value = 150 if kind == "fabric" else 65
        noise.inputs["Detail"].default_value = 2
    l.new(mapping.outputs["Vector"], noise.inputs["Vector"])
    bump = n.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = .20 if kind == "wood" else .25
    bump.inputs["Distance"].default_value = .008 if kind == "wood" else .006
    l.new(noise.outputs["Fac"], bump.inputs["Height"])
    l.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    return mat


def box(name, loc, dims, mat, bevel=.025):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
    obj = register(bpy.context.object, name, mat)
    obj.dimensions = dims
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if bevel:
        mod = obj.modifiers.new("Soft manufactured edges", "BEVEL")
        mod.width = min(bevel, min(dims) * .45)
        mod.segments = 3
        mod = obj.modifiers.new("Weighted surface normals", "WEIGHTED_NORMAL")
        mod.keep_sharp = True
    return obj


def sphere(name, loc, scale, mat):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=24, ring_count=16, radius=1, location=loc)
    obj = register(bpy.context.object, name, mat)
    obj.scale = scale
    return smooth(obj)


def cylinder(name, loc, radius, depth, mat, top=None, vertices=32):
    bpy.ops.mesh.primitive_cone_add(vertices=vertices, radius1=radius,
                                  radius2=radius if top is None else top,
                                  depth=depth, location=loc)
    obj = register(bpy.context.object, name, mat)
    mod = obj.modifiers.new("Edge highlight", "BEVEL")
    mod.width = min(.012, radius * .12, depth * .12)
    mod.segments = 2
    return smooth(obj)


def rod(name, a, b, radius, mat):
    a, b = Vector(a), Vector(b)
    obj = cylinder(name, (a + b) / 2, radius, (b - a).length, mat, vertices=16)
    obj.rotation_euler = (b - a).to_track_quat("Z", "Y").to_euler()
    return obj


def curve(name, points, radius, mat, cyclic=False):
    data = bpy.data.curves.new(name, "CURVE")
    data.dimensions = "3D"
    data.resolution_u = 12
    data.bevel_depth = radius
    data.bevel_resolution = 2
    spline = data.splines.new("POLY")
    spline.points.add(len(points) - 1)
    for p, v in zip(spline.points, points):
        p.co = (*v, 1)
    spline.use_cyclic_u = cyclic
    obj = bpy.data.objects.new(name, data)
    collections[ACTIVE].objects.link(obj)
    data.materials.append(mat)
    return obj


def torus(name, loc, major, minor, mat, rotation=None):
    bpy.ops.mesh.primitive_torus_add(major_segments=48, minor_segments=10,
                                    major_radius=major, minor_radius=minor,
                                    location=loc)
    obj = register(bpy.context.object, name, mat)
    if rotation:
        obj.rotation_euler = rotation
    return smooth(obj)


def mesh(name, vertices, faces, mat, thickness=0):
    data = bpy.data.meshes.new(name)
    data.from_pydata(vertices, [], faces)
    data.update()
    obj = bpy.data.objects.new(name, data)
    collections[ACTIVE].objects.link(obj)
    data.materials.append(mat)
    smooth(obj)
    if thickness:
        mod = obj.modifiers.new("Fabric thickness", "SOLIDIFY")
        mod.thickness = thickness
    return obj


def light(name, loc, energy, color, size=1, target=None, kind="AREA"):
    data = bpy.data.lights.new(name, kind)
    data.energy = energy
    data.color = color
    if kind == "AREA":
        data.shape = "DISK"
        data.size = size
    elif kind == "POINT":
        data.shadow_soft_size = size
    obj = bpy.data.objects.new(name, data)
    collections["Lighting"].objects.link(obj)
    obj.location = loc
    if target is not None:
        obj.rotation_euler = (Vector(target) - obj.location).to_track_quat("-Z", "Y").to_euler()
    return obj


PLASTER = textured("Warm chalk plaster", (.67, .58, .47), "plaster")
TRIM = material("Painted ivory trim", (.77, .73, .65), .65)
OAK = textured("Honey oak furniture", (.42, .22, .085), "wood")
WALNUT = textured("Walnut detail", (.16, .075, .03), "wood")
BLACK = material("Graphite powder coat", (.025, .033, .034), .35, .35)
BRASS = material("Brushed warm brass", (.53, .29, .085), .27, .8)
CREAM = textured("Ivory cotton", (.8, .75, .65))
WHITE = textured("Warm white linen", (.9, .86, .77))
TEAL = textured("Petrol upholstery", (.075, .20, .21))
THROW = textured("Deep teal woven throw", (.055, .17, .18))
TAUPE = textured("Sand upholstery", (.44, .36, .29))
TERRA = material("Matte terracotta", (.40, .18, .075), .85)
CERAMIC = material("Glazed cream ceramic", (.75, .69, .56), .24)
SOIL = material("Potting soil", (.035, .021, .012), 1)
LEAF = material("Leaf green", (.055, .18, .035), .4)
LEAF_LIGHT = material("Young leaf green", (.14, .28, .045), .5)
STEM = material("Plant stems", (.085, .16, .025), .65)
GLASS = material("Clear glass", (.88, .96, .97), .07, transmission=1)
GLASS.node_tree.nodes["Principled BSDF"].inputs["IOR"].default_value = 1.45
WARM = material("Warm LED glow", (1, .54, .19), .3, emission=4)
PAPER = material("Book pages", (.72, .68, .56), .9)
BOOKS = [material("Book cover " + str(i), c, .7) for i, c in enumerate(
    [(.08, .12, .14), (.30, .15, .08), (.48, .43, .31), (.13, .23, .19), (.59, .55, .44)])]


def make_architecture():
    group("Architecture")
    box("Diorama foundation", (0, 0, -.15), (6.65, 5.8, .3), TRIM, .025)
    floor_mats = [textured("Oak floor variation " + str(i),
                          (.34 + i * .018, .17 + i * .012, .062 + i * .007), "wood")
                  for i in range(5)]
    # Physical staggered floor boards; grain and seams survive other views.
    for row in range(25):
        y = -2.65 + row * .22
        start = -3.2 - (row % 3) * .50
        for j in range(6):
            left, right = max(-3.2, start + j * 1.48), min(3.2, start + (j + 1) * 1.48)
            if right > left:
                box(f"Floor board {row:02d}-{j}", ((left + right) / 2, y, .018),
                    (right - left - .007, .214, .038), rng.choice(floor_mats), .005)
    box("Left wall", (-3.28, 0, 1.53), (.16, 5.65, 3.06), PLASTER, .015)
    box("Right wall", (3.28, 0, 1.53), (.16, 5.65, 3.06), PLASTER, .015)
    # Rear wall assembled around a genuine window opening.
    wx, width, bottom, top = -.45, 3.1, 1.70, 2.80
    wl, wr = wx - width / 2, wx + width / 2
    box("Rear wall below window", (0, 2.78, bottom / 2), (6.4, .16, bottom), PLASTER)
    box("Rear wall above window", (0, 2.78, (3.06 + top) / 2), (6.4, .16, 3.06 - top), PLASTER)
    box("Rear wall left pier", ((-3.2 + wl) / 2, 2.78, (bottom + top) / 2),
        (wl + 3.2, .16, top - bottom), PLASTER)
    box("Rear wall right pier", ((wr + 3.2) / 2, 2.78, (bottom + top) / 2),
        (3.2 - wr, .16, top - bottom), PLASTER)
    box("Left skirting", (-3.185, 0, .08), (.03, 5.45, .12), TRIM, .004)
    box("Right skirting", (3.185, 0, .08), (.03, 5.45, .12), TRIM, .004)
    box("Rear skirting", (0, 2.675, .08), (6.4, .035, .12), TRIM, .004)
    for x in [wl, wr]:
        box("Window side frame", (x, 2.705, (top + bottom) / 2), (.065, .10, 1.17), BLACK, .008)
    for z in [bottom, top]:
        box("Window horizontal frame", (wx, 2.705, z), (3.16, .10, .065), BLACK, .008)
    for x in [wx - .52, wx + .52]:
        box("Window mullion", (x, 2.70, 2.25), (.035, .09, 1.06), BLACK, .006)
    box("Window sill", (wx, 2.61, 1.66), (3.3, .31, .065), TRIM, .012)
    # The distant garden is a flat backdrop sampled from the supplied reference;
    # all interior furniture and architectural elements remain real geometry.
    garden = material("Reference greenery beyond window", (.18, .29, .07), .9, emission=.35)
    n, l = garden.node_tree.nodes, garden.node_tree.links
    texture = n.new("ShaderNodeTexImage")
    texture.image = bpy.data.images.load(str(ROOT / "reference.png"), check_existing=True)
    texture.image.pack()
    l.new(texture.outputs["Color"], n["Principled BSDF"].inputs["Base Color"])
    l.new(texture.outputs["Color"], n["Principled BSDF"].inputs["Emission Color"])
    backdrop = mesh("Window garden backdrop", [(wl, 2.96, bottom), (wr, 2.96, bottom),
                     (wr, 2.96, top), (wl, 2.96, top)], [(0, 1, 2, 3)], garden)
    uv = backdrop.data.uv_layers.new(name="Reference window crop")
    corners = [(218 / 1536, 1 - 145 / 1024), (450 / 1536, 1 - 145 / 1024),
               (450 / 1536, 1 - 84 / 1024), (218 / 1536, 1 - 84 / 1024)]
    for datum, coord in zip(uv.data, corners): datum.uv = coord
    backdrop.visible_shadow = False
    # Decorative doorway is explicitly an inferred door in the left wall.
    box("Door leaf", (-3.175, -1.92, 1.02), (.04, .91, 2.04), OAK, .012)
    for y in [-2.405, -1.435]:
        box("Door jamb", (-3.14, y, 1.035), (.065, .045, 2.09), TRIM, .006)
    box("Door header", (-3.14, -1.92, 2.095), (.065, 1.015, .055), TRIM, .006)
    box("Door handle plate", (-3.11, -1.61, 1.02), (.012, .06, .14), BLACK, .005)
    rod("Door lever", (-3.08, -1.61, 1.02), (-3.08, -1.77, 1.02), .016, BLACK)


def chair(cx, cy, advanced=False):
    group("Furniture")
    mat = BLACK if advanced else (CREAM if LEVEL == 1 else TEAL)
    box("Desk chair seat", (cx, cy, .56), (.56, .62, .13), mat, .06)
    back = box("Desk chair back", (cx + .255, cy, .97), (.13, .61, .60), mat, .055)
    back.rotation_euler.y = -.12
    if advanced:
        frame = box("Ergonomic chair back frame", (cx + .285, cy, 1.02), (.10, .66, .66), BLACK, .04)
        frame.rotation_euler.y = -.12
        box("Ergonomic chair lumbar cushion", (cx + .19, cy, .79), (.08, .53, .12), THROW, .04)
        for y in [cy - .31, cy + .31]:
            rod("Chair arm upright", (cx + .1, y, .57), (cx + .1, y, .78), .023, BLACK)
            box("Chair armrest", (cx, y, .79), (.43, .075, .055), BLACK, .022)
    rod("Chair lift column", (cx, cy, .16), (cx, cy, .50), .035, BLACK)
    for i in range(5):
        angle = i * math.tau / 5
        x, y = cx + .35 * math.cos(angle), cy + .35 * math.sin(angle)
        rod("Chair five-star base", (cx, cy, .18), (x, y, .10), .022, BLACK)
        wheel = cylinder("Chair caster", (x, y, .075), .048, .045, BLACK)
        wheel.rotation_euler.x = math.pi / 2


def desk():
    group("Furniture")
    box("Oak desk top", (-2.54, .55, .88), (.92, 2.30, .075), OAK, .017)
    for x in [-2.90, -2.18]:
        for y in [-.46, 1.56]:
            box("Desk leg", (x, y, .43), (.075, .075, .85), OAK, .012)
    box("Desk rear stretcher", (-2.92, .55, .49), (.055, 2.1, .08), OAK, .006)
    chair(-1.64, .44, LEVEL >= 3)
    if LEVEL >= 2:
        desk_lamp((-2.69, 1.37, .93))
        book_stack((-2.45, 1.02, .933), 3, scale=.65)
    if LEVEL >= 3:
        monitor = box("Ultrawide monitor housing", (-2.82, .32, 1.39), (.07, 1.08, .49), BLACK, .018)
        screen = material("Monitor blue interface", (.014, .10, .20), .25, emission=.6)
        box("Monitor display", (-2.776, .32, 1.39), (.008, 1.015, .43), screen, .005)
        ui = material("Monitor interface line", (.19, .58, .76), .5, emission=.4)
        for i in range(10):
            box("Monitor interface detail", (-2.768, .32 + rng.uniform(-.08, .08), 1.21 + i * .034),
                (.003, rng.uniform(.4, .88), .007), ui, 0)
        rod("Monitor pedestal", (-2.81, .32, .96), (-2.81, .32, 1.22), .028, BLACK)
        box("Monitor foot", (-2.69, .32, .94), (.28, .43, .025), BLACK)
        box("Keyboard base", (-2.36, .34, .95), (.27, .68, .025), BLACK, .008)
        for row in range(4):
            for j in range(12):
                box("Keyboard key", (-2.455 + row * .058, .03 + j * .053, .97),
                    (.043, .044, .012), BOOKS[0], .003)
        sphere("Mouse", (-2.34, -.21, .97), (.08, .048, .027), BLACK)
        box("Desk mouse mat", (-2.37, -.19, .931), (.35, .23, .003), TAUPE, .002)
        cylinder("Desk pen cup", (-2.66, -.40, 1.01), .05, .15, CERAMIC)
        for j in range(4):
            rod("Pencil", (-2.66 + j * .012, -.40, .98), (-2.65 + j * .012, -.40, 1.16), .005, BRASS)


def pillow(name, loc, dims, mat, rotation=(0, 0, 0)):
    # Closed, softly squared superellipsoid with small surface creases.
    verts, faces = [], []
    nr, ns = 20, 40
    for i in range(1, nr):
        lat = -math.pi / 2 + math.pi * i / nr
        cl, sl = math.cos(lat), math.sin(lat)
        for j in range(ns):
            a = math.tau * j / ns
            def signed(v, p): return math.copysign(abs(v) ** p, v)
            x = dims[0] / 2 * cl ** .45 * signed(math.cos(a), .38)
            y = dims[1] / 2 * cl ** .45 * signed(math.sin(a), .38)
            z = dims[2] / 2 * signed(sl, .75)
            z += .008 * math.sin(x * 55 + y * 18) * cl ** 3
            verts.append((x, y, z))
    for i in range(nr - 2):
        for j in range(ns):
            a, b = i * ns + j, i * ns + (j + 1) % ns
            faces.append((a, b, b + ns, a + ns))
    bottom, top = len(verts), len(verts) + 1
    verts += [(0, 0, -dims[2] / 2), (0, 0, dims[2] / 2)]
    for j in range(ns):
        faces.append((bottom, (j + 1) % ns, j))
        a = (nr - 2) * ns
        faces.append((top, a + j, a + (j + 1) % ns))
    obj = mesh(name, verts, faces, mat)
    obj.location = loc
    obj.rotation_euler = rotation
    return obj


def cloth(name, cx, cy, top, width, length, mat, folds=.035, yaw=0):
    verts, faces = [], []
    nx, ny = 45, 65
    for j in range(ny):
        v = -1 + 2 * j / (ny - 1)
        for i in range(nx):
            u = -1 + 2 * i / (nx - 1)
            x, y = u * width / 2, v * length / 2
            side_drop = .38 * max(0, (abs(u) - .78) / .22) ** .85
            foot_drop = .30 * max(0, (-v - .80) / .20) ** .85
            z = top - max(side_drop, foot_drop)
            z += folds * (math.sin(x * 17 + y * 5) + .4 * math.sin(y * 25 - x * 8))
            z += .025 * math.sin(y * 7) * math.sin(math.pi * (u + 1) / 2)
            wx = cx + x * math.cos(yaw) - y * math.sin(yaw)
            wy = cy + x * math.sin(yaw) + y * math.cos(yaw)
            if name == "Loose sand blanket":
                def under_surface(center_y, level, w, ln, amplitude):
                    a, b = (wx - 1.97) / (w / 2), (wy - center_y) / (ln / 2)
                    if abs(a) > 1 or abs(b) > 1: return -100
                    xx, yy = wx - 1.97, wy - center_y
                    drop = max(.38 * max(0, (abs(a) - .78) / .22) ** .85,
                               .30 * max(0, (-b - .80) / .20) ** .85)
                    return level - drop + amplitude * (math.sin(xx * 17 + yy * 5) +
                            .4 * math.sin(yy * 25 - xx * 8)) + .025 * math.sin(yy * 7) * math.sin(math.pi * (a + 1) / 2)
                z = max(under_surface(-.08, .87, 2.12, 3.45, .045),
                        under_surface(-.96, 1.035, 2.18, 1.25, .026)) + .035 + .009 * math.sin(x * 21 + y * 16)
            verts.append((wx, wy, z))
    for j in range(ny - 1):
        for i in range(nx - 1):
            a = j * nx + i
            faces.append((a, a + 1, a + nx + 1, a + nx))
    return mesh(name, verts, faces, mat, .018)


def bed():
    group("Furniture")
    cx, cy, width, length = 1.97, .02, 1.72, 3.60
    box("Bed structural base", (cx, cy, .30), (width, length, .48), OAK if LEVEL < 4 else TAUPE, .045)
    box("Bed lower plinth", (cx, cy, .075), (width - .13, length - .13, .11), WALNUT, .008)
    box("Mattress", (cx, cy, .68), (width - .05, length - .07, .31), WHITE, .10)
    if LEVEL == 1:
        box("Simple oak headboard", (cx, 1.90, .88), (width + .03, .08, 1.3), OAK, .025)
    else:
        box("Upholstered headboard", (cx, 1.91, 1.03), (width + .08, .13, 1.22), TAUPE, .06)
        if LEVEL == 4:
            box("Daybed upholstered wall back", (2.88, .0, 1.01), (.15, 3.65, 1.02), TAUPE, .055)
    group("Textiles")
    if LEVEL >= 2:
        cloth("White duvet with modeled folds", cx, -.08, .87, 2.12, 3.45, WHITE,
              .023 if LEVEL == 2 else .045)
        for j in range(2):
            pillow("Sleeping pillow", (cx - .43 + j * .86, 1.36, 1.01), (.78, .60, .23), WHITE,
                   (.12, 0, -.035 + j * .07))
        pillow("Teal accent cushion", (cx, 1.10, 1.13), (.69, .46, .27), TEAL, (.32, .02, .05))
        cloth("Teal throw with hanging edges", cx, -.96, 1.035, 2.18, 1.25, THROW, .026)
        # Modeled fringe along the front end of the teal throw.
        for i in range(44):
            x = cx - 1.04 + i * 2.08 / 43
            rod("Throw fringe", (x, -1.59, .68), (x + .008 * math.sin(i), -1.66, .62), .003, THROW)
        if LEVEL == 4:
            cloth("Loose sand blanket", cx - .22, -.42, 1.015, 1.25, 1.9, TAUPE, .07, -.18)
            for y in [-.95, -.1, .75]:
                pillow("Daybed side cushion", (2.64, y, 1.16), (.27, .68, .67),
                       WHITE if y != -.1 else TEAL, (0, -.22, .05))
    if LEVEL >= 2:
        group("Furniture")
        for y in ([1.76] if LEVEL < 4 else [1.76, -2.05]):
            box("Oak bedside cabinet", (2.98, y, .40), (.42, .53, .70), OAK, .015)
            for z in [.31, .52]:
                box("Bedside drawer", (2.98, y - .278, z), (.36, .022, .17), OAK, .004)
                rod("Drawer pull", (2.92, y - .297, z), (3.04, y - .297, z), .007, BLACK)
            table_lamp((2.98, y, .77), small=True)


def rug():
    group("Textiles")
    mat = textured("Cream woven rug with labyrinth pattern", (.63, .55, .43))
    n, l = mat.node_tree.nodes, mat.node_tree.links
    coord = n.new("ShaderNodeTexCoord")
    noise = n.new("ShaderNodeTexNoise"); noise.inputs["Scale"].default_value = 4
    noise.inputs["Detail"].default_value = 3
    l.new(coord.outputs["Generated"], noise.inputs["Vector"])
    wave = n.new("ShaderNodeTexWave")
    wave.wave_type = "RINGS"; wave.rings_direction = "Z"
    wave.inputs["Scale"].default_value = 12
    wave.inputs["Distortion"].default_value = 7
    wave.inputs["Detail Scale"].default_value = 3
    l.new(coord.outputs["Generated"], wave.inputs["Vector"])
    ramp = n.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = (.41, .34, .25, 1)
    ramp.color_ramp.elements[1].color = (.80, .75, .64, 1)
    ramp.color_ramp.elements[0].position = .38
    ramp.color_ramp.elements[1].position = .57
    l.new(wave.outputs["Color"], ramp.inputs["Fac"])
    l.new(ramp.outputs["Color"], n["Principled BSDF"].inputs["Base Color"])
    dims = (2.80, 2.85) if LEVEL == 2 else ((3.10, 3.75) if LEVEL == 3 else (3.85, 3.95))
    cx, cy = .15, -.56
    box("Patterned rug", (cx, cy, .057), (*dims, .035), mat, .01)
    for side in [-1, 1]:
        y = cy + side * dims[1] / 2
        for i in range(65):
            x = cx - dims[0] / 2 + .025 + i * (dims[0] - .05) / 64
            rod("Rug tassel", (x, y, .059), (x, y + side * .07, .055), .004, CREAM)


def vase(name, loc, height=.35, mat=CERAMIC):
    profile = [(0, .055), (.04, .095), (.20, .125), (.45, .11), (.67, .055), (.82, .041), (1, .045)]
    verts, faces = [], []
    segments = 40
    for z, r in profile:
        for j in range(segments):
            a = j * math.tau / segments
            verts.append((loc[0] + r * height / .35 * math.cos(a),
                          loc[1] + r * height / .35 * math.sin(a), loc[2] + z * height))
    for i in range(len(profile) - 1):
        for j in range(segments):
            a, b = i * segments + j, i * segments + (j + 1) % segments
            faces.append((a, b, b + segments, a + segments))
    obj = mesh(name, verts, faces, mat, .008)
    cylinder(name + " dark opening", (loc[0], loc[1], loc[2] + height - .015),
             .033 * height / .35, .005, SOIL)
    return obj


def table_lamp(loc, small=False):
    group("Decor")
    x, y, z = loc
    if small:
        cylinder("Bedside lamp ceramic base", (x, y, z + .115), .085, .22, CERAMIC, top=.065)
        cylinder("Bedside lampshade", (x, y, z + .30), .145, .20, CREAM, top=.10)
        light("Bedside lamp warm pool", (x, y - .035, z + .30), 28, (1, .61, .29), .10, kind="POINT")
        return
    ring = torus("Sculptural ring lamp base", (x, y, z + .20), .16, .064, CERAMIC,
                 (math.pi / 2, 0, 0))
    ring.scale.z = 1.12
    rod("Lamp neck", (x, y, z + .35), (x, y, z + .60), .016, BRASS)
    verts, faces = [], []
    for k in range(2):
        for j in range(128):
            a = j * math.tau / 128
            r = (.39 if k == 0 else .11) + (.009 if j % 2 else -.009)
            verts.append((x + r * math.cos(a), y + r * math.sin(a), z + .55 + k * .35))
    for j in range(128):
        faces.append((j, (j + 1) % 128, (j + 1) % 128 + 128, j + 128))
    mesh("Pleated conical lampshade", verts, faces, CREAM, .007)
    light("Pleated lamp warm pool", (x, y, z + .66), 42, (1, .66, .36), .15, kind="POINT")


def desk_lamp(loc):
    group("Decor")
    x, y, z = loc
    cylinder("Desk lamp round foot", (x, y, z + .01), .10, .025, BLACK)
    rod("Desk lamp upright", (x, y, z + .025), (x, y, z + .42), .012, BLACK)
    rod("Desk lamp arm", (x, y, z + .42), (x + .13, y, z + .55), .012, BLACK)
    shade = cylinder("Desk lamp shade", (x + .16, y, z + .48), .075, .13, BLACK, top=.027)
    shade.rotation_euler.y = -.38
    light("Desk lamp task light", (x + .17, y, z + .40), 13, (1, .75, .46), .06, kind="POINT")


def side_table(x, y, height=.74, radius=.40):
    group("Furniture")
    cylinder("Round oak side table top", (x, y, height), radius, .055, OAK)
    for i in range(3):
        a = i * math.tau / 3
        rod("Side table splayed leg", (x + .23 * math.cos(a), y + .23 * math.sin(a), height - .04),
            (x + .32 * math.cos(a), y + .32 * math.sin(a), .075), .032, OAK)


def book_stack(loc, count, scale=1):
    group("Decor")
    x, y, z = loc
    for i in range(count):
        h = .035 * scale
        obj = box("Stacked book cover", (x, y, z + i * .045 * scale + h / 2),
                  (.30 * scale, .22 * scale, h), BOOKS[i % len(BOOKS)], .003)
        obj.rotation_euler.z = .03 * math.sin(i * 2)
        box("Stacked book page block", (x, y - .003, z + i * .045 * scale + h / 2),
            (.284 * scale, .212 * scale, h * .7), PAPER, .001)


def leaf(name, start, direction, length, width, mat, lobed=False):
    start, direction = Vector(start), Vector(direction).normalized()
    cross = direction.cross(Vector((0, 0, 1)))
    if cross.length < .1: cross = Vector((1, 0, 0))
    cross.normalize()
    verts, faces = [], []
    for i in range(13):
        t = i / 12
        center = start + direction * length * t + Vector((0, 0, .18 * length * math.sin(math.pi * t)))
        w = width * max(.025, math.sin(math.pi * t) ** .7)
        if lobed: w *= .63 + .37 * abs(math.cos(t * math.pi * 5))
        for side in [-1, 0, 1]:
            p = center + cross * w * side
            p.z -= .07 * length * abs(side) * math.sin(math.pi * t)
            verts.append(tuple(p))
    for i in range(12):
        for side in range(2):
            a = i * 3 + side
            faces.append((a, a + 1, a + 4, a + 3))
    mesh(name, verts, faces, mat, .002)
    curve(name + " midrib", [tuple(start + direction * length * t + Vector((0, 0, .18 * length * math.sin(math.pi * t) + .003)))
                             for t in [i / 12 for i in range(13)]], .0018, STEM)


def plant(name, loc, height=.7, pot_radius=.15, tropical=False):
    group("Plants")
    x, y, z = loc
    ph = pot_radius * 1.8
    cylinder(name + " planter", (x, y, z + ph / 2), pot_radius * .78, ph, CERAMIC,
             top=pot_radius)
    cylinder(name + " soil", (x, y, z + ph - .012), pot_radius * .90, .014, SOIL)
    torus(name + " pot rim", (x, y, z + ph), pot_radius * .96, .012, CERAMIC)
    n = 15 if tropical else 11
    for i in range(n):
        a = math.tau * i / n + rng.uniform(-.2, .2)
        rise = height * rng.uniform(.35, .75)
        base = (x, y, z + ph)
        attach = (x + .08 * math.cos(a), y + .08 * math.sin(a), z + ph + rise * .62)
        rod(name + " stem", base, attach, .006 if tropical else .003, STEM)
        length = height * rng.uniform(.35, .55)
        leaf(name + " leaf", attach, (math.cos(a), math.sin(a), rng.uniform(-.3, .4)),
             length, length * (.28 if tropical else .14), LEAF if i % 3 else LEAF_LIGHT, tropical)


def curtains():
    group("Textiles")
    rod("Curtain pole", (-2.20, 2.40, 2.93), (1.29, 2.40, 2.93), .018, BLACK)
    for cx in [-2.03, 1.10]:
        verts, faces = [], []
        nx, nz = 49, 25
        for j in range(nz):
            t = j / (nz - 1)
            for i in range(nx):
                u = i / (nx - 1)
                x = cx + (u - .5) * (.50 + .09 * (1 - t))
                y = 2.34 + .045 * math.sin(u * math.tau * 7)
                z = .13 + t * 2.75 + .018 * math.cos(u * math.tau * 7) * (1 - t)
                verts.append((x, y, z))
        for j in range(nz - 1):
            for i in range(nx - 1):
                a = j * nx + i
                faces.append((a, a + 1, a + nx + 1, a + nx))
        mesh("Pleated linen curtain", verts, faces, CREAM, .008)
        for j in range(9):
            torus("Curtain hanging ring", (cx - .22 + j * .055, 2.40, 2.91), .023, .006, BLACK,
                  (0, math.pi / 2, 0))


def shelves():
    group("Furniture")
    for z in [1.77, 2.22, 2.67]:
        box("Wall-mounted oak shelf", (-3.015, .45, z), (.34, 1.94, .06), OAK, .008)
        for y in [-.26, 1.16]:
            rod("Shelf bracket", (-3.16, y, z - .23), (-2.88, y, z - .04), .009, BLACK)
    plant("Desk plant", (-2.75, -.41, .94), .30, .075)
    plant("Shelf plant one", (-3.00, 1.02, 2.25), .30, .072)
    plant("Shelf plant two", (-3.00, -.18, 2.70), .33, .075)
    group("Decor")
    book_stack((-3.015, .48, 1.805), 3, .62)
    vase("Shelf ceramic", (-3.01, .37, 2.25), .25)
    group("Furniture")
    cx, y, w = 2.17, 2.46, 1.69
    for x in [cx - w / 2, cx + w / 2]:
        box("Bookcase upright", (x, y, 1.48), (.065, .38, 2.87), OAK, .008)
    box("Bookcase backing", (cx, 2.66, 1.48), (w, .025, 2.87), WALNUT, .003)
    for z in [.08, .64, 1.20, 1.76, 2.32, 2.90]:
        box("Bookcase shelf", (cx, y, z), (w, .40, .055), OAK, .009)
    for level, z in enumerate([.69, 1.25, 1.81, 2.37]):
        group("Decor")
        left = cx - w / 2 + .10
        for j in range(9):
            bw = rng.uniform(.035, .08)
            bh = rng.uniform(.24, .41)
            x = left + j * .11
            obj = box("Shelved book", (x, 2.42, z + bh / 2), (bw, .23, bh), rng.choice(BOOKS), .003)
            if j == 7: obj.rotation_euler.y = -.12
            box("Book spine label", (x, 2.297, z + bh * .70), (bw * .6, .004, .016), PAPER, .001)
        if level % 2 == 0: vase("Bookcase vase", (cx + .62, 2.43, z), .22)
    plant("Bookcase crown plant", (cx - .53, 2.44, 2.94), .38, .105)
    plant("Bookcase trailing plant", (cx + .58, 2.44, 2.94), .32, .09)
    group("Plants")
    for j in range(20):
        t = j / 19
        x, y, z = cx + .68 + .05 * math.sin(t * 14), 2.21, 2.97 - t * 1.32
        if j: rod("Trailing vine", previous, (x, y, z), .004, STEM)
        leaf("Trailing vine leaf", (x, y, z), (1 if j % 2 else -1, -.25, -.20), .13, .045, LEAF)
        previous = (x, y, z)


def wall_art(side=1, y=.0, z=1.9, width=.65, height=.80):
    group("Decor")
    x = side * 3.165
    box("Framed wall art oak surround", (x, y, z), (.035, width, height), OAK, .005)
    box("Framed wall art ivory print", (x - side * .022, y, z), (.01, width - .055, height - .055), PAPER, 0)
    for j in range(3):
        disc = cylinder("Abstract artwork circle", (x - side * .030, y + (j - 1) * .12, z + .1 * math.sin(j)),
                        .13, .003, [TEAL, TERRA, CREAM][j])
        disc.rotation_euler.y = math.pi / 2
    curve("Abstract artwork line", [(x - side * .035, y - width * .35 + k * width * .7 / 15,
                                     z - .20 + .10 * math.sin(k / 3)) for k in range(16)], .007, WALNUT)


def guitar():
    group("Decor")
    x, y, z = -.42, 1.12, .59
    verts, faces = [], []
    ns = 80
    for layer in range(2):
        for j in range(ns):
            a = math.tau * j / ns
            zz = .40 * math.sin(a)
            xx = .28 * math.cos(a) * (1 - .34 * math.exp(-((zz - .05) / .13) ** 2))
            verts.append((x + xx, y + layer * .13, z + zz))
    faces.append(tuple(reversed(range(ns))))
    faces.append(tuple(range(ns, ns * 2)))
    for j in range(ns): faces.append((j, (j + 1) % ns, (j + 1) % ns + ns, j + ns))
    mesh("Acoustic guitar hollow-body exterior", verts, faces, OAK)
    hole = cylinder("Guitar soundhole dark inset", (x, y - .003, z + .08), .075, .008, BLACK)
    hole.rotation_euler.x = math.pi / 2
    torus("Guitar rosette", (x, y - .011, z + .08), .079, .006, BRASS, (math.pi / 2, 0, 0))
    box("Guitar neck", (x, y + .05, 1.26), (.075, .06, .80), WALNUT, .009)
    box("Guitar headstock", (x, y + .05, 1.74), (.12, .055, .18), OAK, .009)
    box("Guitar bridge", (x, y - .014, .40), (.18, .025, .042), WALNUT, .006)
    for j in range(15):
        rod("Guitar fret", (x - .038, y + .012, .94 + j * .047),
            (x + .038, y + .012, .94 + j * .047), .002, BRASS)
    for j in range(6):
        dx = -.025 + j * .01
        rod("Guitar string", (x + dx, y - .027, .39), (x + dx, y - .027, 1.79), .0008, BRASS)
    for i in [-1, 1]:
        rod("Guitar stand foot", (x, y + .10, .20), (x + .22 * i, y - .10, .06), .015, BLACK)
    rod("Guitar stand upright", (x, y + .14, .12), (x, y + .14, .62), .015, BLACK)


def fan():
    group("Decor")
    x, y, z = -2.63, 1.43, 1.22
    cylinder("Fan desk base", (x, y, .96), .13, .04, BLACK)
    rod("Fan stand", (x, y, .97), (x, y, z), .022, BLACK)
    for r in [.08, .14, .20, .24]:
        torus("Fan safety guard ring", (x + .025, y, z), r, .0035, BLACK, (0, math.pi / 2, 0))
    for j in range(16):
        a = j * math.tau / 16
        rod("Fan guard spoke", (x + .029, y, z),
            (x + .029, y + .24 * math.cos(a), z + .24 * math.sin(a)), .0025, BLACK)
    sphere("Fan center cap", (x + .04, y, z), (.035, .04, .04), BLACK)
    for j in range(3):
        a = j * math.tau / 3
        blade = sphere("Fan blade", (x, y + .11 * math.cos(a), z + .11 * math.sin(a)),
                       (.014, .065, .12), WALNUT)
        blade.rotation_euler.x = a - math.pi / 2


def basket():
    group("Decor")
    x, y = .28, .36
    weave = material("Wicker golden reed", (.37, .22, .09), .7)
    for j in range(34):
        a = j * math.tau / 34
        points = [(x + (.20 + .055 * t) * math.cos(a), y + (.20 + .055 * t) * math.sin(a), .085 + .48 * t)
                  for t in [k / 12 for k in range(13)]]
        curve("Basket vertical woven rib", points, .007, weave)
    for k in range(25):
        t = k / 24
        points = [(x + (.20 + .055 * t + .004 * math.sin(j * 34 / 2)) * math.cos(j * math.tau / 100),
                   y + (.20 + .055 * t + .004 * math.sin(j * 34 / 2)) * math.sin(j * math.tau / 100),
                   .085 + .48 * t) for j in range(100)]
        curve("Basket horizontal woven reed", points, .006, weave, True)
    torus("Basket bound rim", (x, y, .565), .255, .014, weave)
    for side in [-1, 1]:
        curve("Basket handle", [(x + side * .22, y + .14 * math.cos(a), .56 + .16 * math.sin(a))
                                for a in [i * math.pi / 24 for i in range(25)]], .013, weave)
    cylinder("Basket base", (x, y, .075), .20, .015, weave)


def helix():
    group("Decor")
    x, y, z = -.67, 1.89, .15
    cylinder("Helix sculpture plinth", (x, y, z), .32, .15, BLACK)
    verts, faces = [], []
    for i in range(240):
        t = i / 239
        a = math.tau * 2.75 * t
        for r in [.235, .31]:
            verts.append((x + r * math.cos(a), y + r * math.sin(a), z + .09 + 2.30 * t))
    for i in range(239):
        a = i * 2
        faces.append((a, a + 1, a + 3, a + 2))
    mesh("Continuous brass helix ribbon", verts, faces, BRASS, .018)


def armchair():
    group("Furniture")
    x, y = .53, 1.70
    box("Lounge chair lower seat", (x, y, .46), (.90, .84, .22), TEAL, .09)
    box("Lounge chair back", (x, y + .32, .86), (.93, .22, .78), TEAL, .095)
    for dx in [-.40, .40]:
        box("Lounge chair padded arm", (x + dx, y, .69), (.19, .80, .36), TEAL, .075)
        for dy in [-.27, .28]:
            rod("Lounge chair leg", (x + dx * .8, y + dy, .40),
                (x + dx, y + dy * 1.15, .06), .025, WALNUT)
    pillow("Lounge chair back cushion", (x, y + .18, .94), (.68, .20, .47), TEAL, (.13, 0, 0))


def ottoman():
    group("Furniture")
    x, y, z = -.47, -1.85, .35
    verts, faces = [], []
    ns, nr = 80, 24
    for i in range(1, nr):
        lat = -math.pi / 2 + i * math.pi / nr
        for j in range(ns):
            a = j * math.tau / ns
            r = .47 * math.cos(lat) ** .45 * (1 + .045 * math.cos(a * 10))
            verts.append((x + r * math.cos(a), y + r * math.sin(a), z + .30 * math.sin(lat)))
    for i in range(nr - 2):
        for j in range(ns):
            a = i * ns + j; b = i * ns + (j + 1) % ns
            faces.append((a, b, b + ns, a + ns))
    bot, top = len(verts), len(verts) + 1
    verts += [(x, y, z - .3), (x, y, z + .3)]
    for j in range(ns):
        faces += [(bot, (j + 1) % ns, j), (top, (nr - 2) * ns + j, (nr - 2) * ns + (j + 1) % ns)]
    mesh("Fluted upholstered ottoman", verts, faces, TEAL)
    sphere("Ottoman center tuft", (x, y, z + .285), (.04, .04, .012), TEAL)


def dream_details():
    group("Furniture")
    for x in [-2.94 + i * .085 for i in range(10)] + [2.99 - i * .065 for i in range(5)]:
        box("Rear wall oak acoustic slat", (x, 2.665, 1.54), (.045, .035, 2.97), OAK, .008)
    group("Decor")
    box("Rear cove light", (0, 2.655, 2.96), (6.22, .035, .022), WARM, .004)
    box("Rear skirting light", (0, 2.65, .17), (6.22, .020, .014), WARM, .003)
    for x in [-2.5, 0, 2.5]:
        light("Warm cove wash", (x, 2.49, 2.91), 28, (1, .56, .25), .8, (x, 2.6, 1.6))
    helix(); armchair(); ottoman()
    group("Furniture")
    x, y = -.08, -.63
    cylinder("Circular glass coffee tabletop", (x, y, .66), .66, .025, GLASS, vertices=64)
    torus("Glass tabletop brass edge", (x, y, .66), .66, .009, BRASS)
    for i in range(3):
        a = i * math.tau / 3 + .3
        lx, ly = x + .43 * math.cos(a), y + .43 * math.sin(a)
        cylinder("Glass coffee table column", (lx, ly, .35), .057, .59, GLASS)
        torus("Glass column brass foot", (lx, ly, .065), .065, .009, BRASS)
    book_stack((x - .12, y, .68), 3, .8)
    plant("Coffee table plant", (x + .18, y + .07, .685), .22, .062)
    side_table(-.31, .79, .75, .27)
    group("Decor")
    # Actual intertwined curves for the cream knot ornament.
    curve("Knot sculpture", [(-.31 + .13 * math.sin(t * 2), .79 + .13 * math.sin(t * 3),
                              .94 + .10 * math.cos(t * 5)) for t in [j * math.tau / 240 for j in range(240)]],
          .033, CERAMIC, True)
    cylinder("Floor lamp weighted base", (1.00, 2.05, .08), .17, .08, BLACK)
    rod("Floor lamp stem", (1.00, 2.05, .10), (1.00, 2.05, 1.99), .012, BLACK)
    rod("Floor lamp angled arm", (1.00, 2.05, 1.99), (.67, 1.98, 2.08), .012, BLACK)
    cylinder("Floor lamp reading shade", (.67, 1.98, 1.98), .10, .15, BLACK, top=.025)
    light("Floor lamp warm pool", (.67, 1.98, 1.87), 20, (1, .72, .41), .06, kind="POINT")
    sphere("Shelf robot head", (-2.96, 1.22, 2.09), (.09, .09, .085), CERAMIC)
    sphere("Shelf robot dark visor", (-2.88, 1.22, 2.10), (.018, .062, .040), BLACK)
    sphere("Shelf robot body", (-2.96, 1.22, 1.94), (.07, .07, .10), CERAMIC)
    for side in [-1, 1]:
        rod("Shelf robot arm", (-2.96, 1.22 + side * .075, 2.0),
            (-2.93, 1.22 + side * .11, 1.92), .021, CERAMIC)
        box("Shelf robot foot", (-2.94, 1.22 + side * .045, 1.835), (.10, .055, .03), BLACK, .008)
    plant("Dream corner plant", (-1.30, 2.05, .05), 1.32, .18, True)
    wall_art(1, .72, 1.98, .72, .83)
    wall_art(1, -.30, 1.75, .60, .76)


make_architecture()
desk()
bed()
if LEVEL == 1:
    group("Decor")
    sphere("Study primitive sphere", (-.91, -1.50, .26), (.24, .24, .24), CREAM)
    study_cube = box("Study primitive cube", (-.15, -.96, .30), (.53, .53, .53), TEAL, .004)
    study_cube.rotation_euler.z = .38
    cylinder("Study primitive cylinder", (.23, -1.82, .27), .25, .48, TEAL)
    cylinder("Study primitive cone", (.91, -1.12, .31), .25, .57, CREAM, top=0)
    wall_art(-1, -1.08, 1.09, .60, .88)
else:
    rug()
    shelves() if LEVEL >= 3 else None
    if LEVEL == 2:
        side_table(-.04, -.30, .75, .43)
        vase("Side table white vase", (-.23, -.31, .79), .36)
        table_lamp((.12, -.27, .79))
        plant("Comfort monstera", (.70, -1.15, .075), .80, .22, True)
        plant("Desk small plant", (-2.67, -.30, .933), .36, .08)
        group("Furniture")
        for z in [1.88, 2.38]:
            box("Comfort wall shelf", (-3.00, .88, z), (.28, 1.18, .055), OAK, .008)
        plant("Comfort shelf plant", (-3.00, .60, 1.91), .30, .075)
        plant("Comfort upper shelf plant", (-3.00, 1.10, 2.415), .34, .085)
        wall_art(1, .65, 1.92)
    if LEVEL >= 3:
        curtains()
        plant("Floor plant at door", (-2.59, -1.83, .04), 1.12, .20, True)
        if LEVEL == 3:
            plant("Studio rear plant", (.70, 1.80, .04), 1.40, .22, True)
            guitar(); fan(); basket()
            side_table(-.74, .68, .70, .27)
            plant("Studio side table plant", (-.74, .68, .735), .20, .06)
            vase("Studio glass carafe", (.45, .94, .075), .64, GLASS)
            wall_art(1, .24, 1.98)
        else:
            dream_details()
        wall_art(-1, -.68, 1.62, .62, .52)
        wall_art(-1, -.05, 1.75, .40, .58)

# Presentation and light rigs remain separate from authored room collections.
group("Presentation")
SLATE = textured("Dark slate presentation ground", (.047, .054, .060), "plaster")
box("Presentation ground", (0, 0, -.34), (200, 200, .07), SLATE, 0)
light("Large soft studio key", (-3.5, -3.5, 7.5), 450, (1, .86, .69), 5, (0, 0, .5))
light("Soft front fill", (3, -4, 5), 230, (.77, .86, 1), 4, (0, 0, 1))
light("Window daylight", (-.60, 2.45, 2.40), 240, (1, .89, .66), 2, (.75, -.7, .05))
sun = light("Afternoon sun", (0, 4, 7), 2.7, (1, .83, .56), kind="SUN")
sun.data.angle = math.radians(4)
sun.rotation_euler = Vector((.8, -1.7, -1.5)).to_track_quat("-Z", "Y").to_euler()
scene = bpy.context.scene
scene.world.use_nodes = True
scene.world.node_tree.nodes["Background"].inputs["Color"].default_value = (.27, .32, .40, 1)
scene.world.node_tree.nodes["Background"].inputs["Strength"].default_value = .22

camera_data = bpy.data.cameras.new("Reference-matching camera")
camera = bpy.data.objects.new("Reference-matching camera", camera_data)
collections["Presentation"].objects.link(camera)
camera.location = (.18, -11.2, 9.6)
camera.rotation_euler = (Vector((0, .14, .95)) - camera.location).to_track_quat("-Z", "Y").to_euler()
camera_data.type = "PERSP"
camera_data.lens = 48
scene.camera = camera
scene.render.engine = "CYCLES"
scene.cycles.device = "CPU"
scene.cycles.samples = 16 if args.preview else args.samples
scene.cycles.use_denoising = True
scene.cycles.max_bounces = 8
scene.cycles.transmission_bounces = 6
scene.render.resolution_x = 560 if args.preview else 1100
scene.render.resolution_y = 387 if args.preview else 760
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = "PNG"
scene.render.film_transparent = False
scene.view_settings.view_transform = "AgX"
scene.render.threads_mode = "FIXED"
scene.render.threads = 8
scene["reference"] = "dream_rooms/reference.png"
scene["reference_panel"] = LEVEL
scene["assumed_room_dimensions_m"] = "6.4 wide x 5.5 deep x 3.06 high"
scene["construction_method"] = "Procedural Blender geometry; no purchased or generated assets"
scene["limitations"] = "Dimensions and hidden geometry inferred; image resemblance, not recovered source geometry"

stem = f"{LEVEL:02d}_{LABELS[LEVEL].lower()}"
scene.render.filepath = str(ROOT / "renders" / ("previews" if args.preview else "") / (stem + ".png"))
blend_path = ROOT / "scenes" / (stem + ".blend")
bpy.ops.wm.save_as_mainfile(filepath=str(blend_path))
counts = {name: len(col.objects) for name, col in collections.items()}
manifest = {"room": LABELS[LEVEL], "panel": LEVEL, "blender_version": bpy.app.version_string,
            "scene_file": str(blend_path), "render_file": scene.render.filepath,
            "object_count": len(scene.objects), "collections": counts,
            "assumed_dimensions_m": [6.4, 5.5, 3.06], "preview": args.preview}
(ROOT / "evidence" / (stem + ".json")).write_text(json.dumps(manifest, indent=2) + "\n")
print("ROOM_BUILT " + json.dumps(manifest), flush=True)
bpy.ops.render.render(write_still=True)
print("ROOM_RENDERED " + scene.render.filepath, flush=True)

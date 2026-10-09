"""Solo Buddy Bunkers release art: the hero scene, rendered in 3D with Blender (Cycles).
A buddy bunker at dusk on an alien world: an earth-covered concrete bunker with its blast door opening (warm light and
haze spilling out), a switch post on each side with its green lamp lit (both pressed), and a faint holographic link
between the two switches (one press, both switches).
Run with Blender's Python module (pip install bpy):
  python scene.py <out.png> <width> <height> <shot> [samples]
shots: square, wide (16:9), social (2:1), header (3.5:1)."""
import math, sys
import bpy
from mathutils import Vector, Euler

OUT, W, H, SHOT = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4]
SAMPLES = int(sys.argv[5]) if len(sys.argv) > 5 else 128

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene


# ------------------------------------------------------------------ helpers
def mat(name, base=(0.5, 0.5, 0.5), rough=0.6, metal=0.0, emit=None, strength=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = (*base, 1)
    b.inputs['Roughness'].default_value = rough
    b.inputs['Metallic'].default_value = metal
    if emit:
        b.inputs['Emission Color'].default_value = (*emit, 1)
        b.inputs['Emission Strength'].default_value = strength
    return m


def node(nt, kind, loc=(0, 0), **inputs):
    n = nt.nodes.new(kind)
    n.location = loc
    for k, v in inputs.items():
        if k in n.inputs:
            n.inputs[k].default_value = v
        else:
            setattr(n, k, v)
    return n


def link(nt, a, b):
    nt.links.new(a, b)


def textured(name, c1, c2, scale=6.0, rough=(0.55, 0.9), bump=0.4, detail=8.0, stains=None):
    """A noisy two-color material with bump (concrete, earth, rock, metal)."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes['Principled BSDF']
    tc = node(nt, 'ShaderNodeTexCoord', (-1200, 0))
    n1 = node(nt, 'ShaderNodeTexNoise', (-900, 200), Scale=scale, Detail=detail, Roughness=0.62)
    link(nt, tc.outputs['Object'], n1.inputs['Vector'])
    ramp = node(nt, 'ShaderNodeValToRGB', (-600, 200))
    ramp.color_ramp.elements[0].position = 0.35
    ramp.color_ramp.elements[0].color = (*c1, 1)
    ramp.color_ramp.elements[1].position = 0.7
    ramp.color_ramp.elements[1].color = (*c2, 1)
    link(nt, n1.outputs['Fac'], ramp.inputs['Fac'])
    col = ramp.outputs['Color']
    if stains:
        n2 = node(nt, 'ShaderNodeTexNoise', (-900, -200), Scale=stains[0], Detail=4.0)
        link(nt, tc.outputs['Object'], n2.inputs['Vector'])
        r2 = node(nt, 'ShaderNodeValToRGB', (-600, -200))
        r2.color_ramp.elements[0].position = 0.45
        r2.color_ramp.elements[1].position = 0.62
        link(nt, n2.outputs['Fac'], r2.inputs['Fac'])
        mix = node(nt, 'ShaderNodeMix', (-300, 100), data_type='RGBA')
        mix.inputs[7].default_value = (*stains[1], 1)
        link(nt, r2.outputs['Color'], mix.inputs[0])
        link(nt, col, mix.inputs[6])
        col = mix.outputs[2]
    link(nt, col, b.inputs['Base Color'])
    rr = node(nt, 'ShaderNodeMapRange', (-300, -100))
    rr.inputs['To Min'].default_value, rr.inputs['To Max'].default_value = rough
    link(nt, n1.outputs['Fac'], rr.inputs['Value'])
    link(nt, rr.outputs['Result'], b.inputs['Roughness'])
    n3 = node(nt, 'ShaderNodeTexNoise', (-900, -500), Scale=scale * 6, Detail=6.0)
    link(nt, tc.outputs['Object'], n3.inputs['Vector'])
    bp = node(nt, 'ShaderNodeBump', (-300, -400), Strength=bump)
    link(nt, n3.outputs['Fac'], bp.inputs['Height'])
    link(nt, bp.outputs['Normal'], b.inputs['Normal'])
    return m


def hazard(name, scale=10.0):
    """Yellow and black diagonal stripes, worn."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes['Principled BSDF']
    tc = node(nt, 'ShaderNodeTexCoord', (-1200, 0))
    wave = node(nt, 'ShaderNodeTexWave', (-900, 0), wave_type='BANDS', bands_direction='DIAGONAL', Scale=scale, Distortion=0.0)
    link(nt, tc.outputs['Object'], wave.inputs['Vector'])
    gt = node(nt, 'ShaderNodeMath', (-700, 0), operation='GREATER_THAN')
    gt.inputs[1].default_value = 0.5
    link(nt, wave.outputs['Fac'], gt.inputs[0])
    wear = node(nt, 'ShaderNodeTexNoise', (-900, -300), Scale=30.0, Detail=10.0)
    link(nt, tc.outputs['Object'], wear.inputs['Vector'])
    wr = node(nt, 'ShaderNodeValToRGB', (-700, -300))
    wr.color_ramp.elements[0].position = 0.62
    wr.color_ramp.elements[1].position = 0.68
    link(nt, wear.outputs['Fac'], wr.inputs['Fac'])
    mix = node(nt, 'ShaderNodeMix', (-450, 0), data_type='RGBA')
    mix.inputs[6].default_value = (0.012, 0.012, 0.012, 1)
    mix.inputs[7].default_value = (0.85, 0.62, 0.02, 1)
    link(nt, gt.outputs[0], mix.inputs[0])
    mix2 = node(nt, 'ShaderNodeMix', (-250, 0), data_type='RGBA')
    mix2.inputs[7].default_value = (0.18, 0.17, 0.16, 1)        # worn to bare metal
    link(nt, wr.outputs['Color'], mix2.inputs[0])
    link(nt, mix.outputs[2], mix2.inputs[6])
    link(nt, mix2.outputs[2], b.inputs['Base Color'])
    b.inputs['Roughness'].default_value = 0.55
    return m


def box(name, loc, size, material, bevel=0.03, rot=(0, 0, 0)):
    bpy.ops.mesh.primitive_cube_add(location=loc, rotation=rot)
    o = bpy.context.object
    o.name = name
    o.scale = (size[0] / 2, size[1] / 2, size[2] / 2)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if bevel:
        m = o.modifiers.new('bevel', 'BEVEL')
        m.width, m.segments = bevel, 3
    o.data.materials.append(material)
    for p in o.data.polygons:
        p.use_smooth = True
    return o


def cyl(name, loc, r, depth, material, rot=(0, 0, 0), verts=32):
    bpy.ops.mesh.primitive_cylinder_add(vertices=verts, radius=r, depth=depth, location=loc, rotation=rot)
    o = bpy.context.object
    o.name = name
    o.data.materials.append(material)
    bpy.ops.object.shade_smooth()
    return o


def sphere(name, loc, r, material, scale=(1, 1, 1)):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=48, ring_count=24, radius=r, location=loc)
    o = bpy.context.object
    o.name = name
    o.scale = scale
    o.data.materials.append(material)
    bpy.ops.object.shade_smooth()
    return o


# ------------------------------------------------------------------ materials
M_GROUND = textured('ground', (0.05, 0.04, 0.034), (0.16, 0.125, 0.095), scale=1.2, rough=(0.75, 0.95), bump=0.6, stains=(0.25, (0.07, 0.04, 0.025)))
M_EARTH = textured('earth', (0.025, 0.02, 0.016), (0.075, 0.06, 0.045), scale=2.5, rough=(0.85, 1.0), bump=1.2, stains=(0.6, (0.035, 0.04, 0.025)))
M_CONCRETE = textured('concrete', (0.2, 0.2, 0.19), (0.3, 0.295, 0.28), scale=5.0, rough=(0.65, 0.9), bump=0.3, stains=(0.9, (0.12, 0.11, 0.1)))
M_DOOR = textured('door metal', (0.06, 0.065, 0.065), (0.13, 0.135, 0.13), scale=4.0, rough=(0.35, 0.65), bump=0.15, stains=(2.0, (0.09, 0.05, 0.03)))
for b in (M_DOOR,):
    b.node_tree.nodes['Principled BSDF'].inputs['Metallic'].default_value = 0.7
M_DARK = mat('dark metal', (0.02, 0.022, 0.024), rough=0.4, metal=0.8)
M_PANEL = mat('panel', (0.01, 0.012, 0.013), rough=0.25, metal=0.2)
M_HAZ = hazard('hazard', 2.2)
M_HAZ2 = hazard('hazard small', 5.0)
M_GREEN = mat('lamp green', (0.2, 1, 0.3), emit=(0.25, 1.0, 0.35), strength=40)
M_RED = mat('lever red', (0.5, 0.03, 0.02), rough=0.35)
M_STEEL = mat('steel', (0.55, 0.55, 0.55), rough=0.3, metal=1.0)
M_WARM = mat('warm light', (1, 0.7, 0.4), emit=(1.0, 0.55, 0.25), strength=3)
M_HOLO = mat('holo', (0.2, 0.8, 1), emit=(0.25, 0.85, 1.0), strength=18)
M_ARMOR = textured('armor', (0.1, 0.1, 0.095), (0.2, 0.2, 0.19), scale=8.0, rough=(0.45, 0.7), bump=0.1)
M_ARMOR_Y = mat('armor yellow', (0.32, 0.22, 0.02), rough=0.6)
M_CAPE = textured('cape', (0.03, 0.035, 0.06), (0.06, 0.07, 0.11), scale=10.0, rough=(0.8, 0.95), bump=0.2)
M_VISOR = mat('visor', (0.01, 0.01, 0.01), rough=0.05, metal=0.6)
M_ROCK = textured('rock', (0.04, 0.035, 0.03), (0.13, 0.11, 0.09), scale=3.0, rough=(0.6, 0.9), bump=1.0)

# ------------------------------------------------------------------ ground and terrain
bpy.ops.mesh.primitive_plane_add(size=400, location=(0, 40, -0.25))
g = bpy.context.object
g.name = 'ground'
mod = g.modifiers.new('sub', 'SUBSURF'); mod.subdivision_type = 'SIMPLE'; mod.levels = mod.render_levels = 6
tex = bpy.data.textures.new('gdisp', 'CLOUDS'); tex.noise_scale = 6.0
d = g.modifiers.new('disp', 'DISPLACE'); d.texture = tex; d.strength = 0.35; d.mid_level = 0.5
g.data.materials.append(M_GROUND)
bpy.ops.object.shade_smooth()
# far hills
for i, (x, y, sx, sz) in enumerate([(-70, 140, 60, 18), (10, 170, 80, 26), (90, 150, 55, 16), (-150, 190, 90, 30), (170, 200, 90, 34)]):
    o = sphere('hill%d' % i, (x, y, -4), 1.0, M_EARTH, scale=(sx, 25, sz))
    dd = o.modifiers.new('disp', 'DISPLACE'); t2 = bpy.data.textures.new('h%d' % i, 'CLOUDS'); t2.noise_scale = 0.4
    dd.texture = t2; dd.strength = 0.25
# rocks
import random
random.seed(4)
for i in range(70):
    x, y = random.uniform(-40, 40), random.uniform(-6, 60)
    if -14 < x < 14 and -4 < y < 22:
        continue
    if -8 < x < 8 and y < 0:                    # keep the view to the door clear
        continue
    r = random.uniform(0.15, 0.9) * (1 + y / 60)
    o = sphere('rock%d' % i, (x, y, 0), r, M_ROCK, scale=(random.uniform(0.7, 1.5), random.uniform(0.7, 1.3), random.uniform(0.4, 0.8)))
    o.rotation_euler = (random.uniform(-0.3, 0.3), random.uniform(-0.3, 0.3), random.uniform(0, 6.28))
    dd = o.modifiers.new('disp', 'DISPLACE'); t2 = bpy.data.textures.new('r%d' % i, 'VORONOI'); t2.noise_scale = 0.6
    dd.texture = t2; dd.strength = 0.25 * r

# ------------------------------------------------------------------ the bunker (door faces -Y, toward the camera)
# earth berm over it
berm = box('berm', (0, 9.0, 1.6), (21.0, 14.0, 6.4), M_EARTH, bevel=2.6)
berm.modifiers['bevel'].segments = 6
sb = berm.modifiers.new('sub', 'SUBSURF'); sb.levels = sb.render_levels = 3
dd = berm.modifiers.new('disp', 'DISPLACE'); t3 = bpy.data.textures.new('berm', 'CLOUDS'); t3.noise_scale = 1.2
dd.texture = t3; dd.strength = 1.1
t3.noise_scale = 0.8; t3.noise_depth = 4
# a cracked concrete apron in front of the door
box('apron', (0, -1.0, -0.05), (12.0, 4.6, 0.3), M_CONCRETE, bevel=0.05)
# concrete front: a wall with a roof slab and side wing walls
wall = box('front wall', (0, 2.0, 2.0), (9.0, 1.6, 4.0), M_CONCRETE, bevel=0.06)
cutter = box('cutter', (0, 3.8, 1.4), (3.8, 6.6, 2.8), M_CONCRETE, bevel=0)
bo = wall.modifiers.new('door', 'BOOLEAN'); bo.object = cutter; bo.operation = 'DIFFERENCE'
wall.modifiers.move(1, 0)
cutter.hide_render = True
bo2 = berm.modifiers.new('door', 'BOOLEAN'); bo2.object = cutter; bo2.operation = 'DIFFERENCE'
box('roof slab', (0, 1.6, 4.15), (9.8, 2.6, 0.45), M_CONCRETE, bevel=0.08)
for s in (-1, 1):
    o = box('wing', (s * 5.6, 0.3, 1.0), (0.7, 4.2, 2.0), M_CONCRETE, bevel=0.06, rot=(0, 0, s * 0.35))
# door opening: the hazard frame, the dark interior and two leaves sliding apart
box('frame top', (0, 1.1, 2.98), (4.5, 0.25, 0.36), M_HAZ, bevel=0.03)
for s_ in (-1, 1):
    box('frame side', (s_ * 2.07, 1.1, 1.4), (0.36, 0.25, 2.8), M_HAZ, bevel=0.03)
box('interior back', (0, 6.0, 1.4), (3.8, 0.2, 2.8), M_WARM, bevel=0)
box('interior floor', (0, 4.0, -0.05), (3.8, 4.4, 0.1), M_CONCRETE, bevel=0)
for s_ in (-1, 1):
    box('interior wall', (s_ * 1.95, 4.0, 1.4), (0.1, 4.4, 2.8), M_CONCRETE, bevel=0)
box('interior ceiling', (0, 4.0, 2.85), (3.8, 4.4, 0.1), M_CONCRETE, bevel=0)
gap = 1.3
for s in (-1, 1):
    cx_ = s * (0.95 + gap / 2)
    leaf = box('leaf', (cx_, 1.55, 1.4), (1.9, 0.22, 2.8), M_DOOR, bevel=0.02)
    for k in range(4):                         # ribs
        box('rib', (cx_ + (k - 1.5) * 0.42, 1.42, 1.45), (0.12, 0.1, 2.5), M_DARK, bevel=0.01)
    box('stripe', (cx_, 1.42, 0.22), (1.85, 0.08, 0.3), M_HAZ2, bevel=0.005)
# warm light from inside, spilling out
bpy.ops.object.light_add(type='AREA', location=(0, 4.5, 2.6))
L = bpy.context.object; L.data.energy = 6000; L.data.color = (1.0, 0.62, 0.32); L.data.shape = 'RECTANGLE'
L.data.size, L.data.size_y = 3.0, 3.0; L.rotation_euler = (math.radians(60), 0, 0)
bpy.ops.object.light_add(type='SPOT', location=(0, 3.5, 2.4))
S = bpy.context.object; S.data.energy = 12000; S.data.color = (1.0, 0.6, 0.3); S.data.spot_size = math.radians(70)
S.data.spot_blend = 0.7; S.rotation_euler = (math.radians(125), 0, 0)
# lamps on the front wall
for s in (-1, 1):
    box('lamp housing', (s * 3.2, 0.95, 3.45), (0.5, 0.3, 0.22), M_DARK, bevel=0.02)
    box('lamp', (s * 3.2, 0.8, 3.38), (0.38, 0.05, 0.08), mat('lamp warm', emit=(1, 0.75, 0.45), strength=30), bevel=0)

# props: an antenna mast on the roof, crates and barrels by the wing walls, cable runs from the switches to the door
cyl('mast', (3.6, 2.4, 6.4), 0.06, 4.2, M_STEEL)
box('mast box', (3.6, 2.4, 4.6), (0.5, 0.5, 0.5), M_DARK, bevel=0.03)
for k in range(3):
    cyl('mast arm', (3.6, 2.4, 6.6 + k * 0.7), 0.02, 1.2 - k * 0.3, M_STEEL, rot=(0, math.radians(90), 0))
bpy.ops.object.light_add(type='POINT', location=(3.6, 2.4, 8.55))
bpy.context.object.data.energy = 15; bpy.context.object.data.color = (1, 0.15, 0.1); bpy.context.object.data.shadow_soft_size = 0.02
sphere('beacon', (3.6, 2.4, 8.55), 0.06, mat('beacon red', emit=(1, 0.1, 0.05), strength=50))
M_CRATE = textured('crate', (0.08, 0.09, 0.07), (0.16, 0.17, 0.13), scale=6.0, rough=(0.5, 0.8), bump=0.2)
for (x, y, z, sx, sy, sz, rz) in [(7.6, 0.2, 0.45, 1.2, 0.9, 0.9, 0.2), (8.3, 1.3, 0.45, 1.0, 1.0, 0.9, -0.1), (7.9, 0.6, 1.25, 0.8, 0.7, 0.7, 0.35)]:
    box('crate', (x, y, z), (sx, sy, sz), M_CRATE, bevel=0.04, rot=(0, 0, rz))
for (x, y) in [(-7.8, 0.4), (-8.4, 1.2), (-7.4, 1.4)]:
    cyl('barrel', (x, y, 0.5), 0.32, 1.0, M_CRATE)
    cyl('barrel rim', (x, y, 0.98), 0.33, 0.05, M_DARK)
for s_ in (-1, 1):
    cd = bpy.data.curves.new('cable', 'CURVE'); cd.dimensions = '3D'; cd.bevel_depth = 0.045
    sp = cd.splines.new('BEZIER'); sp.bezier_points.add(2)
    pts = [(s_ * 6.6, -1.4, 0.05), (s_ * 4.3, -0.4, 0.04), (s_ * 2.4, 1.0, 0.04)]
    for bp_, p_ in zip(sp.bezier_points, pts):
        bp_.co = p_; bp_.handle_left_type = bp_.handle_right_type = 'AUTO'
    co = bpy.data.objects.new('cable', cd); scene.collection.objects.link(co); cd.materials.append(M_DARK)

# ------------------------------------------------------------------ the two switches
SW = []
for s in (-1, 1):
    x, y = s * 6.6, -1.6
    box('post', (x, y, 0.75), (0.45, 0.45, 1.5), M_CONCRETE, bevel=0.04)
    box('console', (x, y - 0.05, 1.75), (1.0, 0.55, 0.75), M_DARK, bevel=0.05, rot=(math.radians(-18), 0, 0))
    box('screen', (x - 0.12, y - 0.33, 1.8), (0.55, 0.04, 0.42), M_PANEL, bevel=0.01, rot=(math.radians(-18), 0, 0))
    box('plate', (x, y - 0.24, 1.3), (1.0, 0.08, 0.14), M_HAZ2, bevel=0.005)
    lamp = sphere('lamp', (x + 0.3, y - 0.34, 1.86), 0.07, M_GREEN)
    bpy.ops.object.light_add(type='POINT', location=(x + 0.3, y - 0.6, 1.9))
    P = bpy.context.object; P.data.energy = 12; P.data.color = (0.3, 1.0, 0.4); P.data.shadow_soft_size = 0.05
    # the lever, thrown down (pressed)
    cyl('lever', (x - 0.12, y - 0.42, 1.68), 0.03, 0.4, M_STEEL, rot=(math.radians(40), 0, 0))
    sphere('knob', (x - 0.12, y - 0.55, 1.53), 0.07, M_RED)
    SW.append(Vector((x, y - 0.1, 2.25)))
# the holographic link: a faint dashed arc from switch to switch over the door
a, b2 = SW
N = 48
for i in range(N):
    if i % 2:
        continue
    u0, u1 = i / N, (i + 0.8) / N
    def pt(u):
        p = a.lerp(b2, u)
        p.z += math.sin(math.pi * u) * 4.2
        p.y += math.sin(math.pi * u) * 0.8
        return p
    p0, p1 = pt(u0), pt(u1)
    mid, v = (p0 + p1) / 2, p1 - p0
    bpy.ops.mesh.primitive_cylinder_add(vertices=8, radius=0.025, depth=v.length, location=mid)
    o = bpy.context.object
    o.rotation_euler = v.to_track_quat('Z', 'Y').to_euler()
    o.data.materials.append(M_HOLO)
for p in SW:                                   # rings above the switch consoles
    bpy.ops.mesh.primitive_torus_add(location=(p.x, p.y, p.z), major_radius=0.32, minor_radius=0.012)
    bpy.context.object.data.materials.append(M_HOLO)

# ------------------------------------------------------------------ sky, sun, moon and haze
world = bpy.data.worlds.new('world'); scene.world = world
world.use_nodes = True
wn = world.node_tree
bg = wn.nodes['Background']
tc = node(wn, 'ShaderNodeTexCoord', (-900, 0))
sep = node(wn, 'ShaderNodeSeparateXYZ', (-700, 0))
link(wn, tc.outputs['Generated'], sep.inputs[0])
ramp = node(wn, 'ShaderNodeValToRGB', (-450, 0))
cr = ramp.color_ramp
cr.elements[0].position = 0.0; cr.elements[0].color = (0.9, 0.32, 0.08, 1)        # the horizon: burnt orange
cr.elements[1].position = 0.35; cr.elements[1].color = (0.012, 0.03, 0.06, 1)     # high: deep blue
e = cr.elements.new(0.06); e.color = (0.35, 0.16, 0.12, 1)
e = cr.elements.new(0.15); e.color = (0.06, 0.08, 0.12, 1)
link(wn, sep.outputs['Z'], ramp.inputs['Fac'])
link(wn, ramp.outputs['Color'], bg.inputs['Color'])
bg.inputs['Strength'].default_value = 1.0
# a big pale moon / gas giant low in the sky
bpy.ops.mesh.primitive_uv_sphere_add(segments=64, ring_count=32, radius=60, location=(-300, 900, 230))
moon = bpy.context.object
mm = textured('moon', (0.25, 0.27, 0.3), (0.55, 0.57, 0.6), scale=0.03, rough=(0.9, 1.0), bump=0.0)
mm.node_tree.nodes['Principled BSDF'].inputs['Emission Color'].default_value = (0.55, 0.62, 0.75, 1)
mm.node_tree.nodes['Principled BSDF'].inputs['Emission Strength'].default_value = 0.25
moon.data.materials.append(mm)
bpy.ops.object.shade_smooth()
bpy.ops.object.light_add(type='SUN', location=(0, 0, 10))
sun = bpy.context.object
sun.data.energy = 1.6; sun.data.color = (1.0, 0.55, 0.3); sun.data.angle = math.radians(3)
sun.rotation_euler = (math.radians(86), 0, math.radians(200))
bpy.ops.object.light_add(type='SUN', location=(0, 0, 10))
fill = bpy.context.object
fill.data.energy = 0.9; fill.data.color = (0.5, 0.62, 0.95); fill.data.angle = math.radians(1)
fill.rotation_euler = (math.radians(55), 0, math.radians(200))    # moonlight from the upper left, behind
# rim light behind the figure and the bunker (cool, from the sky)
bpy.ops.object.light_add(type='AREA', location=(0, 18, 9))
R = bpy.context.object; R.data.energy = 1500; R.data.size = 12; R.data.color = (0.5, 0.65, 1.0)
R.rotation_euler = (math.radians(-60), 0, 0)
# volumetric haze in a box around the scene
bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 20, 8))
fog = bpy.context.object
fog.scale = (90, 90, 18)
fm = bpy.data.materials.new('fog'); fm.use_nodes = True
fnt = fm.node_tree
fnt.nodes.remove(fnt.nodes['Principled BSDF'])
vol = node(fnt, 'ShaderNodeVolumePrincipled', (0, 0))
vol.inputs['Density'].default_value = 0.0035
vol.inputs['Color'].default_value = (0.8, 0.7, 0.62, 1)
vol.inputs['Anisotropy'].default_value = 0.35
link(fnt, vol.outputs[0], fnt.nodes['Material Output'].inputs['Volume'])
fog.data.materials.append(fm)
bpy.ops.mesh.primitive_cube_add(size=1, location=(0, -2.0, 2.0))
fog2 = bpy.context.object
fog2.scale = (60, 30, 4.2)
fm2 = fm.copy(); fog2.data.materials.append(fm2)
fm2.node_tree.nodes['Principled Volume'].inputs['Density'].default_value = 0.018

# ------------------------------------------------------------------ camera
SHOTS = {
    #          camera location           look at              lens   shift x, y
    'square': ((-4.6, -12.0, 1.2), (0.0, 0.8, 2.6), 22, -0.05, -0.02),
    'wide':   ((-8.0, -17.0, 1.35), (0.6, 1.0, 2.9), 24, -0.16, 0.03),
    'social': ((-8.0, -17.0, 1.35), (0.6, 1.0, 2.9), 24, -0.16, 0.05),
    'header': ((-10.5, -25.0, 1.9), (0.8, 1.0, 3.1), 26, -0.3, 0.08),
    'debug':  ((-6.0, -6.5, 1.6), (-5.9, -2.0, 1.3), 35, 0.0, 0.0),
}
loc, at, lens, sx, sy = SHOTS[SHOT]
bpy.ops.object.camera_add(location=loc)
cam = bpy.context.object
cam.rotation_euler = (Vector(at) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
cam.data.lens = lens
cam.data.shift_x, cam.data.shift_y = sx, sy
scene.camera = cam

# ------------------------------------------------------------------ render
scene.render.engine = 'CYCLES'
scene.cycles.device = 'CPU'
scene.cycles.samples = SAMPLES
scene.cycles.use_denoising = True
scene.cycles.max_bounces = 6
scene.cycles.volume_bounces = 1
scene.cycles.volume_step_rate = 4.0
scene.render.resolution_x, scene.render.resolution_y = W, H
scene.render.resolution_percentage = 100
scene.view_settings.view_transform = 'AgX'
scene.view_settings.look = 'AgX - Punchy'
scene.view_settings.exposure = 0.8
scene.render.image_settings.file_format = 'PNG'
scene.render.filepath = OUT
bpy.ops.render.render(write_still=True)
print('rendered', OUT)

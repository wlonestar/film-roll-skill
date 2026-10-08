#!/usr/bin/env python3
"""Dev-only Blender 5 / Pillow renderer; see references/renderer-details.md."""
import argparse
import fcntl
import hashlib
import importlib.util
import json, math, os, shutil, stat, tempfile, time
from pathlib import Path
import bpy
from mathutils import Vector
from bpy_extras.object_utils import world_to_camera_view
from PIL import Image
from label_artwork import (_assert_private_cache_directory, _assert_safe_write_directory,
                           save_webp_with_limit, write_text_atomic)

ROOT = Path(__file__).resolve().parents[1]
MODEL_REVISION = 'true-shell-v15'
SHELL_XY_SCALE = 0.94
VARIANT_IDS = ('kodak-ultramax-400', 'kodak-gold-200', 'kodak-ektar-100',
               'fuji-superia-400', 'ilford-hp5-400')
COMPATIBILITY_VARIANT_IDS = ('kodak-portra-400',)
parser = argparse.ArgumentParser(description=__doc__)
mode = parser.add_mutually_exclusive_group()
mode.add_argument('--variant', default='blank-shell',
                  choices=('blank-shell', 'light-notes', 'all', *VARIANT_IDS,
                           *COMPATIBILITY_VARIANT_IDS),
                  help='render a built-in label, or the blank shell by default')
mode.add_argument('--label-image', type=Path,
                  help='render a completed 2:1 raster label texture')
parser.add_argument('--output-dir', type=Path,
                    help='asset output directory (default: $FILM_ROLL_OUTPUT_DIR or ./output)')
args = parser.parse_args()

CACHE = Path(os.environ.get('FILM_RENDER_CACHE', str(Path.home()/'.cache/film-roll-skill/render'))).expanduser().resolve()
CACHE.mkdir(parents=True, exist_ok=True)
_assert_private_cache_directory(CACHE)
output_dir = args.output_dir or Path(os.environ.get('FILM_ROLL_OUTPUT_DIR', str(ROOT/'output')))
OUT = output_dir.expanduser().resolve()
OUT.mkdir(parents=True, exist_ok=True)
_assert_safe_write_directory(OUT)
lock_directory = Path.home() / '.cache' / 'film-roll-skill'
lock_directory.mkdir(parents=True, exist_ok=True, mode=0o700)
if lock_directory.is_symlink() or lock_directory.stat().st_uid != os.geteuid():
    raise SystemExit(f'Render lock directory must be a real directory owned by this user: {lock_directory}')
_assert_safe_write_directory(lock_directory)
os.chmod(lock_directory, 0o700)
lock_path = lock_directory / 'renderer.lock'
lock_fd = os.open(lock_path, os.O_CREAT | os.O_RDWR | getattr(os, 'O_NOFOLLOW', 0), 0o600)
lock_info = os.fstat(lock_fd)
if not stat.S_ISREG(lock_info.st_mode) or lock_info.st_uid != os.geteuid():
    os.close(lock_fd)
    raise SystemExit(f'Render lock must be a regular file owned by this user: {lock_path}')
os.fchmod(lock_fd, 0o600)
lock_file = os.fdopen(lock_fd, 'r+')
fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)


def cleanup_stale_intermediates(root):
    prefixes = ('film-roll-shell-', 'film-roll-variants-', 'film-roll-custom-')
    marker_name = '.film-roll-temp-marker'
    cutoff = time.time() - 24 * 60 * 60
    for child in root.iterdir():
        try:
            info = child.lstat()
            marker = child / marker_name
            if (stat.S_ISDIR(info.st_mode) and info.st_uid == os.geteuid()
                    and child.name.startswith(prefixes) and info.st_mtime < cutoff
                    and not marker.is_symlink()
                    and marker.read_text(encoding='utf-8') == 'film-roll-skill-render-temp-v1'):
                shutil.rmtree(child)
            elif (stat.S_ISREG(info.st_mode) and info.st_uid == os.geteuid()
                    and child.name.startswith('.film-roll-custom-reservation-')
                    and info.st_mtime < cutoff):
                child.unlink()
        except OSError:
            pass


cleanup_stale_intermediates(CACHE)
cleanup_stale_intermediates(OUT)

if args.label_image is not None or args.variant != 'blank-shell':
    support = Path(__file__).with_name('film-cartridge-variants.py')
    spec = importlib.util.spec_from_file_location('film_cartridge_variants', support)
    variants = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(variants)
    if args.label_image is not None:
        variants.render_custom_artwork(args.label_image.expanduser().resolve(), CACHE, OUT, MODEL_REVISION)
    else:
        variants.render_variants(args.variant, CACHE, OUT, MODEL_REVISION)
    raise SystemExit(0)

# Keep each render's Blender/Pillow intermediates in an isolated private directory.
INTERMEDIATE_ROOT = tempfile.TemporaryDirectory(prefix='film-roll-shell-', dir=CACHE)
INTERMEDIATE = Path(INTERMEDIATE_ROOT.name)
(INTERMEDIATE / '.film-roll-temp-marker').write_text('film-roll-skill-render-temp-v1', encoding='utf-8')

# Start from a blank, unbranded label stock. Preset or user artwork is applied later.
bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)
W,H=4096,2048
im=Image.new('RGB',(W,H),(224,220,208))
im.save(INTERMEDIATE/'label.png')

def material(name,color,metal=0,rough=.4):
    m=bpy.data.materials.new(name); m.diffuse_color=(*color,1); m.use_nodes=True
    p=m.node_tree.nodes.get('Principled BSDF'); p.inputs['Base Color'].default_value=(*color,1)
    p.inputs['Metallic'].default_value=metal; p.inputs['Roughness'].default_value=rough
    return m
black=material('Satin black rolled steel',(.018,.021,.024),.18,.48)
plastic=material('Soft-touch charcoal spindle polymer',(.015,.017,.018),.025,.52)
felt=material('Light trap velvet',(.007,.008,.009),0,.96)
recess=material('Recessed cap interior',(.001,.001,.001),0,1.0)
recess_bsdf=recess.node_tree.nodes.get('Principled BSDF')
specular=recess_bsdf.inputs.get('Specular IOR Level')
if specular: specular.default_value=.02

# The photo reference shows fine paper tooth, ink sitting in the stock, and
# gentle material variation rather than a perfectly uniform color swatch.
label=material('Satin printed paper with fine fiber',(.48,.37,.17),0,.61)
n=label.node_tree.nodes; l=label.node_tree.links; p=n.get('Principled BSDF')
t=n.new('ShaderNodeTexImage'); t.image=bpy.data.images.load(str(INTERMEDIATE/'label.png'))
graining=n.new('ShaderNodeTexNoise'); graining.label='Fine paper fibers'; graining.inputs['Scale'].default_value=320
l.new(t.outputs['Color'],p.inputs['Base Color'])
color_mottle=n.new('ShaderNodeMixRGB'); color_mottle.label='Subtle paper tone variation'
color_mottle.blend_type='MULTIPLY'; color_mottle.inputs[0].default_value=.085
l.new(t.outputs['Color'],color_mottle.inputs[1]); l.new(graining.outputs['Color'],color_mottle.inputs[2])
l.new(color_mottle.outputs['Color'],p.inputs['Base Color'])
roughness_noise=n.new('ShaderNodeTexNoise'); roughness_noise.label='Satin stock roughness variation'
roughness_noise.inputs['Scale'].default_value=34
roughness_map=n.new('ShaderNodeMapRange'); roughness_map.label='Matte-to-satin stock'
roughness_map.inputs['From Min'].default_value=0; roughness_map.inputs['From Max'].default_value=1
roughness_map.inputs['To Min'].default_value=.57; roughness_map.inputs['To Max'].default_value=.74
l.new(roughness_noise.outputs['Fac'],roughness_map.inputs['Value'])
l.new(roughness_map.outputs['Result'],p.inputs['Roughness'])
bump=n.new('ShaderNodeBump'); bump.label='Paper tooth'; bump.inputs['Strength'].default_value=.23
bump.inputs['Distance'].default_value=.003
l.new(graining.outputs['Fac'],bump.inputs['Height']); l.new(bump.outputs['Normal'],p.inputs['Normal'])

# Fine directional ridges and restrained orange-peel texture keep the black
# cap and spindle from reading as smooth, computer-perfect plastic.
plastic_bump=None
for surface, scale, strength, distance in ((black, 260, .10, .0016), (plastic, 46, .16, .0026)):
    nodes=surface.node_tree.nodes; links=surface.node_tree.links
    shader=nodes.get('Principled BSDF')
    grain=nodes.new('ShaderNodeTexNoise'); grain.inputs['Scale'].default_value=scale
    grain.inputs['Detail'].default_value=2
    surface_bump=nodes.new('ShaderNodeBump'); surface_bump.inputs['Strength'].default_value=strength
    surface_bump.inputs['Distance'].default_value=distance
    links.new(grain.outputs['Fac'],surface_bump.inputs['Height'])
    links.new(surface_bump.outputs['Normal'],shader.inputs['Normal'])
    if surface == plastic:
        plastic_bump=surface_bump
plastic_ridges=plastic.node_tree.nodes.new('ShaderNodeTexWave')
plastic_ridges.label='Subtle molded horizontal rings'
plastic_ridges.wave_type='BANDS'; plastic_ridges.bands_direction='Z'
plastic_ridges.inputs['Scale'].default_value=110; plastic_ridges.inputs['Distortion'].default_value=.08
plastic.node_tree.links.new(plastic_ridges.outputs['Color'],plastic_bump.inputs['Height'])

def bevel(obj,amount=.025):
    mod=obj.modifiers.new('Machined edge radii','BEVEL'); mod.width=amount; mod.segments=3
    obj.modifiers.new('Weighted normals','WEIGHTED_NORMAL')
    for poly in obj.data.polygons: poly.use_smooth=True

def cyl(name,r,depth,z,mat):
    bpy.ops.mesh.primitive_cylinder_add(vertices=192,radius=r,depth=depth,location=(0,0,z))
    o=bpy.context.object; o.name=name; o.data.materials.append(mat); bevel(o); return o

def ring(name,profile,mat,reverse_faces=False):
    if name == 'Rolled black metal rim' and ((profile[1][1] > profile[0][1]) == reverse_faces):
        raise ValueError('Mirrored rim face winding must point outward on both ends.')
    verts=[]; faces=[]; count=192
    for r,z in profile:
        for i in range(count):
            a=2*math.pi*i/count; verts.append((r*math.sin(a),-r*math.cos(a),z))
    for j in range(len(profile)-1):
        for i in range(count):
            k=j*count+i; nxt=j*count+(i+1)%count
            face=(k,nxt,nxt+count,k+count)
            faces.append(tuple(reversed(face)) if reverse_faces else face)
    mesh=bpy.data.meshes.new(name); mesh.from_pydata(verts,[],faces); mesh.update()
    o=bpy.data.objects.new(name,mesh); bpy.context.collection.objects.link(o); mesh.materials.append(mat)
    for poly in mesh.polygons: poly.use_smooth=True
    return o

cyl('Steel shell under paper',1.235,4.03,0,black)
# Seam at the rear; front center is u=.5. Real cylindrical UV interpolation.
verts=[]; faces=[]; N=384
for z in [-1.94,1.94]:
    for i in range(N+1):
        a=-math.pi+2*math.pi*i/N; verts.append((1.25*math.sin(a),-1.25*math.cos(a),z))
for i in range(N): faces.append((i,i+1,N+2+i,N+1+i))
mesh=bpy.data.meshes.new('Continuous cylindrical label'); mesh.from_pydata(verts,[],faces); mesh.update()
o=bpy.data.objects.new('Fully wrapped printed stock',mesh); bpy.context.collection.objects.link(o); mesh.materials.append(label)
uv=mesh.uv_layers.new()
for poly in mesh.polygons:
    poly.use_smooth=True
    for li in poly.loop_indices:
        vi=mesh.loops[li].vertex_index; uv.data[li].uv=(vi%(N+1)/N,vi//(N+1))
for sign in [-1,1]:
    if sign > 0:
        # Keep a closed steel floor beneath the recessed top well.
        cyl('Pressed steel end plate',1.235,.12,1.70,black)
    else:
        cyl('Pressed steel end plate',1.235,.12,sign*2.015,black)
    ring('Rolled black metal rim',[(1.21,sign*1.91),(1.272,sign*1.935),(1.29,sign*1.99),(1.28,sign*2.055),(1.245,sign*2.10),(1.18,sign*2.10),(1.16,sign*2.065)],black,reverse_faces=sign < 0)
    cyl('Spool bearing seat',.58,.065,sign*2.10,black if sign > 0 else plastic)
    if sign > 0:
        # The cap stays sealed, but its broad top face steps down into a dark
        # annular well around the raised bearing seat and hollow winding spindle.
        ring('Recessed top-cap well',[(1.16,2.065),(1.13,1.78),(.61,1.78),(.58,2.0675)],recess)
# Actual open tube with inner wall and recessed dark floor, not a painted circle.
ring('Hollow winding spindle',[(.36,2.10),(.36,2.56),(.335,2.60),(.235,2.60),(.213,2.565),(.213,2.15)],plastic)
cyl('Dark cavity floor',.213,.02,2.145,felt)
cyl('Bottom spool nub',.33,.12,-2.16,plastic)
def surface_strip(name,angle_center,angle_width,z_min,z_max,radius,mat):
    segments=24; verts=[]; faces=[]
    for z in (z_min,z_max):
        for i in range(segments+1):
            angle=angle_center-angle_width/2+angle_width*i/segments
            verts.append((radius*math.sin(angle),-radius*math.cos(angle),z))
    for i in range(segments):
        faces.append((i,i+1,segments+2+i,segments+1+i))
    mesh=bpy.data.meshes.new(name); mesh.from_pydata(verts,[],faces); mesh.update()
    obj=bpy.data.objects.new(name,mesh); bpy.context.collection.objects.link(obj)
    mesh.materials.append(mat)
    for polygon in mesh.polygons: polygon.use_smooth=True
    return obj

# Thin curved layers follow the cylinder at the side slit. They sit on the
# printed-stock radius instead of using boxes that can extend beyond the shell.
SLIT_ANGLE=-1.43
SLIT_RADIUS=1.252
SLIT_HALF_ANGLE=.0175
SLIT_HALF_HEIGHT=1.72
surface_strip('Left light trap backing',-1.48,.22,-1.86,1.86,1.2505,black)
surface_strip('Full height felt opening',SLIT_ANGLE,SLIT_HALF_ANGLE*2,-SLIT_HALF_HEIGHT,SLIT_HALF_HEIGHT,1.251,felt)
surface_strip('Flush slit edge',SLIT_ANGLE+.032,.012,-1.81,1.81,1.2515,black)

# The reference cartridge reads slightly slimmer than the previous render.
# Compress the complete shell radially while keeping the hollow spindle's
# diameter unchanged, so the cap opening remains believable at the new width.
for obj in bpy.context.scene.objects:
    if obj.type != 'MESH':
        continue
    obj.location.x *= SHELL_XY_SCALE
    obj.location.y *= SHELL_XY_SCALE
    obj.scale.x *= SHELL_XY_SCALE
    obj.scale.y *= SHELL_XY_SCALE
    if obj.name == 'Hollow winding spindle':
        obj.scale.x /= SHELL_XY_SCALE
        obj.scale.y /= SHELL_XY_SCALE

scene=bpy.context.scene
scene['modelRevision']=MODEL_REVISION
world=bpy.data.worlds.new('Neutral studio'); scene.world=world; world.use_nodes=True
world.node_tree.nodes['Background'].inputs[0].default_value=(.55,.60,.67,1)
world.node_tree.nodes['Background'].inputs[1].default_value=.16

def aim(o,point): o.rotation_euler=(Vector(point)-o.location).to_track_quat('-Z','Y').to_euler()
def area(name,loc,power,size,color,shape='DISK',size_y=None):
    data=bpy.data.lights.new(name,'AREA'); data.energy=power; data.shape=shape; data.size=size; data.color=color
    if size_y: data.size_y=size_y
    o=bpy.data.objects.new(name,data); scene.collection.objects.link(o); o.location=loc; aim(o,(0,0,.1))
area('Broad upper-left key',(-4,-5,6),620,4.5,(1,.94,.83),'RECTANGLE',6)
area('Quiet right bounce card',(4,-1,3),125,2.5,(.83,.90,1),'RECTANGLE',5)
area('Soft top rim light',(0,3,6),520,4,(1,.95,.88))
area('Low front shadow fill',(0,-7,0),16,4,(1,1,1))
bpy.ops.object.camera_add(location=(0,-16,3.02)); camera=bpy.context.object; aim(camera,(0,0,.20))
camera.data.type='ORTHO'; camera.data.ortho_scale=5.45; scene.camera=camera
scene.render.engine='CYCLES'; scene.cycles.samples=96; scene.cycles.use_denoising=True
scene.render.resolution_x=900; scene.render.resolution_y=1500; scene.render.resolution_percentage=100
scene.render.film_transparent=True; scene.render.image_settings.file_format='PNG'; scene.render.image_settings.color_mode='RGBA'
scene.view_settings.view_transform='AgX'; scene.render.filepath=str(INTERMEDIATE/'render.png')
t.image.pack()
bpy.ops.wm.save_as_mainfile(filepath=str(INTERMEDIATE/'film-cartridge.blend'))
bpy.ops.render.render(write_still=True)
image=Image.open(INTERMEDIATE/'render.png').convert('RGBA'); bounds=image.getchannel('A').getbbox()
pad=8; crop=(max(0,bounds[0]-pad),max(0,bounds[1]-pad),min(image.width,bounds[2]+pad),min(image.height,bounds[3]+pad))
image=image.crop(crop)
save_webp_with_limit(image,OUT/'film-cartridge-shell.webp',(92,88,84,80),250000)

def projected(point):
    v=world_to_camera_view(scene,camera,Vector(point)); return [(v.x*scene.render.resolution_x-crop[0])/image.width,((1-v.y)*scene.render.resolution_y-crop[1])/image.height]
def slit_point(angle,z):
    return (SLIT_RADIUS*math.sin(angle)*SHELL_XY_SCALE,
            -SLIT_RADIUS*math.cos(angle)*SHELL_XY_SCALE,z)
a=projected(slit_point(SLIT_ANGLE,SLIT_HALF_HEIGHT)); b=projected(slit_point(SLIT_ANGLE,-SLIT_HALF_HEIGHT))
left=min(projected(slit_point(SLIT_ANGLE-SLIT_HALF_ANGLE,0))[0],
         projected(slit_point(SLIT_ANGLE+SLIT_HALF_ANGLE,0))[0])
right=max(projected(slit_point(SLIT_ANGLE-SLIT_HALF_ANGLE,0))[0],
          projected(slit_point(SLIT_ANGLE+SLIT_HALF_ANGLE,0))[0])
data={'modelRevision':MODEL_REVISION,'renderFrame':{'width':scene.render.resolution_x,'height':scene.render.resolution_y},'crop':list(crop),'width':image.width,'height':image.height,'coordinateSystem':'normalized image coordinates, origin top left','slit':{'centerY':(a[1]+b[1])/2,'topY':a[1],'bottomY':b[1],'leftX':left,'rightX':right,'centerX':(left+right)/2},'contentBounds':{'left':(bounds[0]-crop[0])/image.width,'top':(bounds[1]-crop[1])/image.height,'right':(bounds[2]-crop[0])/image.width,'bottom':(bounds[3]-crop[1])/image.height},'bodyCenter':projected((0,0,0)),'topCapCenter':projected((0,0,2.1)),'bottomCapCenter':projected((0,0,-2.1)),'physicalDimensionsMm':{'bodyDiameter':23.5,'bodyHeight':42,'totalHeight':48.2,'slitHeight':35,'spindleOuterDiameter':7.2,'spindleInnerDiameter':4.26,'spindleHeight':5.0,'rimHeight':2.0},'cameraElevationDegrees':10,'bytes':(OUT/'film-cartridge-shell.webp').stat().st_size,'sha256':hashlib.sha256((OUT/'film-cartridge-shell.webp').read_bytes()).hexdigest()}
os.replace(INTERMEDIATE/'film-cartridge.blend',CACHE/'film-cartridge.blend')
write_text_atomic(OUT/'film-cartridge.geometry.json',json.dumps(data,indent=2)+'\n')
INTERMEDIATE_ROOT.cleanup()
print(json.dumps(data,indent=2))

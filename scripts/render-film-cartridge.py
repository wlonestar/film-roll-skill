#!/usr/bin/env python3
"""Dev-only Blender 5 / Pillow renderer; see film-cartridge.README.md."""
import argparse
import importlib.util
import json, math, os
from pathlib import Path
import bpy
from mathutils import Vector
from bpy_extras.object_utils import world_to_camera_view
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
MODEL_REVISION = 'true-shell-v10'
SHELL_XY_SCALE = 0.94
VARIANT_IDS = ('kodak-gold-200', 'kodak-portra-400', 'kodak-ektar-100',
               'fuji-superia-400', 'ilford-hp5-400')
parser = argparse.ArgumentParser(description=__doc__)
mode = parser.add_mutually_exclusive_group()
mode.add_argument('--variant', default='light-notes',
                  choices=('light-notes', 'all', *VARIANT_IDS),
                  help='render a built-in label (default: light-notes)')
mode.add_argument('--design-json', type=Path,
                  help='render a custom label from a validated design JSON file')
parser.add_argument('--output-dir', type=Path,
                    help='asset output directory (default: $FILM_ROLL_OUTPUT_DIR or ./output)')
args = parser.parse_args()

CACHE = Path(os.environ.get('FILM_RENDER_CACHE', str(Path.home()/'.cache/film-roll-skill/render'))).expanduser().resolve()
CACHE.mkdir(parents=True, exist_ok=True)
output_dir = args.output_dir or Path(os.environ.get('FILM_ROLL_OUTPUT_DIR', str(ROOT/'output')))
OUT = output_dir.expanduser().resolve()
OUT.mkdir(parents=True, exist_ok=True)

if args.design_json is not None or args.variant != 'light-notes':
    support = Path(__file__).with_name('film-cartridge-variants.py')
    spec = importlib.util.spec_from_file_location('film_cartridge_variants', support)
    variants = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(variants)
    if args.design_json is not None:
        variants.render_custom_design(args.design_json.expanduser().resolve(), CACHE, OUT, MODEL_REVISION)
    else:
        variants.render_variants(args.variant, CACHE, OUT, MODEL_REVISION)
    raise SystemExit(0)

# Preserve the original Light Notes generation path and geometry metadata.
bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)
# Original print artwork, mapped continuously around the full circumference.
W,H=4096,2048
im=Image.new('RGB',(W,H),(177,153,94)); d=ImageDraw.Draw(im)
font='/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
bold='/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
ink=(30,32,29)
def text(s,y,size,width=None,face=bold):
    f=ImageFont.truetype(face,size)
    box=f.getbbox(s); tile=Image.new('RGBA',(box[2]+12,box[3]-box[1]+12))
    ImageDraw.Draw(tile).text((6,6-box[1]),s,font=f,fill=ink)
    if width: tile=tile.resize((width,tile.height),Image.Resampling.LANCZOS)
    im.paste(tile,((W-tile.width)//2,y),tile)
text('LIGHT NOTES',220,155,1530)
text('135',590,690,1580)
text('36 EXP',1450,155,850)
text('PHOTO ARCHIVE',1710,100,1270, font)
def vtext(s,box,color=ink,face=bold):
    f=ImageFont.truetype(face,220)
    b=f.getbbox(s); tile=Image.new('RGBA',(b[2]-b[0]+16,b[3]-b[1]+16))
    ImageDraw.Draw(tile).text((8-b[0],8-b[1]),s,font=f,fill=color)
    tile=tile.rotate(90,expand=True)
    tile=tile.resize((box[2]-box[0],box[3]-box[1]),Image.Resampling.LANCZOS)
    im.paste(tile,box[:2],tile)
# Flat exit-side face beside the felt opening, as on real 135 shells.
d.rectangle((1040,0,1700,2048),fill=(20,21,18))
paperish=(233,227,215)
vtext('36',(1380,260,1660,900),paperish)
vtext('CA135',(1380,960,1620,1560),paperish)
d.rectangle((1120,280,1300,620),outline=paperish,width=12)
vtext('DX',(1140,330,1280,570),paperish)
vtext('LIGHT NOTES',(1060,700,1180,1500),paperish,font)
# Thin wraparound rules and secondary printing on the unseen rear.
d.line((0,135,W,135),fill=ink,width=9)
d.line((0,1910,W,1910),fill=ink,width=9)
for x in range(190,610,20): d.rectangle((x,630,x+8,1280),fill=ink)
im.save(CACHE/'label.png')

def material(name,color,metal=0,rough=.4):
    m=bpy.data.materials.new(name); m.diffuse_color=(*color,1); m.use_nodes=True
    p=m.node_tree.nodes.get('Principled BSDF'); p.inputs['Base Color'].default_value=(*color,1)
    p.inputs['Metallic'].default_value=metal; p.inputs['Roughness'].default_value=rough
    return m
black=material('Black enamel rolled steel',(.018,.021,.024),.34,.38)
plastic=material('Charcoal spindle polymer',(.015,.017,.018),.08,.38)
felt=material('Light trap velvet',(.007,.008,.009),0,.96)
recess=material('Recessed cap interior',(.001,.001,.001),0,1.0)
recess_bsdf=recess.node_tree.nodes.get('Principled BSDF')
specular=recess_bsdf.inputs.get('Specular IOR Level')
if specular: specular.default_value=.02
label=material('Muted ochre printed paper',(.48,.37,.17),0,.46)
n=label.node_tree.nodes; l=label.node_tree.links; p=n.get('Principled BSDF')
t=n.new('ShaderNodeTexImage'); t.image=bpy.data.images.load(str(CACHE/'label.png')); l.new(t.outputs['Color'],p.inputs['Base Color'])
noise=n.new('ShaderNodeTexNoise'); noise.inputs['Scale'].default_value=190
bump=n.new('ShaderNodeBump'); bump.inputs['Strength'].default_value=.12; bump.inputs['Distance'].default_value=.006
l.new(noise.outputs['Fac'],bump.inputs['Height']); l.new(bump.outputs['Normal'],p.inputs['Normal'])

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
# The light trap is on the left tangent. Nothing projects as an extruded film strip.
def box(name,loc,scale,mat,edge):
    bpy.ops.mesh.primitive_cube_add(size=1,location=loc); o=bpy.context.object; o.name=name
    o.dimensions=scale; bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    o.data.materials.append(mat); bevel(o,edge); return o
box('Left light trap backing',(-1.234,-.10,0),(.17,.28,3.88),black,.035)
box('Full height felt opening',(-1.305,-.251,0),(.075,.037,3.5),felt,.012)
box('Front folded slit lip',(-1.247,-.265,0),(.055,.05,3.77),black,.015)

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
world.node_tree.nodes['Background'].inputs[1].default_value=.28

def aim(o,point): o.rotation_euler=(Vector(point)-o.location).to_track_quat('-Z','Y').to_euler()
def area(name,loc,power,size,color,shape='DISK',size_y=None):
    data=bpy.data.lights.new(name,'AREA'); data.energy=power; data.shape=shape; data.size=size; data.color=color
    if size_y: data.size_y=size_y
    o=bpy.data.objects.new(name,data); scene.collection.objects.link(o); o.location=loc; aim(o,(0,0,.1))
area('Broad left softbox',(-4,-5,6),470,5,(1,.94,.83),'RECTANGLE',7)
area('Tall right edge card',(4,-1,3),360,3,(.83,.90,1),'RECTANGLE',6)
area('Top rim softbox',(0,3,6),550,4,(1,.95,.88))
area('Front gentle fill',(0,-7,0),65,4,(1,1,1))
bpy.ops.object.camera_add(location=(0,-16,3.02)); camera=bpy.context.object; aim(camera,(0,0,.20))
camera.data.type='ORTHO'; camera.data.ortho_scale=5.45; scene.camera=camera
scene.render.engine='CYCLES'; scene.cycles.samples=96; scene.cycles.use_denoising=True
scene.render.resolution_x=900; scene.render.resolution_y=1500; scene.render.resolution_percentage=100
scene.render.film_transparent=True; scene.render.image_settings.file_format='PNG'; scene.render.image_settings.color_mode='RGBA'
scene.view_settings.view_transform='AgX'; scene.render.filepath=str(CACHE/'render.png')
bpy.ops.wm.save_as_mainfile(filepath=str(CACHE/'film-cartridge.blend'))
bpy.ops.render.render(write_still=True)
image=Image.open(CACHE/'render.png').convert('RGBA'); bounds=image.getchannel('A').getbbox()
pad=8; crop=(max(0,bounds[0]-pad),max(0,bounds[1]-pad),min(image.width,bounds[2]+pad),min(image.height,bounds[3]+pad))
image=image.crop(crop); image.save(CACHE/'film-cartridge.png')
for quality in [92,88,84,80]:
    image.save(OUT/'film-cartridge.webp',quality=quality,method=6)
    if (OUT/'film-cartridge.webp').stat().st_size<250000: break

def projected(point):
    v=world_to_camera_view(scene,camera,Vector(point)); return [(v.x*scene.render.resolution_x-crop[0])/image.width,((1-v.y)*scene.render.resolution_y-crop[1])/image.height]
a=projected((-1.405*SHELL_XY_SCALE,-.2695*SHELL_XY_SCALE,1.75)); b=projected((-1.405*SHELL_XY_SCALE,-.2695*SHELL_XY_SCALE,-1.75))
left=projected((-1.4425*SHELL_XY_SCALE,-.2695*SHELL_XY_SCALE,0))[0]; right=projected((-1.3675*SHELL_XY_SCALE,-.2695*SHELL_XY_SCALE,0))[0]
data={'modelRevision':MODEL_REVISION,'renderFrame':{'width':scene.render.resolution_x,'height':scene.render.resolution_y},'crop':list(crop),'width':image.width,'height':image.height,'coordinateSystem':'normalized image coordinates, origin top left','slit':{'centerY':(a[1]+b[1])/2,'topY':a[1],'bottomY':b[1],'leftX':left,'rightX':right,'centerX':(left+right)/2},'contentBounds':{'left':(bounds[0]-crop[0])/image.width,'top':(bounds[1]-crop[1])/image.height,'right':(bounds[2]-crop[0])/image.width,'bottom':(bounds[3]-crop[1])/image.height},'bodyCenter':projected((0,0,0)),'topCapCenter':projected((0,0,2.1)),'bottomCapCenter':projected((0,0,-2.1)),'physicalDimensionsMm':{'bodyDiameter':23.5,'bodyHeight':42,'totalHeight':48.2,'slitHeight':35,'spindleOuterDiameter':7.2,'spindleInnerDiameter':4.26,'spindleHeight':5.0,'rimHeight':2.0},'cameraElevationDegrees':10,'bytes':(OUT/'film-cartridge.webp').stat().st_size}
(OUT/'film-cartridge.geometry.json').write_text(json.dumps(data,indent=2)+'\n')
print(json.dumps(data,indent=2))

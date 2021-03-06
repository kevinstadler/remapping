#!/usr/bin/env python2
from mapnik import *
from copy import copy
import cairo
from argparse import ArgumentParser
import colorsys

parser = ArgumentParser(description='Overlay several .osm files on top of each other. By default all layers are translated so that the center of their extents coincide with the center of the target map (which is the origin). Different centers (and map orientations) can be specified per input file with the -lon -lat and --up options. When using those options, it is often safer to pass the osmfile arguments first, to stop the options from eating up all following arguments.')
parser.add_argument('osmfile', help='The OSM data file(s)', nargs='+')

# general rendering & geography
parser.add_argument('-s', '--scale', type=float, help='map scale denominator (i.e. render map as 1:x)')
parser.add_argument('--srs', default='+proj=ortho', help='projection to be used (proj.4 string, default: +proj=ortho)')
parser.add_argument('-lon', '--longitude', type=float, default=[None], help='map center longitude, one per osm file (e.g. -3.1977 -.2326)', nargs='*')
parser.add_argument('-lat', '--latitude', type=float, default=[None], help='map center latitude, one per osm file (e.g. 55.9486 51.5465)', nargs='*')
parser.add_argument('-u', '--up', default=['N'], choices=['N', 'S'], help='"up" orientation of map (currently only supports north and south). Can specify either one (for entire map) or one per osm file for individual rotations.', nargs='*')

# drawing: layer properties
parser.add_argument('-bg', '--background-color', default='white', help='background color (default white)')
parser.add_argument('-col', '--color', help='stroke color, provide one for each layer', nargs='*')
#parser.add_argument('--layer-opacity', type=float, default=[1], help='opacity of all strokes of a layer, provide one for each layer', nargs='*')

# drawing: filter properties
parser.add_argument('--filter', '--draw', default=['[highway] != null'], help='mapnik filter(s) specifying what entities to render (default: a single filter "[highway] != null")', nargs='*')
parser.add_argument('--stroke-width', type=float, default=[0.5], help='stroke width(s) to draw entities with in pt, one per specified filter (default 0.5)', nargs='*')
#parser.add_argument('--stroke-opacity', type=float, default=[1], help='stroke opacity, one per specified filter (default 1.0)', nargs='*')

# extra filters
parser.add_argument('-w', '--water', type=float, nargs='?', const=0.3, help='render water and other natural bodies (optional: specify fill opacity, default 0.3)')
parser.add_argument('-r', '--railways', type=float, nargs='?', const=1, help='render railways (optional: specify stroke width, default 1)')
parser.add_argument('--draw-all', type=float, nargs='?', const=0.5, help="draw all other as yet undrawn data from the input files (using mapnik's ElseFilter). optional: specify stroke width (default 0.5)")

# misc annotation
parser.add_argument('-i', '--include-scale', action='store_true', help='add scale and projection information to the map')
parser.add_argument('-c', '--copyright', action='store_true', help='add copyright information and url to the map')
parser.add_argument('-n', action='store_true', help='add osm file name and center point information for every layer.')
parser.add_argument('--names', nargs='+', help='add the given names and center point information for every layer. to simply re-use the input file names as names, use the -n flag instead.')
parser.add_argument('-g', '--grid', action='store_true', help='add red meridian/parallel lines to the map (latitude and longitude labels are bogus/relative to map center)')

parser.add_argument('-f', '--format', default='a4l', help='Cairo target page format (default a4l)')

parser.add_argument('--width', type=float, help='output file width in meters (overrides --format)')
parser.add_argument('--height', type=float, help='output file height in meters (overrides --format)')
parser.add_argument('-m', '--margin', type=float, default=0, help='page margin in meters (default 0)')

parser.add_argument('-d', '--dpi', type=int, default=72, help='target pdf resolution (default 72)')
parser.add_argument('-o', '--output', default='overlay.pdf', help='output filename (default overlay.pdf)')

args = vars(parser.parse_args())

nlayers = len(args['osmfile'])
if nlayers == 1:
  nlayers = max(1, len(args['longitude']), len(args['latitude']), len(args['up']))
  print 'rendering', nlayers, 'layers from one file'
else:
  print 'rendering from', len(args['osmfile']), 'data files'

def checkarglen(argname):
  if args[argname] != None and len(args[argname]) != nlayers:
    if len(args[argname]) == 1:
     args[argname] = args[argname][0:1] * nlayers
    else:
      print 'number of ' + argname + 's does not match number of layers, ignoring ' + argname + 's'
      args[argname] = None

checkarglen('longitude')
checkarglen('latitude')
checkarglen('up')
#checkarglen('layer_opacity')

checkarglen('color')
if args['color'] == None:
  # pale rainbow
  args['color'] = map(lambda rgb: Color(int(256*rgb[0]), int(256*rgb[1]), int(256*rgb[2])), [colorsys.hsv_to_rgb(i / float(nlayers+1), 0.5, 0.7) for i in range(nlayers)])
else:
  args['color'] = map(Color, args['color'])

if len(args['stroke_width']) != len(args['filter']):
  if len(args['stroke_width']) != 1:
    print "Number of stroke-widths doesn't match number of filters, using", args['stroke_width'][0], 'for all filter rules'
  args['stroke_width'] = args['stroke_width'][0:1] * len(args['filter'])
#args['stroke_opacity'] = args['stroke_opacity'][0:1] * len(args['filter'])

# if only one set, make square
args['width'] = args['width'] or args['height']
args['height'] = args['height'] or args['width']
# --width/--height override --format
if args['width']:
  pagesize = (args['width'], args['height'])
else:
  pagesize = printing.pagesizes[args['format']]

pixelperm = 3571

m = Map(int(pixelperm*pagesize[0]), int(pixelperm*pagesize[1]), args['srs'])

# FIXME doesn't seem to be working, maybe have to use cairo.paint()?
m.background_color = Color(args['background_color'])

def addrule(style, filter, color, width):
  r = Rule()
  r.filter = Filter(filter)
  r.symbols.append(LineSymbolizer(color, width))
  style.rules.append(r)

def addlayer(data, i):
  s = Style()
#  s.opacity = args['layer_opacity'][i]

  if args['water']:
    watercolor = copy(args['color'][i])
    watercolor.a = int(256*args['water'])
    r = Rule() # bodies of water with area
    r.filter = Filter("[water] = 'lake' or [natural] = 'lake' or [landuse] = 'reservoir' or [landuse] = 'water' or [natural] = 'bay'")
    r.symbols.append(PolygonSymbolizer(watercolor)) # FIXME multipolygons
    s.rules.append(r)
    addrule(s, "[waterway] != null", watercolor, args['stroke_width'][0]) # default width

  if args['railways']:
    addrule(s, '[railway] != null', args['color'][i], args['railways'])

  for j in range(len(args['filter'])):
    addrule(s, args['filter'][j], args['color'][i], args['stroke_width'][j])

  if args['draw_all']:
    r = Rule()
    r.set_else(True)
    r.symbols.append(LineSymbolizer(args['color'][i], args['stroke_width'][i]))
    s.rules.append(r)

  name = str(i)
  m.append_style(name, s)
  layer = Layer(name)
  layer.datasource = data
  layer.styles.append(name)
  m.layers.append(layer)

for i in range(nlayers):
  if i == 0 or len(args['osmfile']) > 1:
    print 'loading', args['osmfile'][i]
    ds = Osm(file=args['osmfile'][i])

  addlayer(ds, i)
  # identify center
  tmpcoord = m.layers[-1].envelope().center()
  if args['longitude'][i] == None:
    args['longitude'][i] = tmpcoord.x
  if args['latitude'][i] == None:
    args['latitude'][i] = tmpcoord.y
  if args['longitude'][i] != 0 or args['latitude'][i] != 0 or args['up'][i] != 'N':
    print '  centering layer', str(i+1), 'on', args['longitude'][i], '/', args['latitude'][i]
    # use ob_tran to rotate globe so center is at (0,0)
    # see p.19: ftp://ftp.remotesensing.org/proj/proj.4.3.I2.pdf
    tmpcoord.x = args['longitude'][i]
    tmpcoord.y = args['latitude'][i]
    if args['up'][i] == 'S': # south-up: new up pole is at center.x, center.y-90
      tmpcoord.y = tmpcoord.y - 90
    else: # north-up: new up pole is lon=180+center.x, lat=90-center.y
      tmpcoord.x = 180 + tmpcoord.x
      tmpcoord.y = 90 - tmpcoord.y
      
    m.layers[-1].srs = '+proj=ob_tran +o_proj=latlong +lon_0=180 +o_lon_p=' + str(tmpcoord.x) + ' +o_lat_p=' + str(tmpcoord.y) + ' +to_meter=0.017453292519943295'


# zoom to fit all data, but stay centered on origin
extent = m.layers[0].envelope()
x = min(max(abs(extent[0]), extent[2]), 90)
y = min(max(abs(extent[1]), extent[3]), 90)
m.zoom_to_box(Box2d(-x, -y, x, y))

if args['scale'] != None:
  m.zoom(args['scale'] / m.scale_denominator())
# else: adjust box according to data+page aspect?

surface = printing.PDFPrinter(pagesize=pagesize, margin=args['margin'], resolution=args['dpi'], centering=printing.centering.both, scale=lambda(s):round(s,-1))

print 'Writing map at scale 1:' + str(m.scale_denominator())
surface.render_map(m, args['output'])


# add annotations
ctx = surface.get_context()

if args['grid']: # TODO replace with concentric (distance) circles
  surface.render_on_map_lat_lon_grid(m)

def setstroke(color):
  ctx.set_source_rgba(color.r/255.0, color.g/255.0, color.b/255.0) # color.a/255.0

def addline(txt):
  extent = ctx.text_extents(txt)
  ctx.show_text(txt)
  ctx.rel_move_to(-extent[4], 1.5*extent[3])


# respect margin
ctx.translate(args['margin']*pixelperm, args['margin']*pixelperm)
#ctx.rel_move_to(0, 10)
if args['include_scale']:
  scale = surface.render_scale(m, ctx)
  ctx.rel_move_to(0, scale[1])
  addline(m.srs)

if args['copyright']:
  addline('(c) OpenStreetMap contributors')
  addline('http://github.com/kevinstadler/remap')

if args['names'] != None:
  checkarglen('names')
elif args['n']:
  args['names'] = args['osmfile']

if args['names']:
  if len(args['names']) == 1:
    args['names'] = [args['names'][0]] * nlayers
  for i in range(nlayers):
    setstroke(args['color'][i])
    addline(args['names'][i] + ': ' + str(args['longitude'][i]) + ' / ' + str(args['latitude'][i]))
#  ctx.set_source_rgba()

surface.finish()
print 'successfully wrote to', args['output']

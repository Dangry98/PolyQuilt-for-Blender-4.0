# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTIBILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.

import bpy
import bmesh
import math
import copy
import mathutils
import gpu
from gpu_extras.batch import batch_for_shader
from .pqutil import *
from .dpi import *


dot_line_vertex_shader = '''
uniform mat4 ProjectionMatrix;

in vec2 pos;
in float dist;
out float distance;

void main()
{
    gl_Position = ProjectionMatrix * vec4(pos,0, 1.0f);
    distance = dist;
}
'''

dot_line_fragment_shader = '''
uniform vec4 color;
uniform vec2 line_t;

in float distance;

void main()
{
    float t = line_t.x + line_t.y;
    float a = mod( distance / t , 1 );
    a = step( a , line_t.x / t );

}
'''

def batch_draw( shader , primitiveType , content  , indices = None ) :
    if indices :
        batch = batch_for_shader(shader, primitiveType , content , indices=indices )
    else :
        batch = batch_for_shader(shader, primitiveType , content )
    batch.draw(shader)
    return batch

try :
    shaderEx = gpu.types.GPUShader(dot_line_vertex_shader, dot_line_fragment_shader)
except Exception as e:
    shaderEx = gpu.shader.from_builtin('UNIFORM_COLOR')

shader2D = gpu.shader.from_builtin('UNIFORM_COLOR')
shader3D = gpu.shader.from_builtin('UNIFORM_COLOR')

def draw_circle2D( pos , radius , color = (1,1,1,1), fill = False , subdivide = 64 , dpi = True, width : float = 1.0  ):
    if dpi :
        r = display.dot( radius )
    else :
        r = radius

    dr = math.pi * 2 / subdivide
    vertices = [( pos[0] + r * math.cos(i*dr), pos[1] + r * math.sin(i*dr)) for i in range(subdivide+1)]

    region = bpy.context.region
    shader = gpu.shader.from_builtin('POLYLINE_UNIFORM_COLOR')

    shader.bind()
    shader.uniform_float("color", color)
    shader.uniform_float("lineWidth", width)
    shader.uniform_float("viewportSize", (region.width, region.height))
    gpu.state.blend_set("ALPHA")


    primitiveType = 'TRIS' if fill else 'LINE_STRIP'
    batch_for_shader(shader, primitiveType, {"pos": vertices}).draw(shader)
     

def draw_donuts2D( pos , radius_out , width , rate , color = (1,1,1,1) ):
    r = display.dot(radius_out )
    subdivide = 100
    t = int( max(min(rate,1),0)*subdivide)
    dr = math.pi * 2 / subdivide
    vertices = [( pos[0] + r * math.sin(i*dr), pos[1] + r * math.cos(i*dr)) for i in range(t+1)]

    draw_lines2D( vertices , (0,0,0,color[3]*0.5) , display.dot(width )+ 1.0  )
    draw_lines2D( vertices , color ,  display.dot( width )  )

def draw_points2D( poss , radius , color = (1,1,1,1) ):
    shader2D.bind()
    shader2D.uniform_float("color", color )
    batch_draw(shader2D, 'POINTS', {"pos": poss} )


def draw_lines2D(verts, color=(1, 1, 1, 1), width: float = 1.0):
    region = bpy.context.region
    shader = gpu.shader.from_builtin('POLYLINE_UNIFORM_COLOR')

    shader.bind()
    shader.uniform_float("color", color)
    shader.uniform_float("lineWidth", width)
    shader.uniform_float("viewportSize", (region.width, region.height))
    gpu.state.blend_set("ALPHA")
    batch_for_shader(shader, 'LINE_STRIP', {"pos": verts}).draw(shader)

def draw_dot_lines2D(verts , color = (1,1,1,0.5) , width : float = 2.0 , pattern = (4,2), primitiveType='LINE_STRIP'):
    region = bpy.context.region
    shader = gpu.shader.from_builtin('POLYLINE_UNIFORM_COLOR')
    batch = batch_for_shader(shader, primitiveType, {"pos": verts})
 
    shader.uniform_float("viewportSize", (region.width, region.height))
    shader.uniform_float("lineWidth", width)

    shader.uniform_float("color", color)
    gpu.state.blend_set("ALPHA")
    batch.draw(shader)

def draw_poly2D(verts, color=(1, 1, 1, 1)):
    shader2D.bind()
    shader2D.uniform_float("color", color)
    batch_for_shader(shader2D, 'TRIS', {"pos": verts}).draw(shader2D)


def draw_lines3D(context, verts, color=(1, 1, 1, 1), width: float = 1.0, hide_alpha: float = 1.0, primitiveType='LINE_STRIP'):
    region = bpy.context.region
    shader = gpu.shader.from_builtin('POLYLINE_UNIFORM_COLOR')
    batch = batch_for_shader(shader, primitiveType, {"pos": verts})
 
    shader.uniform_float("viewportSize", (region.width, region.height))
    shader.uniform_float("lineWidth", width)

    shader.uniform_float("color", color)
    gpu.state.blend_set("ALPHA")
    batch.draw(shader)


def draw_Poly3D(context, verts, color=(1, 1, 1, 1), hide_alpha=0.5):
    polys = mathutils.geometry.tessellate_polygon((verts,))
    shader3D.bind()
    gpu.state.blend_set("ALPHA")
    shader3D.uniform_float("color", color)
    batch_for_shader(shader3D, 'TRIS', {"pos": verts}, indices=polys).draw(shader3D)

def draw_pivots3D( poss , radius , color = (1,1,1,1) ):
    shader3D.bind()
    shader3D.uniform_float("color", color)
    batch_draw(shader3D, 'POINTS', {"pos": poss} )



def draw_Face3D( obj , bm : bmesh.types.BMesh , face : bmesh.types.BMFace , color = (1,1,1,1) , isFill = True ):

    if isFill :
        vs = [ obj.matrix_world @ v.vert.co for v in face.loops ]
        polys = mathutils.geometry.tessellate_polygon( (vs,) )
        shader3D.bind()
        shader3D.uniform_float("color", color )
        gpu.state.blend_set("ALPHA")
        batch_draw(shader3D, 'TRIS', {"pos": vs } , indices=polys )
    else :
        verts = []
        for edge in face.edges :
            verts.append( obj.matrix_world @ edge.verts[0].co )
            verts.append( obj.matrix_world @ edge.verts[1].co )
        shader3D.bind()
        shader3D.uniform_float("color", color )
        gpu.state.blend_set("ALPHA")
        batch_draw(shader3D, 'LINES', {"pos": verts} )


def draw_Edge3D(obj, edge: bmesh.types.BMEdge, color=(1, 1, 1, 1), width=1):
    region = bpy.context.region
    shader = gpu.shader.from_builtin('POLYLINE_UNIFORM_COLOR')

    shader.bind()
    shader.uniform_float("viewportSize", (region.width, region.height))
    shader.uniform_float("lineWidth", width)

    shader.uniform_float("color", color)
    gpu.state.blend_set("ALPHA")
    batch_for_shader(shader, 'LINE_STRIP', {"pos": [obj.matrix_world @ edge.verts[0].co, obj.matrix_world @ edge.verts[1].co]}).draw(shader) 


def drawElementsHilight3D( obj , bm : bmesh.types.BMesh  , elements, radius,width ,alpha, color = (1,1,1,1) ) :
    for element in elements :
        drawElementHilight3D(obj , bm , element, radius ,width,alpha, color)

def drawElementsHilight3DFunc( obj , bm : bmesh.types.BMesh , elements, radius,width ,alpha, color = (1,1,1,1) ) :
    funcs = [ drawElementHilight3DFunc(obj ,bm, e, radius ,width,alpha, color) for e in elements ]
    def func() :
        for f in funcs :
            f()
    return func

def drawElementHilight3D( obj , bm : bmesh.types.BMesh , element, radius ,width , alpha, color = (1,1,1,1) ) :
    if isinstance( element , bmesh.types.BMVert ) :
        v = obj.matrix_world @ element.co
        draw_pivots3D( (v,) , radius , color )
    elif isinstance( element , bmesh.types.BMFace  ) :
        draw_Face3D(obj,bm,element, (color[0],color[1],color[2],color[3] * alpha) )
    elif isinstance( element , bmesh.types.BMEdge ) :
        draw_Edge3D(obj,element,color,width)

def drawElementHilight3DFunc( obj  , bm : bmesh.types.BMesh , element, radius ,width , alpha, color = (1,1,1,1) ) :
    matrix_world = copy.copy( obj.matrix_world )

    if isinstance( element , bmesh.types.BMVert ) :
        co = copy.copy(element.co)
        v = matrix_world @ co
        def draw() :
            draw_pivots3D( (v,) , radius , color )
        return draw

    elif isinstance(element, bmesh.types.BMFace):
        vs = [matrix_world @ v.vert.co for v in element.loops]
        polys = mathutils.geometry.tessellate_polygon((vs,))
        def draw():
            shader3D.bind()
            shader3D.uniform_float("color",  (color[0],color[1],color[2],color[3] * alpha) )
            gpu.state.blend_set("ALPHA")
            batch_for_shader(shader3D, 'TRIS', {"pos": vs}, indices=polys).draw(shader3D)
        return draw

    elif isinstance(element, bmesh.types.BMEdge):
        verts = (matrix_world @ element.verts[0].co, matrix_world @ element.verts[1].co)
        def draw():
            region = bpy.context.region
            shader = gpu.shader.from_builtin('POLYLINE_UNIFORM_COLOR')

            shader.bind()
            shader.uniform_float("viewportSize", (region.width, region.height))
            shader.uniform_float("lineWidth",  display.dot( width) )    
            shader.uniform_float("color", (color[0], color[1], color[2], color[3]))
            gpu.state.blend_set("ALPHA")

            batch = batch_for_shader(shader, 'LINES', {"pos": verts} )
            batch.draw(shader)
        return draw

    return None



def DrawFont( text , size , position , offset = (0,0) ) :
    font_id = 0

    blf.size(font_id, int( size * display.pixel_size() ) )
    w,h = blf.dimensions(font_id, text )
    blf.position(font_id, position[0] - w / 2 + display.dot( offset[0] ) , position[1] + h + display.dot( offset[1] ) , 0)
    blf.draw(font_id, text )


def make_mat4_ortho( left, right, bottom, top, _near = - 100, _far = 100) :
    return mathutils.Matrix(
        (
        (2.0 / (right - left),0,0,-(right + left) / (right - left)) ,
        (0,2.0 / (top - bottom),0,-(top + bottom) / (top - bottom)) ,
        (0,0,-2.0 / (_far - _near),-(_far + _near) / (_far - _near)) ,
        (0,0,0,1) )
        )

class push_pop_projection2D:
    def __enter__(self):
        region = bpy.context.region   
        matrix = make_mat4_ortho( 0 , region.width , 0 , region.height )
        gpu.matrix.push()
        gpu.matrix.push_projection()
        gpu.matrix.load_projection_matrix( matrix )
        gpu.matrix.load_identity()
        return self
    def __exit__(self, exc_type, exc_value, traceback):
        gpu.matrix.pop()
        gpu.matrix.pop_projection()
        if (exc_type!=None):
            #return True  #例外を抑制するには
            return False #例外を伝播する



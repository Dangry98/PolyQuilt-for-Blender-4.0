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
import bpy_extras
import collections
import time
from mathutils import *
from ..utils import pqutil
from ..utils import draw_util
from .ElementItem import *
from ..utils.dpi import *

class QMeshOperators :
    def __init__(self,obj , preferences) :
        self.obj = obj
        self.mesh = obj.data
        self.bm = bmesh.from_edit_mesh(self.mesh)
        self.current_matrix = None
        self.__btree = None
        self.__kdtree = None
        self.preferences = preferences
        
    def __del__(self) :
        del self.__btree
        del self.__kdtree

    def _CheckValid( self , context ) :
        active_obj = context.active_object
        if self.obj != context.active_object or self.mesh != context.active_object.data or self.bm.is_valid is False :
            return False
        bm = bmesh.from_edit_mesh(self.mesh)
        if bm != self.bm :
            return False

        return True

    def ensure_lookup_table( self ) :
        # ensure系は一応ダーティフラグチェックしてるので無暗に呼んでいいっぽい？
        self.bm.faces.ensure_lookup_table()
        self.bm.verts.ensure_lookup_table()
        self.bm.edges.ensure_lookup_table()      

    def reload_obj( self , context ) :
        self.obj = context.active_object
        if self.obj != None :
            self.mesh = self.obj.data
            self.bm = bmesh.from_edit_mesh(self.mesh)
            self.ensure_lookup_table()
        else :
            self.mesh = None
            self.bm = None
        self.current_matrix = None
        self.reload_tree()            

    def reload_tree( self ) :
        if self.__btree :
            del self.__btree
            self.__btree = None
        if self.__kdtree :
            del self.__kdtree
            self.__kdtree = None


    def UpdateMesh( self , changeTopology = True , loop_triangles = True,destructive = True ) :
        self.bm.normal_update()
        self.ensure_lookup_table()
        self.obj.data.update_gpu_tag()
        self.obj.data.update_tag()
        self.obj.update_tag()
        bmesh.update_edit_mesh(self.obj.data , loop_triangles = loop_triangles,destructive = destructive )
#       self.obj.update_from_editmode()
        if changeTopology :
            self.__btree = None
            self.__kdtree = None
            self.current_matrix = None    

    @property
    def btree(self):
        if self.__btree == None :
            self.__btree = bvhtree.BVHTree.FromBMesh(self.bm)
        return self.__btree

    @property
    def kdtree(self):
        if self.__kdtree == None :
            size = len(self.bm.verts)
            self.__kdtree = mathutils.kdtree.KDTree(size)
            for i, v in enumerate(self.bm.verts):
                self.__kdtree.insert(v.co, i)
            self.__kdtree.balance()
        return self.__kdtree

    @property
    def verts(self): 
        return self.bm.verts

    @property
    def faces(self) :
        return self.bm.faces

    @property
    def edges(self):
        return self.bm.edges

    @property
    def is_mirror_mode(self) :
        return self.mesh.use_mirror_x

    def check_mirror(self , is_mirror ) :
        r = self.is_mirror_mode if is_mirror is None else is_mirror
        return r

    def local_to_world_pos(  self ,pos : Vector ) :
        return self.obj.matrix_world @ pos

    def world_to_local_pos(  self ,pos : Vector ) :
        return self.obj.matrix_world.inverted() @ pos

    def local_to_world_nrm(  self , norm : Vector ) :
        p0 = self.obj.matrix_world @ Vector( (0,0,0) )
        p1 = self.obj.matrix_world @ norm
        return ( p0 - p1 ).normalized()

    def world_to_local_nrm(  self , norm : Vector ) :
        inv = self.obj.matrix_world.inverted()
        p0 = inv @ Vector( (0,0,0) )
        p1 = inv @ norm
        return ( p0 - p1 ).normalized()


    def world_to_2d(  self ,pos : Vector ) :
        return pqutil.location_3d_to_region_2d( pos )

    def local_to_2d(  self ,pos : Vector ) :
        return pqutil.location_3d_to_region_2d( self.obj.matrix_world @ pos )

    @staticmethod
    def mirror_pos( pos : Vector ) :
        return Vector( (-pos[0],pos[1],pos[2]) )

    def mirror_pos_w2l( self , pos : Vector ) :
        wp = self.world_to_local_pos(pos)
        wp[0] = - wp[0]
        return self.local_to_world_pos(wp)

    @staticmethod
    def zero_pos( pos : Vector ) :
        return Vector( (0,pos[1],pos[2]) )

    @staticmethod
    def zero_vector( norm : Vector ) :
        return Vector( (0,norm[1],norm[2]) ).normalized() * norm.length

    def zero_pos_w2l( self , pos : Vector ) :
        wp = self.world_to_local_pos(pos)
        wp[0] = 0
        return self.local_to_world_pos(wp)


    @staticmethod
    def is_x_zero_pos( pos : Vector ) :
        dist = bpy.context.scene.tool_settings.double_threshold
        return abs(pos[0]) < dist

    def is_x_zero_pos_w2l( self , pos : Vector ) :
        wp = self.world_to_local_pos(pos)        
        dist = bpy.context.scene.tool_settings.double_threshold
        return abs(wp[0]) < dist

    def is_snap( self , p0 : Vector  , p1 : Vector  ) :
        t0 = pqutil.location_3d_to_region_2d(p0)
        t1 = pqutil.location_3d_to_region_2d(p1)
        return self.is_snap2D(t0,t1)

    def is_snap2D( self , p0 : Vector  , p1 : Vector  ) :
        dist = display.dot( self.preferences.distance_to_highlight )
        return ( p0 - p1 ).length <= dist

    def is_x0_snap( self , p  : Vector  ) :
        p0 = pqutil.location_3d_to_region_2d( p )
        p1 = pqutil.location_3d_to_region_2d( self.mirror_pos_w2l(p) )
        if p0 == None or p1 == None :
            return False
        dist = display.dot(self.preferences.distance_to_highlight )  
        return ( p0 - p1 ).length <= dist

    def mirror_world_pos( self , world_pos ) :
        pos = self.obj.matrix_world.inverted() @ world_pos
        rpos = self.mirror_pos(pos)
        wpos = self.obj.matrix_world @ rpos
        return wpos

    def mirror_world_poss( self , poss ) :
        return [ self.mirror_world_pos(pos) for pos in poss ]

    def check_near( self , v0 , v1 ) :
        if v0 == None or v1 == None :
            return False
        c0 = pqutil.location_3d_to_region_2d( self.obj.matrix_world @ v0 )
        c1 = pqutil.location_3d_to_region_2d( self.obj.matrix_world @ v1 )        
        if c0 == None or c1 == None :
            return False
        radius = display.dot(self.preferences.distance_to_highlight )
        return (c0-c1).length <= radius 


    def AddVertex( self , local_pos : Vector , is_mirror = None ) :
        vert = self.bm.verts.new( local_pos )
        if self.check_mirror(is_mirror) and self.is_x_zero_pos(local_pos) is False :
            mirror = self.bm.verts.new( self.mirror_pos(local_pos) )
        self.bm.verts.index_update()
        return vert

    def AddVertexWorld( self , world_pos : Vector , is_mirror = None ) :
        p = self.obj.matrix_world.inverted() @ world_pos
        vert = self.AddVertex( p , is_mirror )
        return vert

    def AddFace( self , verts , normal = None , is_mirror = None ) :
        self.ensure_lookup_table()
        verts = list(verts)
        if len(verts) < 3:
            return None
        face = self.bm.faces.new( verts )
        if face == None :
            return None

        linkCount = 0
        for loop in [ l for l in face.loops if not l.edge.is_boundary ] :
            for  link in loop.link_loops :
                if link != loop :
                    if link.vert == loop.vert :
                        linkCount = linkCount + 1
                    else :
                        linkCount = linkCount - 1

        if linkCount > 0 :
            face.normal_flip()
            face.normal_update()           

        if linkCount == 0 and normal != None :
            face.normal_update()
            dp = face.normal.dot( self.obj.matrix_world.inverted().to_3x3() @ normal )
            if dp > 0.0 :
                face.normal_flip()
                face.normal_update()           
                verts = verts[::-1] 

        if self.check_mirror(is_mirror) :
            verts = list(face.verts)[::-1]
            mirror = [ self.find_mirror(v,False) for v in verts  ]
            mirror = [ m if m != None else self.bm.verts.new( self.mirror_pos(o.co) ) for o,m in zip(verts, mirror) ]
            self.ensure_lookup_table()

            if all(mirror) :
                if set(verts) ^ set(mirror) :
                    face_mirror = self.AddFace( mirror , normal , False )

        return face

    def add_edge( self , v0 , v1 , is_mirror = None ) :
        edge = self.bm.edges.get( (v0,v1) )        
        if edge is None :
            edge = self.bm.edges.new( (v0,v1) )

        if self.check_mirror(is_mirror) :
            m0 = self.find_mirror( v0 , False )
            m1 = self.find_mirror( v1 , False )
            if m0 is not None and m1 is not None :
                if m0 == v0 and m1 == v1 :
                    pass
                else :
                    self.add_edge( m0 , m1 , False )

        return edge

    def Remove( self , geom , is_mirror = None ) :
        geoms = (geom,)
        if self.check_mirror(is_mirror) :
            mirror = self.find_mirror(geom)
            if mirror is not None :
                geoms = (geom,mirror)
        if isinstance( geom , bmesh.types.BMVert ) :
            bmesh.ops.delete( self.bm , geom = geoms , context = 'VERTS' )
        elif isinstance( geom , bmesh.types.BMFace ) :
            bmesh.ops.delete( self.bm , geom = geoms , context = 'FACES' )
        elif isinstance( geom , bmesh.types.BMEdge ) :
            bmesh.ops.delete( self.bm , geom = geoms , context = 'EDGES' )

    # BMesh Operators

    def delete_faces( self , faces , is_mirror = None ) :
        if self.check_mirror(is_mirror) :
            mirror_faces = [self.find_mirror(face) for face in faces ]
            mirror_faces = {face for face in mirror_faces if face is not None }
            faces = list( set(faces) | mirror_faces )
        bmesh.ops.delete( self.bm , geom = faces , context = 'FACES' )

    def delete_edges( self , edges , is_mirror = None ) :
        if self.check_mirror(is_mirror) :
            mirror_edges = [self.find_mirror(edge) for edge in edges ]
            mirror_edges = {edge for edge in mirror_edges if edge is not None }
            edges = list( set(edges) | mirror_edges )
        bmesh.ops.delete( self.bm , geom = edges , context = 'FACES' )


    def dissolve_vert( self , vert  , use_verts = False , use_face_split = False , use_boundary_tear = False, dissolve_vert_angle = 180, is_mirror = None  ) :
        if vert.is_manifold == False :
            self.Remove( vert , is_mirror )
        else :
            verts = [vert,]
            if self.check_mirror(is_mirror) :
                mirror = self.find_mirror( vert )
                if mirror != None :
                    verts = [vert,mirror]

            other_verts = set()
            for vt in verts : 
                for e in vt.link_edges : 
                    ov = e.other_vert(vt)
                    if ov not in verts and len(ov.link_edges) > 2 :
                        other_verts.add( ov )
            bmesh.ops.dissolve_verts( self.bm , verts  = verts , use_face_split = use_face_split , use_boundary_tear = use_boundary_tear )
            other_verts = self.calc_limit_verts( other_verts , dissolve_vert_angle = dissolve_vert_angle , is_mirror = False )
            bmesh.ops.dissolve_verts( self.bm , verts  = other_verts , use_face_split = use_face_split , use_boundary_tear = use_boundary_tear )

    def dissolve_edge( self , edge , use_verts = False , use_face_split = False , dissolve_vert_angle = 180 , is_mirror = None  ) :
        self.dissolve_edges( [edge,] , use_verts , use_face_split, dissolve_vert_angle , is_mirror )

    def dissolve_edges( self , edges , use_verts = False , use_face_split = False, dissolve_vert_angle = 180 , is_mirror = None ) :
        if self.check_mirror(is_mirror) :
            mirror_edges = [self.find_mirror(edge) for edge in edges ]
            mirror_edges = {edge for edge in mirror_edges if edge is not None }
            edges = list( set(edges) | mirror_edges )

        verts = {}
        for e in edges :
            verts[ e.verts[0] ] = e.is_wire
            verts[ e.verts[1] ] = e.is_wire

        for edge in edges :
            if edge.is_valid :
                if edge.is_boundary :
                    bmesh.ops.delete( self.bm , geom = [edge] , context = 'EDGES' )
                elif edge.is_wire :
                    bmesh.ops.delete( self.bm , geom = [edge] , context = 'EDGES' )
                else :
                    bmesh.ops.dissolve_edges( self.bm , edges = [edge] , use_verts = use_verts , use_face_split = use_face_split )

        # 独立頂点を削除
        delete_Verts = [ v for v , w in verts.items() if v.is_valid and len(v.link_edges) == 0 ]
        bmesh.ops.delete( self.bm , geom = delete_Verts , context = 'VERTS' )
        delete_Verts = [ v for v , w in verts.items() if v.is_valid and len(v.link_edges) == 1 and not w ]
        bmesh.ops.delete( self.bm , geom = delete_Verts , context = 'VERTS' )

        dissolve_verts = [ v for v in verts if v.is_valid ]

        if dissolve_vert_angle > 0 :
            dissolve_verts = self.calc_limit_verts( dissolve_verts , dissolve_vert_angle = dissolve_vert_angle , is_mirror = False )
        if len(dissolve_verts) > 0 :
            bmesh.ops.dissolve_verts( self.bm , verts  = dissolve_verts , use_face_split = use_face_split , use_boundary_tear = False  )

    def calc_limit_verts( self , verts , dissolve_vert_angle  = 180 , is_mirror = None ) :
        removes = set()
        for vert in [ v for v in verts if v.is_valid and len(v.link_edges) == 2 ] :
            n0 = (vert.link_edges[0].other_vert(vert).co - vert.co).normalized()
            n1 = (vert.link_edges[1].other_vert(vert).co - vert.co).normalized()
            r = max( min( n0.dot(n1) , 1 ) , -1 )
            r = math.acos(r)
            r = math.ceil(math.degrees(r))
            if r > dissolve_vert_angle :
                removes.add(vert)
                if self.check_mirror(is_mirror) :
                    mirror = self.find_mirror( vert )
                    if mirror != None :
                        removes.add(mirror)                
        return list(removes)


    def dissolve_limit_verts( self , verts , dissolve_vert_angle  = 180 , is_mirror = None ) :
        removes = self.calc_limit_verts(verts , dissolve_vert_angle  , is_mirror = None)
        if removes :          
            bmesh.ops.dissolve_verts( self.bm , verts  = removes , use_face_split = False , use_boundary_tear = False )

    def dissolve_faces( self , fades , use_verts = False ) :
        return bmesh.ops.dissolve_faces( self.bm , fades = fades , use_verts = use_verts )

    def face_split( self , face , v0 , v1 , coords = () , use_exist=True, example=None, is_mirror = None  ) :
        """Face split with optional intermediate points."""
        if self.check_mirror(is_mirror) :
            mirror_face = self.find_mirror(face , False)
            mirror_v0 = self.find_mirror(v0 , False)
            mirror_v1 = self.find_mirror(v1 , False)
            if None not in ( mirror_face , mirror_v0 , mirror_v1 ) :
                if (mirror_v0 == v0 and mirror_v1 == v1) or (mirror_v0 == v1 and mirror_v1 == v0) :
                    pass
                else :
                    new_face , new_edge = bmesh.utils.face_split( mirror_face , mirror_v0  , mirror_v1 , coords = coords , use_exist = use_exist )
                    if (v0 not in face.verts or v1 not in face.verts ) and (v0 not in new_face.verts or v1 not in new_face.verts ):
                        return
                    if v0 in new_face.verts and v1 in new_face.verts :
                        return bmesh.utils.face_split( new_face , v0  , v1 )
            
        return bmesh.utils.face_split( face , v0  , v1 , coords = coords , use_exist = use_exist )

    def __calc_split_fac( self , edge , refPos ) :
        fac = 0.5
        d0 = (edge.verts[0].co - refPos ).length
        d1 = (edge.verts[1].co - refPos ).length
        fac = d0 / (d0 + d1)
        return fac

    def edge_split_from_position( self , edge , refPos , is_mirror = None):
        mirror_edge = None
        if self.check_mirror(is_mirror) and self.is_x_zero_pos( refPos ) is False :
            mirror_edge = self.find_mirror( edge , False )

        fac = self.__calc_split_fac( edge , refPos )
        new_edge , new_vert = bmesh.utils.edge_split( edge , edge.verts[0] , fac )

        if mirror_edge is not None :
            if new_edge is mirror_edge :
                if set(edge.verts) & set(mirror_edge.verts) :
                    mirror_edge = new_edge
            rfac = self.__calc_split_fac( mirror_edge , self.mirror_pos(refPos) )
            bmesh.utils.edge_split( mirror_edge , mirror_edge.verts[0] , rfac )

        return new_edge , new_vert


    def weld( self , targetmap ) :
        bmesh.ops.weld_verts(self.bm,targetmap)

    def set_positon( self , geom , pos , is_world = True ) :            
        if is_world :
            pos = self.obj.matrix_world.inverted() @ pos   
        geom.co = pos

    def test_mirror( self , v0 , v1 ) :
        dist = bpy.context.scene.tool_settings.double_threshold
        p0 = Vector((-v0[0],v0[1],v0[2]))
        p1 = v1
        return (p0 - p1).length <= dist

    def test_mirror_geom( self , geom0 , geom1 ) :
        if type(geom0) == type(geom1) :
            if isinstance( geom0 , bmesh.types.BMVert ) :
                return self.test_mirror( geom0.co , geom1.co )
            elif isinstance( geom0 , bmesh.types.BMFace ) or isinstance( geom0 , bmesh.types.BMEdge ):
                for vert0 in geom0.verts :
                    if not any( [ self.test_mirror(vert0.co,vert1.co) for vert1 in geom1.verts] ) :
                        break
                else :
                    return True
        return False



    def find_mirror( self , geom , check_same = True ) :
        result = None
        dist = bpy.context.scene.tool_settings.double_threshold

        if isinstance( geom , bmesh.types.BMVert ) :
            co = self.mirror_pos( geom.co )

            hits = self.kdtree.find_range(co, dist )

            if hits != None :
                if len(hits) == 1 :
                    result = self.bm.verts[hits[0][1]] 
                elif len(hits) > 0 :
                    hits = sorted( hits , key=lambda x:x[2])
                    result = self.bm.verts[ hits[0][1] ] 
                    for h in hits :
                        hitV = self.bm.verts[h[1]]
                        for edge in geom.link_edges :
                            if not any( [ self.test_mirror_geom(edge,e) for e in hitV.link_edges ]):
                                break
                        else :
                            result = hitV
                            break
        elif isinstance( geom , bmesh.types.BMFace ) or isinstance( geom , bmesh.types.BMEdge ):
            mirror_cos = [ self.mirror_pos( v.co ) for v in geom.verts ]

            hits = self.kdtree.find_range(mirror_cos[0], dist )
            if hits != None :
                for hit in hits :
                    hitvert = self.bm.verts[hit[1]]                    
                    links = hitvert.link_edges if isinstance( geom , bmesh.types.BMEdge ) else hitvert.link_faces
                    for link in links :
                        if self.test_mirror_geom( link , geom ) :
                            result = link
                            break
                    else :
                        continue
                    break

        if check_same and result is not None and result.index == geom.index :
            return None

        return result

    def find_near( self , pos : mathutils.Vector , is_mirror = None ) :
        threshold = bpy.context.scene.tool_settings.double_threshold
        hits = set()

        ipos = self.obj.matrix_world.inverted() @ pos   
        pts = self.kdtree.find_range( ipos , threshold )
        if pts :
            hits = set([ self.bm.verts[i] for p , i ,d in pts ])

        if self.check_mirror(is_mirror) and self.is_x_zero_pos( pos ) is False :
            mpos = self.obj.matrix_world.inverted() @ pos
            mpos.x = -mpos.x
            mpts = self.kdtree.find_range( mpos , threshold )
            if mpts :            
                mhits = set([ self.bm.verts[i] for p , i ,d in mpts ])
                return mhits | hits

        return hits


    @staticmethod
    def get_shading(context):
        # Get settings from 3D viewport or OpenGL render engine
        view = context.space_data
        if view.type == 'VIEW_3D':
            return view.shading
        else:
            return context.scene.display.shading


    def calc_edge_loop( self , startEdge , check_func = None , is_mirror = None ) :
        if not isinstance( startEdge , bmesh.types.BMEdge ) :
            return [] ,[]

        edges = [startEdge]
        verts = [startEdge.verts[0],startEdge.verts[1]]

        def append( lst , geom ) :
            if geom not in lst :
                lst.append(geom)

        def check( src , dst ) :
            if src != dst :
                 if len(dst.link_faces) == satrt_link_face_cnt :
                     if not set(src.link_faces) & set(dst.link_faces) :
                         src_edges = sum( ( tuple(f.edges) for f in src.link_faces ) , () )
                         if all( ( set(src_edges) & set( f.edges ) for f in  dst.link_faces  ) )  :
                             return True
            return False

        satrt_link_face_cnt = len( startEdge.link_faces )

        loop_verts = [ (startEdge,startEdge.verts[0] ), (startEdge,startEdge.verts[1]) ]
        while( len(loop_verts) > 0 ) :
            cur_edge = loop_verts[-1][0]
            cur_vert = loop_verts[-1][1]
            loop_verts.pop(-1)

            if check_func != None and not check_func(cur_edge,cur_vert) :
                continue

            est_edges = [ e for e in cur_vert.link_edges if check(cur_edge , e) ]
            if len(est_edges) == 1 :
                append_edge = est_edges[0]
                if len(append_edge.link_faces) == satrt_link_face_cnt and  append_edge not in edges :
                    other_vert = append_edge.other_vert(cur_vert)
#                    if other_vert.is_boundary or  len( other_vert.link_faces ) == len(cur_vert.link_faces ) :
                    loop_verts.append( (append_edge , other_vert ) )
                    append( edges , append_edge)
                    if cur_vert not in verts :
                        append( verts , cur_vert )

        if self.check_mirror(is_mirror) :
            edges.extend( [ m for m in ( self.find_mirror( e ) for e in edges ) if m and m not in edges ] )
            verts.extend( [ m for m in ( self.find_mirror( v ) for v in verts ) if m and m not in verts ] )

        return edges , verts



    def collect_loops( self , source_loop : bmesh.types.BMLoop , edgeloops ) :
        def next( loop , rh , start ) :
            if rh :
                next_loop = loop.link_loop_next
                radial = next_loop.link_loop_radial_next
            else :
                next_loop = loop.link_loop_prev
                radial = next_loop.link_loop_radial_next

            if next_loop != radial :
                t = rh if next_loop.vert != radial.vert else not rh
                link = radial.link_loop_next if t else radial.link_loop_prev
                if link != start and link.edge in edgeloops :
                    return link , t

            return None , rh

        lnext = source_loop
        rh = True
        eol = None
        while( lnext ) :
            eol = lnext
            lnext , rh = next(lnext , rh , source_loop )

        loops = []
        rh = not rh
        lnext = eol
        while( lnext ) :
            loops.append(lnext)
            lnext , rh = next(lnext , rh , eol)

        return loops

    @staticmethod
    def calc_loop_face( edge ) :
        chk = []
        def opposite_side( loop , edge ) :
            while( loop ) :
                loop = loop.link_loop_next
                if loop.edge == edge :
                    break
            loop = loop.link_loop_next
            loop = loop.link_loop_next
            return loop.edge if loop.edge not in chk else None

        loops = []
        def step( edge ) :
            chk.append(edge)
            nLinkFace = len(edge.link_faces)
            if nLinkFace > 2 or nLinkFace <= 0 :
                return []
            quads = [ f for f in edge.link_faces if len( f.edges ) == 4 and f not in loops ]
            loops.extend( quads )
            opposite = [ opposite_side( q.loops[0] , edge ) for q in quads ]
            return [ o for o in opposite if o ]

        edges = step(edge)
        while( edges ) :
            edges = [ step( e ) for e in edges ]
            edges = [ e for e in sum(edges, []) if e ]
        return loops


    def calc_edge_boundary_loop( self , startEdge , check_func = None , is_mirror = None ) :
        if not isinstance( startEdge , bmesh.types.BMEdge ) :
            return [] ,[]

        if startEdge.is_manifold :
            return [] ,[]

        edges = [startEdge]
        verts = [startEdge.verts[0],startEdge.verts[1]]

        for vert in verts :
            cur = vert
            while(cur) :
                if len( [ e for e in cur.link_edges if e in edges ] ) == 2 :
                    break

                links = [ e for e in cur.link_edges if not e.is_manifold and e not in edges ]
                if len(links) == 1 :
                    next = links[0]
                    edges.append( next )
                    cur = next.other_vert(cur)
                    if cur not in verts :
                        verts.append(cur)
                    else :
                        break
                else :
                    break
        return edges , verts


    def select_flush( self ) :
        for face in self.bm.faces :
            face.select_set(False)
        for edge in self.bm.edges :
            edge.select_set(False)
        for vert in self.bm.verts :
            vert.select_set(False)
        self.bm.select_history.clear()                        
        self.bm.select_flush(False)

    def select_component( self , component , select = True ) :
        select_mode_log = self.bm.select_mode
        if isinstance( component , bmesh.types.BMVert ) :
            self.bm.select_mode = {'VERT'}
            component.select_set(select)
        elif isinstance( component , bmesh.types.BMEdge ) :
            self.bm.select_mode = {'EDGE'}
            component.select_set(select)
        elif isinstance( component , bmesh.types.BMFace ) :
            self.bm.select_mode = {'FACE'}
            component.select_set(select)
        else :
            return

        if select :
            self.bm.select_history.add( component )
        else :
            self.bm.select_history.discard( component )

        self.bm.select_mode = select_mode_log

    def select_components( self , components , select = True ) :
        for component in components :
            self.select_component(component,select)
            if select :
                self.bm.select_history.add( component )
            else :
                self.bm.select_history.discard( component )

    def calc_shortest_pass( self , bm , start , end , boundaryOnly = False ) :
        from .QMesh import SelectStack        

        if isinstance( start , bmesh.types.BMFace ) :
            for edge in start.edges :
                if end in edge.link_faces :
                    return ([start,end],[])
        elif isinstance( start , bmesh.types.BMEdge ) :
            for vert in start.verts :
                if end in vert.link_edges :
                    return ([start,end],[])
        elif isinstance( start , bmesh.types.BMVert ) :
            for edge in start.link_edges :
                if end in edge.verts :
                    return ([edge],[])

        def calc( s , e ) :
            if s == e :
                return [s]

            if isinstance( e , bmesh.types.BMVert ) and isinstance( s , bmesh.types.BMVert ) :
                for le in s.link_edges :
                    if le.other_vert( s ) == e :
                        return [le]

            bpy.ops.mesh.select_all(action='DESELECT')
            bm.select_history = []
            s.select = True
            e.select = True
            bpy.context.tool_settings.mesh_select_mode = ( isinstance( s , bmesh.types.BMVert ) , isinstance( s , bmesh.types.BMEdge ) , isinstance( s , bmesh.types.BMFace ) )
            bpy.ops.mesh.shortest_path_select( edge_mode = 'SELECT' , use_face_step = False , use_topology_distance = False , use_fill = False )

            ss = []
            if isinstance( s , bmesh.types.BMFace ) :
                ss = [ f for f in bm.faces if f.select ]
            elif isinstance( s , bmesh.types.BMEdge ) :
                ss = [ f for f in bm.edges if f.select ]
            elif isinstance( s , bmesh.types.BMVert ) :
                ss = [ f for f in bm.edges if f.select ]
                if not ss :
                    ss = [ f for f in bm.verts if f.select ]

            bpy.ops.mesh.select_all(action='DESELECT')

            return ss


        select = SelectStack( bpy.context , bm )
        select.push()

        if boundaryOnly :
            hides = [ e for e in bm.edges if not (e.is_boundary or e.is_wire) and not e.hide ]
            for hide in hides :
                hide.hide_set(True)

        if isinstance( start , bmesh.types.BMVert ) and isinstance( end , bmesh.types.BMEdge ) :
            c0 = calc( start , end.verts[0] )
            c1 = calc( start , end.verts[1] )
            l0 = sum( [ e.calc_length() for e in c0 if isinstance( e , bmesh.types.BMEdge ) ] )
            l1 = sum( [ e.calc_length() for e in c1 if isinstance( e , bmesh.types.BMEdge ) ] )
            collect = c0 if l0 < l1 else c1
            if end not in collect :
                collect.append( end )
        elif isinstance( start , bmesh.types.BMEdge ) and isinstance( end , bmesh.types.BMVert ) :
            c0 = calc( start.verts[0] , end )
            c1 = calc( start.verts[1] , end )
            l0 = sum( [ e.calc_length() for e in c0 if not isinstance( e , bmesh.types.BMVert ) ] )
            l1 = sum( [ e.calc_length() for e in c1 if not isinstance( e , bmesh.types.BMVert ) ] )
            collect = c0 if l0 < l1 else c1
            if start not in collect :
                collect.append( start )
        else :
            collect = calc( start , end )

        select.pop()

        if boundaryOnly :
            for hide in hides :
                hide.hide_set(False)

        return ( collect , [] )

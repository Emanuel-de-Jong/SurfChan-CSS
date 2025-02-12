import os
import pickle
import numpy as np
from valvevmf import Vmf
from scipy.spatial import cKDTree

SHOULD_CACHE_VMF = True
SHOULD_CACHE_TREE = False
MAP_CACHE_DIR = "map_cache"

class MapObjects:
    def __init__(self, map_name):
        os.makedirs(MAP_CACHE_DIR, exist_ok=True)

        vmf_cache_path = f"{MAP_CACHE_DIR}/surf_{map_name}_vmf.pkl"
        if os.path.exists(vmf_cache_path):
            with open(vmf_cache_path, "rb") as file:
                vmf = pickle.load(file)
        else:
            vmf = Vmf(f"css_server/server/cstrike/maps/surf_{map_name}.vmf")
            if SHOULD_CACHE_VMF and vmf is not None:
                with open(vmf_cache_path, "wb") as file:
                    pickle.dump(vmf, file)

        obj_centroids = self._filter_vmf(vmf)

        tree_cache_path = f"{MAP_CACHE_DIR}/surf_{map_name}_tree.pkl"
        if os.path.exists(tree_cache_path):
            with open(tree_cache_path, "rb") as file:
                self.obj_tree = pickle.load(file)
        else:
            self._create_obj_tree(obj_centroids)
            if SHOULD_CACHE_TREE and self.obj_tree is not None:
                with open(tree_cache_path, "wb") as file:
                    pickle.dump(self.obj_tree, file)
    
    def _filter_vmf(self, vmf):
        self.objs = []
        obj_centroids = []
        
        for node in vmf.nodes:
            if node.name in ["world", "entity"]:
                classname = None
                solid = False
                
                if node.name == "entity":
                    for prop, val in node.properties:
                        if type(val) != str:
                            continue

                        prop = prop.lower().strip()
                        val = val.lower().strip()

                        if prop == "classname":
                            classname = val
                        elif prop in ["solid", "physbox"]:
                            solid = True

                for subnode in node.nodes:
                    if subnode.name == "solid":
                        if not self._has_collision(node.name, classname, solid):
                            continue
                        
                        centroid = self._calc_obj_centroid(subnode)
                        if centroid is None:
                            continue
                        
                        self.objs.append(subnode)
                        obj_centroids.append(centroid)
        
        return obj_centroids

    def _has_collision(self, node_type, classname, solid_flag):
        if node_type == "world":
            return True

        if solid_flag:
            if classname in ["func_clip", "trigger_multiple", "func_illusionary"]:
                return False
            return True

        if not classname:
            return False

        if classname.startswith("trigger_") or "illusionary" in classname:
            return False

        collidable_classes = [
            "func_detail", "func_brush", "func_wall", "func_physbox",
            "prop_static", "prop_dynamic", "prop_physics"
        ]

        return classname in collidable_classes

    def _calc_obj_centroid(self, obj):
        planes = []
        for node in obj.nodes:
            if node.name == "side":
                for property in node.properties:
                    if property[0] == "plane":
                        planes.append(property)
        
        points = []
        for plane in planes:
            for vertex in plane[1]:
                points.append([float(coord) for coord in vertex])

        if len(points) < 3:
            return None

        points = np.array(points)
        
        min_corner = np.min(points, axis=0)
        max_corner = np.max(points, axis=0)

        diagonal_len = np.linalg.norm(max_corner - min_corner)
        if diagonal_len < 5:
            return None

        return (min_corner + max_corner) / 2.0

    def _create_obj_tree(self, obj_centroids):
        self.obj_tree = None
        if not obj_centroids:
            return
        
        obj_centroids = np.array(obj_centroids)
        self.obj_tree = cKDTree(obj_centroids)

    def get_near_objects(self, coord, k=5, radius=None):
        coord = np.array(coord)

        if radius is not None:
            indices = self.obj_tree.query_ball_point(coord, r=radius)
        else:
            _, indices = self.obj_tree.query(coord, k=k)

        if isinstance(indices, int):
            indices = [indices]

        return [self.objs[i] for i in indices]

if __name__ == '__main__':
    map_objects = MapObjects("beginner")
    
    player_pos = (-128.0, 0.0, 372.0)
    nearby_objs = map_objects.get_near_objects(player_pos, k=5)

    print(f"Found {len(nearby_objs)} nearby objects:")
    for obj in nearby_objs:
        print(obj)

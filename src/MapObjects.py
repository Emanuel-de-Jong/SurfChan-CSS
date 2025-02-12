import os
import pickle
import numpy as np
from valvevmf import Vmf
from scipy.spatial import cKDTree

SHOULD_CACHE_VMF = True
SHOULD_CACHE_TREES = False
MAP_CACHE_DIR = "map_cache"
PLAYER_HEIGHT = 72
MIN_RAMP_HEIGHT = PLAYER_HEIGHT / 2
MIN_RAMP_ANGLE = 48
MAX_RAMP_ANGLE = 65

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

        obj_centroids, ramp_centroids = self._filter_vmf(vmf)

        trees_cache_path = f"{MAP_CACHE_DIR}/surf_{map_name}_trees.pkl"
        if os.path.exists(trees_cache_path):
            with open(trees_cache_path, "rb") as file:
                self.obj_tree, self.ramp_tree = pickle.load(file)
        else:
            self.obj_tree = cKDTree(obj_centroids)
            self.ramp_tree = cKDTree(ramp_centroids)
            if SHOULD_CACHE_TREES:
                with open(trees_cache_path, "wb") as file:
                    pickle.dump((self.obj_tree, self.ramp_tree), file)
    
    def _filter_vmf(self, vmf):
        all_objs = []
        all_obj_centroids = []
        
        for node in vmf.nodes:
            classname = None
            solid = False

            if node.name == "entity":
                if hasattr(node, "properties"):
                    for prop, val in self._extract_properties(node.properties):
                        prop = prop.lower().strip()
                        if prop == "classname":
                            classname = val.lower().strip()
                        elif prop in ["solid", "physbox"]:
                            solid = True

            for subnode in node.nodes:
                if subnode.name == "solid":
                    if not self._has_collision(node.name, classname, solid):
                        continue
                    
                    centroid = self._calc_obj_centroid(subnode)
                    if centroid is None:
                        continue
                    
                    all_objs.append(subnode)
                    all_obj_centroids.append(centroid)
        
        self.objs = []
        obj_centroids = []
        self.ramps = []
        ramp_centroids = []
        for i, obj in enumerate(all_objs):
            # Check if object is a ramp (48-65 degrees bottom)
            if i % 2 == 0:
                self.ramps.append(obj)
                ramp_centroids.append(all_obj_centroids[i])
            else:
                self.objs.append(obj)
                obj_centroids.append(all_obj_centroids[i])
        
        return np.array(obj_centroids), np.array(ramp_centroids)

    def _extract_properties(self, properties):
        if isinstance(properties, dict):
            for key, value in properties.items():
                if isinstance(value, dict):
                    yield from self._extract_properties(value)
                else:
                    yield key, value
        elif isinstance(properties, list):
            for item in properties:
                if isinstance(item, tuple) and len(item) == 2:
                    yield item

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

    def get_near(self, coord, k=5, radius=None):
        objs = self.get_near_in_tree(self.obj_tree, coord, k, radius)
        ramps = self.get_near_in_tree(self.ramp_tree, coord, k, radius)
        return objs, ramps

    def get_near_in_tree(self, tree, coord, k=5, radius=None):
        coord = np.array(coord)

        if radius is not None:
            indices = tree.query_ball_point(coord, r=radius)
        else:
            _, indices = tree.query(coord, k=k)

        if isinstance(indices, int):
            indices = [indices]

        return [self.objs[i] for i in indices]

if __name__ == '__main__':
    map_objects = MapObjects("beginner")
    
    player_pos = (-128.0, 0.0, 372.0)
    objs, ramps = map_objects.get_near(player_pos, k=5)

    print(f"Found {len(objs)} nearby objects:")
    for obj in objs:
        print(obj)
    
    print(f"Found {len(ramps)} nearby ramps:")
    for ramp in ramps:
        print(ramp)

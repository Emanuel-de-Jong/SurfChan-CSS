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

        vmf = None
        vmf_cache_path = f"{MAP_CACHE_DIR}/surf_{map_name}_vmf.pkl"
        if os.path.exists(vmf_cache_path):
            with open(vmf_cache_path, "rb") as file:
                vmf = pickle.load(file)
        else:
            vmf = Vmf(f"css_server/server/cstrike/maps/surf_{map_name}.vmf")
            if SHOULD_CACHE_VMF and vmf is not None:
                with open(vmf_cache_path, "wb") as file:
                    pickle.dump(vmf, file)
        
        # Maybe save solids instead of vmf
        solid_centroids = self._filter_vmf(vmf)
        
        tree_cache_path = f"{MAP_CACHE_DIR}/surf_{map_name}_tree.pkl"
        if os.path.exists(tree_cache_path):
            with open(tree_cache_path, "rb") as file:
                self.obj_tree = pickle.load(file)
        else:
            self._create_obj_tree(solid_centroids)
            if SHOULD_CACHE_TREE and self.obj_tree is not None:
                with open(tree_cache_path, "wb") as file:
                    pickle.dump(self.obj_tree, file)
    
    def _filter_vmf(self, vmf):
        self.solids = []
        solid_centroids = []
        for node in vmf.nodes:
            if node.name in ["world", "entity"]:
                classname = None
                if node.name == "entity":
                    for prop, val in node.properties:
                        if prop == "classname":
                            classname = val.lower().strip()
                            break
                
                for subnode in node.nodes:
                    if subnode.name == "solid":
                        if not self._has_collision(node.name, classname):
                            continue

                        centroid = self._calculate_solid_centroid(subnode)
                        if centroid is None:
                            continue
                        
                        self.solids.append(subnode)
                        solid_centroids.append(centroid)
        
        return solid_centroids

    def _has_collision(self, node_type, classname):
        if node_type == "world":
            return True

        if not classname:
            return False
        
        if classname.startswith("trigger_"):
            return False
        if "illusionary" in classname:
            return False
        
        if classname in ["func_detail", "func_brush", "func_wall", "func_physbox"]:
            return True
        
        return False

    def _create_obj_tree(self, solid_centroids):
        self.obj_tree = None
        if not solid_centroids:
            return
        
        solid_centroids = np.array(solid_centroids)
        self.obj_tree = cKDTree(solid_centroids)

    def _calculate_solid_centroid(self, solid):
        planes = []
        for node in solid.nodes:
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

        # Compute the bounding box
        min_corner = np.min(points, axis=0)
        max_corner = np.max(points, axis=0)

        # Compute the centroid (midpoint of bounding box)
        centroid = (min_corner + max_corner) / 2.0
        return centroid

    def get_near_objects(self, coord, k=5, radius=None):
        coord = np.array(coord)

        if radius is not None:
            # Find all solids within the radius
            indices = self.obj_tree.query_ball_point(coord, r=radius)
        else:
            # Find the k-nearest solids
            _, indices = self.obj_tree.query(coord, k=k)

        if isinstance(indices, int):
            indices = [indices]

        return [self.solids[i] for i in indices]

if __name__ == '__main__':
    map_objects = MapObjects("beginner")
    
    player_pos = (-128.0, 0.0, 372.0)
    nearby_solids = map_objects.get_near_objects(player_pos, k=5)

    print(f"Found {len(nearby_solids)} nearby solids:")
    for solid in nearby_solids:
        print(solid)

import os
import pickle
import numpy as np
from valvevmf import Vmf
from scipy.spatial import cKDTree

class MapObjects:
    def __init__(self, map_name):
        tree_cache_path = f"map_cache/surf_{map_name}_tree.pkl"
        if os.path.exists(tree_cache_path):
            with open(tree_cache_path, "rb") as file:
                self.obj_tree = pickle.load(file)
        else:
            self._create_obj_tree(map_name)
            if self.obj_tree is not None:
                with open(tree_cache_path, "wb") as file:
                    pickle.dump(self.obj_tree, file)

    def _create_obj_tree(self, map_name):
        vmf = None
        vmf_cache_path = f"map_cache/surf_{map_name}_vmf.pkl"
        if os.path.exists(vmf_cache_path):
            with open(vmf_cache_path, "rb") as file:
                vmf = pickle.load(file)
        else:
            vmf = Vmf(f"css_server/server/cstrike/maps/surf_{map_name}.vmf")
            with open(vmf_cache_path, "wb") as file:
                pickle.dump(vmf, file)
        
        self.solids = []
        for node in vmf.nodes:
            if node.name in ["world", "entity"]:
                for subnode in node.nodes:
                    if subnode.name == "solid":
                        self.solids.append(subnode)
        
        self.solid_centroids = []
        for solid in self.solids:
            centroid = self._calculate_solid_centroid(solid)
            if centroid is not None:
                self.solid_centroids.append(centroid)

        self.obj_tree = None
        if not self.solid_centroids:
            return
        
        self.solid_centroids = np.array(self.solid_centroids)
        self.obj_tree = cKDTree(self.solid_centroids)

    def _calculate_solid_centroid(self, solid):
        points = []
        for node in solid.nodes:
            if node.name == "side":
                for subnode in node.nodes:
                    if subnode.name == "plane":
                        # Extract the 3D plane points
                        points.extend(self._parse_plane(subnode.value))

        if len(points) < 3:
            return None

        points = np.array(points)

        # Compute the bounding box
        min_corner = np.min(points, axis=0)
        max_corner = np.max(points, axis=0)

        # Compute the centroid (midpoint of bounding box)
        centroid = (min_corner + max_corner) / 2.0
        return centroid

    def _parse_plane(self, plane_str):
        coords = plane_str.replace("(", "").replace(")", "").split()
        points = []
        for i in range(0, len(coords), 3):
            points.append([float(coords[i]), float(coords[i+1]), float(coords[i+2])])
        return points

    def get_near_objects(self, coord, k=5, radius=None):
        if self.obj_tree is None:
            return []

        coord = np.array(coord)

        if radius:
            # Find all solids within the radius
            indices = self.obj_tree.query_ball_point(coord, r=radius)
        else:
            # Find the k-nearest solids
            _, indices = self.obj_tree.query(coord, k=k)

        return [self.solids[i] for i in indices]

if __name__ == '__main__':
    map_objects = MapObjects("beginner")
    
    player_pos = (-128.0, 0.0, 372.0)
    nearby_solids = map_objects.get_near_objects(player_pos, k=5)

    print(f"Found {len(nearby_solids)} nearby solids:")
    for solid in nearby_solids:
        print(solid)

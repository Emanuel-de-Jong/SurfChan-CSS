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
                self.obj_tree, self.solid_indices = pickle.load(file)
        else:
            self._create_obj_tree(map_name)
            if self.obj_tree is not None:
                with open(tree_cache_path, "wb") as file:
                    pickle.dump((self.obj_tree, self.solid_indices), file)

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

        solid_centroids = []
        self.solid_indices = []

        for i, solid in enumerate(self.solids):
            centroid = self._calculate_solid_centroid(solid)
            if centroid is not None:
                solid_centroids.append(centroid)
                self.solid_indices.append(i)  # Store index instead of object

        if not solid_centroids:
            self.obj_tree = None
            return

        solid_centroids = np.array(solid_centroids)
        self.solid_indices = np.array(self.solid_indices)  # Convert to NumPy array

        # Store centroids in a KDTree
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
            for i in range(1, len(plane)):
                for point in plane[i]:
                    converted_point = []
                    for num in point:
                        converted_point.append(float(num))
                
                    points.append(converted_point)

        if len(points) < 3:
            return None

        points = np.array(points)

        # Compute the bounding box
        min_corner = np.min(points, axis=0)
        max_corner = np.max(points, axis=0)

        # Compute the centroid (midpoint of bounding box)
        centroid = (min_corner + max_corner) / 2.0
        return centroid

    def get_near_objects(self, coord, k=5, radius=None):
        if self.obj_tree is None:
            return []

        coord = np.array(coord)

        if radius:
            indices = self.obj_tree.query_ball_point(coord, r=radius)
        else:
            _, indices = self.obj_tree.query(coord, k=k)

        # Ensure indices are in list format
        if isinstance(indices, int):  # Case when k=1 returns a single index
            indices = [indices]

        # Retrieve the corresponding solids using stored indices
        near_solids = [self.solids[self.solid_indices[i]] for i in indices]
        
        return near_solids


if __name__ == '__main__':
    map_objects = MapObjects("beginner")
    
    player_pos = (-128.0, 0.0, 372.0)
    nearby_solids = map_objects.get_near_objects(player_pos, k=5)

    print(f"Found {len(nearby_solids)} nearby solids:")
    for solid in nearby_solids:
        print(solid)

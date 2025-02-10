import numpy as np
from valvevmf import Vmf
from scipy.spatial import cKDTree

class MapObjects:
    def __init__(self, map_name):
        self.vmf = Vmf(f"css_server/server/cstrike/maps/surf_{map_name}.vmf")

        self.solids = []
        for node in self.vmf.nodes:
            if node.name in ["world", "entity"]:
                for subnode in node.nodes:
                    if subnode.name == "solid":
                        self.solids.append(subnode)
        
        self.solid_centroids = []
        for solid in self.solids:
            centroid = self._calculate_solid_centroid(solid)
            if centroid is not None:
                self.solid_centroids.append(centroid)

        self.kdtree = None
        if self.solid_centroids:
            self.solid_centroids = np.array(self.solid_centroids)
            self.kdtree = cKDTree(self.solid_centroids)

    def _calculate_solid_centroid(self, solid):
        points = []
        for node in solid.nodes:
            if node.name == "side":
                for subnode in node.nodes:
                    if subnode.name == "plane":
                        # Extract the 3D plane points
                        points.append(self._parse_plane(subnode.value))

        if len(points) >= 3:
            return np.mean(points, axis=0)  # Centroid of the solid
        return None

    def _parse_plane(self, plane_str):
        coords = plane_str.replace("(", "").replace(")", "").split()
        return np.array([float(coords[0]), float(coords[1]), float(coords[2])])

    def get_near_objects(self, coord, k=5, radius=None):
        if self.kdtree is None:
            return []

        coord = np.array(coord)

        if radius:
            # Find all solids within the radius
            indices = self.kdtree.query_ball_point(coord, r=radius)
        else:
            # Find the k-nearest solids
            _, indices = self.kdtree.query(coord, k=k)

        return [self.solids[i] for i in indices]

if __name__ == '__main__':
    map_objects = MapObjects("beginner")
    player_pos = (-128.0, 0.0, 372.0)
    nearby_solids = map_objects.get_near_objects(player_pos, k=5)

    print(f"Found {len(nearby_solids)} nearby solids:")
    for solid in nearby_solids:
        print(solid)

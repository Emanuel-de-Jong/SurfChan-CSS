from valvevmf import Vmf

class MapObjects:
    def __init__(self, map_name):
        self.vmf = Vmf(f"css_server/server/cstrike/maps/surf_{map_name}.vmf")

        self.solids = []
        for node in self.vmf.nodes:
            if node.name == "world" or node.name == "entity":
                for subnode in node.nodes:
                    if subnode.name == "solid":
                        self.solids.append(subnode)

    def get_near_objects(self, coord):
        pass

if __name__ == '__main__':
    MapObjects("beginner")

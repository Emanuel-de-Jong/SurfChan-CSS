from valvevmf import Vmf

class MapObjects:
    def __init__(self, map_name):
        self.vmf = Vmf(f"css_server/server/cstrike/maps/surf_{map_name}.vmf")
    
    def get_near_objects(self, coord):
        pass

    def get_near_ramps(self, coord):
        pass

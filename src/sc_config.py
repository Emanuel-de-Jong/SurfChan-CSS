import yaml

_CONFIG_FILE_NAME = "config.yml"
_CONFIG_USER_FILE_NAME = "config_user.yml"

_config = None

class _Config:
    def __init__(self, config_dict, depth=0):
        self._depth = depth

        for key, val in config_dict.items():
            if isinstance(val, (list, tuple)):
                setattr(self, key, [_Config(x, depth + 1) if isinstance(x, dict) else x for x in val])
            else:
                setattr(self, key, _Config(val, depth + 1) if isinstance(val, dict) else val)
    
    def __getitem__(self, key):
        return getattr(self, key)
    
    def __str__(self):
        str = "\n"
        for key, val in self.__dict__.items():
            if key == "_depth":
                continue

            str += f"{'  ' * self._depth}{key}: {val}\n"
        
        return str

def get_config():
    global _config

    if _config is None:
        with open(_CONFIG_FILE_NAME, "r") as file:
            config_dict = yaml.safe_load(file)
        with open(_CONFIG_USER_FILE_NAME, "r") as file:
            config_user_dict = yaml.safe_load(file)
        
        config_dict = _merge_dicts(config_dict, config_user_dict)
        _config = _Config(config_dict)

    return _config

def _merge_dicts(dict1, dict2):
    for key, val in dict2.items():
        if key in dict1 and isinstance(val, dict) and isinstance(dict1[key], dict):
            _merge_dicts(dict1[key], val)
        else:
            dict1[key] = val
    return dict1

if __name__ == "__main__":
    config = get_config()
    print(config)

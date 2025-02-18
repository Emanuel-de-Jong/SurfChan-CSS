from config import get_config
from SCEnv import SCEnv

config = get_config()
SCEnv(config.infer.map)

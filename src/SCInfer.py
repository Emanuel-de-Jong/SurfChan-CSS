import os
import shutil
import time
import asyncio
import tqdm
import torch
from sc_config import get_config, CONFIG_FILE_NAME
from sc_model_utils import get_torch_device
from SCEnv import create_env
from SCTimer import sc_timer

class SCInfer():
    def __init__(self, surfchan):
        self.surfchan = surfchan
    
    async def infer(self):
        self.config = get_config()

        self.device = get_torch_device()
        
        self.env = create_env(self.surfchan, self.config.infer.map)

        # avg_step_time = sum(self.stats.step_times) / len(self.stats.step_times) * self.stats.game_speed
        # self.env.set_target_step_time(avg_step_time)
    
    def close(self):
        self.env.close()

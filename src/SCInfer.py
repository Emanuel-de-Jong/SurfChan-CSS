import os
import shutil
import time
import asyncio
from datetime import datetime
import tqdm
import torch
from tensordict import TensorDict
from torchrl.collectors import SyncDataCollector
from torchrl.data import LazyTensorStorage, TensorDictReplayBuffer
from torchrl.data.replay_buffers.samplers import SamplerWithoutReplacement
from torchrl.objectives.value import GAE
from torchrl.record.loggers.tensorboard import TensorboardLogger
from torchrl._utils import compile_with_warmup
from sc_config import get_config, CONFIG_FILE_NAME
from sc_model_utils import get_torch_device, get_models
from SCEnv import create_torchrl_env
from SCTimer import sc_timer

class SCInfer():
    def __init__(self, surfchan):
        self.surfchan = surfchan
    
    async def infer(self):
        self.config = get_config()
        
        torch.set_float32_matmul_precision("high")

        self.device = get_torch_device()
        
        self.env = create_torchrl_env(self.surfchan, self.config.infer.map)
        
        self.models, self.stats = get_models(self.env, self.device)

        avg_step_time = sum(self.stats.step_times) / len(self.stats.step_times) * self.stats.game_speed
        self.env.set_target_step_time(avg_step_time)
    
    def close(self):
        self.env.close()

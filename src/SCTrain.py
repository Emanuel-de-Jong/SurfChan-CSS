import os
import shutil
import time
import asyncio
import tqdm
import torch
from stable_baselines3 import PPO
from stable_baselines3.common.env_checker import check_env
from sc_config import get_config, CONFIG_FILE_NAME
from sc_model_utils import get_torch_device
from SCEnv import create_env
from SCTimer import sc_timer

class SCTrain():
    def __init__(self, surfchan):
        self.surfchan = surfchan

    async def train(self):
        self.config = get_config()
        self.collector_conf = self.config.train.collector
        self.optimizer_conf = self.config.train.optimizer
        self.loss_conf = self.config.train.loss

        self.device = get_torch_device()

        frames_per_batch = self.collector_conf.frames_per_batch
        total_frames = frames_per_batch * self.collector_conf.batches
        
        self.env = create_env(self.surfchan, self.config.train.map)
        check_env(self.env, warn=True)

        self.model = PPO("CnnPolicy", self.env, device=self.device, verbose=1)

        sc_timer.start("training")
        self.model.learn(total_timesteps=total_frames, progress_bar=True)

    def close(self):
        if self.config.train.should_save:
            self.model.save("model")
        self.env.close()

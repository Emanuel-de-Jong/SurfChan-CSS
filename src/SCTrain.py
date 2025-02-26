import os
import shutil
import time
import asyncio
import tqdm
import torch
from stable_baselines3 import PPO
from stable_baselines3.common.env_checker import check_env
from stable_baselines3.common.callbacks import BaseCallback
from stable_baselines3.common.logger import configure
from sc_config import get_config, CONFIG_FILE_NAME
from sc_model_utils import get_torch_device
from SCEnv import create_env
from SCTimer import sc_timer

class ModelCallbacks(BaseCallback):
    # https://stable-baselines3.readthedocs.io/en/master/guide/callbacks.html
    def __init__(self, verbose=0):
        super().__init__(verbose)

    def _on_training_start(self):
        pass

    def _on_rollout_start(self):
        pass

    def _on_step(self):
        return True

    def _on_rollout_end(self):
        pass

    def _on_training_end(self):
        pass

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

        logger = configure(os.path.join(self.config.model.results_dir, "logs"), ["tensorboard"])
        if self.config.train.should_save:
            self.model.set_logger(logger)

        model_callbacks = ModelCallbacks()

        sc_timer.start("training")
        self.model.learn(total_timesteps=total_frames, progress_bar=True, callback=model_callbacks)

    def close(self):
        if self.config.train.should_save:
            self.model.save("model")
        self.env.close()

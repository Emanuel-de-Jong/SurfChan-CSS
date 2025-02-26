import sys
import asyncio
import traceback
import subprocess
import time
import os
from enum import Enum
import numpy as np
import gymnasium as gym
from sc_config import get_config
from SCEnv import SCEnv, create_env
from SCTrain import SCTrain
from SCInfer import SCInfer
from SCTimer import sc_timer

class MODE(Enum):
    PLAY = 1
    TRAIN = 2
    INFER = 3
    FAKE_INFER = 4

class SurfChan():
    env = None
    train = None
    infer = None

    async def run(self):
        try:
            self.config = get_config()

            if os.path.exists("log.txt"):
                os.remove("log.txt")

            gym.register(self.config.env.name, lambda: SCEnv())

            self.mode = MODE.PLAY
            if len(sys.argv) > 1:
                mode_str = sys.argv[1].lower()
                if mode_str.startswith("t"):
                    self.mode = MODE.TRAIN
                elif mode_str.startswith("i"):
                    self.mode = MODE.INFER
                elif mode_str.startswith("f"):
                    self.mode = MODE.FAKE_INFER

            if self.mode == MODE.PLAY:
                await self._create_play()
            elif self.mode == MODE.TRAIN:
                await self._create_train()
            elif self.mode == MODE.INFER:
                await self._create_infer()
            elif self.mode == MODE.FAKE_INFER:
                await self._create_fake_infer()
        except KeyboardInterrupt:
            pass
        except asyncio.CancelledError:
            pass
        except Exception:
            traceback.print_exc()
        finally:
            sc_timer.print()

            print("Closing...")
            if self.train is not None:
                self.train.close()
            if self.infer is not None:
                self.infer.close()
            if self.env is not None:
                self.env.close()
            
            tasks = [task for task in asyncio.all_tasks() if task is not asyncio.current_task()]
            if tasks:
                [task.cancel() for task in tasks]
                await asyncio.gather(*tasks, return_exceptions=True)
    
    async def _create_play(self):
        print("Mode: Play")
        self.env = create_env(self, self.config.infer.map, base_only=True, should_run_ai=False)
        while self.env is not None:
            await asyncio.sleep(0.2)
            obs, reward, terminated, truncated, _ = self.env.step(self.env._fake_action())
    
    async def _create_train(self):
        print("Mode: Train")
        self.train = SCTrain(self)
        await self.train.train()
    
    async def _create_infer(self):
        print("Mode: Infer")
        self.infer = SCInfer(self)
        await self.infer.infer()
    
    async def _create_fake_infer(self):
        print("Mode: Fake Infer")
        self.env = create_env(self, self.config.infer.map, True)

        action = self.env._fake_action()
        action[self.env.button_count] = 0.7 # look right
        action[self.env.button_count + 1] = 0.5 # vertical center
        i = 0
        while self.env is not None:
            i += 1
            if i % 2 == 0:
                i = 0
                action[0] = 1.0
                action[1] = 0.0
            else:
                action[0] = 0.0
                action[1] = 1.0
            
            self.env.step(action)
            await asyncio.sleep(0.034) # 30 fps

if __name__ == "__main__":
    surfchan = SurfChan()
    asyncio.run(surfchan.run())

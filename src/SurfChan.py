import sys
import asyncio
from enum import Enum
import numpy as np
import gymnasium as gym
from sc_config import get_config
from SCEnv import SCEnv, create_torchrl_env
from SCTrain import SCTrain

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
                await self.create_play()
                while True:
                    await asyncio.sleep(1)
            elif self.mode == MODE.TRAIN:
                await self.create_train()
            elif self.mode == MODE.INFER:
                await self.create_infer()
            elif self.mode == MODE.FAKE_INFER:
                await self.create_fake_infer()
        except KeyboardInterrupt:
            pass
        except asyncio.CancelledError:
            pass
        finally:
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
    
    async def create_play(self):
        print("Mode: Play")
        self.env = create_torchrl_env(self.config.env.name, self.config.infer.map, True)
        self.env.env.game.should_run_ai = False
    
    async def create_train(self):
        print("Mode: Train")
        self.train = SCTrain()
    
    async def create_infer(self):
        print("Mode: Infer")
        return
    
    async def create_fake_infer(self):
        print("Mode: Fake Infer")
        self.env = create_torchrl_env(self.config.env.name, self.config.infer.map, True)

        action = self.env.env._fake_action()
        action[0] = 1.0 # forward
        action[self.env.env.button_count] = 0.7 # look right
        action[self.env.env.button_count + 1] = 0.5 # vertical center
        while not self.env.is_closed:
            await asyncio.sleep(0.034) # 30 fps
            self.env.env.step(action)

if __name__ == "__main__":
    surfchan = SurfChan()
    asyncio.run(surfchan.run())

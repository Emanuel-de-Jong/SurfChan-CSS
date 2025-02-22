import time
import gymnasium as gym
import numpy as np
from torchrl.envs import (
    TransformedEnv,
    StepCounter,
    RenameTransform,
    ToTensorImage,
    DoubleToFloat,
    VecNorm,
    RewardSum
)
from torchrl.envs.libs.gym import GymEnv
from sc_utils import run_async
from sc_model_utils import get_torch_device
from sc_config import get_config
from SCGame import SCGame

class SCEnv(gym.Env):
    button_count = 6
    mouse_count = 2
    button_model_to_game = ["f", "b", "l", "r", "j", "c"]
    last_sec_between_step = 0.0

    def __init__(self):
        super(SCEnv, self).__init__()

        self.config = get_config()
        self.output_count = self.button_count + self.mouse_count

        self._clear_attributes()

        self.game = SCGame(self)

        self.size = self.config.model.img_size

        self.observation_space = gym.spaces.Dict({
            "pixels": gym.spaces.Box(low=0, high=255, shape=(self.size, self.size, 3), dtype=np.uint8)
        })
        self.observation_spec = self.observation_space

        self.action_space = gym.spaces.Box(low=0.0, high=1.0, shape=(self.output_count, ), dtype=np.float32)
        self.action_spec = self.action_space
    
    def _clear_attributes(self):
        self.last_player_dist = None
        self.last_total_velocity = 0.0
        self.terminated = False
        self.truncated = False
        self.done = False
    
    async def init(self, map_name):
        await self.game.init(map_name)

    def step(self, action):
        # sec_between_step = time.time()
        # print(f"Seconds between step: {sec_between_step - self.last_sec_between_step}")
        # self.last_sec_between_step = sec_between_step

        obs, player_pos, total_velocity = self._game_step(action)
        reward = self._calc_reward(player_pos, total_velocity)

        return obs, reward, self.terminated, self.truncated, {}
    
    def _game_step(self, action):
        game_buttons = ""
        for i in range(self.button_count):
            game_buttons += self.button_model_to_game[i] if action[i] > 0.5 else ""
        
        game_mouseH = action[self.button_count] * 3.6 - 1.8
        game_mouseV = action[self.button_count + 1] * 1.8 - 0.9

        pixels, player_pos, total_velocity = run_async(self.game.step(game_buttons, game_mouseH, game_mouseV))
        obs = {"pixels": pixels}
        return obs, player_pos, total_velocity

    def _calc_reward(self, player_pos, total_velocity):
        reward = -0.1
        
        if self.last_player_dist is None:
            self.last_player_dist = abs(self.game.map.start_pos[self.game.map.axis] - self.game.map.finish_pos[self.game.map.axis])
        
        player_dist = abs(player_pos[self.game.map.axis] - self.game.map.finish_pos[self.game.map.axis])

        if player_dist < self.last_player_dist:
            reward += 0.1
        else:
            reward -= 0.1
        
        self.last_player_dist = player_dist

        if total_velocity > self.last_total_velocity:
            reward += 0.1
        else:
            reward -= 0.1
        
        self.last_total_velocity = total_velocity

        if self.last_player_dist < 25.0:
            self.done = True
            self.terminated = True
            reward = 15.0
        elif player_pos[2] <= self.game.map.ground:
            self.done = True
            self.terminated = True
            reward = -5.0

        return reward

    def reset(self, seed=None, options=None):
        run_async(self.game.reset())
        self._clear_attributes()
        obs, player_pos, total_velocity = self._game_step(self._fake_action())
        return obs, {}
    
    def _fake_action(self):
        action = np.zeros((self.output_count,), dtype=np.float32)
        action[self.button_count] = 0.5
        action[self.button_count + 1] = 0.5
        return action
    
    async def change_map(self, map_name):
        await self.game.change_map(map_name)
    
    def close(self):
        if self.game:
            self.game.close()

def create_torchrl_env(name, map, base_only=False):
    env = GymEnv(name)
    env = TransformedEnv(env).to(get_torch_device())
    if not base_only:
        env.append_transform(RenameTransform(in_keys=["pixels"], out_keys=["pixels_int"]))
        env.append_transform(ToTensorImage(in_keys=["pixels_int"], out_keys=["pixels"]))
        env.append_transform(RewardSum())
        # env.append_transform(DoubleToFloat())
        env.append_transform(VecNorm(in_keys=["pixels"]))
    
    run_async(env.env.init(map))
    
    return env

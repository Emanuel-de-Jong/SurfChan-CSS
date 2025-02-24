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
from SCTimer import sc_timer

class SCEnv(gym.Env):
    target_step_time = None
    button_count = 6
    mouse_count = 2
    button_model_to_game = ["f", "b", "l", "r", "j", "c"]

    def __init__(self):
        super(SCEnv, self).__init__()

        self.config = get_config()
        self.output_count = self.button_count + self.mouse_count

        self.truncate_time = self.config.env.seconds_to_finish / self.config.env.game_speed

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
        self.time_till_truncate = None
    
    async def init(self, map_name):
        await self.game.init(map_name)
    
    def set_target_step_time(self, avg_step_time):
        # Steps are never shorter than target_step_time but occasionally longer. This balances it out.
        self.target_step_time = avg_step_time * 0.95

    def step(self, action):
        if self.target_step_time is not None:
            step_time = sc_timer.stop("real_step")
            if step_time:
                remaining_time = self.target_step_time - step_time
                if remaining_time > 0.0:
                    time.sleep(remaining_time)

        sc_timer.stop("step")
        sc_timer.start("step")

        if self.target_step_time is not None:
            sc_timer.start("real_step")
        
        if self.time_till_truncate is None:
            self.time_till_truncate = time.perf_counter()
        elif self.game.should_run_ai and time.perf_counter() - self.time_till_truncate >= self.truncate_time:
                self.truncated = True
                obs, _ = self.reset()
                return obs, 0.0, self.terminated, True, {}

        obs, player_pos, total_velocity = self._game_step(action)
        reward = self._calc_reward(player_pos, total_velocity)

        # print(obs)
        # print(reward)

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
        map = self.game.map
        axis = map.axis
        
        if self.last_player_dist is None:
            self.last_player_dist = abs(map.start_pos[axis] - map.finish_pos[axis])
        
        player_dist = abs(player_pos[axis] - map.finish_pos[axis])
        if player_dist < self.last_player_dist:
            reward += 1
        else:
            reward -= 1
        
        if total_velocity > self.last_total_velocity:
            reward += 1
        else:
            reward -= 1

        if self.last_player_dist < 25.0:
            self.terminated = True
            reward += 25.0
        elif player_pos[2] <= map.ground:
            self.terminated = True
            reward -= 10.0

        self.last_player_dist = player_dist
        self.last_total_velocity = total_velocity

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

config = get_config()
def create_torchrl_env(map, base_only=False):
    global config

    env = GymEnv(config.env.name)
    env = TransformedEnv(env).to(get_torch_device())
    if not base_only:
        env.append_transform(RenameTransform(in_keys=["pixels"], out_keys=["pixels_int"]))
        env.append_transform(ToTensorImage(from_int=True, in_keys=["pixels_int"], out_keys=["pixels"]))
        env.append_transform(RewardSum())
        # env.append_transform(DoubleToFloat())
        env.append_transform(VecNorm(in_keys=["pixels"]))
    
    run_async(env.env.init(map))
    
    return env

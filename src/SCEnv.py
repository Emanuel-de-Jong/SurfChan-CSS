import gymnasium as gym
import numpy as np
from config import get_config
from SCGame import SCGame

class SCEnv(gym.Env):
    last_player_dist = None
    last_total_velocity = 0.0

    def __init__(self):
        super(SCEnv, self).__init__()

        self.config = get_config()

        self.game = SCGame(self)

        self.size = self.config.model.img_size
        self.key_count = 6

        self.action_space = gym.spaces.Dict({
            "keys": gym.spaces.Discrete(self.key_count),
            "mouse": gym.spaces.Box(low=-1, high=1, shape=(2,), dtype=np.float32)
        })
        self.observation_space = gym.spaces.Dict({
            "pixels": gym.spaces.Box(low=0, high=255, shape=(self.size, self.size, 3), dtype=np.uint8),
        })
    
    async def start(self, map_name):
        await self.game.start(map_name)
    
    async def change_map(self, map_name):
        await self.game.change_map(map_name)

    def step(self, action):
        obs = self._get_obs()
        reward = 0
        terminated = False
        truncated = False
        return obs, reward, terminated, truncated, {}

    def step_test(self, screenshot, player_pos, total_velocity):
        reward = self._calc_reward(player_pos, total_velocity)
        return f"f,1.0,0.0"
    
    def _get_obs(self):
        return {
            "pixels": np.zeros((self.size, self.size, 3), dtype=np.uint8)
        }

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

        return reward

    def reset(self, seed=None, options=None):
        obs = self._get_obs()
        return obs, {}
    
    def close(self):
        if self.game:
            self.game.close()

import gymnasium as gym
import numpy as np

class SCEnv(gym.Env):
    def __init__(self):
        super(SCEnv, self).__init__()

        self.size = 500
        self.key_count = 6

        self.action_space = gym.spaces.Dict({
            "keys": gym.spaces.Discrete(self.key_count),
            "mouse": gym.spaces.Box(low=-1, high=1, shape=(2,), dtype=np.float32)
        })
        self.observation_space = gym.spaces.Dict({
            "pixels": gym.spaces.Box(low=0, high=255, shape=(self.size, self.size, 3), dtype=np.uint8),
        })
    
    def _get_obs(self):
        pass

    def step(self, action):
        obs = self._get_obs()
        reward = 0
        terminated = False
        truncated = False
        return obs, reward, terminated, truncated, {}

    def reset(self, seed=None, options=None):
        obs = self._get_obs()
        return obs, {}
    
    def close():
        pass

if __name__ == "__main__":
    gym.register("SurfChan", SCEnv)

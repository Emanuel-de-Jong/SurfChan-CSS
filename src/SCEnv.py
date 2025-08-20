import time
import gymnasium as gym
import numpy as np
from sc_utils import run_async, write_to_log
from sc_model_utils import get_torch_device
from sc_config import get_config
from SCGame import SCGame
from SCTimer import sc_timer

class SCEnv(gym.Env):
    target_step_time = None
    button_count = 6
    mouse_count = 2
    button_model_to_game = ["f", "b", "l", "r", "j", "c"]
    dist_milestone_step = 5

    metadata = {"render_modes": ["console"]}

    def __init__(self):
        super(SCEnv, self).__init__()

        self.config = get_config()
        self.output_count = self.button_count + self.mouse_count

        self.truncate_time = self.config.env.seconds_to_finish / self.config.env.game_speed

        self._clear_attributes()

        self.game = SCGame(self)

        self.size = self.config.model.img_size

        self.observation_space = gym.spaces.Box(low=0, high=255, shape=(3, self.size, self.size), dtype=np.uint8)
        self.observation_spec = self.observation_space

        self.action_space = gym.spaces.Box(low=-1.0, high=1.0, shape=(self.output_count, ), dtype=np.float32)
        self.action_spec = self.action_space
    
    def _clear_attributes(self):
        self.terminated = False
        self.truncated = False
        self.time_till_truncate = None
        self.last_dist_milestone = None
    
    async def init(self, surfchan, map_name, should_run_ai):
        self.surfchan = surfchan
        await self.game.init(surfchan, map_name, should_run_ai)
    
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

        game_action = self._action_to_game(action)
        obs, player_pos, total_velocity = self._game_step(game_action)
        reward = self._calc_reward(game_action, player_pos, total_velocity)

        # print(obs)
        # print(reward)

        return obs, reward, self.terminated, self.truncated, {}
    
    def _action_to_game(self, action):
        game_action = {
            "buttons": "",
            "mouse_h": 0.0,
            "mouse_v": 0.0
        }

        for i in range(self.button_count):
            game_action["buttons"] += self.button_model_to_game[i] if action[i] > 0.0 else ""
        
        game_action["mouse_h"] = action[self.button_count] * 3.6 * 0.5
        game_action["mouse_v"] = action[self.button_count + 1] * 1.8 * 0.5

        return game_action
    
    def _game_step(self, game_action):
        pixels, player_pos, total_velocity = run_async(self.game.step(game_action))

        # write_to_log(pixels[0][0])
        obs = np.transpose(pixels, (2, 0, 1))

        return obs, player_pos, total_velocity

    def _calc_reward(self, game_action, player_pos, total_velocity):
        reward = 0.0
        
        map = self.game.map
        axis = map.axis

        if self.last_dist_milestone is None:
            map_length = abs(map.start_pos[axis] - map.finish_pos[axis])
            self.last_dist_milestone = map_length - (map_length % self.dist_milestone_step)

        player_dist = abs(player_pos[axis] - map.finish_pos[axis])
        while self.last_dist_milestone - player_dist > self.dist_milestone_step:
            reward += 0.5
            self.last_dist_milestone -= self.dist_milestone_step

        if player_dist < 25.0:
            self.terminated = True
            time_multiplier = 1 + (1 - ((time.perf_counter() - self.time_till_truncate) / self.truncate_time))
            reward += 15.0 * time_multiplier

        return reward

    def reset(self, seed=None, options=None):
        run_async(self.game.reset())
        self._clear_attributes()
        game_action = self._action_to_game(self._fake_action())
        obs, player_pos, total_velocity = self._game_step(game_action)
        return obs, {}
    
    def _fake_action(self):
        action = []
        for i in range(self.output_count):
            action.append(-1.0)
        action[self.button_count] = 0.0
        action[self.button_count + 1] = 0.0
        return np.array(action, dtype=np.float32)
    
    async def change_map(self, map_name):
        await self.game.change_map(map_name)

    def render(self):
        pass
    
    def close(self):
        if self.game:
            self.game.close()

config = get_config()
def create_env(surfchan, map, base_only=False, should_run_ai=True):
    global config

    env = SCEnv()
    
    run_async(env.init(surfchan, map, should_run_ai))
    
    return env

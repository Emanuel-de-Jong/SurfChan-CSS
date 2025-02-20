import os
from sc_config import get_config
import torch

config = get_config()
def load_latest_models():
    global config
    results_dir = config.model.results_dir
    result_paths = [os.path.join(results_dir, p) for p in os.listdir(results_dir)]
    actor_paths = [p for p in result_paths if p.endswith('actor.pth')]
    if len(actor_paths) == 0:
        return None, None
    
    actor_path = max(actor_paths, key=lambda p: os.path.getctime(p))
    critic_path = actor_path.replace('actor', 'critic')

    actor = torch.load(actor_path)
    critic = torch.load(critic_path)
    return actor, critic

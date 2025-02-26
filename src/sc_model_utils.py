import os
from sc_config import get_config
import torch
from sc_utils import write_to_log

config = get_config()

torch_device = None
def get_torch_device():
    global torch_device
    if torch_device is None:
        torch_device = torch.device("cuda:0") if torch.cuda.is_available() else torch.device("cpu")
        print(f"Using torch device: {torch_device}")
    
    return torch_device

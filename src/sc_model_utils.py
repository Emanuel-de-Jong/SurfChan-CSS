import os
from datetime import datetime
from sc_config import get_config
import torch
from tensordict.nn import TensorDictModule
from torchrl.data.tensor_specs import Bounded, Composite
from torchrl.envs.utils import ExplorationType
from torchrl.objectives import ClipPPOLoss
from torchrl.modules import (
    ProbabilisticActor,
    TanhNormal,
    ValueOperator,
    ConvNet,
    MLP,
    ActorValueOperator,
    NormalParamExtractor
)

class SCModels():
    actor=None
    critic=None
    loss_module=None
    optimizer=None

    def __init__(self, actor=None, critic=None, loss_module=None, optimizer=None):
        self.actor = actor
        self.critic = critic
        self.loss_module = loss_module
        self.optimizer = optimizer

class SCStats():
    update_count=None
    step_times=None
    game_speed=None

    def __init__(self, update_count=None, step_times=None, game_speed=None):
        self.update_count = update_count
        self.step_times = step_times
        self.game_speed = game_speed

config = get_config()

torch_device = None
def get_torch_device():
    global torch_device
    if torch_device is None:
        torch_device = torch.device("cuda:0") if torch.cuda.is_available() else torch.device("cpu")
        print(f"Using torch device: {torch_device}")
    
    return torch_device

def get_models(env, device):
    global config
    models, stats = None, None
    if config.train.should_resume:
        models, stats = load_latest_models(env, device)

    if models is None:
        print(f"Created new models")
        models = create_models(env, device)

        stats = SCStats()
        stats.update_count = torch.zeros((), dtype=torch.int64, device=device)
        stats.step_times = []
        stats.game_speed = config.env.game_speed

    return models, stats

def load_latest_models(env, device):
    global config
    results_dir = config.model.results_dir
    if not os.path.exists(results_dir):
        return None, None
    
    result_paths = [os.path.join(results_dir, p) for p in os.listdir(results_dir)]
    checkpoint_paths = [p for p in result_paths if p.endswith('checkpoint.pth')]
    if len(checkpoint_paths) == 0:
        return None, None
    
    checkpoint_path = max(checkpoint_paths, key=os.path.getctime)
    checkpoint = torch.load(checkpoint_path, map_location=device)

    models = create_models(env, device)
    models.actor.load_state_dict(checkpoint["models"]["actor"])
    models.critic.load_state_dict(checkpoint["models"]["critic"])
    models.optimizer.load_state_dict(checkpoint["models"]["optimizer"])

    stats = SCStats()
    stats.update_count = torch.tensor(checkpoint["stats"]["update_count"], dtype=torch.int64, device=device)
    stats.step_times = checkpoint["stats"]["step_times"]
    stats.game_speed = checkpoint["stats"]["game_speed"]

    models_date = datetime.fromtimestamp(os.path.getctime(checkpoint_path)).strftime("%d-%m-%y %H:%M:%S")
    print(f"Loaded models from {models_date} (update count: {stats.update_count.item()})")

    return models, stats

def create_models(env, device):
    global config
    input_shape = env.observation_spec["pixels"].shape
    num_outputs = env.action_spec.shape[0]

    common_cnn = ConvNet(
        activation_class=torch.nn.ReLU,
        num_cells=[32, 64, 64],
        kernel_sizes=[8, 4, 3],
        strides=[4, 2, 1],
        device=device,
    )

    # TODO: Remove
    # class DebugCNNWrapper(torch.nn.Module):
    #     def __init__(self, cnn):
    #         super().__init__()
    #         self.cnn = cnn

    #     def forward(self, x):
    #         print(x)
    #         print(x.shape)
    #         return self.cnn(x)
    # common_cnn = DebugCNNWrapper(common_cnn)

    common_cnn_output = common_cnn(torch.ones(input_shape, device=device))
    common_mlp = MLP(
        in_features=common_cnn_output.shape[-1],
        activation_class=torch.nn.ReLU,
        activate_last_layer=True,
        out_features=512,
        num_cells=[],
        device=device,
    )
    common_mlp_output = common_mlp(common_cnn_output)

    common_module = TensorDictModule(
        module=torch.nn.Sequential(common_cnn, common_mlp),
        in_keys=["pixels"],
        out_keys=["common_features"],
    )

    policy_net = MLP(
        in_features=common_mlp_output.shape[-1],
        out_features=num_outputs * 2,
        activation_class=torch.nn.ReLU,
        num_cells=[],
        device=device,
    )

    policy_module = TensorDictModule(
        module=policy_net,
        in_keys=["common_features"],
        out_keys=["policy_params"],
    )

    policy_module = TensorDictModule(
        module=torch.nn.Sequential(
            policy_module,
            NormalParamExtractor(scale_mapping="biased_softplus_1", scale_lb=0.01)
        ),
        in_keys=["common_features"],
        out_keys=["loc", "scale"],
    )

    policy_module = ProbabilisticActor(
        policy_module,
        in_keys=["loc", "scale"],
        spec=env.action_spec.to(device),
        distribution_class=TanhNormal,
        distribution_kwargs={
            "low": 0.0,
            "high": 1.0,
        },
        return_log_prob=True,
        default_interaction_type=ExplorationType.RANDOM,
    )

    value_net = MLP(
        activation_class=torch.nn.ReLU,
        in_features=common_mlp_output.shape[-1],
        out_features=1,
        num_cells=[],
        device=device,
    )
    value_module = ValueOperator(
        value_net,
        in_keys=["common_features"],
    )

    actor_critic = ActorValueOperator(
        common_operator=common_module,
        policy_operator=policy_module,
        value_operator=value_module,
    )

    with torch.no_grad():
        td = env.fake_tensordict().expand(10)
        actor_critic(td)
        del td

    actor = actor_critic.get_policy_operator()
    critic = actor_critic.get_value_operator()

    loss_module = ClipPPOLoss(
        actor_network=actor,
        critic_network=critic,
        clip_epsilon=config.train.loss.clip_epsilon,
        loss_critic_type=config.train.loss.loss_critic_type,
        entropy_coef=config.train.loss.entropy_coefficient,
        critic_coef=config.train.loss.critic_coefficient,
        normalize_advantage=True,
    )

    optimizer = torch.optim.Adam(
        loss_module.parameters(),
        lr=config.train.optimizer.lr,
        weight_decay=config.train.optimizer.weight_decay,
        eps=config.train.optimizer.epsilon,
    )

    return SCModels(actor, critic, loss_module, optimizer)

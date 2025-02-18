import copy
from collections import defaultdict
import matplotlib.pyplot as plt
from tqdm import tqdm
import torch
from torch import nn
from tensordict.nn import TensorDictModule, set_composite_lp_aggregate
from tensordict.nn.distributions import NormalParamExtractor
from torchrl.collectors import SyncDataCollector
from torchrl.data.tensor_specs import BoundedTensorSpec, CompositeSpec
from torchrl.data.data_buffers import ReplayBuffer
from torchrl.data.data_buffers.samplers import SamplerWithoutReplacement
from torchrl.data.data_buffers.storages import LazyTensorStorage
from torchrl.envs.utils import ExplorationType, set_exploration_type
from torchrl.modules import ProbabilisticActor, TanhNormal, ValueOperator, ConvNet, MLP, ActorValueOperator
from torchrl.objectives import ClipPPOLoss
from torchrl.objectives.value import GAE
from torchrl.record.loggers.tensorboard import TensorboardLogger
from config import get_config

class SCTrain():
    def __init__(self, env):
        self.env = env
        
        self.config = get_config()
        
        self.device = torch.device("cuda:0") if torch.cuda.is_available() else torch.device("cpu")
        nodes_per_layer = 256
        max_grad_norm = 1.0

        max_steps=4500
        frames_per_batch = 1000
        total_frames = frames_per_batch * 10

        sub_batch_size = 64
        num_epochs = 10
        clip_epsilon = 0.2
        gamma = 0.99
        lmbda = 0.95
        entropy_eps = 0.0001

        input_shape = env.observation_spec["pixels"].shape

        num_outputs = 8
        distribution_kwargs = {
            "low": 0.0,
            "high": 1.0,
        }

        common_cnn = ConvNet(
            activation_class=torch.nn.ReLU,
            num_cells=[32, 64, 64],
            kernel_sizes=[8, 4, 3],
            strides=[4, 2, 1],
            device=self.device,
        )
        common_cnn_output = common_cnn(torch.ones(input_shape, device=self.device))

        common_mlp = MLP(
            in_features=common_cnn_output.shape[-1],
            activation_class=torch.nn.ReLU,
            activate_last_layer=True,
            out_features=512,
            num_cells=[],
            device=self.device,
        )
        common_mlp_output = common_mlp(common_cnn_output)

        common_module = TensorDictModule(
            module=torch.nn.Sequential(common_cnn, common_mlp),
            in_keys=["pixels"],
            out_keys=["common_features"],
        )

        policy_net = MLP(
            in_features=common_mlp_output.shape[-1],
            out_features=num_outputs,
            activation_class=torch.nn.ReLU,
            num_cells=[],
            device=self.device,
        )
        policy_module = TensorDictModule(
            module=policy_net,
            in_keys=["common_features"],
            out_keys=["logits"],
        )

        spec = CompositeSpec(
            action=BoundedTensorSpec(
                low=0.0, high=1.0, shape=(num_outputs,), dtype=torch.float32, device=self.device
            )
        )
        policy_module = ProbabilisticActor(
            policy_module,
            in_keys=["logits"],
            spec=spec,
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
            device=self.device,
        )
        value_module = ValueOperator(
            value_net,
            in_keys=["common_features"],
        )
        dummy_tensordict = env.reset()
        value_module(dummy_tensordict)

        actor_critic = ActorValueOperator(
            common_operator=common_module,
            policy_operator=policy_module,
            value_operator=value_module,
        )

        actor = actor_critic.get_policy_operator()
        critic = actor_critic.get_value_operator()

        collector = SyncDataCollector(
            create_env_fn=env,
            policy=actor,
            frames_per_batch=frames_per_batch,
            total_frames=total_frames,
            device=self.device,
            max_frames_per_traj=-1,
        )

        data_buffer = ReplayBuffer(
            storage=LazyTensorStorage(
                max_size=frames_per_batch,
                device=self.device
            ),
            sampler=SamplerWithoutReplacement(),
            batch_size=sub_batch_size,
        )

        adv_module = GAE(
            gamma=gamma,
            lmbda=lmbda,
            value_network=critic,
            average_gae=False,
            device=self.device
        )

        loss_module = ClipPPOLoss(
            actor_network=actor,
            critic_network=critic,
            clip_epsilon=clip_epsilon,
            loss_critic_type="smooth_l1",
            entropy_coef=entropy_eps,
            entropy_bonus=bool(entropy_eps),
            critic_coef=1.0,
            normalize_advantage=True
        )

        adv_module.set_keys(done="end-of-life", terminated="end-of-life")
        loss_module.set_keys(done="end-of-life", terminated="end-of-life")

        optim = torch.optim.Adam(loss_module.parameters(), self.config.train.lr)
        scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
            optim, total_frames // frames_per_batch, 0.0
        )

        logger = TensorboardLogger("SCLogger", "logs")

        test_env = copy.deepcopy(env)
        test_env.eval()

        logs = defaultdict(list)
        pbar = tqdm(total=total_frames)
        eval_str = ""

        for i, tensordict_data in enumerate(collector):
            for _ in range(num_epochs):
                adv_module(tensordict_data)
                data_view = tensordict_data.reshape(-1)
                data_buffer.extend(data_view.cpu())
                for _ in range(frames_per_batch // sub_batch_size):
                    subdata = data_buffer.sample(sub_batch_size)
                    loss_vals = loss_module(subdata.to(device))
                    loss_value = (
                        loss_vals["loss_objective"]
                        + loss_vals["loss_critic"]
                        + loss_vals["loss_entropy"]
                    )

                    loss_value.backward()
                    torch.nn.utils.clip_grad_norm_(loss_module.parameters(), max_grad_norm)
                    optim.step()
                    optim.zero_grad()

            logs["reward"].append(tensordict_data["next", "reward"].mean().item())
            pbar.update(tensordict_data.numel())
            cum_reward_str = (
                f"average reward={logs['reward'][-1]: 4.4f} (init={logs['reward'][0]: 4.4f})"
            )
            logs["step_count"].append(tensordict_data["step_count"].max().item())
            stepcount_str = f"step count (max): {logs['step_count'][-1]}"
            logs["lr"].append(optim.param_groups[0]["lr"])
            lr_str = f"lr policy: {logs['lr'][-1]: 4.4f}"
            if i % 10 == 0:
                with set_exploration_type(ExplorationType.DETERMINISTIC), torch.no_grad():
                    eval_rollout = env.rollout(1000, policy_module)
                    logs["eval reward"].append(eval_rollout["next", "reward"].mean().item())
                    logs["eval reward (sum)"].append(
                        eval_rollout["next", "reward"].sum().item()
                    )
                    logs["eval step_count"].append(eval_rollout["step_count"].max().item())
                    eval_str = (
                        f"eval cumulative reward: {logs['eval reward (sum)'][-1]: 4.4f} "
                        f"(init: {logs['eval reward (sum)'][0]: 4.4f}), "
                        f"eval step-count: {logs['eval step_count'][-1]}"
                    )
                    del eval_rollout
            pbar.set_description(", ".join([eval_str, cum_reward_str, stepcount_str, lr_str]))
            scheduler.step()

        plt.figure(figsize=(10, 10))
        plt.subplot(2, 2, 1)
        plt.plot(logs["reward"])
        plt.title("training rewards (average)")
        plt.subplot(2, 2, 2)
        plt.plot(logs["step_count"])
        plt.title("Max step count (training)")
        plt.subplot(2, 2, 3)
        plt.plot(logs["eval reward (sum)"])
        plt.title("Return (test)")
        plt.subplot(2, 2, 4)
        plt.plot(logs["eval step_count"])
        plt.title("Max step count (test)")
        plt.show()

import os
import shutil
import time
from datetime import datetime
import tqdm
import torch
from tensordict import TensorDict
from tensordict.nn import TensorDictModule
from torchrl.collectors import SyncDataCollector
from torchrl.data import LazyTensorStorage, TensorDictReplayBuffer
from torchrl.data.tensor_specs import Bounded, Composite
from torchrl.data.replay_buffers.samplers import SamplerWithoutReplacement
from torchrl.envs.utils import ExplorationType, set_exploration_type
from torchrl.modules import (
    ProbabilisticActor,
    TanhNormal,
    ValueOperator,
    ConvNet,
    MLP,
    ActorValueOperator,
    NormalParamExtractor
)
from torchrl.objectives import ClipPPOLoss
from torchrl.objectives.value import GAE
from torchrl.record import VideoRecorder
from torchrl.record.loggers.tensorboard import TensorboardLogger
from torchrl._utils import compile_with_warmup, timeit
from sc_config import get_config, CONFIG_FILE_NAME
from SCEnv import create_torchrl_env

class SCTrain():
    def __init__(self):
        self.config = get_config()
        
        torch.set_float32_matmul_precision("high")

        self.device = torch.device("cuda:0") if torch.cuda.is_available() else torch.device("cpu")

        frames_per_batch = self.config.train.collector.frames_per_batch
        total_frames = frames_per_batch * self.config.train.collector.batches
        mini_batch_size = self.config.train.loss.mini_batch_size

        should_compile = self.config.train.compile
        compile_mode = False # "reduce-overhead"
        
        self.env = create_torchrl_env(self.config.env.name, self.config.train.map)
        
        actor, critic = self.make_models()

        collector = SyncDataCollector(
            create_env_fn=self.env,
            policy=actor,
            frames_per_batch=frames_per_batch,
            total_frames=total_frames,
            device=self.device,
            max_frames_per_traj=-1,
            compile_policy={"mode": compile_mode, "warmup": 1} if compile_mode else False
        )

        sampler = SamplerWithoutReplacement()
        data_buffer = TensorDictReplayBuffer(
            storage=LazyTensorStorage(
                frames_per_batch, compilable=should_compile, device=self.device
            ),
            sampler=sampler,
            batch_size=mini_batch_size,
            compilable=should_compile,
        )

        adv_module = GAE(
            gamma=self.config.train.loss.gamma,
            lmbda=self.config.train.loss.gae_lambda,
            value_network=critic,
            average_gae=False,
            device=self.device,
            vectorized=not should_compile,
        )
        loss_module = ClipPPOLoss(
            actor_network=actor,
            critic_network=critic,
            clip_epsilon=self.config.train.loss.clip_epsilon,
            loss_critic_type=self.config.train.loss.loss_critic_type,
            entropy_coef=self.config.train.loss.entropy_coef,
            critic_coef=self.config.train.loss.critic_coef,
            normalize_advantage=True,
        )

        optim = torch.optim.Adam(
            loss_module.parameters(),
            lr=self.config.train.optim.lr,
            weight_decay=self.config.train.optim.weight_decay,
            eps=self.config.train.optim.eps,
        )

        date_str = datetime.now().strftime("%d-%m_%H-%M")
        logger = TensorboardLogger(exp_name=date_str, log_dir=f"{self.config.model.results_dir}/logs")

        collected_frames = 0
        num_network_updates = torch.zeros((), dtype=torch.int64, device=self.device)
        pbar = tqdm.tqdm(total=total_frames)
        num_mini_batches = frames_per_batch // mini_batch_size
        total_network_updates = (
            (total_frames // frames_per_batch) * self.config.train.loss.ppo_epochs * num_mini_batches
        )

        def update(batch, num_network_updates):
            optim.zero_grad(set_to_none=True)

            alpha = torch.ones((), device=self.device)
            if cfg_optim_anneal_lr:
                alpha = 1 - (num_network_updates / total_network_updates)
                for group in optim.param_groups:
                    group["lr"] = cfg_optim_lr * alpha
            if cfg_loss_anneal_clip_eps:
                loss_module.clip_epsilon.copy_(cfg_loss_clip_epsilon * alpha)
            num_network_updates = num_network_updates + 1
            
            batch = batch.to(self.device, non_blocking=True)

            loss = loss_module(batch)
            loss_sum = loss["loss_critic"] + loss["loss_objective"] + loss["loss_entropy"]
            
            loss_sum.backward()
            torch.nn.utils.clip_grad_norm_(
                loss_module.parameters(), max_norm=cfg_optim_max_grad_norm
            )

            optim.step()
            return loss.detach().set("alpha", alpha), num_network_updates

        if should_compile:
            update = compile_with_warmup(update, mode=compile_mode, warmup=1)
            adv_module = compile_with_warmup(adv_module, mode=compile_mode, warmup=1)

        cfg_loss_ppo_epochs = self.config.train.loss.ppo_epochs
        cfg_optim_anneal_lr = self.config.train.optim.anneal_lr
        cfg_optim_lr = self.config.train.optim.lr
        cfg_loss_anneal_clip_eps = self.config.train.loss.anneal_clip_epsilon
        cfg_loss_clip_epsilon = self.config.train.loss.clip_epsilon
        cfg_optim_max_grad_norm = self.config.train.optim.max_grad_norm
        
        losses = TensorDict(batch_size=[cfg_loss_ppo_epochs, num_mini_batches])

        training_seconds_start = time.time()

        collector_iter = iter(collector)
        total_iter = len(collector)
        for i in range(total_iter):
            timeit.printevery(1000, total_iter, erase=True)

            with timeit("collecting"):
                data = next(collector_iter)

            metrics_to_log = {}
            frames_in_batch = data.numel()
            collected_frames += frames_in_batch
            pbar.update(frames_in_batch)

            episode_rewards = data["next", "episode_reward"][data["next", "terminated"]]
            if len(episode_rewards) > 0:
                episode_length = data["next", "step_count"][data["next", "terminated"]]
                metrics_to_log.update(
                    {
                        "train/reward": episode_rewards.mean().item(),
                        "train/episode_length": episode_length.sum().item()
                        / len(episode_length),
                    }
                )

            with timeit("training"):
                for j in range(cfg_loss_ppo_epochs):
                    with torch.no_grad(), timeit("adv"):
                        data = adv_module(data)
                        if compile_mode:
                            data = data.clone()
                    with timeit("rb - extend"):
                        data_reshape = data.reshape(-1)
                        data_buffer.extend(data_reshape)

                    for k, batch in enumerate(data_buffer):
                        if k >= num_mini_batches:
                            break
                        
                        with timeit("update"):
                            loss, num_network_updates = update(
                                batch, num_network_updates=num_network_updates
                            )
                        loss = loss.clone()
                        num_network_updates = num_network_updates.clone()
                        losses[j, k] = loss.select(
                            "loss_critic", "loss_entropy", "loss_objective"
                        )

            losses_mean = losses.apply(lambda x: x.float().mean(), batch_size=[])
            for key, value in losses_mean.items():
                metrics_to_log.update({f"train/{key}": value.item()})
            metrics_to_log.update(
                {
                    "train/lr": loss["alpha"] * cfg_optim_lr,
                    "train/clip_epsilon": loss["alpha"] * cfg_loss_clip_epsilon,
                }
            )

            if logger:
                metrics_to_log.update(timeit.todict(prefix="time"))
                metrics_to_log["time/speed"] = pbar.format_dict["rate"]
                for key, value in metrics_to_log.items():
                    logger.log_scalar(key, value, collected_frames)

            collector.update_policy_weights_()
        
        pbar.close()

        training_seconds = time.time() - training_seconds_start
        print(f"Training time: {training_seconds:.2f}s or {training_seconds/60:.2f}m or {training_seconds/3600:.2f}h")

        self.save(actor, critic, date_str)

        collector.shutdown()
        
    def make_models(self):
        input_shape = self.env.observation_spec["pixels"].shape
        num_outputs = self.env.action_spec.shape[0]

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
            in_features=common_mlp.out_features,
            out_features=num_outputs * 2,
            activation_class=torch.nn.ReLU,
            num_cells=[],
            device=self.device,
        )
        policy_module = TensorDictModule(
            module=torch.nn.Sequential(
                policy_net,
                NormalParamExtractor(scale_mapping="exp")
            ),
            in_keys=["common_features"],
            out_keys=["loc", "scale"],
        )

        spec = Composite(
            action=Bounded(
                low=0.0, high=1.0, shape=(num_outputs,), dtype=torch.float32, device=self.device
            )
        )

        policy_module = ProbabilisticActor(
            policy_module,
            in_keys=["loc", "scale"],
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

        actor_critic = ActorValueOperator(
            common_operator=common_module,
            policy_operator=policy_module,
            value_operator=value_module,
        )

        with torch.no_grad():
            td = self.env.fake_tensordict().expand(10)
            actor_critic(td)
            del td

        actor = actor_critic.get_policy_operator()
        critic = actor_critic.get_value_operator()

        return actor, critic
    
    def save(self, actor, critic, date_str):
        results_dir = self.config.model.results_dir
        if not os.path.exists(results_dir):
            os.makedirs(results_dir)
        
        print("Saving results...")
        shutil.copy2(CONFIG_FILE_NAME, os.path.join(results_dir, f"{date_str}_config.yml"))
        torch.save(actor.state_dict(), os.path.join(results_dir, f"{date_str}_actor.pth"))
        torch.save(critic.state_dict(), os.path.join(results_dir, f"{date_str}_critic.pth"))

    def close(self):
        pass

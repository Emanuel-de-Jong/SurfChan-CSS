import os
import shutil
import time
from datetime import datetime
import tqdm
import torch
from tensordict import TensorDict
from torchrl.collectors import SyncDataCollector
from torchrl.data import LazyTensorStorage, TensorDictReplayBuffer
from torchrl.data.replay_buffers.samplers import SamplerWithoutReplacement
from torchrl.objectives.value import GAE
from torchrl.record.loggers.tensorboard import TensorboardLogger
from torchrl._utils import compile_with_warmup, timeit
from sc_config import get_config, CONFIG_FILE_NAME
from sc_utils import get_torch_device
from sc_model_utils import get_models
from SCEnv import create_torchrl_env

class SCTrain():
    def __init__(self):
        self.config = get_config()
        
        torch.set_float32_matmul_precision("high")

        self.device = get_torch_device()

        frames_per_batch = self.config.train.collector.frames_per_batch
        total_frames = frames_per_batch * self.config.train.collector.batches
        mini_batch_size = self.config.train.loss.mini_batch_size

        should_compile = self.config.train.compile
        compile_mode = False # "reduce-overhead"
        
        self.env = create_torchrl_env(self.config.env.name, self.config.train.map)
        
        actor, critic, loss_module, optim = get_models(self.env, self.device)

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

        self.save(actor, critic, optim, date_str)

        collector.shutdown()
    
    def save(self, actor, critic, optim, date_str):
        results_dir = self.config.model.results_dir
        if not os.path.exists(results_dir):
            os.makedirs(results_dir)
        
        print("Saving results...")
        shutil.copy2(CONFIG_FILE_NAME, os.path.join(results_dir, f"{date_str}_config.yml"))
        torch.save(actor.state_dict(), os.path.join(results_dir, f"{date_str}_actor.pth"))
        torch.save(critic.state_dict(), os.path.join(results_dir, f"{date_str}_critic.pth"))
        torch.save(optim.state_dict(), os.path.join(results_dir, f"{date_str}_optim.pth"))

    def close(self):
        pass

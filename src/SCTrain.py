import os
import shutil
import time
import asyncio
from datetime import datetime
import tqdm
import torch
from tensordict import TensorDict
from torchrl.collectors import SyncDataCollector
from torchrl.data import LazyTensorStorage, TensorDictReplayBuffer
from torchrl.data.replay_buffers.samplers import SamplerWithoutReplacement
from torchrl.objectives.value import GAE
from torchrl.record.loggers.tensorboard import TensorboardLogger
from torchrl._utils import compile_with_warmup
from sc_config import get_config, CONFIG_FILE_NAME
from sc_model_utils import get_torch_device, get_models
from SCEnv import create_torchrl_env
from SCTimer import sc_timer

class SCTrain():
    async def train(self):
        self.config = get_config()
        self.collector_conf = self.config.train.collector
        self.optimizer_conf = self.config.train.optimizer
        self.loss_conf = self.config.train.loss
        
        torch.set_float32_matmul_precision("high")

        self.device = get_torch_device()

        frames_per_batch = self.collector_conf.frames_per_batch
        total_frames = frames_per_batch * self.collector_conf.batches

        should_compile = self.config.train.should_compile
        compile_mode = "reduce-overhead" if should_compile else None
        
        self.env = create_torchrl_env(self.config.train.map)
        
        self.models, self.stats = get_models(self.env, self.device)

        self.collector = SyncDataCollector(
            create_env_fn=self.env,
            policy=self.models.actor,
            frames_per_batch=frames_per_batch,
            total_frames=total_frames,
            device=self.device,
            max_frames_per_traj=-1,
            compile_policy={"mode": compile_mode, "warmup": 1} if compile_mode else False
        )

        mini_batch_size = frames_per_batch // self.loss_conf.mini_batches_per_batch
        sampler = SamplerWithoutReplacement()
        data_buffer = TensorDictReplayBuffer(
            storage=LazyTensorStorage(
                frames_per_batch, compilable=should_compile, device=self.device
            ),
            sampler=sampler,
            batch_size=mini_batch_size,
            compilable=should_compile,
        )

        advantage_module = GAE(
            gamma=self.loss_conf.gamma,
            lmbda=self.loss_conf.gae_lambda,
            value_network=self.models.critic,
            average_gae=False,
            device=self.device,
            vectorized=not should_compile,
        )

        self.date_str = datetime.now().strftime("%d-%m_%H-%M")
        logger = None
        if self.config.train.should_save:
            logger = TensorboardLogger(exp_name=self.date_str, log_dir=f"{self.config.model.results_dir}/logs")

        collected_frames = 0
        pbar = tqdm.tqdm(total=total_frames)
        self.total_network_updates = (
            (total_frames // frames_per_batch) *
            self.loss_conf.ppo_epochs *
            self.loss_conf.mini_batches_per_batch
        )

        if should_compile:
            self.update = compile_with_warmup(self.update, mode=compile_mode, warmup=1)
            advantage_module = compile_with_warmup(advantage_module, mode=compile_mode, warmup=1)
        
        losses = TensorDict(batch_size=[self.loss_conf.ppo_epochs, self.loss_conf.mini_batches_per_batch])

        sc_timer.start("training")

        collector_iter = iter(self.collector)
        total_iter = len(self.collector)
        for i in range(total_iter):
            await asyncio.sleep(0.1)

            sc_timer.start("collecting", "tb")
            data = next(collector_iter)
            sc_timer.stop("collecting", "tb")

            if i != total_iter - 1:
                self.env.env.reset()

            metrics_to_log = {}
            frames_in_batch = data.numel()
            collected_frames += frames_in_batch
            pbar.update(frames_in_batch)

            episode_rewards = data["next", "episode_reward"][data["next", "terminated"]]
            if len(episode_rewards) > 0:
                metrics_to_log.update({"train/reward": episode_rewards.mean().item()})

            sc_timer.start("training", "tb")
            for j in range(self.loss_conf.ppo_epochs):
                with torch.no_grad():
                    sc_timer.start("advantage", "tb")
                    data = advantage_module(data)
                    if compile_mode:
                        data = data.clone()
                    sc_timer.stop("advantage", "tb")
                
                sc_timer.start("rb extend", "tb")
                data_reshape = data.reshape(-1)
                data_buffer.extend(data_reshape)
                sc_timer.stop("rb extend", "tb")

                for k, batch in enumerate(data_buffer):
                    if k >= self.loss_conf.mini_batches_per_batch:
                        break
                    
                    sc_timer.start("update", "tb")
                    loss = self.update(batch)
                    sc_timer.stop("update", "tb")

                    loss = loss.clone()
                    losses[j, k] = loss.select(
                        "loss_critic", "loss_entropy", "loss_objective"
                    )
            sc_timer.stop("training", "tb")

            losses_mean = losses.apply(lambda x: x.float().mean(), batch_size=[])
            for key, value in losses_mean.items():
                metrics_to_log.update({f"train/{key}": value.item()})
            metrics_to_log.update(
                {
                    "train/lr": loss["alpha"] * self.optimizer_conf.lr,
                    "train/clip_epsilon": loss["alpha"] * self.loss_conf.clip_epsilon,
                }
            )

            if logger:
                avg_batch_step_time = self.get_avg_batch_step_time()
                self.stats.step_times.append(avg_batch_step_time)

                time_dict = sc_timer.to_dict("tb", "time/")
                time_dict["time/avg_step"] = avg_batch_step_time
                metrics_to_log.update(time_dict)
                metrics_to_log["time/speed"] = pbar.format_dict["rate"]
                for key, value in metrics_to_log.items():
                    logger.log_scalar(key, value, collected_frames)

            self.collector.update_policy_weights_()
        
        pbar.close()

    def update(self, batch):
        self.models.optimizer.zero_grad(set_to_none=True)

        alpha = torch.ones((), device=self.device)
        if self.optimizer_conf.anneal_lr:
            alpha = 1 - (self.stats.update_count / self.total_network_updates)
            for group in self.models.optimizer.param_groups:
                group["lr"] = self.optimizer_conf.lr * alpha
        if self.loss_conf.anneal_clip_epsilon:
            self.models.loss_module.clip_epsilon.copy_(self.loss_conf.clip_epsilon * alpha)
        self.stats.update_count += 1
        
        batch = batch.to(self.device, non_blocking=True)

        if "sample_log_prob" in batch:
            batch["sample_log_prob"] = batch["sample_log_prob"].clamp(-10, 10)

        loss = self.models.loss_module(batch)
        loss_sum = loss["loss_critic"] + loss["loss_objective"] + loss["loss_entropy"]
        
        loss_sum.backward()
        torch.nn.utils.clip_grad_norm_(
            self.models.loss_module.parameters(), max_norm=self.optimizer_conf.max_gradient_norm
        )

        self.models.optimizer.step()
        return loss.detach().set("alpha", alpha)
    
    def get_avg_batch_step_time(self):
        step_times = sc_timer.get("step")
        sc_timer.clear("step")

        # Last step is always longer because it includes collector finish time
        step_times.pop()
        avg_step_time = sum(step_times) / len(step_times)

        treshold = avg_step_time * 2
        step_times = [time for time in step_times if time < treshold]
        return sum(step_times) / len(step_times)

    def close(self):
        self.save()

        if not self.collector is None:
            self.collector.shutdown()

    def save(self):
        if not self.config.train.should_save:
            return

        if self.models.actor is None or self.models.critic is None or self.models.optimizer is None \
                or self.stats.update_count is None or self.date_str is None \
                or self.stats.step_times is None:
            return

        results_dir = self.config.model.results_dir
        if not os.path.exists(results_dir):
            os.makedirs(results_dir)
        
        print("Saving results...")
        shutil.copy2(CONFIG_FILE_NAME, os.path.join(results_dir, f"{self.date_str}_config.yml"))

        checkpoint = {
            "models": {
                "actor": self.models.actor.state_dict(),
                "critic": self.models.critic.state_dict(),
                "optimizer": self.models.optimizer.state_dict(),
            },
            "stats": {
                "update_count": self.stats.update_count.item(),
                "step_times": self.stats.step_times,
                "game_speed": self.config.env.game_speed,
            },
        }
        torch.save(checkpoint, os.path.join(results_dir, f"{self.date_str}_checkpoint.pth"))

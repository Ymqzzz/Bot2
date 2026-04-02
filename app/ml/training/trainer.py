from __future__ import annotations

from dataclasses import dataclass

from app.ml.config import PPOConfig

try:
    from stable_baselines3 import A2C, PPO, SAC
except Exception:
    PPO = A2C = SAC = None


@dataclass(frozen=True)
class TrainResult:
    algo: str
    timesteps: int


def train_policy(env, algo: str, config: PPOConfig, total_timesteps: int = 10_000):
    if algo == "ppo":
        if PPO is None:
            raise RuntimeError("stable_baselines3 is required for PPO training")
        model = PPO("MlpPolicy", env, learning_rate=config.learning_rate, gamma=config.gamma, gae_lambda=config.gae_lambda, ent_coef=config.ent_coef, clip_range=config.clip_range, batch_size=config.batch_size, n_steps=config.n_steps, max_grad_norm=config.max_grad_norm, verbose=0)
    elif algo == "a2c":
        if A2C is None:
            raise RuntimeError("stable_baselines3 is required for A2C training")
        model = A2C("MlpPolicy", env, learning_rate=config.learning_rate, gamma=config.gamma, gae_lambda=config.gae_lambda, ent_coef=config.ent_coef, verbose=0)
    elif algo == "sac":
        if SAC is None:
            raise RuntimeError("stable_baselines3 is required for SAC training")
        model = SAC("MlpPolicy", env, learning_rate=config.learning_rate, gamma=config.gamma, batch_size=config.batch_size, verbose=0)
    else:
        raise ValueError(f"unsupported algo: {algo}")
    model.learn(total_timesteps=total_timesteps)
    return model, TrainResult(algo=algo, timesteps=total_timesteps)

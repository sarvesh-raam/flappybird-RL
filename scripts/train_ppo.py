import gymnasium as gym
import flappy_bird_gymnasium
from stable_baselines3 import PPO
from stable_baselines3.common.callbacks import CheckpointCallback
import os

class RewardShapingWrapper(gym.Wrapper):
    """
    Custom wrapper to shape the reward function.
    Helps the agent learn to stay in the middle of the pipes.
    """
    def step(self, action):
        obs, reward, terminated, truncated, info = self.env.step(action)
        
        # obs is usually a numpy array: [bird_y, bird_v, pipe_x, pipe_y, ...]
        bird_y = obs[0]
        # In flappy-bird-gymnasium V0, index 3 is the next pipe's top edge or center? 
        # Typically it is the gap's vertical position.
        pipe_y = obs[3] 
        
        # Calculate distance to center of pipe gap
        dist = abs(bird_y - pipe_y)
        
        # Small bonus for staying near the center (max 0.1 bonus per step)
        bonus = max(0, 0.1 - (dist * 0.2))
        
        return obs, reward + bonus, terminated, truncated, info

def train_ppo():
    # 1. Create the environment
    env = gym.make("FlappyBird-v0", render_mode="rgb_array")
    # Apply reward shaping
    env = RewardShapingWrapper(env)

    # 2. Define PPO model (More stable than DQN)
    model = PPO(
        "MlpPolicy",
        env,
        verbose=1,
        learning_rate=3e-4,
        n_steps=2048,
        batch_size=64,
        n_epochs=10,
        gamma=0.99,
        gae_lambda=0.95,
        clip_range=0.2,
        ent_coef=0.01, # Encourage exploration
        tensorboard_log="./logs/flappy_ppo/"
    )

    # 3. Setup Checkpoints
    checkpoint_callback = CheckpointCallback(
        save_freq=20000,
        save_path='./models_ppo/',
        name_prefix='flappy_ppo'
    )

    # 4. Train the agent
    print("Starting PPO training (300,000 steps)...")
    model.learn(total_timesteps=300000, callback=checkpoint_callback)

    # 5. Save the final model
    model.save("flappy_ppo_final")
    print("Training complete. Model saved as flappy_ppo_final.")

if __name__ == "__main__":
    if not os.path.exists('./models_ppo/'):
        os.makedirs('./models_ppo/')
    train_ppo()

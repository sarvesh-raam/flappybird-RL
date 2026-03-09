import gymnasium as gym
import flappy_bird_gymnasium
from stable_baselines3 import DQN
from stable_baselines3.common.callbacks import CheckpointCallback
import os

def train():
    # 1. Create the environment
    env = gym.make("FlappyBird-v0", render_mode="rgb_array")

    # 2. Define the model with optimized hyperparameters
    # We increase the training time and adjust exploration to find the pipes better
    model = DQN(
        "MlpPolicy",
        env,
        verbose=1,
        learning_rate=5e-4,          # Slightly higher learning rate for faster initial progress
        buffer_size=100000,          # Larger buffer to remember more successes
        learning_starts=1500,        # More initial random exploration
        batch_size=128,              # Larger batch size for more stable gradient updates
        tau=1.0,
        gamma=0.99,                  # Standard discount factor
        train_freq=4,
        gradient_steps=1,
        target_update_interval=1000,
        exploration_fraction=0.2,    # Spend more time exploring (20% of training)
        exploration_final_eps=0.01,
        tensorboard_log="./logs/flappy_dqn_v2/"
    )

    # 3. Setup Checkpoints
    checkpoint_callback = CheckpointCallback(
        save_freq=20000,
        save_path='./models_v2/',
        name_prefix='flappy_dqn'
    )

    # 4. Train the agent with more steps
    print("Starting improved training (250,000 steps)...")
    model.learn(total_timesteps=250000, callback=checkpoint_callback)

    # 5. Save the final model
    model.save("flappy_dqn_v2_final")
    print("Training complete. Model saved as flappy_dqn_v2_final.")

if __name__ == "__main__":
    if not os.path.exists('./models_v2/'):
        os.makedirs('./models_v2/')
    train()

import gymnasium as gym
import flappy_bird_gymnasium
from stable_baselines3 import DQN
from stable_baselines3.common.callbacks import CheckpointCallback
import os

def train():
    # 1. Create the environment
    # Using 'FlappyBird-v0' which provides a state-based observation [bird_y, bird_v, pipe_x, pipe_y]
    env = gym.make("FlappyBird-v0", render_mode="rgb_array")

    # 2. Define the model
    # DQN is suitable for the discrete action space (flap or no flap)
    model = DQN(
        "MlpPolicy",
        env,
        verbose=1,
        learning_rate=1e-4,
        buffer_size=50000,
        learning_starts=1000,
        batch_size=64,
        tau=1.0,
        gamma=0.99,
        train_freq=4,
        gradient_steps=1,
        target_update_interval=1000,
        exploration_fraction=0.1,
        exploration_final_eps=0.01,
        tensorboard_log="./logs/flappy_dqn_tensorboard/"
    )

    # 3. Setup Checkpoints
    checkpoint_callback = CheckpointCallback(
        save_freq=10000,
        save_path='./models/',
        name_prefix='flappy_dqn'
    )

    # 4. Train the agent
    print("Starting training...")
    model.learn(total_timesteps=100000, callback=checkpoint_callback)

    # 5. Save the final model
    model.save("flappy_dqn_final")
    print("Training complete. Model saved as flappy_dqn_final.")

if __name__ == "__main__":
    if not os.path.exists('./models/'):
        os.makedirs('./models/')
    train()

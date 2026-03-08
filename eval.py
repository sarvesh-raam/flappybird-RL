import gymnasium as gym
import flappy_bird_gymnasium
from stable_baselines3 import DQN
import cv2
import numpy as np
import os

def evaluate_and_record(model_path, output_video="flappy_perfomance.mp4"):
    # 1. Load the model
    model = DQN.load(model_path)

    # 2. Create the environment
    env = gym.make("FlappyBird-v0", render_mode="rgb_array")
    
    obs, info = env.reset()
    done = False
    frames = []

    print("Evaluating and recording...")
    score = 0
    
    while not done:
        # Get frame for video
        frame = env.render()
        frames.append(frame)

        # Get action from model
        action, _states = model.predict(obs, deterministic=True)
        
        # Step environment
        obs, reward, terminated, truncated, info = env.step(action)
        score += reward
        
        done = terminated or truncated

    env.close()

    # 3. Save video using OpenCV
    if frames:
        height, width, layers = frames[0].shape
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        video = cv2.VideoWriter(output_video, fourcc, 30, (width, height))

        for frame in frames:
            # Convert RGB to BGR for OpenCV
            bgr_frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
            video.write(bgr_frame)
        
        video.release()
        print(f"Video saved to {output_video}. Total Reward: {score}")
    else:
        print("No frames captured.")

if __name__ == "__main__":
    # Update with your model name if different
    model_file = "flappy_dqn_final.zip"
    if not os.path.exists(model_file):
        # Fallback to a checkpoint if final isn't found
        print(f"{model_file} not found. Check ./models/ for checkpoints.")
    else:
        evaluate_and_record(model_file)

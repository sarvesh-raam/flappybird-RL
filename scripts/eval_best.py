import gymnasium as gym
import flappy_bird_gymnasium
from stable_baselines3 import PPO, DQN
import cv2
import numpy as np
import os

def record_best_run(model_path, model_type="PPO", num_episodes=10, output_video="best_flappy_run.mp4"):
    # 1. Load the model
    if model_type.upper() == "PPO":
        model = PPO.load(model_path)
    else:
        model = DQN.load(model_path)

    env = gym.make("FlappyBird-v0", render_mode="rgb_array")
    
    best_score = -float('inf')
    best_frames = []

    print(f"Evaluating {num_episodes} episodes to find the best run...")

    for i in range(num_episodes):
        obs, info = env.reset()
        done = False
        current_frames = []
        current_score = 0
        
        while not done:
            frame = env.render()
            current_frames.append(frame)

            action, _states = model.predict(obs, deterministic=True)
            obs, reward, terminated, truncated, info = env.step(action)
            
            # Use gameplay score for best run selection
            current_score = info.get('score', 0)
            done = terminated or truncated

        print(f"Episode {i+1}: Score = {current_score}")
        
        if current_score >= best_score:
            best_score = current_score
            best_frames = current_frames

    env.close()

    # Save the best run
    if best_frames:
        height, width, layers = best_frames[0].shape
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        video = cv2.VideoWriter(output_video, fourcc, 30, (width, height))

        for frame in best_frames:
            bgr_frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
            video.write(bgr_frame)
        
        video.release()
        print(f"\nDONE! Best video saved to {output_video} with Score: {best_score}")
    else:
        print("No frames captured.")

if __name__ == "__main__":
    # Check what models are available
    if os.path.exists("flappy_ppo_final.zip"):
        record_best_run("flappy_ppo_final", "PPO")
    elif os.path.exists("flappy_dqn_v2_final.zip"):
        print("PPO model not found. Using best DQN model for evaluation.")
        record_best_run("flappy_dqn_v2_final", "DQN")
    else:
        print("No final models found to evaluate!")

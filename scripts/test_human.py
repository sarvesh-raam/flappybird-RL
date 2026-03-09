import gymnasium as gym
import flappy_bird_gymnasium
from stable_baselines3 import DQN
import time

def test_human():
    # 1. Load the trained model
    model_path = "flappy_dqn_v2_final.zip"
    try:
        model = DQN.load(model_path)
        print(f"Loaded model from {model_path}")
    except Exception as e:
        print(f"Error loading model: {e}")
        return

    # 2. Create the environment with render_mode="human" to see the window
    env = gym.make("FlappyBird-v0", render_mode="human")
    
    obs, info = env.reset()
    done = False
    score = 0
    
    print("Watching the agent play... Close the window or press Ctrl+C to stop.")
    
    try:
        while not done:
            # Get action from model
            action, _states = model.predict(obs, deterministic=True)
            
            # Step environment
            obs, reward, terminated, truncated, info = env.step(action)
            score += reward
            
            # small delay to make it watchable if needed (env usually handles this in human mode)
            # time.sleep(1/30) 
            
            if terminated or truncated:
                print(f"Game Over! Score: {info.get('score', 0)}")
                obs, info = env.reset()
                score = 0
    except KeyboardInterrupt:
        print("\nStopping visualization...")
    finally:
        env.close()

if __name__ == "__main__":
    test_human()

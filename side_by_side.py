import gymnasium as gym
import flappy_bird_gymnasium
from stable_baselines3 import PPO, DQN
import pygame
import numpy as np
import os
import sys

def main():
    # 1. Setup Pygame
    pygame.init()
    pygame.display.set_caption("FLAPPY BIRD: TOURNAMENT MODE")
    
    screen_width = 288 * 2
    screen_height = 512
    screen = pygame.display.set_mode((screen_width, screen_height))
    clock = pygame.time.Clock()
    font_large = pygame.font.SysFont("Arial", 32, bold=True)
    font_small = pygame.font.SysFont("Arial", 20, bold=True)

    # 2. Setup Environments
    env_human = gym.make("FlappyBird-v0", render_mode="rgb_array")
    env_ai = gym.make("FlappyBird-v0", render_mode="rgb_array")
    
    # 3. Load AI Model Logic (Latest PPO/DQN)
    def load_model():
        model_path = ""
        model_type = "PPO" # Default to PPO
        # Priority: 1. Final PPO, 2. Latest PPO Checkpoint, 3. Final DQN
        if os.path.exists("flappy_ppo_final.zip"):
            model_path = "flappy_ppo_final.zip"
        elif os.path.exists("models_ppo"):
            import glob
            checkpoints = glob.glob("models_ppo/*.zip")
            if checkpoints:
                model_path = max(checkpoints, key=os.path.getmtime)
        
        # Check legacy folder if PPO is not found
        if not model_path:
            legacy_path = os.path.join("legacy_models", "flappy_dqn_v2_final.zip")
            if os.path.exists(legacy_path):
                model_path = legacy_path
                model_type = "DQN"
            
        if model_path:
            return PPO.load(model_path) if model_type == "PPO" else DQN.load(model_path)
        return None

    model = load_model()

    # 4. Global Stats
    total_runs = 0
    best_h = 0
    best_a = 0
    
    # Game States: "START", "RUNNING", "GAMEOVER"
    state = "START"
    
    obs_h, _ = env_human.reset()
    obs_a, _ = env_ai.reset()
    done_h = done_a = False
    score_h = score_a = 0

    running = True
    while running:
        # --- EVENT HANDLING ---
        flap_human = False
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            if event.type == pygame.KEYDOWN:
                if state == "START" and event.key == pygame.K_SPACE:
                    state = "RUNNING"
                    total_runs += 1
                    # Refresh model for latest training progress
                    model = load_model()
                elif state == "GAMEOVER" and event.key == pygame.K_r:
                    obs_h, _ = env_human.reset()
                    obs_a, _ = env_ai.reset()
                    done_h = done_a = False
                    score_h = score_a = 0
                    state = "START"
                elif state == "RUNNING" and event.key == pygame.K_SPACE:
                    flap_human = True

        # --- LOGIC ---
        if state == "RUNNING":
            if not done_a:
                action_ai, _ = model.predict(obs_a, deterministic=True)
                obs_a, _, term_a, trunc_a, info_a = env_ai.step(action_ai)
                score_a = info_a.get('score', 0)
                done_a = term_a or trunc_a
                if score_a > best_a: best_a = score_a

            if not done_h:
                action_h = 1 if flap_human else 0
                obs_h, _, term_h, trunc_h, info_h = env_human.step(action_h)
                score_h = info_h.get('score', 0)
                done_h = term_h or trunc_h
                if score_h > best_h: best_h = score_h
            
            if done_h and done_a:
                state = "GAMEOVER"

        # --- RENDERING ---
        frame_h = env_human.render()
        frame_a = env_ai.render()
        surf_h = pygame.surfarray.make_surface(np.transpose(frame_h, (1, 0, 2)))
        surf_a = pygame.surfarray.make_surface(np.transpose(frame_a, (1, 0, 2)))
        screen.blit(surf_h, (0, 0))
        screen.blit(surf_a, (288, 0))
        pygame.draw.line(screen, (0, 0, 0), (288, 0), (288, 512), 4)

        # Helper for UI boxes
        def draw_ui_box(text, pos, font, color=(255, 255, 255), bgcolor=(40, 40, 40), center=False):
            txt_surf = font.render(text, True, color)
            if center:
                txt_rect = txt_surf.get_rect(center=pos)
            else:
                txt_rect = txt_surf.get_rect(topleft=pos)
            bg_rect = txt_rect.inflate(15, 8)
            pygame.draw.rect(screen, bgcolor, bg_rect)
            pygame.draw.rect(screen, (200, 200, 200), bg_rect, 2)
            screen.blit(txt_surf, txt_rect)

        # Permanent HUD
        draw_ui_box(f"Score: {score_h}", (10, 10), font_large, color=(0, 255, 0))
        draw_ui_box(f"Score: {score_a}", (298, 10), font_large, color=(0, 255, 0))
        draw_ui_box(f"HUMAN BEST: {best_h}", (10, 65), font_small, color=(100, 255, 100))
        draw_ui_box(f"AI BEST: {best_a}", (298, 65), font_small, color=(100, 255, 100))
        
        # Move RUN counter to the bottom center
        draw_ui_box(f"TOTAL ROUNDS: {total_runs}", (288, 485), font_small, center=True)

        if state == "START":
            draw_ui_box("TOURNAMENT MODE", (288, 200), font_large, color=(255, 255, 0), center=True)
            draw_ui_box("Press SPACE to Start Battle", (288, 250), font_small, center=True)
        
        if state == "RUNNING":
            if done_h: draw_ui_box("HUMAN CRASHED!", (144, 250), font_small, color=(255, 50, 50), center=True)
            if done_a: draw_ui_box("AI CRASHED!", (432, 250), font_small, color=(255, 50, 50), center=True)

        if state == "GAMEOVER":
            winner = "HUMAN WINS ROUND!" if score_h > score_a else "AI WINS ROUND!"
            if score_h == score_a: winner = "ROUND TIED!"
            draw_ui_box(winner, (288, 220), font_large, color=(255, 255, 0), center=True)
            draw_ui_box("Press 'R' to Start Next Round", (288, 270), font_small, center=True)

        pygame.display.flip()
        clock.tick(30)

    env_human.close()
    env_ai.close()
    pygame.quit()

if __name__ == "__main__":
    main()

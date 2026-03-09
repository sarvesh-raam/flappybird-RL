import os
# HYNC TRIGGER - v6.0 (Hyper-Sync: Data-Mode)
import logging
import threading
import time
import json

# Force headless
os.environ["SDL_VIDEODRIVER"] = "dummy"

from flask import Flask, render_template, request, jsonify
import gymnasium as gym
import flappy_bird_gymnasium
from stable_baselines3 import PPO

app = Flask(__name__)
logging.basicConfig(level=logging.ERROR)

def load_model():
    p = "flappy_ppo_final.zip"
    if os.path.exists(p):
        try: return PPO.load(p)
        except: pass
    return None

class GameState:
    def __init__(self):
        self.env_h = gym.make("FlappyBird-v0", render_mode="rgb_array")
        self.env_a = gym.make("FlappyBird-v0", render_mode="rgb_array")
        self.model = load_model()
        
        self.obs_h, _ = self.env_h.reset()
        self.obs_a, _ = self.env_a.reset()
        
        self.score_h = 0
        self.score_a = 0
        self.best_h = 0
        self.best_a = 0
        
        self.done_h = True
        self.done_a = True
        self.is_running = False
        
        self.flap_human = False
        self.lock = threading.Lock()
        
        # State Data for Hyper-Sync
        self.data_h = {"y": 256, "pipes": []}
        self.data_a = {"y": 256, "pipes": []}

game = GameState()

# --- PHYSICS LOGIC (Data Extraction) ---
def physics_loop():
    global game
    while True:
        start = time.time()
        with game.lock:
            running = game.is_running
            flap = game.flap_human
            if flap: game.flap_human = False
            d_h = game.done_h
            d_a = game.done_a
        
        if running:
            ai_act = 0
            if not d_a and game.model:
                try: ai_act, _ = game.model.predict(game.obs_a, deterministic=True)
                except: pass
            
            if not d_h:
                game.obs_h, _, t_h, tr_h, i_h = game.env_h.step(1 if flap else 0)
                game.score_h = i_h.get("score", 0)
                if game.score_h > game.best_h: game.best_h = game.score_h
                if t_h or tr_h: game.done_h = True
                
                # Extract Coordinates for Human
                try:
                    g = game.env_h.unwrapped._game
                    game.data_h = {
                        "y": g.player_y,
                        "rot": g.player_rot,
                        "pipes": [{"x": p.x, "y": p.y} for p in g.upper_pipes]
                    }
                except: pass
            
            if not d_a:
                game.obs_a, _, t_a, tr_a, i_a = game.env_a.step(ai_act)
                game.score_a = i_a.get("score", 0)
                if game.score_a > game.best_a: game.best_a = game.score_a
                if t_a or tr_a: game.done_a = True
                
                # Extract Coordinates for AI
                try:
                    g = game.env_a.unwrapped._game
                    game.data_a = {
                        "y": g.player_y,
                        "rot": g.player_rot,
                        "pipes": [{"x": p.x, "y": p.y} for p in g.upper_pipes]
                    }
                except: pass

            if game.done_h and game.done_a:
                game.is_running = False

        # Physics runs at 30Hz - The "Source of Truth"
        time.sleep(max(0.005, 0.033 - (time.time() - start)))

# --- ROUTE: HYPER-SYNC ---
@app.route('/sync')
def sync():
    """Returns raw coordinates for the browser to draw. Extremely fast."""
    global game
    act = request.args.get('act')
    if act == 'flap':
        with game.lock:
            if game.is_running and not game.done_h:
                game.flap_human = True
            else:
                game.env_h.reset(); game.env_a.reset()
                game.score_h = 0; game.score_a = 0
                game.done_h = False; game.done_a = False
                game.is_running = True

    return jsonify({
        "h": game.data_h,
        "a": game.data_a,
        "score_h": game.score_h,
        "score_a": game.score_a,
        "best_h": game.best_h,
        "best_a": game.best_a,
        "running": game.is_running,
        "done_h": game.done_h,
        "done_a": game.done_a
    })

@app.route('/')
def index(): return render_template('index.html')

@app.route('/leaderboard')
def lb(): return jsonify(board=[])

if __name__ == '__main__':
    threading.Thread(target=physics_loop, daemon=True).start()
    app.run(host='0.0.0.0', port=7860, threaded=True)

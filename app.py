import os
# SYNC TRIGGER - Turbo-Sync v2 (Lag-Fix)
import logging
import threading
import time
import json
import base64

# Force headless mode
os.environ["SDL_VIDEODRIVER"] = "dummy"

from flask import Flask, render_template, Response, request, jsonify
import gymnasium as gym
import flappy_bird_gymnasium
from stable_baselines3 import PPO, DQN
import cv2
import numpy as np

app = Flask(__name__)
logging.basicConfig(level=logging.ERROR) # Lower noise to speed up logger

# --- LEADERBOARD & MODEL ---
LEADERBOARD_FILE = "leaderboard.json"

def load_leaderboard():
    if not os.path.exists(LEADERBOARD_FILE): return []
    try:
        with open(LEADERBOARD_FILE, "r") as f:
            return sorted(json.loads(f.read().strip() or "[]"), key=lambda x: x['score'], reverse=True)[:10]
    except: return []

def save_to_leaderboard(name, score):
    board = load_leaderboard()
    existing = next((e for e in board if e['name'] == name), None)
    if existing:
        if score > existing['score']:
            existing['score'] = score
            existing['date'] = time.strftime("%Y-%m-%d")
    else: board.append({"name": name, "score": score, "date": time.strftime("%Y-%m-%d")})
    board = sorted(board, key=lambda x: x['score'], reverse=True)[:10]
    with open(LEADERBOARD_FILE, "w") as f: json.dump(board, f)

def load_model():
    p1 = "flappy_ppo_final.zip"
    if os.path.exists(p1):
        try: return PPO.load(p1)
        except: pass
    return None

# --- STATE ---
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
        self.player_name = "PILOT"
        self.latest_b64 = ""
        self.lock = threading.Lock()

game = GameState()

# --- LOOP ---
def game_loop():
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
            # 1. AI Logic
            ai_act = 0
            if not d_a and game.model:
                try: ai_act, _ = game.model.predict(game.obs_a, deterministic=True)
                except: pass
            
            # 2. Step
            if not d_h:
                game.obs_h, _, term_h, trunc_h, info_h = game.env_h.step(1 if flap else 0)
                game.score_h = info_h.get("score", 0)
                if game.score_h > game.best_h: game.best_h = game.score_h
                if term_h or trunc_h: 
                    game.done_h = True
                    save_to_leaderboard(game.player_name, game.score_h)
            
            if not d_a:
                game.obs_a, _, term_a, trunc_a, info_a = game.env_a.step(ai_act)
                game.score_a = info_a.get("score", 0)
                if game.score_a > game.best_a: game.best_a = game.score_a
                if term_a or trunc_a: 
                    game.done_a = True
                    save_to_leaderboard("AI", game.score_a)

            # 3. Round End Condition
            # Round only stops completely if BOTH are dead
            if game.done_h and game.done_a:
                game.is_running = False

        # Render Composite
        fh = game.env_h.render()
        fa = game.env_a.render()
        if fh is not None and fa is not None:
            comb = np.ascontiguousarray(np.hstack((fh, fa)))
            h, w, _ = comb.shape
            cv2.line(comb, (w // 2, 0), (w // 2, h), (255, 255, 255), 2)
            bgr = cv2.cvtColor(comb, cv2.COLOR_RGB2BGR)
            # Higher quality (75) but still compressed for speed
            ret, buf = cv2.imencode('.jpg', bgr, [int(cv2.IMWRITE_JPEG_QUALITY), 75])
            if ret: game.latest_b64 = base64.b64encode(buf).decode('utf-8')

        # 30Hz logic for ultra-smooth gameplay
        time.sleep(max(0.005, 0.033 - (time.time() - start)))

# --- ROUTES ---
@app.route('/')
def index(): return render_template('index.html')

@app.route('/sync', methods=['GET', 'POST'])
def sync():
    global game
    if request.method == 'POST':
        data = request.json
        if data.get('type') == 'flap':
            with game.lock:
                if game.is_running and not game.done_h:
                    game.flap_human = True
                elif not game.is_running or game.done_h:
                    # Reset both for a fresh duel
                    game.env_h.reset(); game.env_a.reset()
                    game.score_h = 0; game.score_a = 0
                    game.done_h = False; game.done_a = False
                    game.is_running = True
        elif data.get('type') == 'set_name':
            game.player_name = data.get('name', 'PILOT').upper()

    return jsonify({
        "image": game.latest_b64,
        "score_h": game.score_h,
        "score_a": game.score_a,
        "best_h": game.best_h,
        "best_a": game.best_a,
        "running": game.is_running,
        "done_h": game.done_h,
        "done_a": game.done_a
    })

@app.route('/leaderboard')
def get_lb(): return jsonify(board=load_leaderboard())

if __name__ == '__main__':
    threading.Thread(target=game_loop, daemon=True).start()
    # Using threaded=False potentially reduces overhead for high-speed polling
    app.run(host='0.0.0.0', port=7860, threaded=True)

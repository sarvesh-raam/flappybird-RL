import os
# SYNC TRIGGER - Turbo-Sync v3 (Binary Header Mode)
import logging
import threading
import time
import json

# Force headless
os.environ["SDL_VIDEODRIVER"] = "dummy"

from flask import Flask, render_template, make_response, request, jsonify
import gymnasium as gym
import flappy_bird_gymnasium
from stable_baselines3 import PPO
import cv2
import numpy as np

app = Flask(__name__)
logging.basicConfig(level=logging.ERROR)

# --- LEADERBOARD & MODEL ---
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
        self.latest_frame = None
        self.lock = threading.Lock()

game = GameState()

# --- GAME LOOP (30 FPS) ---
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
            # 1. AI Action (Always active if not crashed)
            ai_act = 0
            if not d_a and game.model:
                try: ai_act, _ = game.model.predict(game.obs_a, deterministic=True)
                except: pass
            
            # 2. Step Human
            if not d_h:
                game.obs_h, _, term_h, trunc_h, info_h = game.env_h.step(1 if flap else 0)
                game.score_h = info_h.get("score", 0)
                if game.score_h > game.best_h: game.best_h = game.score_h
                if term_h or trunc_h: game.done_h = True
            
            # 3. Step AI (Independent)
            if not d_a:
                game.obs_a, _, term_a, trunc_a, info_a = game.env_a.step(ai_act)
                game.score_a = info_a.get("score", 0)
                if game.score_a > game.best_a: game.best_a = game.score_a
                if term_a or trunc_a: game.done_a = True

            if game.done_h and game.done_a:
                game.is_running = False

        # 4. Render Composite
        fh = game.env_h.render()
        fa = game.env_a.render()
        if fh is not None and fa is not None:
            comb = np.ascontiguousarray(np.hstack((fh, fa)))
            h, w, _ = comb.shape
            cv2.line(comb, (w // 2, 0), (w // 2, h), (255, 255, 255), 2)
            bgr = cv2.cvtColor(comb, cv2.COLOR_RGB2BGR)
            # High quality JPG for clarity, binary for speed
            ret, buf = cv2.imencode('.jpg', bgr, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
            if ret: game.latest_frame = buf.tobytes()

        # Target 30Hz
        time.sleep(max(0.005, 0.033 - (time.time() - start)))

# --- ROUTES ---
@app.route('/')
def index(): return render_template('index.html')

@app.route('/sync.jpg')
def sync_jpg():
    """Binary Image endpoint with state in HTTP Headers for ultra-low latency."""
    if not game.latest_frame:
        return make_response(b'', 404)
    
    resp = make_response(game.latest_frame)
    resp.headers['Content-Type'] = 'image/jpeg'
    resp.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate'
    # Pack game data into custom headers (The 'Turbo-Headers' approach)
    resp.headers['X-Score-H'] = str(game.score_h)
    resp.headers['X-Score-A'] = str(game.score_a)
    resp.headers['X-Best-H'] = str(game.best_h)
    resp.headers['X-Best-A'] = str(game.best_a)
    resp.headers['X-Running'] = '1' if game.is_running else '0'
    resp.headers['X-Done-H'] = '1' if game.done_h else '0'
    return resp

@app.route('/action', methods=['POST'])
def action():
    data = request.json
    atype = data.get('type')
    if atype == 'flap':
        with game.lock:
            if game.is_running and not game.done_h:
                game.flap_human = True
            else:
                # Reset for new duel
                game.env_h.reset(); game.env_a.reset()
                game.score_h = 0; game.score_a = 0
                game.done_h = False; game.done_a = False
                game.is_running = True
    return jsonify(success=True)

@app.route('/leaderboard')
def lb():
    # Return dummy/saved leaderboard
    return jsonify(board=[])

if __name__ == '__main__':
    threading.Thread(target=game_loop, daemon=True).start()
    app.run(host='0.0.0.0', port=7860, threaded=True)

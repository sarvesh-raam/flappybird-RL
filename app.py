import os
# Force headless mode for pygame to work stable on web servers
os.environ["SDL_VIDEODRIVER"] = "dummy"

from flask import Flask, render_template, Response, request, jsonify
import gymnasium as gym
import flappy_bird_gymnasium
from stable_baselines3 import PPO, DQN
import cv2
import numpy as np
import threading
import time
import json
import logging

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- CONFIG ---
LEADERBOARD_FILE = "leaderboard.json"

def load_leaderboard():
    if os.path.exists(LEADERBOARD_FILE):
        try:
            with open(LEADERBOARD_FILE, "r") as f:
                content = f.read().strip()
                if not content: return []
                return sorted(json.loads(content), key=lambda x: x['score'], reverse=True)[:10]
        except: return []
    return []

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
    return board

def load_model_ppo():
    p = "flappy_ppo_final.zip"
    if os.path.exists(p): return PPO.load(p)
    return None

class GameState:
    def __init__(self):
        self.env_h = gym.make("FlappyBird-v0", render_mode="rgb_array")
        self.env_a = gym.make("FlappyBird-v0", render_mode="rgb_array")
        self.model = load_model_ppo()
        
        self.obs_h, _ = self.env_h.reset()
        self.obs_a, _ = self.env_a.reset()
        
        self.score_h = self.score_a = 0
        self.best_h = self.best_a = 0
        self.human_best_this_round = 0
        self.history = []
        
        self.done_h = self.done_a = False
        self.is_running = False
        self.flap_human = False
        self.player_name = "PILOT"
        
        self.latest_frame = None
        self.lock = threading.Lock()
        self.frame_event = threading.Event()
        
        # Performance Flags
        self.render_ready = True

game = GameState()

# --- 1. THE BRAIN (Physics Loop 30Hz) ---
def physics_loop():
    global game
    while True:
        loop_start = time.time()
        
        ai_act = 0
        h_act = 0
        with game.lock:
            running = game.is_running
            if game.flap_human:
                h_act = 1
                game.flap_human = False
            d_h = game.done_h
            d_a = game.done_a

        if running:
            # AI Logic
            if not d_a and game.model:
                try: ai_act, _ = game.model.predict(game.obs_a, deterministic=True)
                except: ai_act = 0
            
            # Step Environments
            if not d_h:
                game.obs_h, _, t_h, tr_h, i_h = game.env_h.step(h_act)
                with game.lock:
                    game.score_h = i_h.get("score", 0)
                    game.done_h = t_h or tr_h
                    if game.score_h > game.best_h: game.best_h = game.score_h
                    if game.score_h > game.human_best_this_round: game.human_best_this_round = game.score_h
            
            if not d_a:
                game.obs_a, _, t_a, tr_a, i_a = game.env_a.step(ai_act)
                with game.lock:
                    game.score_a = i_a.get("score", 0)
                    game.done_a = t_a or tr_a
                    if game.score_a > game.best_a: game.best_a = game.score_a

            # Auto-Stop Round
            if game.done_h and game.done_a:
                with game.lock:
                    if game.is_running:
                        game.history.append({"human": game.human_best_this_round, "ai": game.score_a})
                        if len(game.history) > 5: game.history.pop(0)
                        game.is_running = False
                        # Prep for next round
                        game.env_h.reset(); game.env_a.reset()

        # Constant 30 steps/sec
        time.sleep(max(0.005, 0.033 - (time.time() - loop_start)))

# --- 2. THE EYES (Render Loop - Maximum Speed) ---
def render_loop():
    global game
    while True:
        try:
            fh = game.env_h.render()
            fa = game.env_a.render()
            if fh is not None and fa is not None:
                # 1:1 High Res Merge
                comb = np.ascontiguousarray(np.hstack((fh, fa)))
                bgr = cv2.cvtColor(comb, cv2.COLOR_RGB2BGR)
                
                # HD 100 Quality Encode
                _, buf = cv2.imencode('.jpg', bgr, [int(cv2.IMWRITE_JPEG_QUALITY), 100])
                game.latest_frame = buf.tobytes()
                game.frame_event.set()
        except: pass
        time.sleep(0.01) # Max ~100 FPS rendering

# --- ROUTES ---
@app.route('/')
def index(): return render_template('index.html')

@app.route('/video_feed')
def video_feed():
    def gen():
        while True:
            game.frame_event.wait(timeout=1.0)
            game.frame_event.clear()
            if game.latest_frame:
                yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + game.latest_frame + b'\r\n')
    return Response(gen(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/action', methods=['POST'])
def action():
    data = request.json
    atype = data.get('type')
    if atype == 'flap':
        with game.lock:
            if not game.is_running or game.done_h:
                game.env_h.reset(); game.env_a.reset()
                game.score_h = game.score_a = 0
                game.done_h = game.done_a = False
                game.human_best_this_round = 0
                game.is_running = True
            else: game.flap_human = True
    elif atype == 'set_name':
        game.player_name = data.get('name', 'Guest')
    return jsonify(success=True)

@app.route('/stats')
def stats():
    return jsonify({
        "score_h": game.score_h, "score_a": game.score_a,
        "best_h": game.best_h, "best_a": game.best_a,
        "is_running": game.is_running, "done_h": game.done_h,
        "history": game.history
    })

@app.route('/leaderboard')
def lb(): return jsonify(board=load_leaderboard())

if __name__ == '__main__':
    threading.Thread(target=physics_loop, daemon=True).start()
    threading.Thread(target=render_loop, daemon=True).start()
    app.run(host='0.0.0.0', port=7860, threaded=True)

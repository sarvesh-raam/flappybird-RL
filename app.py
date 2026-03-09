import os
import logging
import threading
import time
import json

# Force headless mode for pygame on web servers
os.environ["SDL_VIDEODRIVER"] = "dummy"

from flask import Flask, render_template, Response, request, jsonify
import gymnasium as gym
import flappy_bird_gymnasium
from stable_baselines3 import PPO, DQN
import cv2
import numpy as np

app = Flask(__name__)

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- LEADERBOARD ---
LEADERBOARD_FILE = "leaderboard.json"

def load_leaderboard():
    if os.path.exists(LEADERBOARD_FILE):
        try:
            with open(LEADERBOARD_FILE, "r") as f:
                content = f.read().strip()
                if not content: return []
                return sorted(json.loads(content), key=lambda x: x['score'], reverse=True)[:10]
        except Exception:
            return []
    return []

def save_to_leaderboard(name, score):
    board = load_leaderboard()
    existing = next((e for e in board if e['name'] == name), None)
    if existing:
        if score > existing['score']:
            existing['score'] = score
            existing['date'] = time.strftime("%Y-%m-%d")
    else:
        board.append({"name": name, "score": score, "date": time.strftime("%Y-%m-%d")})
    board = sorted(board, key=lambda x: x['score'], reverse=True)[:10]
    with open(LEADERBOARD_FILE, "w") as f:
        json.dump(board, f)
    return board

# --- AI LOADER ---
def load_model():
    p1 = "flappy_ppo_final.zip"
    p2 = os.path.join("legacy_models", "flappy_dqn_v2_final.zip")
    if os.path.exists(p1):
        try: return PPO.load(p1)
        except Exception: pass
    if os.path.exists(p2):
        try: return DQN.load(p2)
        except Exception: pass
    return None

# --- GAME STATE ---
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
        self.done_round = True # Start in "Ready" state
        self.is_running = False
        
        self.flap_human = False
        self.player_name = "Guest"
        self.history = []
        self.latest_frame = None
        self.lock = threading.Lock()
        self.total_rounds = 0

game = GameState()

# --- GAME LOOP ---
def game_loop():
    global game
    logger.info("Core game loop started.")
    
    while True:
        loop_start = time.time()
        
        try:
            with game.lock:
                running = game.is_running
                flap = game.flap_human
                if flap: game.flap_human = False
            
            if running:
                # 1. AI Action
                ai_action = 0
                if game.model:
                    try: ai_action, _ = game.model.predict(game.obs_a, deterministic=True)
                    except: pass
                
                # 2. Step Environments
                h_act = 1 if flap else 0
                game.obs_h, _, term_h, trunc_h, info_h = game.env_h.step(h_act)
                game.obs_a, _, term_a, trunc_a, info_a = game.env_a.step(ai_action)
                
                # 3. Update Scores
                game.score_h = info_h.get("score", 0)
                game.score_a = info_a.get("score", 0)
                
                if game.score_h > game.best_h: game.best_h = game.score_h
                if game.score_a > game.best_a: game.best_a = game.score_a
                
                # 4. Check Duel End (Synchronized Death)
                # If EITHER crashes, round stops for everyone
                if term_h or trunc_h or term_a or trunc_a:
                    game.is_running = False
                    game.done_round = True
                    game.history.append({"id": game.total_rounds, "h": game.score_h, "a": game.score_a})
                    if len(game.history) > 5: game.history.pop(0)
                    
                    # Auto-submit high scores
                    if game.score_h > 0: save_to_leaderboard(game.player_name, game.score_h)
                    save_to_leaderboard("AI", game.score_a)
            
            # 5. Render always (to show birds falling or ready screen)
            try:
                f_h = game.env_h.render()
                f_a = game.env_a.render()
                if f_h is not None and f_a is not None:
                    comb = np.ascontiguousarray(np.hstack((f_h, f_a)))
                    h, w, _ = comb.shape
                    cv2.line(comb, (w // 2, 0), (w // 2, h), (255, 255, 255), 2)
                    bgr = cv2.cvtColor(comb, cv2.COLOR_RGB2BGR)
                    ret, buf = cv2.imencode('.jpg', bgr, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
                    if ret: game.latest_frame = buf.tobytes()
            except Exception as e:
                logger.error(f"Render bug: {e}")

        except Exception as e:
            logger.error(f"Game loop error: {e}")
            time.sleep(0.1)

        # Target 25Hz - Perfect for web duel
        elapsed = time.time() - loop_start
        time.sleep(max(0.005, 0.04 - elapsed))

# --- ROUTES ---
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/frame')
def frame():
    if game.latest_frame:
        return Response(game.latest_frame, mimetype='image/jpeg',
                        headers={'Cache-Control': 'no-store, no-cache, must-revalidate'})
    return Response(b'', mimetype='image/jpeg')

@app.route('/action', methods=['POST'])
def action():
    data = request.json
    atype = data.get('type')
    
    if atype == 'flap':
        with game.lock:
            if game.is_running:
                game.flap_human = True
            elif game.done_round:
                # Restart Duel Logic
                game.obs_h, _ = game.env_h.reset()
                game.obs_a, _ = game.env_a.reset()
                game.score_h = game.score_a = 0
                game.done_round = False
                game.total_rounds += 1
                game.is_running = True
    elif atype == 'set_name':
        game.player_name = data.get('name', 'PILOT').upper()
    return jsonify(success=True)

@app.route('/stats')
def stats():
    return jsonify({
        "score_h": game.score_h,
        "score_a": game.score_a,
        "best_h": game.best_h,
        "best_a": game.best_a,
        "history": game.history,
        "is_running": game.is_running,
        "done": game.done_round
    })

@app.route('/leaderboard')
def leaderboard():
    return jsonify(board=load_leaderboard())

@app.route('/submit_score', methods=['POST'])
def submit():
    d = request.json
    save_to_leaderboard(d.get('name'), d.get('score'))
    return jsonify(success=True)

if __name__ == '__main__':
    threading.Thread(target=game_loop, daemon=True).start()
    app.run(host='0.0.0.0', port=7860, threaded=True)

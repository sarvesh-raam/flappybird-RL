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
print(f"===== Application Startup at {time.strftime('%Y-%m-%d %H:%M:%S')} =====")

# --- LEADERBOARD ---
LEADERBOARD_FILE = "leaderboard.json"

def load_leaderboard():
    if os.path.exists(LEADERBOARD_FILE):
        try:
            with open(LEADERBOARD_FILE, "r") as f:
                content = f.read().strip()
                if not content: return []
                return sorted(json.loads(content), key=lambda x: x['score'], reverse=True)[:10]
        except Exception as e:
            logger.error(f"Leaderboard load error: {e}")
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

# --- AI MODEL LOADER ---
def load_model():
    if os.path.exists("flappy_ppo_final.zip"):
        logger.info("FOUND: flappy_ppo_final.zip — Loading PPO model")
        try:
            return PPO.load("flappy_ppo_final.zip")
        except Exception as e:
            logger.error(f"PPO load failed: {e}")
    if os.path.exists(os.path.join("legacy_models", "flappy_dqn_v2_final.zip")):
        logger.info("FALLBACK: Loading legacy DQN model")
        try:
            return DQN.load(os.path.join("legacy_models", "flappy_dqn_v2_final.zip"))
        except Exception as e:
            logger.error(f"DQN load failed: {e}")
    logger.warning("NO AI MODEL FOUND — AI bird will fall immediately")
    return None

# --- GAME STATE ---
class GameState:
    def __init__(self):
        self.env_human = gym.make("FlappyBird-v0", render_mode="rgb_array")
        self.env_ai   = gym.make("FlappyBird-v0", render_mode="rgb_array")
        self.model    = load_model()
        self.obs_h, _ = self.env_human.reset()
        self.obs_a, _ = self.env_ai.reset()
        self.done_h = self.done_a = False
        self.score_h = self.score_a = 0
        self.best_h  = self.best_a  = 0
        self.human_best_this_round = 0
        self.total_ai_runs   = 0
        self.human_attempts  = 0
        self.history    = []
        self.flap_human = False
        self.is_running = False
        self.latest_frame = None
        self.player_name  = "Guest"
        self.lock = threading.Lock()
        # Render initial frame so the screen isn't blank
        self._render_initial()

    def _render_initial(self):
        try:
            fh = self.env_human.render()
            fa = self.env_ai.render()
            if fh is not None and fa is not None:
                comb = np.ascontiguousarray(np.hstack((fh, fa)))
                h, w, _ = comb.shape
                cv2.line(comb, (w // 2, 0), (w // 2, h), (255, 255, 255), 2)
                bgr = cv2.cvtColor(comb, cv2.COLOR_RGB2BGR)
                _, buf = cv2.imencode('.jpg', bgr, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
                self.latest_frame = buf.tobytes()
        except Exception as e:
            logger.error(f"Initial render error: {e}")

game = GameState()

# --- GAME LOOP ---
def game_loop():
    global game
    logger.info("Game loop started.")

    while True:
        loop_start = time.time()
        try:
            # 1. Snapshot state under lock
            with game.lock:
                running = game.is_running
                done_a  = game.done_a
                done_h  = game.done_h
                flap    = game.flap_human
                if flap:
                    game.flap_human = False
            h_action = 1 if flap else 0

            # 2. Step environments (no lock — heavy work)
            term_a = trunc_a = False
            term_h = trunc_h = False
            info_a = info_h  = {}

            if running:
                # AI prediction
                ai_action = 0
                if not done_a and game.model:
                    try:
                        ai_action, _ = game.model.predict(game.obs_a, deterministic=True)
                    except Exception as e:
                        logger.error(f"AI predict error: {e}")

                if not done_a:
                    game.obs_a, _, term_a, trunc_a, info_a = game.env_ai.step(ai_action)
                if not done_h:
                    game.obs_h, _, term_h, trunc_h, info_h = game.env_human.step(h_action)

                # 3. Update shared state under lock
                with game.lock:
                    if not done_a:
                        game.score_a = info_a.get("score", 0)
                        game.done_a  = term_a or trunc_a
                        if game.score_a > game.best_a: game.best_a = game.score_a

                    if not done_h:
                        game.score_h = info_h.get("score", 0)
                        game.done_h  = term_h or trunc_h
                        if game.score_h > game.best_h:              game.best_h = game.score_h
                        if game.score_h > game.human_best_this_round: game.human_best_this_round = game.score_h

                    # End round the moment EITHER player crashes
                    if game.done_h or game.done_a:
                        if running:
                            game.history.append({
                                "id": game.total_ai_runs,
                                "human": game.human_best_this_round,
                                "ai": game.score_a
                            })
                            if len(game.history) > 5: game.history.pop(0)
                        game.is_running = False
                        # Reset both birds back to start position
                        game.obs_h, _ = game.env_human.reset()
                        game.obs_a, _ = game.env_ai.reset()

            # 4. Render (no lock)
            try:
                fh = game.env_human.render()
                fa = game.env_ai.render()
                if fh is not None and fa is not None:
                    combined = np.ascontiguousarray(np.hstack((fh, fa)))
                    h, w, _ = combined.shape
                    cv2.line(combined, (w // 2, 0), (w // 2, h), (255, 255, 255), 2)
                    bgr = cv2.cvtColor(combined, cv2.COLOR_RGB2BGR)
                    ret, buf = cv2.imencode('.jpg', bgr, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
                    if ret:
                        game.latest_frame = buf.tobytes()
            except Exception as e:
                logger.error(f"Render error: {e}")

        except Exception as e:
            logger.error(f"Game loop error: {e}")
            time.sleep(1)

        # ~20 Hz — comfortable speed for human reaction
        elapsed = time.time() - loop_start
        time.sleep(max(0.005, 0.05 - elapsed))

# --- FLASK ROUTES ---
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/frame')
def frame():
    """Single-frame JPEG endpoint — frontend polls this instead of MJPEG stream."""
    if game.latest_frame:
        return Response(game.latest_frame, mimetype='image/jpeg',
                        headers={'Cache-Control': 'no-store, no-cache, must-revalidate'})
    return Response(b'', mimetype='image/jpeg')

@app.route('/action', methods=['POST'])
def action():
    data  = request.json
    atype = data.get('type')
    if atype == 'flap':
        with game.lock:
            if game.is_running:
                # Only flap if human is still alive (ignore if already crashed)
                if not game.done_h:
                    game.flap_human = True
            else:
                # Start a new round
                logger.info(f"New round: {game.player_name}")
                game.obs_h, _ = game.env_human.reset()
                game.obs_a, _ = game.env_ai.reset()
                game.score_h = game.score_a = 0
                game.done_h  = game.done_a  = False
                game.human_best_this_round = 0
                game.human_attempts += 1
                game.total_ai_runs  += 1
                game.is_running = True
    elif atype == 'set_name':
        game.player_name = data.get('name', 'Guest')
        logger.info(f"Player name set: {game.player_name}")
    return jsonify(success=True)

@app.route('/submit_score', methods=['POST'])
def submit_score():
    data = request.json
    save_to_leaderboard(data.get('name'), data.get('score'))
    return jsonify(board=load_leaderboard())

@app.route('/leaderboard')
def get_leaderboard():
    return jsonify(board=load_leaderboard())

@app.route('/stats')
def stats():
    return jsonify({
        "score_h":    game.score_h,
        "score_a":    game.score_a,
        "best_h":     game.best_h,
        "best_a":     game.best_a,
        "attempts":   game.human_attempts,
        "round":      game.total_ai_runs,
        "history":    game.history,
        "done_h":     game.done_h,
        "done_a":     game.done_a,
        "is_running": game.is_running,
        "player_name":game.player_name
    })

if __name__ == '__main__':
    threading.Thread(target=game_loop, daemon=True).start()
    app.run(host='0.0.0.0', port=7860, debug=False, threaded=True)

import os
# Force headless mode for pygame to work stable on web servers
os.environ["SDL_VIDEODRIVER"] = "dummy"

from flask import Flask, render_template, Response, request, jsonify
import gymnasium as gym
import flappy_bird_gymnasium
from stable_baselines3 import PPO, DQN
import cv2
import numpy as np
import os
import threading
import time
import json

app = Flask(__name__)

# --- LEADERBOARD LOGIC ---
LEADERBOARD_FILE = "leaderboard.json"

def load_leaderboard():
    if os.path.exists(LEADERBOARD_FILE):
        try:
            with open(LEADERBOARD_FILE, "r") as f:
                content = f.read().strip()
                if not content: return []
                return sorted(json.loads(content), key=lambda x: x['score'], reverse=True)[:10]
        except Exception as e:
            print(f"Leaderboard error: {e}")
            return []
    return []

def save_to_leaderboard(name, score):
    board = load_leaderboard()
    
    # Check if player already exists
    existing_entry = next((e for e in board if e['name'] == name), None)
    
    if existing_entry:
        if score > existing_entry['score']:
            existing_entry['score'] = score
            existing_entry['date'] = time.strftime("%Y-%m-%d")
    else:
        board.append({"name": name, "score": score, "date": time.strftime("%Y-%m-%d")})
    
    # Sort and trim
    board = sorted(board, key=lambda x: x['score'], reverse=True)[:10]
    with open(LEADERBOARD_FILE, "w") as f:
        json.dump(board, f)
    return board

# --- AI & ENV CONFIG ---
def load_model():
    model_path = ""
    model_type = "PPO"
    if os.path.exists("flappy_ppo_final.zip"):
        model_path = "flappy_ppo_final.zip"
        logger.info(f"FOUND AI MODEL: {model_path}")
    elif os.path.exists("models_ppo"):
        import glob
        checkpoints = glob.glob("models_ppo/*.zip")
        if checkpoints:
            model_path = max(checkpoints, key=os.path.getmtime)
            logger.info(f"FOUND CHECKPOINT: {model_path}")
    
    if not model_path and os.path.exists(os.path.join("legacy_models", "flappy_dqn_v2_final.zip")):
        model_path = os.path.join("legacy_models", "flappy_dqn_v2_final.zip")
        model_type = "DQN"
        logger.info(f"FALLING BACK TO LEGACY: {model_path}")
    
    if model_path:
        try:
            return PPO.load(model_path) if model_type == "PPO" else DQN.load(model_path)
        except Exception as e:
            logger.error(f"MODEL LOAD FAILED: {e}")
            return None
    
    logger.warning("CRITICAL: NO AI MODEL FOUND! AI bird will not flap.")
    return None


class GameState:
    def __init__(self):
        self.env_human = gym.make("FlappyBird-v0", render_mode="rgb_array")
        self.env_ai = gym.make("FlappyBird-v0", render_mode="rgb_array")
        self.model = load_model()
        self.obs_h, _ = self.env_human.reset()
        self.obs_a, _ = self.env_ai.reset()
        self.done_h = self.done_a = False
        self.score_h = self.score_a = 0
        self.human_best_this_round = 0
        self.best_h = 0
        self.best_a = 0
        self.total_ai_runs = 0
        self.human_attempts = 0
        self.history = []
        self.flap_human = False
        self.reset_h = False
        self.is_running = False
        self.latest_frame = None
        self.player_name = "Guest"
        self.lock = threading.Lock()
        
        # --- PRE-RENDER INITIAL FRAME ---
        fh = self.env_human.render()
        fa = self.env_ai.render()
        if fh is not None and fa is not None:
            comb = np.ascontiguousarray(np.hstack((fh, fa)))
            h, w, _ = comb.shape
            cv2.line(comb, (w // 2, 0), (w // 2, h), (180, 180, 180), 2)
            bgr = cv2.cvtColor(comb, cv2.COLOR_RGB2BGR)
            _, buffer = cv2.imencode('.jpg', bgr, [int(cv2.IMWRITE_JPEG_QUALITY), 95])
            self.latest_frame = buffer.tobytes()

game = GameState()

import logging

# Setup basic logging to help user debug on HF Settings -> Logs
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def load_model():
    model_path = "flappy_ppo_final.zip"
    if os.path.exists(model_path):
        logger.info(f"Loading PPO model from {model_path}")
        return PPO.load(model_path)
    
    # Fallback search
    logger.warning("Main model not found, searching for fallbacks...")
    if os.path.exists(os.path.join("legacy_models", "flappy_dqn_v2_final.zip")):
        logger.info("Loading legacy DQN model")
        return DQN.load(os.path.join("legacy_models", "flappy_dqn_v2_final.zip"))
    
    logger.error("NO MODEL FOUND! Game will run in random mode.")
    return None

def game_loop():
    global game
    logger.info("Game loop thread started.")
    
    last_frame_time = 0
    while True:
        loop_start = time.time()
        
        try:
            # 1. Action Preparation (Minimal Lock)
            ai_action = None
            h_action = 0
            
            with game.lock:
                running = game.is_running
                done_a = game.done_a
                done_h = game.done_h
                if game.flap_human:
                    h_action = 1
                    game.flap_human = False
            
            # 2. Heavy Computations (NO LOCK)
            if running:
                # AI move
                if not done_a and game.model:
                    try:
                        ai_action, _ = game.model.predict(game.obs_a, deterministic=True)
                    except Exception as e:
                        logger.error(f"AI Predict Error: {e}")
                        ai_action = 0
                else:
                    ai_action = 0
                
                # Step Envs
                if not done_a:
                    game.obs_a, _, term_a, trunc_a, info_a = game.env_ai.step(ai_action)
                if not done_h:
                    if h_action == 0 and game.reset_h: # Handle reset if needed
                        game.obs_h, _ = game.env_human.reset()
                        game.reset_h = False
                    game.obs_h, _, term_h, trunc_h, info_h = game.env_human.step(h_action)
                
                # 3. Update Shared State (Minimal Lock)
                with game.lock:
                    if not done_a:
                        game.score_a = info_a.get("score", 0)
                        game.done_a = term_a or trunc_a
                        if game.score_a > game.best_a: game.best_a = game.score_a
                    
                    if not done_h:
                        game.score_h = info_h.get("score", 0)
                        game.done_h = term_h or trunc_h
                        if game.score_h > game.best_h: game.best_h = game.score_h
                        if game.score_h > game.human_best_this_round: game.human_best_this_round = game.score_h
                    
                    # Stop round when EITHER player crashes - human shouldn't be stuck watching AI
                    if game.done_h or game.done_a:
                        if running:
                            game.history.append({"id": game.total_ai_runs, "human": game.human_best_this_round, "ai": game.score_a})
                            if len(game.history) > 5: game.history.pop(0)
                        
                        game.is_running = False
                        
                        # Reset both birds to top for the Ready screen
                        game.obs_h, _ = game.env_human.reset()
                        game.obs_a, _ = game.env_ai.reset()


            # 4. Rendering (NO LOCK) - High Quality Sync with Loop
            f_h = game.env_human.render()
            f_a = game.env_ai.render()
            if f_h is not None and f_a is not None:
                # Merge full resolution
                combined = np.hstack((f_h, f_a))
                # Ensure memory layout
                combined = np.ascontiguousarray(combined)
                
                # Draw the divider
                h, w, _ = combined.shape
                cv2.line(combined, (w // 2, 0), (w // 2, h), (255, 255, 255), 2)
                
                bgr = cv2.cvtColor(combined, cv2.COLOR_RGB2BGR)
                # Restored 90 quality as requested
                ret, buffer = cv2.imencode('.jpg', bgr, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
                if ret:
                    game.latest_frame = buffer.tobytes()



        except Exception as e:
            logger.error(f"FATAL GAME LOOP ERROR: {e}")
            time.sleep(1) 
            
        # Target ~35hz loop for better web control
        elapsed = time.time() - loop_start
        sleep_time = max(0.005, 0.028 - elapsed)
        time.sleep(sleep_time)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/frame')
def frame():
    """Returns the latest game frame as a single JPEG image. 
    Frontend polls this every ~100ms instead of using MJPEG stream.
    This avoids HF rate-limiting long-lived connections."""
    global game
    if game.latest_frame:
        return Response(game.latest_frame, mimetype='image/jpeg',
                        headers={'Cache-Control': 'no-store, no-cache, must-revalidate, max-age=0'})
    # Return a 1x1 transparent placeholder if no frame yet
    import base64
    placeholder = base64.b64decode(
        '/9j/4AAQSkZJRgABAQEASABIAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8U'
        'HRofHh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/wAARC'
        'AABAAEDASIA...AAD/2Q==')
    return Response(game.latest_frame or b'', mimetype='image/jpeg',
                    headers={'Cache-Control': 'no-store'})

def gen_frames():
    global game
    while True:
        if game.latest_frame:
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + game.latest_frame + b'\r\n')
        time.sleep(0.04)

@app.route('/video_feed')
def video_feed():
    return Response(gen_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')


@app.route('/action', methods=['POST'])
def action():
    global game
    data = request.json
    atype = data.get('type')
    
    if atype == 'flap':
        with game.lock:
            if game.is_running:
                if not game.done_h: game.flap_human = True
                else: game.reset_h = True
            else:
                # Start round
                logger.info(f"Tournament Start: {game.player_name}")
                game.obs_h, _ = game.env_human.reset()
                game.obs_a, _ = game.env_ai.reset()
                game.score_h = game.score_a = 0
                game.done_h = game.done_a = False
                game.human_best_this_round = 0
                game.human_attempts += 1
                game.total_ai_runs += 1
                game.is_running = True
                # Tiny breather for first frame
                time.sleep(0.1)
    elif atype == 'set_name':
        game.player_name = data.get('name', 'Guest')
        logger.info(f"Name set: {game.player_name}")
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
        "score_h": game.score_h,
        "score_a": game.score_a,
        "best_h": game.best_h,
        "best_a": game.best_a,
        "attempts": game.human_attempts,
        "round": game.total_ai_runs,
        "history": game.history,
        "done_h": game.done_h,
        "done_a": game.done_a,
        "is_running": game.is_running,
        "player_name": game.player_name
    })

if __name__ == '__main__':
    threading.Thread(target=game_loop, daemon=True).start()
    logger.info("Starting Flask server on port 7860")
    app.run(host='0.0.0.0', port=7860, debug=False, threaded=True)




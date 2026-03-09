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
    elif os.path.exists("models_ppo"):
        import glob
        checkpoints = glob.glob("models_ppo/*.zip")
        if checkpoints:
            model_path = max(checkpoints, key=os.path.getmtime)
    
    if not model_path and os.path.exists(os.path.join("legacy_models", "flappy_dqn_v2_final.zip")):
        model_path = os.path.join("legacy_models", "flappy_dqn_v2_final.zip")
        model_type = "DQN"
    
    if model_path:
        return PPO.load(model_path) if model_type == "PPO" else DQN.load(model_path)
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

def game_loop():
    global game
    while True:
        with game.lock:
            if game.is_running:
                # AI Logic
                if not game.done_a:
                    action_ai, _ = game.model.predict(game.obs_a, deterministic=True)
                    game.obs_a, _, term_a, trunc_a, info_a = game.env_ai.step(action_ai)
                    game.score_a = info_a.get("score", 0)
                    game.done_a = term_a or trunc_a
                    if game.score_a > game.best_a: game.best_a = game.score_a
                else:
                    # AI Round Finished - but we keep running for human
                    if game.total_ai_runs > len(game.history): # Only add once
                        game.history.append({"id": game.total_ai_runs, "human": game.human_best_this_round, "ai": game.score_a})
                        if len(game.history) > 5: game.history.pop(0)

                # Human Logic
                if game.reset_h:
                    game.obs_h, _ = game.env_human.reset()
                    game.score_h = 0
                    game.done_h = False
                    game.human_attempts += 1
                    game.reset_h = False

                if not game.done_h:
                    action_h = 1 if game.flap_human else 0
                    game.obs_h, _, term_h, trunc_h, info_h = game.env_human.step(action_h)
                    game.score_h = info_h.get("score", 0)
                    game.done_h = term_h or trunc_h
                    if game.score_h > game.human_best_this_round: game.human_best_this_round = game.score_h
                    if game.score_h > game.best_h: game.best_h = game.score_h
                    game.flap_human = False
                
                if game.done_a:
                    game.is_running = False

            # --- OPTIMIZED FOR HOSTING (KOYEB/RENDER) ---
            try:
                frame_h = game.env_human.render()
                frame_a = game.env_ai.render()
                if frame_h is not None and frame_a is not None:
                    # Combine frames
                    combined = np.hstack((frame_h, frame_a))
                    
                    # DOWNSCALE (50% size) = 400% Faster Video
                    h, w, _ = combined.shape
                    small = cv2.resize(combined, (w // 2, h // 2), interpolation=cv2.INTER_AREA)
                    
                    sh, sw, _ = small.shape
                    cv2.line(small, (sw // 2, 0), (sw // 2, sh), (180, 180, 180), 1)
                    
                    bgr = cv2.cvtColor(small, cv2.COLOR_RGB2BGR)
                    # QUALITY 50 = Smooth gameplay, low lag
                    ret, buffer = cv2.imencode('.jpg', bgr, [int(cv2.IMWRITE_JPEG_QUALITY), 50])
                    if ret:
                        game.latest_frame = buffer.tobytes()
            except Exception as e:
                pass 

        # 40 FPS target - smooth and stable for cloud servers
        time.sleep(1/40)

@app.route('/')
def index():
    return render_template('index.html')

def gen_frames():
    global game
    while True:
        # Always serve the current frame at 30fps to the browser 
        # to ensure it's NEVER blank on load.
        if game.latest_frame:
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + game.latest_frame + b'\r\n')
        else:
            # If no frame yet, wait a bit
            time.sleep(0.1)
        time.sleep(1/30) # Steady stream for browser stability

@app.route('/video_feed')
def video_feed():
    return Response(gen_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/action', methods=['POST'])
def action():
    global game
    data = request.json
    atype = data.get('type')
    with game.lock:
        if atype == 'flap':
            if game.is_running:
                if not game.done_h: game.flap_human = True
                else: game.reset_h = True
            else:
                game.obs_h, _ = game.env_human.reset()
                game.obs_a, _ = game.env_ai.reset()
                game.score_h = game.score_a = 0
                game.done_h = game.done_a = False
                game.human_best_this_round = 0
                game.human_attempts = 1
                game.total_ai_runs += 1
                game.is_running = True
                game.model = load_model()
        elif atype == 'set_name':
            game.player_name = data.get('name', 'Guest')
    return jsonify(success=True)

@app.route('/submit_score', methods=['POST'])
def submit_score():
    data = request.json
    name = data.get('name')
    score = data.get('score')
    
    # Simple check to avoid spamming identical scores for same player
    board = load_leaderboard()
    if any(e['name'] == name and e['score'] == score for e in board):
        return jsonify(board=board)
        
    board = save_to_leaderboard(name, score)
    return jsonify(board=board)

@app.route('/leaderboard')
def get_leaderboard():
    return jsonify(board=load_leaderboard())

@app.route('/stats')
def stats():
    global game
    with game.lock:
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
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)

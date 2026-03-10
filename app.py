import os
# Force headless mode for pygame to work stable on web servers
os.environ["SDL_VIDEODRIVER"] = "dummy"

from flask import Flask, render_template, Response, request, jsonify
import gymnasium as gym
import flappy_bird_gymnasium
from stable_baselines3 import PPO
import cv2
import numpy as np
import threading
import time
import logging

app = Flask(__name__)
logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger(__name__)

# --- GAME STATE ---
class GameState:
    def __init__(self):
        self.env_h = gym.make("FlappyBird-v0", render_mode="rgb_array")
        self.env_a = gym.make("FlappyBird-v0", render_mode="rgb_array")
        
        # Load Model
        try: self.model = PPO.load("flappy_ppo_final.zip")
        except: self.model = None
        
        self.obs_h, _ = self.env_h.reset()
        self.obs_a, _ = self.env_a.reset()
        
        self.score_h = self.score_a = 0
        self.best_h = self.best_a = 0
        self.done_h = self.done_a = False
        self.is_running = False
        
        # ATOMIC INPUTS (Zero-Lag)
        self.flap_queue = 0
        self.last_frame = None
        self.frame_event = threading.Event()
        self.lock = threading.Lock()

game = GameState()

# --- 1. THE BRAIN (Turbo Physics - 120Hz Polling, 30Hz Step) ---
def physics_loop():
    global game
    step_time = 0.033 # 30Hz
    last_step = time.time()
    
    while True:
        now = time.time()
        
        # High-Frequency Input Check (Every loop)
        with game.lock:
            do_flap = game.flap_queue > 0
            if do_flap: game.flap_queue = 0
            running = game.is_running
            d_h = game.done_h
            d_a = game.done_a

        # Logic Step (Locked at 30Hz)
        if now - last_step >= step_time:
            last_step = now
            if running:
                # 1. AI Action
                ai_act = 0
                if not d_a and game.model:
                    try: ai_act, _ = game.model.predict(game.obs_a, deterministic=True)
                    except: pass
                
                # 2. Parallel Steps
                if not d_h:
                    game.obs_h, _, t_h, tr_h, i_h = game.env_h.step(1 if do_flap else 0)
                    game.score_h = i_h.get("score", 0)
                    if game.score_h > game.best_h: game.best_h = game.score_h
                    game.done_h = t_h or tr_h
                    do_flap = False # Flap consumed
                
                if not d_a:
                    game.obs_a, _, t_a, tr_a, i_a = game.env_a.step(ai_act)
                    game.score_a = i_a.get("score", 0)
                    if game.score_a > game.best_a: game.best_a = game.score_a
                    game.done_a = t_a or tr_a
                
                # Auto-Stop
                if game.done_h and game.done_a:
                    game.is_running = False
                    game.env_h.reset(); game.env_a.reset()

        # Turbo Wait (8ms polling for input)
        time.sleep(0.008)

# --- 2. THE EYES (Zero-Buffer Render) ---
def render_loop():
    global game
    while True:
        try:
            fh = game.env_h.render()
            fa = game.env_a.render()
            if fh is not None and fa is not None:
                # HD Render 100% Quality
                combined = np.hstack((fh, fa))
                bgr = cv2.cvtColor(combined, cv2.COLOR_RGB2BGR)
                _, buf = cv2.imencode('.jpg', bgr, [int(cv2.IMWRITE_JPEG_QUALITY), 100])
                game.last_frame = buf.tobytes()
                game.frame_event.set()
        except: pass
        time.sleep(0.02) # Cap render at 50FPS to save CPU for physics

# --- ULTRA-LIGHT ROUTES ---
@app.route('/')
def index(): return render_template('index.html')

@app.route('/f') # ATOMIC FLAP ENDPOINT
def flap_atomic():
    global game
    with game.lock:
        if not game.is_running or game.done_h:
            game.score_h = game.score_a = 0
            game.done_h = game.done_a = False
            game.is_running = True
        game.flap_queue += 1
    return "", 204 # Empty success (Fastest possible)

@app.route('/video_feed')
def video_feed():
    def stream():
        while True:
            game.frame_event.wait(timeout=1.0)
            game.frame_event.clear()
            if game.last_frame:
                yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + game.last_frame + b'\r\n')
    return Response(stream(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/stats')
def stats():
    return jsonify({
        "s_h": game.score_h, "s_a": game.score_a,
        "b_h": game.best_h, "b_a": game.best_a,
        "run": game.is_running, "d_h": game.done_h
    })

if __name__ == '__main__':
    threading.Thread(target=physics_loop, daemon=True).start()
    threading.Thread(target=render_loop, daemon=True).start()
    app.run(host='0.0.0.0', port=7860, threaded=True)

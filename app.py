import os
import threading
import time
import cv2
import numpy as np
import gymnasium as gym
import flappy_bird_gymnasium
from flask import Flask, render_template, Response, request, jsonify
from stable_baselines3 import PPO

# --- PROJECT PHOENIX (v13.0) ---
# Goal: Scrapped everything. Rebuilt using official 'flappy-bird-gymnasium' package.
# Logic: Pure Python, Zero-Lag, Real-time AI + Human Dual Stream.

os.environ["SDL_VIDEODRIVER"] = "dummy" # Headless Mode
app = Flask(__name__)

class FlappyPhoenix:
    def __init__(self):
        # 1. Load the AI Brain (PPO Model)
        try:
            self.model = PPO.load("flappy_ppo_final.zip")
            print(">>> RL Brain Linked Perfectly.")
        except:
            self.model = None
            print(">>> RL Brain not found. AI will be random.")

        # 2. Setup the official Python package environments
        # We use 'rgb_array' for high-quality video streaming
        self.env_h = gym.make("FlappyBird-v0", render_mode="rgb_array")
        self.env_a = gym.make("FlappyBird-v0", render_mode="rgb_array")
        
        # State Initialization
        self.obs_h, _ = self.env_h.reset()
        self.obs_a, _ = self.env_a.reset()
        
        self.score_h = self.score_a = 0
        self.best_h = self.best_a = 0
        self.done_h = self.done_a = False
        self.is_running = False
        
        self.action_queue_h = 0
        self.latest_frame = None
        self.lock = threading.Lock()

    def step(self):
        """The atomic heartbeat of the game."""
        if not self.is_running: return

        with self.lock:
            # Get Human Action (0 or 1)
            h_act = 1 if self.action_queue_h > 0 else 0
            self.action_queue_h = 0 # Consume the click
            
            # AI Logic (The Brain)
            a_act = 0
            if not self.done_a and self.model:
                try: a_act, _ = self.model.predict(self.obs_a, deterministic=True)
                except: a_act = 0

            # Execute moves in the Python environment
            if not self.done_h:
                self.obs_h, _, term_h, trunc_h, info_h = self.env_h.step(h_act)
                self.score_h = info_h["score"]
                if self.score_h > self.best_h: self.best_h = self.score_h
                self.done_h = term_h or trunc_h

            if not self.done_a:
                self.obs_a, _, term_a, trunc_a, info_a = self.env_a.step(a_act)
                self.score_a = info_a["score"]
                if self.score_a > self.best_a: self.best_a = self.score_a
                self.done_a = term_a or trunc_a

            # Round Over Check
            if self.done_h and self.done_a:
                self.is_running = False

    def render(self):
        """Generates the side-by-side HD view."""
        try:
            # Get raw pixels from Python package
            img_h = self.env_h.render()
            img_a = self.env_a.render()
            
            if img_h is not None and img_a is not None:
                # Merge Frames
                combined = np.hstack((img_h, img_a))
                bgr = cv2.cvtColor(combined, cv2.COLOR_RGB2BGR)
                
                # Draw separating line
                h, w, _ = bgr.shape
                cv2.line(bgr, (w//2, 0), (w//2, h), (255, 255, 255), 2)
                
                # Encode 100% Quality
                _, buffer = cv2.imencode('.jpg', bgr, [int(cv2.IMWRITE_JPEG_QUALITY), 100])
                self.latest_frame = buffer.tobytes()
        except:
            pass

    def reset_all(self):
        self.obs_h, _ = self.env_h.reset()
        self.obs_a, _ = self.env_a.reset()
        self.score_h = self.score_a = 0
        self.done_h = self.done_a = False
        self.is_running = True

# Initialize global engine
phoenix = FlappyPhoenix()

def bg_loop():
    """Ultra-stable game loop thread."""
    while True:
        start = time.time()
        phoenix.step()
        phoenix.render()
        # Clean 30Hz - The 'Perfect Feel'
        time.sleep(max(0.005, 0.033 - (time.time() - start)))

# --- WEB SERVING ---
@app.route('/')
def home(): return render_template('index.html')

@app.route('/stream')
def stream():
    def gen():
        while True:
            if phoenix.latest_frame:
                yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + phoenix.latest_frame + b'\r\n')
            time.sleep(0.03)
    return Response(gen(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/f') # Instant Flap
def flap():
    if not phoenix.is_running or phoenix.done_h:
        phoenix.reset_all()
    else:
        phoenix.action_queue_h += 1
    return "", 204

@app.route('/stats')
def stats():
    return jsonify({
        "sh": phoenix.score_h,
        "sa": phoenix.score_a,
        "bh": phoenix.best_h,
        "ba": phoenix.best_a,
        "run": phoenix.is_running,
        "dh": phoenix.done_h
    })

if __name__ == '__main__':
    threading.Thread(target=bg_loop, daemon=True).start()
    app.run(host='0.0.0.0', port=7860, threaded=True)

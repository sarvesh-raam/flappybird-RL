import os
import threading
import time
import cv2
import numpy as np
import gymnasium as gym
import flappy_bird_gymnasium
from flask import Flask, render_template, Response, request, jsonify
from stable_baselines3 import PPO

# 1. ENVIRONMENT SETUP
os.environ["SDL_VIDEODRIVER"] = "dummy" # Headless
app = Flask(__name__)

class PhoenixEngine:
    def __init__(self):
        # The AI Brain
        try: self.model = PPO.load("flappy_ppo_final.zip")
        except: self.model = None
        
        # Dual Environments (Human & AI)
        self.env_h = gym.make("FlappyBird-v0", render_mode="rgb_array")
        self.env_a = gym.make("FlappyBird-v0", render_mode="rgb_array")
        
        self.reset_game()
        
        self.lock = threading.Lock()
        self.latest_frame = None
        self.is_running = False
        self.flap_pending = False

    def reset_game(self):
        self.obs_h, _ = self.env_h.reset()
        self.obs_a, _ = self.env_a.reset()
        self.score_h = self.score_a = 0
        self.done_h = self.done_a = False

    def step(self):
        """The atomic game step. Human and AI move together."""
        if not self.is_running: return

        with self.lock:
            h_action = 1 if self.flap_pending else 0
            self.flap_pending = False
            
            # 1. AI Decision
            a_action = 0
            if not self.done_a and self.model:
                try: a_action, _ = self.model.predict(self.obs_a, deterministic=True)
                except: pass

            # 2. Execute Steps
            if not self.done_h:
                self.obs_h, _, term_h, trunc_h, info_h = self.env_h.step(h_action)
                self.score_h = info_h["score"]
                self.done_h = term_h or trunc_h

            if not self.done_a:
                self.obs_a, _, term_a, trunc_a, info_a = self.env_a.step(a_action)
                self.score_a = info_a["score"]
                self.done_a = term_a or trunc_a

            if self.done_h and self.done_a:
                self.is_running = False

    def render(self):
        """Ultra-fast frame generation."""
        img_h = self.env_h.render()
        img_a = self.env_a.render()
        
        if img_h is not None and img_a is not None:
            # Combine Side-by-Side
            combined = np.hstack((img_h, img_a))
            bgr = cv2.cvtColor(combined, cv2.COLOR_RGB2BGR)
            
            # Draw Divider
            h, w, _ = bgr.shape
            cv2.line(bgr, (w//2, 0), (w//2, h), (255, 255, 255), 2)
            
            # High-Speed Encode
            _, buffer = cv2.imencode('.jpg', bgr, [int(cv2.IMWRITE_JPEG_QUALITY), 95])
            self.latest_frame = buffer.tobytes()

engine = PhoenixEngine()

def game_thread():
    """Single master loop for perfect sync."""
    while True:
        start = time.time()
        engine.step()
        engine.render()
        # Clean 30Hz heartbeat
        time.sleep(max(0.001, 0.033 - (time.time() - start)))

# --- WEB API ---
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/video')
def video():
    def stream():
        while True:
            if engine.latest_frame:
                yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + engine.latest_frame + b'\r\n')
            time.sleep(0.03)
    return Response(stream(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/flap')
def flap():
    if not engine.is_running or engine.done_h:
        engine.reset_game()
        engine.is_running = True
    else:
        engine.flap_pending = True
    return "", 204

@app.route('/stats')
def stats():
    return jsonify({
        "score_h": engine.score_h,
        "score_a": engine.score_a,
        "running": engine.is_running,
        "done_h": engine.done_h
    })

if __name__ == '__main__':
    threading.Thread(target=game_thread, daemon=True).start()
    app.run(host='0.0.0.0', port=7860, threaded=True)

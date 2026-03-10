import os
os.environ["SDL_VIDEODRIVER"] = "dummy"

from flask import Flask, render_template, Response, request, jsonify
import gymnasium as gym
import flappy_bird_gymnasium
from stable_baselines3 import PPO
import cv2
import numpy as np
import threading
import time

app = Flask(__name__)

class GameEngine:
    def __init__(self):
        self.env_h = gym.make("FlappyBird-v0", render_mode="rgb_array")
        self.env_a = gym.make("FlappyBird-v0", render_mode="rgb_array")
        
        try: self.model = PPO.load("flappy_ppo_final.zip")
        except: self.model = None
        
        self.env_h.reset()
        self.env_a.reset()
        
        self.score_h = self.score_a = 0
        self.best_h = self.best_a = 0
        self.done_h = self.done_a = False
        self.is_running = False
        
        self.flap_pending = False
        self.reset_pending = False
        self.latest_frame = None
        self.lock = threading.Lock()

game = GameEngine()

def run_loop():
    global game
    while True:
        start = time.time()
        
        with game.lock:
            # 1. ATOMIC RESET (The Fix)
            if game.reset_pending:
                game.env_h.reset()
                game.env_a.reset()
                game.score_h = game.score_a = 0
                game.done_h = game.done_a = False
                game.is_running = True
                game.reset_pending = False
                game.flap_pending = False # Clear stale flaps
            
            flap = game.flap_pending
            game.flap_pending = False
            running = game.is_running
            d_h, d_a = game.done_h, game.done_a

        if running:
            # 2. AI & HUMAN STEPS
            act_a = 0
            if not d_a and game.model:
                try: 
                    # Use deterministic=True for the 'perfect' smooth AI movement
                    obs_a, _ = game.env_a.reset() if d_a else (None, None) # Safety
                    act_a, _ = game.model.predict(game.env_a.unwrapped._get_observation(), deterministic=True)
                except: pass
            
            if not d_h:
                _, _, t_h, tr_h, i_h = game.env_h.step(1 if flap else 0)
                game.score_h = i_h.get("score", 0)
                if game.score_h > game.best_h: game.best_h = game.score_h
                game.done_h = t_h or tr_h
            
            if not d_a:
                _, _, t_a, tr_a, i_a = game.env_a.step(act_a)
                game.score_a = i_a.get("score", 0)
                if game.score_a > game.best_a: game.best_a = game.score_a
                game.done_a = t_a or tr_a

            if game.done_h and game.done_a:
                game.is_running = False

        # 3. HIGH-RES RENDER
        fh = game.env_h.render()
        fa = game.env_a.render()
        if fh is not None and fa is not None:
            comb = np.ascontiguousarray(np.hstack((fh, fa)))
            bgr = cv2.cvtColor(comb, cv2.COLOR_RGB2BGR)
            _, buf = cv2.imencode('.jpg', bgr, [int(cv2.IMWRITE_JPEG_QUALITY), 100])
            game.latest_frame = buf.tobytes()

        # Pure Original 30Hz Rhythm
        time.sleep(max(0.005, 0.033 - (time.time() - start)))

@app.route('/')
def index(): return render_template('index.html')

@app.route('/f')
def flap_trigger():
    with game.lock:
        if not game.is_running or game.done_h:
            game.reset_pending = True
        else:
            game.flap_pending = True
    return "", 204

@app.route('/video_feed')
def video_feed():
    def stream():
        while True:
            if game.latest_frame:
                yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + game.latest_frame + b'\r\n')
            time.sleep(0.03)
    return Response(stream(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/stats')
def stats():
    return jsonify({
        "s_h": game.score_h, "s_a": game.score_a,
        "b_h": game.best_h, "b_a": game.best_a,
        "run": game.is_running, "d_h": game.done_h
    })

if __name__ == '__main__':
    threading.Thread(target=run_loop, daemon=True).start()
    app.run(host='0.0.0.0', port=7860, threaded=True)

import os
import logging
from flask import Flask, render_template

# CLEAN SLATE TEST - Original Engine Only (No AI yet)
app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

@app.route('/')
def index():
    return render_template('index.html')

if __name__ == '__main__':
    # No background threads yet, just the raw game code
    app.run(host='0.0.0.0', port=7860, threaded=True)

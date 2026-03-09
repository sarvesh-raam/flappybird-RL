document.addEventListener('DOMContentLoaded', () => {
    const nameScreen = document.getElementById('name-screen');
    const nameInput = document.getElementById('player-name-input');
    const startBtn = document.getElementById('start-btn');
    const playerDisplay = document.getElementById('player-name-display');
    const labelHuman = document.getElementById('label-human');
    const themeBtn = document.getElementById('theme-btn');

    const scoreH = document.getElementById('score-h');
    const scoreA = document.getElementById('score-a');
    const bestH = document.getElementById('best-h');
    const bestA = document.getElementById('best-a');
    const lbList = document.getElementById('leaderboard-list');

    const overlay = document.getElementById('overlay');
    const overlayTitle = document.getElementById('overlay-title');
    const overlayMsg = document.getElementById('overlay-msg');

    let playerName = "Guest";
    let humanScoreSubmitted = false;
    let aiScoreSubmitted = false;

    // Handle Name Input
    startBtn.addEventListener('click', () => {
        if (nameInput.value.trim()) {
            playerName = nameInput.value.trim().toUpperCase();
            playerDisplay.innerText = playerName;
            labelHuman.innerText = playerName;
            nameScreen.classList.add('hidden');
            fetch('/action', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ type: 'set_name', name: playerName })
            });
            updateLeaderboard();
        }
    });

    // Theme Toggle Logic
    let isDark = true;
    themeBtn.addEventListener('click', () => {
        isDark = !isDark;
        document.body.setAttribute('data-theme', isDark ? 'dark' : 'light');
        themeBtn.innerText = isDark ? '🌙' : '☀️';
    });

    // Handle Keyboard Input
    window.addEventListener('keydown', (e) => {
        if (e.code === 'Space') {
            e.preventDefault();
            triggerFlap();
        }
    });

    // Handle Mobile Touch Input
    window.addEventListener('touchstart', (e) => {
        // Prevent default only if on game area to allow scrolling elsewhere
        if (e.target.id === 'game-stream' || e.target.closest('.video-container')) {
            e.preventDefault();
            triggerFlap();
        }
    }, { passive: false });

    // Flag for debounce
    let lastFlapTime = 0;
    function triggerFlap() {
        const now = Date.now();
        if (nameScreen.classList.contains('hidden') && now - lastFlapTime > 50) {
            lastFlapTime = now;
            fetch('/action', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ type: 'flap' })
            });
        }
    }

    async function updateLeaderboard() {
        try {
            const res = await fetch('/leaderboard');
            const data = await res.json();
            let lbHtml = '';
            data.board.forEach((entry, i) => {
                lbHtml += `
                    <div class="lb-row">
                        <span class="lb-name">${i + 1}. ${entry.name}</span>
                        <span class="lb-score">${entry.score}</span>
                    </div>
                `;
            });
            lbList.innerHTML = lbHtml || '<p style="color: grey; font-size: 0.8rem;">No scores yet</p>';
        } catch (e) { }
    }

    // Main Update Loop - Slowed down to 800ms to avoid 429 Rate Limit
    setInterval(async () => {
        try {
            const res = await fetch('/stats');
            const data = await res.json();

            scoreH.innerText = data.score_h;
            scoreA.innerText = data.score_a;
            bestH.innerText = data.best_h;
            bestA.innerText = data.best_a;

            // Overlay Management
            if (!data.is_running) {
                overlay.classList.remove('hidden');
                overlayTitle.innerText = "READY?";
                overlayMsg.innerText = "PRESS SPACE TO BATTLE";
            } else {
                if (data.done_h) {
                    overlay.classList.remove('hidden');
                    overlayTitle.innerText = "YOU CRASHED!";
                    overlayMsg.innerText = "PRESS SPACE TO TRY AGAIN";
                } else {
                    overlay.classList.add('hidden');
                }
            }

            // Realtime Score Submission
            if (data.done_h && data.score_h > 0 && !humanScoreSubmitted) {
                fetch('/submit_score', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ name: playerName, score: data.score_h })
                }).then(() => updateLeaderboard());
                humanScoreSubmitted = true;
            }

            if (data.is_running && !data.done_h) {
                humanScoreSubmitted = false;
                aiScoreSubmitted = false;
            }

            if (data.done_a && data.score_a > 0 && !aiScoreSubmitted) {
                fetch('/submit_score', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ name: "AI", score: data.score_a })
                });
                aiScoreSubmitted = true;
            }
        } catch (e) { }
    }, 800);

    // Leaderboard Polling - Slowed to 15s
    setInterval(updateLeaderboard, 15000);
    updateLeaderboard();

    // === FRAME POLLING (replaces MJPEG stream) ===
    // Polls /frame at ~15fps instead of one long-lived MJPEG connection.
    // This avoids Hugging Face's 429 rate-limiting on streaming connections.
    const gameStream = document.getElementById('game-stream');
    function refreshFrame() {
        // Cache-bust so browser doesn't serve a stale image
        gameStream.src = '/frame?t=' + Date.now();
    }
    // Start polling once the first image loads to avoid broken frames
    gameStream.onload = function () {
        setTimeout(refreshFrame, 67); // ~15 FPS
    };
    gameStream.onerror = function () {
        setTimeout(refreshFrame, 200); // Slow retry on error
    };
    refreshFrame(); // Initial load
});


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

    function triggerFlap() {
        if (nameScreen.classList.contains('hidden')) {
            // ZERO-LATENCY INPUT: Send immediately, don't wait for a loop
            fetch('/action', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ type: 'flap' }),
                keepalive: true
            });
        }
    }

    async function updateLeaderboard() {
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
    }

    // Main Update Loop
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

            // --- REALTIME SCORE SUBMISSION ---

            // 1. Submit Human Score Immediately on Crash
            if (data.done_h && data.score_h > 0 && !humanScoreSubmitted) {
                fetch('/submit_score', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ name: playerName, score: data.score_h })
                }).then(() => updateLeaderboard());
                humanScoreSubmitted = true;
            }

            // 2. Reset flags when human starts flying again
            if (data.is_running && !data.done_h) {
                humanScoreSubmitted = false;
                aiScoreSubmitted = false;
            }

            // 3. Submit AI's Final Score
            if (data.done_a && data.score_a > 0 && !aiScoreSubmitted) {
                fetch('/submit_score', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ name: "AI", score: data.score_a })
                });
                aiScoreSubmitted = true;
            }

        } catch (e) {
            console.error('Stats update error:', e);
        }
    }, 20);

    // Leaderboard Polling
    setInterval(updateLeaderboard, 5000);
    updateLeaderboard();
});

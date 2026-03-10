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
            // ATOMIC PING: Fastest way to send data from browser to server
            fetch('/f', { priority: 'high' });
        }
    }

    // Main Update Loop
    setInterval(async () => {
        try {
            const res = await fetch('/stats');
            const d = await res.json();

            scoreH.innerText = d.s_h;
            scoreA.innerText = d.s_a;
            bestH.innerText = d.b_h;
            bestA.innerText = d.b_a;

            // Overlay Management
            if (!d.run) {
                overlay.classList.remove('hidden');
                overlayTitle.innerText = "READY?";
                overlayMsg.innerText = "PRESS SPACE";
            } else {
                if (d.d_h) {
                    overlay.classList.remove('hidden');
                    overlayTitle.innerText = "YOU CRASHED";
                    overlayMsg.innerText = "SPACE TO RETRY";
                } else {
                    overlay.classList.add('hidden');
                }
            }
        } catch (e) { }
    }, 40);

    // Leaderboard Polling
    setInterval(updateLeaderboard, 5000);
    updateLeaderboard();
});

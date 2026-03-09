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

    let playerName = "PILOT";
    let tabVisible = true;

    document.addEventListener('visibilitychange', () => {
        tabVisible = !document.hidden;
    });

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

    // Handle Keyboard Input
    window.addEventListener('keydown', (e) => {
        if (e.code === 'Space') {
            e.preventDefault();
            triggerFlap();
        }
    });

    // Handle Mobile Touch
    window.addEventListener('touchstart', (e) => {
        if (e.target.id === 'game-stream' || e.target.closest('.video-container')) {
            e.preventDefault();
            triggerFlap();
        }
    }, { passive: false });

    let lastFlap = 0;
    function triggerFlap() {
        const now = Date.now();
        if (nameScreen.classList.contains('hidden') && now - lastFlap > 30) {
            lastFlap = now;
            fetch('/action', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ type: 'flap' })
            });
        }
    }

    async function updateLeaderboard() {
        if (!tabVisible) return;
        try {
            const res = await fetch('/leaderboard');
            const data = await res.json();
            lbList.innerHTML = data.board.map((e, i) => `
                <div class="lb-row">
                    <span class="lb-name">${i + 1}. ${e.name}</span>
                    <span class="lb-score">${e.score}</span>
                </div>
            `).join('') || '<p>No scores yet</p>';
        } catch (e) { }
    }

    // Stats Loop - 600ms for balance
    setInterval(async () => {
        if (!tabVisible) return;
        try {
            const res = await fetch('/stats');
            const data = await res.json();

            scoreH.innerText = data.score_h;
            scoreA.innerText = data.score_a;
            bestH.innerText = data.best_h;
            bestA.innerText = data.best_a;

            if (!data.is_running && data.done) {
                overlay.classList.remove('hidden');
                overlayTitle.innerText = data.score_h > 0 || data.score_a > 0 ? "GAME OVER" : "READY?";
                overlayMsg.innerText = "PRESS SPACE TO START DUEL";
            } else {
                overlay.classList.add('hidden');
            }
        } catch (e) { }
    }, 600);

    setInterval(updateLeaderboard, 30000);

    // Frame Polling - 5 FPS
    const gameStream = document.getElementById('game-stream');
    function refreshFrame() {
        if (!tabVisible) return;
        gameStream.src = '/frame?t=' + Date.now();
    }
    gameStream.onload = () => setTimeout(refreshFrame, 200);
    gameStream.onerror = () => setTimeout(refreshFrame, 1000);
    refreshFrame();
});

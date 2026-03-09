document.addEventListener('DOMContentLoaded', () => {
    const nameScreen = document.getElementById('name-screen');
    const startBtn = document.getElementById('start-btn');
    const nameInput = document.getElementById('player-name-input');
    const gameImg = document.getElementById('game-stream');
    const overlay = document.getElementById('overlay');
    const overlayTitle = document.getElementById('overlay-title');

    const scoreH = document.getElementById('score-h');
    const scoreA = document.getElementById('score-a');
    const bestH = document.getElementById('best-h');
    const best_A = document.getElementById('best-a');

    let tabVisible = true;
    document.addEventListener('visibilitychange', () => { tabVisible = !document.hidden; });

    startBtn.addEventListener('click', () => {
        if (nameInput.value.trim()) {
            const name = nameInput.value.trim().toUpperCase();
            document.getElementById('player-name-display').innerText = name;
            document.getElementById('label-human').innerText = name;
            nameScreen.classList.add('hidden');
            pollSync();
        }
    });

    window.addEventListener('keydown', (e) => { if (e.code === 'Space') { e.preventDefault(); triggerFlap(); } });
    window.addEventListener('touchstart', (e) => { if (e.target.id === 'game-stream') { e.preventDefault(); triggerFlap(); } }, { passive: false });

    function triggerFlap() {
        if (nameScreen.classList.contains('hidden')) {
            fetch('/action', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ type: 'flap' })
            });
        }
    }

    // Adaptive Sync Loop (Replaces setInterval for zero-lag)
    async function pollSync() {
        if (!tabVisible) {
            setTimeout(pollSync, 500);
            return;
        }

        try {
            const startTime = Date.now();
            const res = await fetch('/sync.jpg?t=' + startTime);

            // 1. Update Image (Binary Blob)
            const blob = await res.blob();
            const oldUrl = gameImg.src;
            gameImg.src = URL.createObjectURL(blob);
            if (oldUrl.startsWith('blob:')) URL.revokeObjectURL(oldUrl);

            // 2. Update Stats (From Headers)
            scoreH.innerText = res.headers.get('X-Score-H');
            scoreA.innerText = res.headers.get('X-Score-A');
            bestH.innerText = res.headers.get('X-Best-H');
            best_A.innerText = res.headers.get('X-Best-A');

            const isRunning = res.headers.get('X-Running') === '1';
            const doneH = res.headers.get('X-Done-H') === '1';

            if (!isRunning || doneH) {
                overlay.classList.remove('hidden');
                overlayTitle.innerText = doneH && scoreH.innerText !== "0" ? "YOU CRASHED!" : "READY?";
            } else {
                overlay.classList.add('hidden');
            }

            // 3. Adaptive Timing (Aim for ~15-20 FPS on web)
            const elapsed = Date.now() - startTime;
            const wait = Math.max(5, 50 - elapsed);
            setTimeout(pollSync, wait);
        } catch (e) {
            setTimeout(pollSync, 200);
        }
    }
});

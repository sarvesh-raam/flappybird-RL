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
    let pendingAction = null;
    let syncInterval = 100; // Default 10 FPS (Safe Zone for HF)

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

    window.addEventListener('keydown', (e) => { if (e.code === 'Space') { e.preventDefault(); pendingAction = 'flap'; } });
    window.addEventListener('touchstart', (e) => { if (e.target.id === 'game-stream') { e.preventDefault(); pendingAction = 'flap'; } }, { passive: false });

    // Adaptive Unified Sync Loop
    async function pollSync() {
        if (!tabVisible) {
            setTimeout(pollSync, 1000);
            return;
        }

        try {
            const startTime = Date.now();
            let url = '/sync?t=' + startTime;

            // ATTACH ACTION TO SYNC (Turbo-Sync v4)
            // One request handles both movement and action
            if (pendingAction) {
                url += '&act=' + pendingAction;
                pendingAction = null;
            }

            const res = await fetch(url);
            if (!res.ok) throw new Error('429 or Server Busy');

            // 1. Update Image
            const blob = await res.blob();
            const oldUrl = gameImg.src;
            gameImg.src = URL.createObjectURL(blob);
            if (oldUrl.startsWith('blob:')) URL.revokeObjectURL(oldUrl);

            // 2. Update Stats (Headers)
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

            // 3. Rate Limit Protection
            // Keep at 10-12 FPS to stay under Hugging Face's radar
            const elapsed = Date.now() - startTime;
            setTimeout(pollSync, Math.max(10, syncInterval - elapsed));
        } catch (e) {
            // Cool down on error (Hugging Face is likely rate-limiting)
            console.error("Network Throttling - Waiting for cool down...");
            setTimeout(pollSync, 2000);
        }
    }
});

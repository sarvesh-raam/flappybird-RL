document.addEventListener('DOMContentLoaded', () => {
    const nameScreen = document.getElementById('name-screen');
    const startBtn = document.getElementById('start-btn');
    const nameInput = document.getElementById('player-name-input');
    const gameImg = document.getElementById('game-stream');
    const overlay = document.getElementById('overlay');
    const overlayTitle = document.getElementById('overlay-title');
    const lbList = document.getElementById('leaderboard-list');

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
            sendAction('set_name', { name });
            updateLeaderboard();
        }
    });

    window.addEventListener('keydown', (e) => { if (e.code === 'Space') { e.preventDefault(); triggerFlap(); } });
    window.addEventListener('touchstart', (e) => { if (e.target.id === 'game-stream') { e.preventDefault(); triggerFlap(); } }, { passive: false });

    async function sendAction(type, extra = {}) {
        try {
            const res = await fetch('/sync', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ type, ...extra })
            });
            handleSync(await res.json());
        } catch (e) { }
    }

    let lastFlap = 0;
    function triggerFlap() {
        const now = Date.now();
        if (!nameScreen.classList.contains('hidden') || now - lastFlap < 50) return;
        lastFlap = now;
        sendAction('flap');
    }

    function handleSync(data) {
        if (data.image) gameImg.src = 'data:image/jpeg;base64,' + data.image;
        scoreH.innerText = data.score_h;
        scoreA.innerText = data.score_a;
        bestH.innerText = data.best_h;
        best_A.innerText = data.best_a;

        if (!data.running && data.done) {
            overlay.classList.remove('hidden');
            overlayTitle.innerText = data.score_h > 0 ? "GAME OVER" : "READY?";
        } else {
            overlay.classList.add('hidden');
        }
    }

    async function updateLeaderboard() {
        if (!tabVisible) return;
        try {
            const res = await fetch('/leaderboard');
            const data = await res.json();
            lbList.innerHTML = data.board.map((e, i) => `<div class='lb-row'><span>${i + 1}. ${e.name}</span><span>${e.score}</span></div>`).join('');
        } catch (e) { }
    }

    // High speed sync (Turbo Mode) - Bundles images and stats
    setInterval(async () => {
        if (!tabVisible || nameScreen.classList.contains('hidden') === false) return;
        try {
            const res = await fetch('/sync');
            handleSync(await res.json());
        } catch (e) { }
    }, 150) // ~7 FPS sync for ultra efficiency on HF

    setInterval(updateLeaderboard, 30000);
});

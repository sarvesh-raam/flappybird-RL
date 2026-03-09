document.addEventListener('DOMContentLoaded', () => {
    const canvas = document.getElementById('game-canvas');
    const ctx = canvas.getContext('2d');
    const nameScreen = document.getElementById('name-screen');
    const startBtn = document.getElementById('start-btn');
    const overlay = document.getElementById('overlay');

    const ui = {
        scoreH: document.getElementById('score-h'),
        scoreA: document.getElementById('score-a'),
        bestH: document.getElementById('best-h'),
        bestA: document.getElementById('best-a'),
        labelH: document.getElementById('label-human'),
        displayH: document.getElementById('player-name-display')
    };

    // Game Config (Matching Gymnasium internals)
    const W = 288;
    const H = 512;
    canvas.width = W * 2;
    canvas.height = H;

    let gameState = null;
    let tabVisible = true;
    let pendingAction = null;

    document.addEventListener('visibilitychange', () => { tabVisible = !document.hidden; });

    startBtn.addEventListener('click', () => {
        const name = document.getElementById('player-name-input').value.trim() || "PILOT";
        ui.labelH.innerText = name.toUpperCase();
        ui.displayH.innerText = name.toUpperCase();
        nameScreen.classList.add('hidden');
        fetch('/sync?act=set_name&name=' + name);
        requestAnimationFrame(renderLoop);
        syncLoop();
    });

    // --- CONTROLS ---
    window.addEventListener('keydown', (e) => { if (e.code === 'Space') { e.preventDefault(); pendingAction = 'flap'; } });
    canvas.addEventListener('touchstart', (e) => { e.preventDefault(); pendingAction = 'flap'; }, { passive: false });

    // --- NETWORK SYNC ---
    async function syncLoop() {
        if (!tabVisible) { setTimeout(syncLoop, 1000); return; }
        try {
            let url = '/sync?t=' + Date.now();
            if (pendingAction) { url += '&act=' + pendingAction; pendingAction = null; }
            const res = await fetch(url);
            gameState = await res.json();

            // Update UI
            ui.scoreH.innerText = gameState.score_h;
            ui.scoreA.innerText = gameState.score_a;
            ui.bestH.innerText = gameState.best_h;
            ui.bestA.innerText = gameState.best_a;

            if (!gameState.running || gameState.done_h) {
                overlay.classList.remove('hidden');
                document.getElementById('overlay-title').innerText = gameState.done_h && gameState.score_h > 0 ? "YOU CRASHED!" : "READY?";
            } else {
                overlay.classList.add('hidden');
            }
        } catch (e) { }
        setTimeout(syncLoop, 50); // 20Hz Sync is plenty when client renders
    }

    // --- CANVAS RENDERER (60 FPS) ---
    function drawBird(x, y, rot, color) {
        ctx.save();
        ctx.translate(x, y);
        ctx.rotate(rot * Math.PI / 180);
        // Bird Body
        ctx.fillStyle = color;
        ctx.beginPath();
        ctx.ellipse(0, 0, 16, 12, 0, 0, Math.PI * 2);
        ctx.fill();
        ctx.strokeStyle = 'black';
        ctx.lineWidth = 2;
        ctx.stroke();
        // Eye
        ctx.fillStyle = 'white';
        ctx.beginPath();
        ctx.arc(8, -4, 5, 0, Math.PI * 2);
        ctx.fill();
        ctx.fillStyle = 'black';
        ctx.beginPath();
        ctx.arc(10, -4, 2, 0, Math.PI * 2);
        ctx.fill();
        // Wing
        ctx.fillStyle = 'rgba(255,255,255,0.6)';
        ctx.beginPath();
        ctx.ellipse(-6, 2, 8, 5, 0, 0, Math.PI * 2);
        ctx.fill();
        ctx.restore();
    }

    function drawPipes(pipes, offsetX) {
        const PIPE_W = 52;
        const GAP = 100;
        ctx.fillStyle = '#73bf2e'; // Pipe Green
        ctx.strokeStyle = '#2d4c0d';
        ctx.lineWidth = 3;

        pipes.forEach(p => {
            const x = p.x + offsetX;
            const topY = p.y;
            // Top Pipe
            ctx.fillRect(x, 0, PIPE_W, topY);
            ctx.strokeRect(x, 0, PIPE_W, topY);
            // Bottom Pipe
            const botY = topY + GAP;
            ctx.fillRect(x, botY, PIPE_W, H - botY);
            ctx.strokeRect(x, botY, PIPE_W, H - botY);
            // Pipe Caps
            ctx.fillStyle = '#8ce03b';
            ctx.fillRect(x - 2, topY - 20, PIPE_W + 4, 20);
            ctx.strokeRect(x - 2, topY - 20, PIPE_W + 4, 20);
            ctx.fillRect(x - 2, botY, PIPE_W + 4, 20);
            ctx.strokeRect(x - 2, botY, PIPE_W + 4, 20);
            ctx.fillStyle = '#73bf2e';
        });
    }

    function renderLoop() {
        if (!gameState) { requestAnimationFrame(renderLoop); return; }

        // 1. Clear Arena
        ctx.fillStyle = '#4ec0ca';
        ctx.fillRect(0, 0, canvas.width, canvas.height);

        // 2. Draw Human Arena (Left)
        drawPipes(gameState.h.pipes, 0);
        drawBird(50, gameState.h.y, gameState.h.rot || 0, '#f7dc6f');

        // 3. Draw AI Arena (Right)
        drawPipes(gameState.a.pipes, W);
        drawBird(W + 50, gameState.a.y, gameState.a.rot || 0, '#58d68d');

        // 4. Draw Ground
        ctx.fillStyle = '#ded895';
        ctx.fillRect(0, H - 50, canvas.width, 50);
        ctx.fillStyle = '#73bf2e';
        ctx.fillRect(0, H - 55, canvas.width, 5);

        requestAnimationFrame(renderLoop);
    }
});

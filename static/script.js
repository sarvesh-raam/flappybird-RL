document.addEventListener('DOMContentLoaded', () => {
    const canvas = document.getElementById('game-canvas');
    const ctx = canvas.getContext('2d');
    const nameScreen = document.getElementById('name-modal');
    const retryScreen = document.getElementById('retry-modal');
    const overlay = document.getElementById('overlay');
    const startBtn = document.getElementById('start-btn');
    const retryBtn = document.getElementById('retry-btn');
    const nameInput = document.getElementById('name-input');

    // Core Game Config
    const W = 288;
    const H = 512;
    canvas.width = W * 2;
    canvas.height = H;

    // Assets
    const atlas = new Image();
    atlas.src = '/static/atlas.png';
    let assetsLoaded = false;
    atlas.onload = () => { assetsLoaded = true; };

    // Sprite Mapping from atlas.png
    const S = {
        bg: { x: 0, y: 0, w: 288, h: 512 },
        bg_night: { x: 288, y: 0, w: 288, h: 512 },
        ground: { x: 584, y: 0, w: 336, h: 112 },
        pipe_top: { x: 112, y: 646, w: 52, h: 320 },
        pipe_bot: { x: 168, y: 646, w: 52, h: 320 },
        birds: [
            // Yellow (Human)
            [{ x: 3, y: 491 }, { x: 31, y: 491 }, { x: 59, y: 491 }],
            // Green (AI)
            [{ x: 3, y: 529 }, { x: 31, y: 529 }, { x: 59, y: 529 }]
        ]
    };

    let gameState = null;
    let playerName = "PILOT";
    let pendingAction = null;
    let tabVisible = true;
    let scroll = 0;

    document.addEventListener('visibilitychange', () => { tabVisible = !document.hidden; });

    // --- RESTART LOGIC ---
    function startDuel() {
        if (nameInput.value.trim()) playerName = nameInput.value.trim().toUpperCase();
        document.getElementById('p-name').innerText = playerName;
        nameScreen.classList.add('hidden');
        retryScreen.classList.add('hidden');
        overlay.classList.add('hidden');

        // Initial sync to start physics thread
        fetch('/sync?act=flap&name=' + playerName);
        if (!gameState) {
            requestAnimationFrame(gameLoop);
            syncLoop();
        }
    }

    startBtn.addEventListener('click', startDuel);
    retryBtn.addEventListener('click', startDuel);

    // Controls
    window.addEventListener('keydown', (e) => { if (e.code === 'Space') { e.preventDefault(); pendingAction = 'flap'; } });
    canvas.addEventListener('touchstart', (e) => { e.preventDefault(); pendingAction = 'flap'; }, { passive: false });

    // --- NET SYNC ---
    async function syncLoop() {
        if (!tabVisible) { setTimeout(syncLoop, 1000); return; }
        try {
            let url = '/sync?t=' + Date.now();
            if (pendingAction) { url += '&act=' + pendingAction; pendingAction = null; }
            const res = await fetch(url);
            gameState = await res.json();

            // Sync UI
            document.getElementById('score-h').innerText = gameState.score_h;
            document.getElementById('score-a').innerText = gameState.score_a;
            document.getElementById('best-h').innerText = 'BEST: ' + gameState.best_h;
            document.getElementById('best-a').innerText = 'BEST: ' + gameState.best_a;

            if (gameState.done_h && gameState.running === false) {
                overlay.classList.remove('hidden');
                nameScreen.classList.add('hidden');
                retryScreen.classList.remove('hidden');
                document.getElementById('final-score').innerText = 'SCORE: ' + gameState.score_h;
            }
        } catch (e) { }
        setTimeout(syncLoop, 40); // 25Hz sync - ultra low latency
    }

    // --- RENDERER (60FPS) ---
    function drawEntity(x, y, rot, typeIdx) {
        const frame = Math.floor(Date.now() / 100) % 3;
        const sprite = S.birds[typeIdx][frame];
        ctx.save();
        ctx.translate(x, y);
        ctx.rotate((rot || 0) * Math.PI / 180);
        ctx.drawImage(atlas, sprite.x, sprite.y, 34, 24, -17, -12, 34, 24);
        ctx.restore();
    }

    function drawPipes(pipes, offsetX) {
        pipes.forEach(p => {
            const x = p.x + offsetX;
            const y = p.y;
            // Draw Top
            ctx.drawImage(atlas, S.pipe_top.x, S.pipe_top.y, 52, 320, x, y - 320, 52, 320);
            // Draw Bottom (Gym gap is ~100)
            ctx.drawImage(atlas, S.pipe_bot.x, S.pipe_bot.y, 52, 320, x, y + 100, 52, 320);
        });
    }

    function gameLoop() {
        if (!assetsLoaded || !gameState) { requestAnimationFrame(gameLoop); return; }

        ctx.clearRect(0, 0, canvas.width, canvas.height);

        // 1. Draw Backgrounds
        ctx.drawImage(atlas, S.bg.x, S.bg.y, S.bg.w, S.bg.h, 0, 0, W, H);
        ctx.drawImage(atlas, S.bg_night.x, S.bg_night.y, S.bg_night.w, S.bg_night.h, W, 0, W, H);

        if (gameState.running) scroll = (scroll + 3.2) % 336;

        // 2. Draw Pipes
        drawPipes(gameState.h.pipes, 0);
        drawPipes(gameState.a.pipes, W);

        // 3. Draw Birds
        drawEntity(50, gameState.h.y, gameState.h.rot, 0); // Yellow (Human)
        drawEntity(W + 50, gameState.a.y, gameState.a.rot, 1); // Green (AI)

        // 4. Draw Ground
        ctx.drawImage(atlas, S.ground.x, S.ground.y, 336, 112, -scroll, H - 110, 336, 112);
        ctx.drawImage(atlas, S.ground.x, S.ground.y, 336, 112, 336 - scroll, H - 110, 336, 112);
        ctx.drawImage(atlas, S.ground.x, S.ground.y, 336, 112, 672 - scroll, H - 110, 336, 112);

        requestAnimationFrame(gameLoop);
    }
});

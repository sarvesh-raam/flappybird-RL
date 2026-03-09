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

    // --- ASSETS ---
    const atlas = new Image();
    atlas.src = '/static/atlas.png';
    let assetsLoaded = false;
    atlas.onload = () => { assetsLoaded = true; };

    const SPRITES = {
        bg_day: [0, 0, 288, 512],
        bg_night: [288, 0, 288, 512],
        ground: [584, 0, 336, 112],
        pipe_green_top: [112, 646, 52, 320],
        pipe_green_bot: [168, 646, 52, 320],
        bird_yellow: [
            [3, 491, 34, 24], [31, 491, 34, 24], [59, 491, 34, 24]
        ],
        bird_green: [
            [3, 529, 34, 24], [31, 529, 34, 24], [59, 529, 34, 24]
        ]
    };

    const W = 288;
    const H = 512;
    canvas.width = W * 2;
    canvas.height = H;

    let serverState = null;
    let clientState = {
        h: { y: 256, rot: 0, frame: 0 },
        a: { y: 256, rot: 0, frame: 0 },
        scroll: 0
    };

    let tabVisible = true;
    let pendingAction = null;
    document.addEventListener('visibilitychange', () => { tabVisible = !document.hidden; });

    startBtn.addEventListener('click', () => {
        const name = document.getElementById('player-name-input').value.trim() || "PILOT";
        ui.labelH.innerText = name.toUpperCase();
        ui.displayH.innerText = name.toUpperCase();
        nameScreen.classList.add('hidden');
        requestAnimationFrame(renderLoop);
        syncLoop();
    });

    // --- SYNC ---
    async function syncLoop() {
        if (!tabVisible) { setTimeout(syncLoop, 1000); return; }
        try {
            let url = '/sync?t=' + Date.now();
            if (pendingAction) { url += '&act=' + pendingAction; pendingAction = null; }
            const res = await fetch(url);
            serverState = await res.json();

            // Stats
            ui.scoreH.innerText = serverState.score_h;
            ui.scoreA.innerText = serverState.score_a;
            ui.bestH.innerText = serverState.best_h;
            ui.bestA.innerText = serverState.best_a;

            if (!serverState.running || serverState.done_h) {
                overlay.classList.remove('hidden');
                document.getElementById('overlay-title').innerText = serverState.done_h && serverState.score_h > 0 ? "YOU CRASHED!" : "READY?";
            } else {
                overlay.classList.add('hidden');
            }
        } catch (e) { }
        setTimeout(syncLoop, 50);
    }

    // --- PRO RENDERER ---
    function drawSprite(key, x, y, options = {}) {
        const s = SPRITES[key];
        if (!s) return;

        ctx.save();
        ctx.translate(x, y);
        if (options.rot) ctx.rotate(options.rot * Math.PI / 180);

        // Scale/Flip support
        const w = options.w || s[2];
        const h = options.h || s[3];

        ctx.drawImage(atlas, s[0], s[1], s[2], s[3], -w / 2, -h / 2, w, h);
        ctx.restore();
    }

    function renderLoop() {
        if (!serverState || !assetsLoaded) { requestAnimationFrame(renderLoop); return; }

        // 1. Update Client Physics (Smoothing)
        // Lerp towards server position
        clientState.h.y += (serverState.h.y - clientState.h.y) * 0.4;
        clientState.a.y += (serverState.a.y - clientState.a.y) * 0.4;

        // Rotation & Animation
        if (serverState.running) {
            clientState.scroll = (clientState.scroll + 2.5) % 288;
            clientState.h.frame = Math.floor(Date.now() / 100) % 3;
            clientState.a.frame = Math.floor(Date.now() / 100) % 3;

            // Calculate rotation based on velocity (delta Y)
            clientState.h.rot = Math.min(Math.max((serverState.h.y - clientState.h.y) * 3, -20), 90);
            clientState.a.rot = Math.min(Math.max((serverState.a.y - clientState.a.y) * 3, -20), 90);
        } else {
            clientState.h.rot = 0; clientState.a.rot = 0;
        }

        // --- DRAWING ---
        // Arena 1
        drawSprite('bg_day', 144, 256);
        serverState.h.pipes.forEach(p => {
            // Top Pipe
            ctx.drawImage(atlas, 112, 646, 52, 320, p.x, p.y - 320, 52, 320);
            // Bottom Pipe (gap is ~100)
            ctx.drawImage(atlas, 168, 646, 52, 320, p.x, p.y + 100, 52, 320);
        });
        const hb = SPRITES.bird_yellow[clientState.h.frame];
        ctx.save();
        ctx.translate(50, clientState.h.y);
        ctx.rotate(clientState.h.rot * Math.PI / 180);
        ctx.drawImage(atlas, hb[0], hb[1], hb[2], hb[3], -17, -12, 34, 24);
        ctx.restore();

        // Arena 2
        ctx.save(); ctx.translate(W, 0);
        drawSprite('bg_night', 144, 256);
        serverState.a.pipes.forEach(p => {
            ctx.drawImage(atlas, 112, 646, 52, 320, p.x, p.y - 320, 52, 320);
            ctx.drawImage(atlas, 168, 646, 52, 320, p.x, p.y + 100, 52, 320);
        });
        const ab = SPRITES.bird_green[clientState.a.frame];
        ctx.save();
        ctx.translate(50, clientState.a.y);
        ctx.rotate(clientState.a.rot * Math.PI / 180);
        ctx.drawImage(atlas, ab[0], ab[1], ab[2], ab[3], -17, -12, 34, 24);
        ctx.restore();
        ctx.restore();

        // Shared Ground
        ctx.drawImage(atlas, 584, 0, 336, 112, -clientState.scroll, H - 112, 336, 112);
        ctx.drawImage(atlas, 584, 0, 336, 112, 336 - clientState.scroll, H - 112, 336, 112);
        ctx.drawImage(atlas, 584, 0, 336, 112, 672 - clientState.scroll, H - 112, 336, 112);

        requestAnimationFrame(renderLoop);
    }

    window.addEventListener('keydown', (e) => { if (e.code === 'Space') { e.preventDefault(); pendingAction = 'flap'; } });
    canvas.addEventListener('touchstart', (e) => { e.preventDefault(); pendingAction = 'flap'; }, { passive: false });
});

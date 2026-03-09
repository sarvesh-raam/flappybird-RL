document.addEventListener('DOMContentLoaded', () => {
    const canvas = document.getElementById('game-canvas');
    const ctx = canvas.getContext('2d');
    const overlay = document.getElementById('overlay');
    const btnStart = document.getElementById('btn-start');
    const nameInput = document.getElementById('name-input');

    // Config
    const W = 288;
    const H = 512;
    canvas.width = W * 2;
    canvas.height = H;

    // Asset Atlas
    const atlas = new Image();
    atlas.src = '/static/atlas.png?v=7.2';
    let loaded = false;
    atlas.onload = () => { loaded = true; };

    // Pixel Perfect Coordinates
    const SPRITES = {
        bg: [0, 0, 288, 512],
        bg_night: [288, 0, 288, 512],
        ground: [584, 0, 336, 112],
        pipe_top: [112, 646, 52, 320],
        pipe_bot: [168, 646, 52, 320],
        birds: [
            [[3, 491, 34, 24], [31, 491, 34, 24], [59, 491, 34, 24]], // Yellow
            [[3, 529, 34, 24], [31, 529, 34, 24], [59, 529, 34, 24]]  // Green
        ]
    };

    let s = null; // Server state
    let pendingAct = null;
    let scroll = 0;
    let tabVisible = true;
    document.addEventListener('visibilitychange', () => { tabVisible = !document.hidden; });

    function play() {
        const n = nameInput.value.trim().toUpperCase() || "PLAYER";
        document.getElementById('label-h').innerText = n;
        overlay.classList.add('hidden');
        if (!s) { sync(); requestAnimationFrame(draw); }
        pendingAct = 'flap';
    }

    btnStart.addEventListener('click', play);
    window.addEventListener('keydown', (e) => { if (e.code === 'Space') { e.preventDefault(); if (overlay.classList.contains('hidden')) pendingAct = 'flap'; else play(); } });

    async function sync() {
        if (!tabVisible) { setTimeout(sync, 1000); return; }
        try {
            let url = '/sync?t=' + Date.now();
            if (pendingAct) { url += '&act=' + pendingAct; pendingAct = null; }
            const res = await fetch(url);
            s = await res.json();

            document.getElementById('score-h').innerText = s.score_h;
            document.getElementById('score-a').innerText = s.score_a;

            if (!s.running && s.done_h) {
                overlay.classList.remove('hidden');
                document.getElementById('modal-title').innerText = "GAME OVER";
                document.getElementById('btn-start').innerText = "RETRY";
                document.getElementById('name-zone').classList.add('hidden');
            }
        } catch (e) { }
        setTimeout(sync, 40);
    }

    function draw() {
        if (!loaded || !s) { requestAnimationFrame(draw); return; }

        // Clear
        ctx.fillStyle = '#4ec0ca';
        ctx.fillRect(0, 0, canvas.width, canvas.height);

        // Backgrounds
        ctx.drawImage(atlas, ...SPRITES.bg, 0, 0, W, H);
        ctx.drawImage(atlas, ...SPRITES.bg_night, W, 0, W, H);

        if (s.running) scroll = (scroll + 3) % 288;

        // Draw Pipes (Arena 1)
        s.h.pipes.forEach(p => {
            ctx.drawImage(atlas, ...SPRITES.pipe_top, p.x, p.y - 320, 52, 320);
            ctx.drawImage(atlas, ...SPRITES.pipe_bot, p.x, p.y + 100, 52, 320);
        });

        // Draw Pipes (Arena 2)
        s.a.pipes.forEach(p => {
            ctx.drawImage(atlas, ...SPRITES.pipe_top, p.x + W, p.y - 320, 52, 320);
            ctx.drawImage(atlas, ...SPRITES.pipe_bot, p.x + W, p.y + 100, 52, 320);
        });

        // Draw Birds
        const f = Math.floor(Date.now() / 100) % 3;
        // Human
        ctx.save(); ctx.translate(50, s.h.y);
        ctx.rotate((s.h.rot || 0) * Math.PI / 180);
        ctx.drawImage(atlas, ...SPRITES.birds[0][f], -17, -12, 34, 24);
        ctx.restore();
        // AI
        ctx.save(); ctx.translate(W + 50, s.a.y);
        ctx.rotate((s.a.rot || 0) * Math.PI / 180);
        ctx.drawImage(atlas, ...SPRITES.birds[1][f], -17, -12, 34, 24);
        ctx.restore();

        // Ground
        ctx.drawImage(atlas, ...SPRITES.ground, -scroll, H - 112, 336, 112);
        ctx.drawImage(atlas, ...SPRITES.ground, 336 - scroll, H - 112, 336, 112);
        ctx.drawImage(atlas, ...SPRITES.ground, 672 - scroll, H - 112, 336, 112);

        requestAnimationFrame(draw);
    }
});

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
                document.getElementById('modal-msg').innerText = "FINAL SCORE: " + s.score_h;
            }
        } catch (e) { }
        setTimeout(sync, 40);
    }

    // --- PRO VECTOR RENDERING (Zero image dependencies) ---
    function drawProBird(x, y, rot, color1, color2) {
        ctx.save();
        ctx.translate(x, y);
        ctx.rotate((rot || 0) * Math.PI / 180);

        // Body Shadow
        ctx.fillStyle = 'rgba(0,0,0,0.2)';
        ctx.beginPath(); ctx.ellipse(2, 2, 17, 13, 0, 0, Math.PI * 2); ctx.fill();

        // Main Body
        ctx.fillStyle = color1;
        ctx.beginPath(); ctx.ellipse(0, 0, 17, 13, 0, 0, Math.PI * 2); ctx.fill();
        ctx.strokeStyle = '#543847'; ctx.lineWidth = 2.5; ctx.stroke();

        // Belly
        ctx.fillStyle = 'white';
        ctx.beginPath(); ctx.ellipse(-2, 4, 10, 6, 0.2, 0, Math.PI * 2); ctx.fill();

        // Eye
        ctx.fillStyle = 'white';
        ctx.beginPath(); ctx.arc(8, -5, 6, 0, Math.PI * 2); ctx.fill();
        ctx.stroke();
        ctx.fillStyle = 'black';
        ctx.beginPath(); ctx.arc(10, -5, 2.5, 0, Math.PI * 2); ctx.fill();

        // Beak
        ctx.fillStyle = '#f76a02';
        ctx.beginPath();
        ctx.moveTo(10, 0); ctx.lineTo(24, 2); ctx.lineTo(10, 6); ctx.closePath();
        ctx.fill(); ctx.stroke();

        // Wing
        const swing = Math.sin(Date.now() / 80) * 4;
        ctx.fillStyle = color2;
        ctx.beginPath(); ctx.ellipse(-7, 2 + swing, 10, 7, 0, 0, Math.PI * 2); ctx.fill();
        ctx.stroke();

        ctx.restore();
    }

    function drawProPipe(x, y, isLeft) {
        const PIPE_W = 52;
        const GAP = 100;
        const color = isLeft ? '#73bf2e' : '#528a1c';
        const dark = '#2d4c0d';

        ctx.fillStyle = color;
        ctx.strokeStyle = dark;
        ctx.lineWidth = 3;

        // Top Pipe
        ctx.fillRect(x, 0, PIPE_W, y);
        ctx.strokeRect(x, 0, PIPE_W, y);
        // Lip
        ctx.fillStyle = '#8ce03b';
        ctx.fillRect(x - 4, y - 25, PIPE_W + 8, 25);
        ctx.strokeRect(x - 4, y - 25, PIPE_W + 8, 25);

        // Bottom Pipe
        const botY = y + GAP;
        ctx.fillStyle = color;
        ctx.fillRect(x, botY, PIPE_W, H - botY);
        ctx.strokeRect(x, botY, PIPE_W, H - botY);
        // Lip
        ctx.fillStyle = '#8ce03b';
        ctx.fillRect(x - 4, botY, PIPE_W + 8, 25);
        ctx.strokeRect(x - 4, botY, PIPE_W + 8, 25);
    }

    function draw(time) {
        if (!s) { requestAnimationFrame(draw); return; }

        // --- ARENA 1 (DAY) ---
        ctx.fillStyle = '#4ec0ca';
        ctx.fillRect(0, 0, W, H);
        // Sun
        ctx.fillStyle = 'white'; ctx.beginPath(); ctx.arc(220, 60, 25, 0, Math.PI * 2); ctx.fill();
        // Pipes
        s.h.pipes.forEach(p => drawProPipe(p.x, p.y, true));
        // Bird
        drawProBird(50, s.h.y, s.h.rot, '#f7dc6f', '#f1c40f');

        // --- ARENA 2 (NIGHT) ---
        ctx.fillStyle = '#272738';
        ctx.fillRect(W, 0, W, H);
        // Moon
        ctx.fillStyle = 'white'; ctx.beginPath(); ctx.arc(W + 50, 60, 20, 0, Math.PI * 2); ctx.fill();
        // Pipes
        s.a.pipes.forEach(p => drawProPipe(p.x + W, p.y, false));
        // Bird
        drawProBird(W + 50, s.a.y, s.a.rot, '#58d68d', '#2ecc71');

        // --- SEPARATOR ---
        ctx.fillStyle = 'rgba(0,0,0,0.1)';
        ctx.fillRect(W - 1, 0, 2, H);

        // --- SCROLLING GROUND ---
        if (s.running) scroll = (scroll + 2.5) % 24;
        ctx.fillStyle = '#ded895';
        ctx.fillRect(0, H - 90, canvas.width, 90);
        ctx.fillStyle = '#8ce03b';
        ctx.fillRect(0, H - 95, canvas.width, 10);
        // Texture marks
        ctx.fillStyle = 'rgba(0,0,0,0.1)';
        for (let i = -scroll; i < canvas.width; i += 24) {
            ctx.fillRect(i, H - 95, 12, 10);
        }

        requestAnimationFrame(draw);
    }
});

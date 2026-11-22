// PRISMO — fabios kleiner helfer. the owner's page ("pie mode"): a live map of everything, the plane radar,
// the watchdog pinging every site, the real LED, stats.
// loaded by index.html after L ×5 / 5 logo taps / MP3 MP4 MP3 MP3 MP4 MP4. the password is checked by the server.
(() => {
  const S = typeof SERVER !== "undefined" ? SERVER : "";
  const KEY = "piepw";
  const HIST = 60;
  let timer = null, tick = 0, busy = false, history = [], pw = "";
  const hist = { cpu: [], temp: [], net: [], ocpu: [] };

  const font = document.createElement("link");
  font.rel = "stylesheet";
  font.href = "https://fonts.googleapis.com/css2?family=Baloo+2:wght@600;800&display=swap";

  const css = `
  #pie { --bg1: #f4effe; --bg2: #e9f4ff; --bg3: #fdf0f8; --card: rgba(255,255,255,.86); --line: #e7e1f7;
    --ink: #1e1a35; --dim: #6c6788; --ok: #11a05a; --bad: #e0245e; --meh: #c27c00;
    --grad: linear-gradient(90deg, #8d7bff, #ff74c8 55%, #38d6c4); --mint: #7ff0e2; --track: #ece8f8; }
  @media (prefers-color-scheme: dark) { #pie { --bg1: #15121f; --bg2: #101827; --bg3: #1d1222; --card: rgba(32,28,48,.9);
    --line: #2f2a45; --ink: #f1eefc; --dim: #a39fbd; --ok: #3ddc8f; --bad: #ff5c8a; --meh: #ffb547; --track: #2b2742; } }
  #pie, #pie * { box-sizing: border-box; }
  #pie { position: fixed; inset: 0; z-index: 99999; overflow: auto; color: var(--ink); -webkit-overflow-scrolling: touch;
    font: 500 15px/1.4 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
    background: radial-gradient(1200px 500px at 15% -10%, rgba(173,140,255,.35), transparent 60%),
      radial-gradient(900px 500px at 100% 0%, rgba(255,140,210,.25), transparent 60%),
      radial-gradient(900px 600px at 50% 110%, rgba(90,220,210,.2), transparent 60%),
      linear-gradient(160deg, var(--bg1), var(--bg2) 50%, var(--bg3)); }
  #pie .wrap { max-width: 1040px; margin: 0 auto; padding: 8px 16px 48px; }
  #pie .head { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 8px 0 12px; }
  #pie .logo { font: 800 38px/1 "Baloo 2", system-ui, sans-serif; color: #fff; letter-spacing: -1px;
    text-shadow: -2px -2px 0 var(--mint), 2px -2px 0 var(--mint), -2px 2px 0 var(--mint), 2px 2px 0 var(--mint), 0 0 16px rgba(127,240,226,.8), 2px 4px 8px rgba(40,20,90,.3); }
  #pie .logo small { font-size: 15px; letter-spacing: 0; margin-left: 8px; color: var(--dim); text-shadow: none; font-weight: 600; }
  #pie .live { font-size: 13px; color: var(--dim); white-space: nowrap; }
  #pie .live i { display: inline-block; width: 8px; height: 8px; border-radius: 50%; background: var(--bad); margin-right: 6px; animation: pie-pulse 1.6s ease-in-out infinite; }
  @keyframes pie-pulse { 50% { opacity: .25; } }
  #pie button { font: 700 15px "Baloo 2", system-ui, sans-serif; cursor: pointer; border: 0; border-radius: 999px; padding: 9px 16px 7px; color: #fff;
    background: var(--grad); box-shadow: 0 4px 14px rgba(120,80,220,.25); touch-action: manipulation; }
  #pie button:active { transform: scale(.96); }
  #pie .actions button { white-space: nowrap; flex: 1 1 auto; }
  #pie .morse button { flex: 0 0 auto; }
  #pie button.ghost { background: transparent; color: var(--ink); box-shadow: inset 0 0 0 2px var(--line); }
  #pie .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 14px; margin-top: 14px; }
  #pie .card { background: var(--card); border: 1px solid var(--line); border-radius: 20px; padding: 16px; box-shadow: 0 10px 30px rgba(60,30,120,.08); min-width: 0; }
  #pie .card.wide { grid-column: 1 / -1; }
  #pie h2 { margin: 0 0 10px; font: 800 20px/1.1 "Baloo 2", system-ui, sans-serif; }
  #pie h2 small { font: 500 13px system-ui, sans-serif; color: var(--dim); margin-left: 6px; }
  #pie .row { display: flex; justify-content: space-between; gap: 12px; padding: 6px 0; border-bottom: 1px solid var(--line); }
  #pie .row:last-child { border-bottom: 0; }
  #pie .row > :first-child { color: var(--dim); flex-shrink: 0; } #pie .row > :last-child { text-align: right; overflow-wrap: anywhere; font-weight: 600; }
  #pie .ok { color: var(--ok); } #pie .bad { color: var(--bad); } #pie .meh { color: var(--meh); }
  #pie .pill { display: inline-block; margin: 6px 6px 0 0; padding: 3px 10px; border-radius: 999px; font-size: 12.5px; font-weight: 600; background: var(--track); }
  #pie .pill.ok { color: var(--ok); } #pie .pill.bad { color: var(--bad); }
  #pie ul { margin: 6px 0 0; padding: 0; list-style: none; } #pie li { padding: 5px 0; border-bottom: 1px solid var(--line); overflow-wrap: anywhere; }
  #pie li:last-child { border-bottom: 0; } #pie small, #pie .dim { color: var(--dim); }
  #pie .lvl { height: 10px; border-radius: 99px; background: var(--track); overflow: hidden; }
  #pie .lvl i { display: block; height: 100%; border-radius: 99px; background: var(--grad); transition: width .8s ease; }

  /* the real LED */
  #pie .led { display: inline-block; width: 12px; height: 12px; border-radius: 50%; margin-left: 8px; vertical-align: 2px; background: #2a6b3a; box-shadow: inset 0 0 0 2px rgba(0,0,0,.15); }
  #pie .led.on { background: #3dff7a; box-shadow: 0 0 12px #3dff7a, 0 0 24px #3dff7a; animation: pie-led .25s steps(1) infinite; }
  @keyframes pie-led { 50% { background: #2a6b3a; box-shadow: none; } }
  #pie .actions { display: flex; flex-wrap: wrap; gap: 8px; }
  #pie .morse { display: flex; gap: 8px; margin-top: 10px; }
  #pie .morse input { flex: 1 1 auto; min-width: 0; width: 100%; font: 600 16px system-ui, sans-serif; padding: 9px 14px; border-radius: 999px; border: 2px solid var(--line);
    background: transparent; color: var(--ink); text-transform: uppercase; }
  #pie .toast { min-height: 1.4em; margin-top: 8px; font-weight: 600; }
  @media (max-width: 520px) { #pie .logo { font-size: 32px; } #pie .logo small { display: none; } }

  /* plane radar */
  #pie .radarbox { position: relative; border-radius: 18px; overflow: hidden; margin: 0 -4px; background: radial-gradient(circle at 50% 40%, #0c2430, #040b10 75%); }
  #pie svg.radar { display: block; width: 100%; max-width: 560px; height: auto; margin: 0 auto; }
  #pie .radar .rg { fill: none; stroke: rgba(56,214,196,.22); stroke-width: 1; }
  #pie .radar .rx { stroke: rgba(56,214,196,.1); stroke-width: 1; }
  #pie .radar .rl { fill: rgba(127,240,226,.6); font: 600 10px system-ui, sans-serif; }
  #pie .radar .cd { fill: rgba(127,240,226,.75); font: 800 11px system-ui, sans-serif; text-anchor: middle; }
  #pie .radar .sweep { transform-origin: 200px 200px; animation: pie-spin 4s linear infinite; }
  @keyframes pie-spin { to { transform: rotate(360deg); } }
  #pie .radar .pl { cursor: pointer; }
  #pie .radar .pl text { font: 700 10px system-ui, sans-serif; fill: #e8fbff; paint-order: stroke; stroke: #040b10; stroke-width: 3px; }
  #pie .radar .pl text.a { font-weight: 600; fill: #9fd3d6; }
  #pie .radar .pl.sel .gl { stroke: #fff; stroke-width: 1.6px; }
  #pie .radar .pl .selr { opacity: 0; } #pie .radar .pl.sel .selr { opacity: .9; }
  #pie .radar .tr { fill: none; stroke-width: 1.6; opacity: .4; stroke-linecap: round; }
  #pie .rinfo { padding: 10px 14px 4px; color: #cdeff0; font-size: 13.5px; min-height: 3.4em; }
  #pie .rinfo b { color: #fff; }
  #pie .plist { display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: 6px; padding: 6px 10px 12px; }
  #pie .plist button { all: unset; cursor: pointer; padding: 6px 10px; border-radius: 10px; background: rgba(255,255,255,.06); color: #d9f6f6; font: 500 12.5px system-ui, sans-serif;
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  #pie .plist button.sel { background: rgba(56,214,196,.25); }

  /* watchdog live */
  #pie .watchbox { position: relative; border-radius: 18px; overflow: hidden; margin: 0 -4px; background: radial-gradient(circle at 50% 50%, #221b4d, #0b0920 80%); }
  #pie svg.watch { display: block; width: 100%; height: auto; }
  #pie .watch .sp { stroke: rgba(255,255,255,.07); stroke-width: 1; }
  #pie .watch .sn { stroke-width: 2.5; fill: #15112e; stroke: #6c6788; transition: fill .4s; }
  #pie .watch .sn.ok { stroke: #3dff9a; } #pie .watch .sn.bad { stroke: #ff4d7a; fill: rgba(255,77,122,.35); }
  #pie .watch .sn.ping { fill: #ffffff; transition: none; }
  #pie .watch text { fill: #ece9ff; font: 600 14px system-ui, sans-serif; }
  #pie .watch text.ms { fill: #a9a3d6; font-size: 12px; }
  @media (max-width: 520px) { #pie .watch text { font-size: 19px; } #pie .watch text.ms { font-size: 16px; } #pie .watch .sn { r: 11px; } }
  #pie .wl { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 0 18px; margin-top: 10px; }
  #pie .wl .row { align-items: center; }
  #pie .wl svg { width: 90px; height: 18px; flex: 0 0 auto; }
  #pie .wl .row > :first-child { flex: 1 1 auto; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  #pie .wl .row > :last-child { flex: 0 0 auto; display: flex; gap: 8px; align-items: center; }

  /* the live map: a little dark universe, also in light mode */
  #pie .mapbox { position: relative; border-radius: 18px; overflow: hidden; margin: 0 -4px;
    background: radial-gradient(circle at 50% 48%, #2b1f5c 0%, #140f2e 55%, #08061a 100%); }
  #pie .mapbox::before { content: ""; position: absolute; inset: 0; pointer-events: none; opacity: .55;
    background-image: radial-gradient(1px 1px at 12% 18%, #fff, transparent), radial-gradient(1px 1px at 72% 12%, #fff, transparent),
      radial-gradient(1px 1px at 33% 76%, #fff, transparent), radial-gradient(1.5px 1.5px at 88% 64%, #fff, transparent),
      radial-gradient(1px 1px at 52% 38%, #cfc6ff, transparent), radial-gradient(1px 1px at 8% 88%, #fff, transparent),
      radial-gradient(1px 1px at 94% 92%, #cfc6ff, transparent), radial-gradient(1px 1px at 61% 86%, #fff, transparent),
      linear-gradient(rgba(255,255,255,.035) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,.035) 1px, transparent 1px);
    background-size: auto, auto, auto, auto, auto, auto, auto, auto, 30px 30px, 30px 30px; }
  #pie svg.map { position: relative; width: 100%; height: auto; display: block; }
  #pie .map .wire { fill: none; stroke-width: 2; opacity: .22; }
  #pie .map .wire.down { stroke: #ff4d7a !important; opacity: .7; stroke-dasharray: 5 7; }
  #pie .map .halo { opacity: .35; transform-box: fill-box; transform-origin: center; animation: pie-halo 2.4s ease-out infinite; }
  @keyframes pie-halo { from { transform: scale(.9); opacity: .55; } to { transform: scale(1.7); opacity: 0; } }
  #pie .map .core { fill: rgba(255,255,255,.07); stroke-width: 2; }
  #pie .map .dead .core { stroke: #ff4d7a !important; }
  #pie .map .dead .halo { display: none; }
  #pie .map text { fill: #ece9ff; font: 600 13px system-ui, sans-serif; text-anchor: middle; }
  #pie .map text.e { font-size: 24px; } #pie .map text.v { fill: #a9a3d6; font-size: 11.5px; }
  #pie .map .node { cursor: pointer; }
  #pie .map .ring { fill: none; stroke-width: 5; stroke-linecap: round; transition: stroke-dashoffset .8s ease, stroke .8s ease; }
  #pie .map .ringbg { fill: none; stroke: rgba(255,255,255,.08); stroke-width: 5; }
  #pie .map .pkt { mix-blend-mode: screen; }
  #pie .maptip { position: relative; margin: 0; padding: 10px 14px 12px; color: #d9d4ff; font-size: 13px; min-height: 2.6em;
    background: linear-gradient(transparent, rgba(0,0,0,.25)); }
  #pie .maptip b { color: #fff; }
  #pie .flash { position: absolute; left: 50%; top: 10px; transform: translateX(-50%); padding: 4px 12px; border-radius: 99px; font-weight: 700; font-size: 13px;
    color: #fff; background: rgba(141,123,255,.85); opacity: 0; transition: opacity .3s; pointer-events: none; white-space: nowrap; }
  #pie .flash.on { opacity: 1; }
  /* meters */
  #pie .meters { display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 10px; }
  #pie .m { padding: 10px 12px; border-radius: 14px; background: var(--track); min-width: 0; }
  #pie .m b { display: block; font: 800 24px/1.1 "Baloo 2", system-ui, sans-serif; }
  #pie .m .lvl { margin: 6px 0 4px; height: 6px; background: rgba(127,127,127,.15); }
  #pie .m small { font-size: 12px; }
  #pie .m.hot b { color: var(--bad); }
  #pie svg.spark { display: block; width: 100%; height: 26px; margin-top: 4px; }
  #pie svg.chart { width: 100%; height: 170px; display: block; color: var(--ink); }
  #pie .legend span { margin-right: 14px; font-size: 13px; } #pie .legend i { display: inline-block; width: 10px; height: 10px; border-radius: 3px; margin-right: 5px; vertical-align: -1px; }

  #pie .foot { margin-top: 22px; text-align: center; color: var(--dim); font-size: 13px; }
  #pie .foot b { font: 800 18px "Baloo 2", system-ui, sans-serif; color: var(--ink); }
  #pie .barcode { height: 34px; width: 180px; margin: 10px auto 0; display: flex; background: #fff; padding: 4px; border-radius: 4px; }
  #pie .barcode i { background: #111; }
  #pie .gate { max-width: 380px; margin: 14vh auto 0; text-align: center; padding: 26px 20px; }
  #pie .gate input { font: 800 34px "Baloo 2", monospace; width: 180px; text-align: center; letter-spacing: 12px; border: 2px solid var(--line);
    border-radius: 18px; padding: 6px; margin: 16px 0; background: transparent; color: var(--ink); }
  #pie .err { color: var(--bad); min-height: 1.4em; margin-top: 10px; font-weight: 600; }
  /* PRISMO offline: full alarm. calms down the second it's back */
  #pie .alarmbar { display: none; position: sticky; top: 0; z-index: 6; margin: 0 -16px 12px; padding: 12px 16px 10px; text-align: center; color: #fff;
    font: 800 24px/1.1 "Baloo 2", system-ui, sans-serif; letter-spacing: 1px; text-shadow: 0 2px 0 #5a0012, 0 0 18px #ff0033;
    background: repeating-linear-gradient(45deg, #ff1744 0 22px, #9a0024 22px 44px); background-size: 62.2px 62.2px;
    animation: pie-stripes .5s linear infinite; box-shadow: 0 6px 30px rgba(255,0,50,.6); }
  #pie .alarmbar div { animation: pie-blink .45s steps(1) infinite; }
  #pie .alarmbar small { display: block; margin-top: 4px; font: 700 14px system-ui, sans-serif; letter-spacing: 0; color: #ffe1e6; }
  #pie.alarm .alarmbar { display: block; }
  #pie.alarm::before { content: ""; position: fixed; inset: 0; z-index: 5; pointer-events: none; box-shadow: inset 0 0 140px 50px rgba(255,0,40,.8);
    animation: pie-redpulse .7s ease-in-out infinite; }
  #pie.alarm .wrap { animation: pie-shake 3s infinite; }
  #pie.alarm .logo { animation: pie-blink .35s steps(1) infinite; text-shadow: -2px -2px 0 #ff1744, 2px -2px 0 #ff1744, -2px 2px 0 #ff1744, 2px 2px 0 #ff1744, 0 0 22px #ff0033; }
  #pie.alarm .card { border-color: rgba(255,23,68,.7); box-shadow: 0 0 0 1px rgba(255,23,68,.4), 0 10px 40px rgba(255,0,50,.25); }
  #pie.alarm .mapbox, #pie.alarm .radarbox, #pie.alarm .watchbox { filter: grayscale(.85) brightness(.7); }
  #pie .okbar { display: none; margin: 0 -16px 12px; padding: 12px 16px; text-align: center; color: #fff; font: 800 22px "Baloo 2", system-ui, sans-serif;
    background: linear-gradient(90deg, #0fa968, #2ad38b); box-shadow: 0 6px 30px rgba(20,200,120,.45); }
  #pie .okbar.on { display: block; animation: pie-calm 6s ease forwards; }
  @keyframes pie-stripes { to { background-position: 62.2px 0; } }
  @keyframes pie-blink { 50% { opacity: .35; } }
  @keyframes pie-redpulse { 50% { box-shadow: inset 0 0 60px 12px rgba(255,0,40,.35); } }
  @keyframes pie-shake { 0%, 14%, 100% { transform: none; } 2% { transform: translate(-7px, 2px) rotate(-.5deg); } 4% { transform: translate(7px, -2px) rotate(.5deg); }
    6% { transform: translate(-5px, -1px) rotate(-.3deg); } 8% { transform: translate(5px, 1px) rotate(.3deg); } 10% { transform: translate(-2px, 0); } 12% { transform: translate(2px, 0); } }
  @keyframes pie-calm { 0% { transform: scale(1.04); opacity: 0; } 8%, 80% { transform: none; opacity: 1; } 100% { opacity: 0; } }
  @media (prefers-reduced-motion: reduce) { #pie * { animation: none !important; } }
  `;

  // --- helpers ---
  const $p = id => document.getElementById(id);
  const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const num = (n, d = 1) => (n ?? 0).toLocaleString("de-AT", { maximumFractionDigits: d });
  const mb = b => num(b / 1e6) + " MB";
  const gb = b => num(b / 1e9) + " GB";
  const rate = b => b >= 1e6 ? num(b / 1e6) + " MB/s" : num(b / 1e3) + " kB/s";
  const dur = s => { s = Math.max(0, Math.round(s)); const d = Math.floor(s / 86400), h = Math.floor(s % 86400 / 3600), m = Math.floor(s % 3600 / 60);
    return d ? `${d} T ${h} Std` : h ? `${h} Std ${m} Min` : m ? `${m} Min` : `${s} s`; };
  const ago = t => t ? "vor " + dur(Date.now() / 1000 - t) : "nie";
  const isoAgo = s => s ? ago(new Date(s).getTime() / 1000) : "nie";
  const when = s => { if (!s) return ""; const d = new Date(s.replace("Z", ""));
    return d.toLocaleDateString("de-AT", { weekday: "short", day: "2-digit", month: "2-digit" }) + " " + d.toLocaleTimeString("de-AT", { hour: "2-digit", minute: "2-digit" }); };
  const row = (k, v) => `<div class="row"><span>${k}</span><span>${v}</span></div>`;
  const bar = pct => `<div class="lvl"><i style="width:${Math.min(100, Math.max(2, pct || 0)).toFixed(0)}%"></i></div>`;
  const yes = (ok, a, b) => ok == null ? `<span class="meh">?</span>` : ok ? `<span class="ok">${a}</span>` : `<span class="bad">${b}</span>`;
  const ICON = { CANCELLED: "❌", ADDITIONAL: "➕", SUBSTITUTION: "🔄", ROOMSUBSTITUTION: "🚪", SHIFT: "🔀", EXAM: "📝", IRREGULAR: "🔄", EVENT: "📅" };
  const THROTTLE = { undervoltage: "Unterspannung ⚡", freq_capped: "Takt gedrosselt", throttled: "gebremst", soft_temp_limit: "zu heiß 🔥" };
  const pushH = (arr, v) => { if (v == null || Number.isNaN(v)) return; arr.push(v); if (arr.length > HIST) arr.shift(); };
  const day = offset => { const d = new Date(Date.now() + offset * 86400e3); return d.getFullYear() + "-" + String(d.getMonth() + 1).padStart(2, "0") + "-" + String(d.getDate()).padStart(2, "0"); };
  function spark(arr, max, color = "#8d7bff") {
    if (arr.length < 2) return `<svg class="spark"></svg>`;
    const m = max || Math.max(...arr, 1), step = 100 / (HIST - 1), off = 100 - (arr.length - 1) * step;
    const pts = arr.map((v, i) => `${(off + i * step).toFixed(1)},${(25 - 23 * Math.min(1, v / m)).toFixed(1)}`).join(" ");
    return `<svg class="spark" viewBox="0 0 100 26" preserveAspectRatio="none"><polyline points="${pts}" fill="none" stroke="${color}" stroke-width="2" vector-effect="non-scaling-stroke"/></svg>`;
  }

  // --- screens ---
  function root() {
    let r = $p("pie");
    if (!r) {
      if (!font.isConnected) document.head.appendChild(font);
      if (!$p("pie-css")) { const st = document.createElement("style"); st.id = "pie-css"; st.textContent = css; document.head.appendChild(st); }
      r = document.createElement("div"); r.id = "pie"; document.body.appendChild(r);
      addEventListener("keydown", e => { if (e.key === "Escape" && $p("pie")) close(); });
    }
    document.documentElement.style.overflow = "hidden";
    return r;
  }

  // --- the offline alarm: 3 missed polls in a row (a wifi hiccup isn't an outage), gone on the first answer ---
  const A = { miss: 0, since: null, on: false, title: null };
  function siren() {
    try {
      const ac = new (window.AudioContext || window.webkitAudioContext)(), o = ac.createOscillator(), g = ac.createGain(), t = ac.currentTime;
      o.type = "sawtooth"; g.gain.value = .05; o.connect(g).connect(ac.destination);
      for (let i = 0; i < 4; i++) { o.frequency.setValueAtTime(620, t + i * .6); o.frequency.linearRampToValueAtTime(1180, t + i * .6 + .3); o.frequency.linearRampToValueAtTime(620, t + i * .6 + .6); }
      g.gain.setValueAtTime(.05, t + 2.2); g.gain.linearRampToValueAtTime(0, t + 2.4);
      o.start(t); o.stop(t + 2.45); o.onended = () => ac.close();
    } catch {}
  }
  function alarm(d) {
    const r = $p("pie"); if (!r || !$p("pie-alarm")) return;
    if (d.pi) {
      A.miss = 0; A.since = null;
      if (A.on) {
        A.on = false; r.classList.remove("alarm"); document.title = A.title;
        const ok = $p("pie-okbar"); ok.classList.remove("on"); void ok.offsetWidth; ok.classList.add("on");
        clearTimeout(alarm.t); alarm.t = setTimeout(() => ok.classList.remove("on"), 6000);
      }
      return;
    }
    A.miss++; A.since ??= Date.now();
    if (A.miss >= 3 && !A.on) { A.on = true; A.title = document.title; r.classList.add("alarm"); $p("pie-okbar").classList.remove("on"); siren(); }
    if (A.on) {
      $p("pie-alarmtxt").textContent = `kein Lebenszeichen seit ${dur((Date.now() - A.since) / 1000)} · Stecker? WLAN? Mama? 🔌`;
      document.title = (Math.floor(Date.now() / 1000) % 2 ? "🚨🚨 " : "⚠️ ") + "PRISMO OFFLINE";
    }
  }

  function close() {
    if (A.on) document.title = A.title;
    A.on = false; A.miss = 0; A.since = null;
    clearInterval(timer);
    $p("pie")?.remove();
    document.documentElement.style.overflow = "";
  }

  function gate(msg = "") {
    root().innerHTML = `<div class="wrap"><div class="card gate">
      <div class="logo">prismo</div><div class="dim" style="margin-top:6px">fabios kleiner helfer</div>
      <form><input type="password" inputmode="numeric" autocomplete="off" maxlength="12" aria-label="Code"><br>
        <button type="submit">Aufmachen</button> <button class="ghost" type="button" data-x>Zurück</button></form>
      <div class="err">${esc(msg)}</div></div></div>`;
    const input = $p("pie").querySelector("input");
    input.focus();
    $p("pie").querySelector("[data-x]").onclick = close;
    $p("pie").querySelector("form").onsubmit = e => { e.preventDefault(); login(input.value.trim()); };
  }

  async function api(body) {
    const r = await fetch(S + "/pie", { method: "POST", body: JSON.stringify({ pw, ...body }), signal: AbortSignal.timeout(9000) });
    return { ok: r.ok, status: r.status, body: await r.json().catch(() => ({})) };
  }

  async function login(code) {
    if (!code) return gate("Code fehlt");
    pw = code;
    root().innerHTML = `<div class="wrap"><div class="card gate"><div class="logo">prismo</div><p class="dim">wird ausgepackt…</p></div></div>`;
    let res;
    try { res = await api({ full: true }); } catch { return gate("Oracle antwortet nicht"); }
    if (!res.ok) {
      try { sessionStorage.removeItem(KEY); } catch {}
      return gate(res.body.error === "locked" ? `Zu oft falsch. Nochmal in ${dur(res.body.wait)}` : "Falscher Code");
    }
    try { sessionStorage.setItem(KEY, code); } catch {}
    show(res.body);
  }

  // --- PRISMO's real green LED ---
  function ledCard(d) {
    return `<section class="card wide"><h2>💡 PRISMOs Licht <span class="led ${d.pi?.led?.what ? "on" : ""}" id="pie-led" title="das echte grüne Licht"></span>
        <small>blinkt wirklich in deinem Zimmer</small></h2>
      <div class="actions"><button data-a="heart">💓 Herzschlag</button><button data-a="wave" class="ghost">👋 Wild blinken</button></div>
      <form class="morse" id="pie-morse"><input maxlength="24" placeholder="Morse-Nachricht ans Zimmer…" autocomplete="off"><button type="submit">📡</button></form>
      <div class="toast" id="pie-toast"></div></section>`;
  }

  async function act(action, text) {
    const t = $p("pie-toast");
    t.textContent = "…"; t.className = "toast";
    spawn("oracle_you", true); setTimeout(() => spawn("pi_oracle", true), 600);
    try {
      const res = await api({ action, text });
      if (res.status !== 504) { spawn("pi_oracle"); setTimeout(() => spawn("oracle_you"), 600); }
      t.textContent = res.body.message || res.body.error || "?";
      t.className = "toast " + (res.ok ? "ok" : "bad");
      if (res.ok) setTimeout(() => refresh(true), 400);
    } catch { t.textContent = "PRISMO antwortet nicht 💤"; t.className = "toast bad"; }
  }

  // --- the live map: everything ytmp34 + prismo touches. packets fly with the real traffic ---
  const NODES = {
    you: { x: 90, y: 70, e: "📱", l: "Du", c: "#ff74c8", r: 28 }, oracle: { x: 300, y: 62, e: "🦁", l: "Oracle", c: "#ffb547", r: 30 },
    yt: { x: 510, y: 70, e: "▶️", l: "YouTube", c: "#ff4d4d", r: 28 }, pi: { x: 300, y: 228, e: "🍓", l: "PRISMO", c: "#3dff9a", r: 40 },
    untis: { x: 90, y: 360, e: "📚", l: "WebUntis", c: "#5cc8ff", r: 28 }, ntfy: { x: 300, y: 382, e: "🔔", l: "ntfy", c: "#c58bff", r: 26 },
    sites: { x: 510, y: 360, e: "🌐", l: "deine Seiten", c: "#38d6c4", r: 28 }, sky: { x: 528, y: 215, e: "✈️", l: "Himmel", c: "#7fb8ff", r: 26 },
  };
  // [from, to, bend]: packets fly from → to (rev = the other way)
  const LINKS = { yt_pi: ["yt", "pi", 40], pi_oracle: ["pi", "oracle", -30], oracle_you: ["oracle", "you", 26], pi_untis: ["pi", "untis", 30],
    pi_ntfy: ["pi", "ntfy", -18], ntfy_you: ["ntfy", "you", -120], pi_sites: ["pi", "sites", -30], sky_pi: ["sky", "pi", 22] };
  const ms = { rates: {}, burst: [], down: {}, led: false, io: false, temp: 45, cpu: 0, lastVideos: null, lastPush: null, lastPlanes: null, lastUntis: null, tip: "pi", d: null };
  let raf = 0, lastT = 0, pkts = [];

  function linkPath([a, b, bend]) {
    const A = NODES[a], B = NODES[b], mx = (A.x + B.x) / 2, my = (A.y + B.y) / 2;
    const dx = B.x - A.x, dy = B.y - A.y, len = Math.hypot(dx, dy) || 1;
    return `M${A.x},${A.y} Q${(mx - dy / len * bend).toFixed(1)},${(my + dx / len * bend).toFixed(1)} ${B.x},${B.y}`;
  }

  function mapSvg() {
    const ringC = 2 * Math.PI * 48;
    return `<div class="mapbox"><div class="flash" id="pie-flash"></div>
      <svg class="map" id="pie-map" viewBox="0 0 600 440" role="img" aria-label="Live-Karte von PRISMO">
      <defs><filter id="pie-glow" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="3.2" result="b"/>
        <feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
        <filter id="pie-soft" x="-100%" y="-100%" width="300%" height="300%"><feGaussianBlur stdDeviation="7"/></filter></defs>
      ${Object.entries(LINKS).map(([k, l]) => `<path class="wire" id="pie-w-${k}" d="${linkPath(l)}" stroke="${NODES[l[0]].c}"/>`).join("")}
      <g id="pie-pkts"></g>
      ${Object.entries(NODES).map(([k, n]) => `<g class="node" id="pie-n-${k}" data-k="${k}">
        <circle class="halo" cx="${n.x}" cy="${n.y}" r="${n.r}" fill="${n.c}" filter="url(#pie-soft)"/>
        ${k === "pi" ? `<circle class="ringbg" cx="${n.x}" cy="${n.y}" r="48"/><circle class="ring" id="pie-ring" cx="${n.x}" cy="${n.y}" r="48"
            stroke-dasharray="${ringC.toFixed(1)}" stroke-dashoffset="${ringC.toFixed(1)}" transform="rotate(-90 ${n.x} ${n.y})"/>` : ""}
        <circle class="core" cx="${n.x}" cy="${n.y}" r="${n.r}" stroke="${n.c}" filter="url(#pie-glow)"/>
        <text class="e" x="${n.x}" y="${n.y + (k === "pi" ? 11 : 8)}" style="${k === "pi" ? "font-size:34px" : ""}">${n.e}</text>
        ${k === "pi" ? `<circle id="pie-mled" cx="${n.x + 27}" cy="${n.y - 27}" r="5" fill="#3dff9a" filter="url(#pie-glow)"/>` : ""}
        <text x="${n.x}" y="${n.y + n.r + (k === "pi" ? 30 : 18)}">${n.l}</text>
        <text class="v" id="pie-v-${k}" x="${n.x}" y="${n.y + n.r + (k === "pi" ? 45 : 33)}"></text></g>`).join("")}
      </svg><p class="maptip" id="pie-tip"></p></div>`;
  }

  function spawn(key, rev = false, color) {
    const path = $p("pie-w-" + key), g = $p("pie-pkts");
    if (!path || !g || pkts.length > 140) return;
    const l = LINKS[key], c = color || NODES[rev ? l[1] : l[0]].c;
    const tail = document.createElementNS("http://www.w3.org/2000/svg", "circle"), head = document.createElementNS("http://www.w3.org/2000/svg", "circle");
    tail.setAttribute("r", "5"); tail.setAttribute("fill", c); tail.setAttribute("opacity", ".35"); tail.setAttribute("filter", "url(#pie-soft)");
    head.setAttribute("r", "2.8"); head.setAttribute("fill", "#fff"); head.setAttribute("filter", "url(#pie-glow)");
    head.classList.add("pkt"); tail.classList.add("pkt");
    g.append(tail, head);
    pkts.push({ path, len: path.getTotalLength(), t: 0, dur: 1.1 + Math.random() * .5, rev, head, tail });
  }

  // a chain of bursts, e.g. a fresh video: youtube → prismo → oracle → you
  function burst(keys, n = 10) {
    keys.forEach(([key, rev], i) => ms.burst.push({ key, rev, n, at: performance.now() + i * 650 }));
  }
  function flash(text) {
    const f = $p("pie-flash"); if (!f) return;
    f.textContent = text; f.classList.add("on");
    clearTimeout(flash.t); flash.t = setTimeout(() => f.classList.remove("on"), 2600);
  }

  function frame(t) {
    if (!$p("pie-map")) { raf = 0; pkts = []; return; }
    const dt = Math.min(.1, (t - (lastT || t)) / 1000); lastT = t;
    // steady traffic
    for (const [key, r] of Object.entries(ms.rates)) {
      const [fwd, back] = Array.isArray(r) ? r : [r, 0];
      if (!ms.down[key] && Math.random() < fwd * dt) spawn(key);
      if (!ms.down[key] && Math.random() < back * dt) spawn(key, true);
    }
    // scheduled bursts
    ms.burst = ms.burst.filter(b => {
      if (t < b.at) return true;
      if (Math.random() < .5) { spawn(b.key, b.rev); b.n--; }
      return b.n > 0;
    });
    // move packets
    pkts = pkts.filter(p => {
      p.t += dt / p.dur;
      if (p.t >= 1) { p.head.remove(); p.tail.remove(); return false; }
      const at = f => p.path.getPointAtLength((p.rev ? 1 - f : f) * p.len);
      const h = at(p.t), tl = at(Math.max(0, p.t - .06));
      p.head.setAttribute("cx", h.x.toFixed(1)); p.head.setAttribute("cy", h.y.toFixed(1));
      p.tail.setAttribute("cx", tl.x.toFixed(1)); p.tail.setAttribute("cy", tl.y.toFixed(1));
      return true;
    });
    // the mini LED copies the real one: solid, flickers with sd activity, blinks wildly during a light show
    const led = $p("pie-mled");
    if (led) {
      const on = ms.led ? (t % 260) < 130 : !(ms.io && Math.random() < .5);
      led.setAttribute("fill", on ? "#3dff9a" : "#1b4d2f"); led.setAttribute("opacity", ms.down.pi_oracle ? ".2" : "1");
    }
    radarFrame();
    watchFrame(dt);
    raf = requestAnimationFrame(frame);
  }

  function setVal(k, text, dead) {
    const v = $p("pie-v-" + k); if (v) v.textContent = text;
    const n = $p("pie-n-" + k); if (n) n.classList.toggle("dead", !!dead);
  }

  function tipText(k, d) {
    const p = d.pi, o = d.oracle || {}, sites = Object.entries(p?.prismo?.sites || {});
    return {
      you: `<b>📱 Du & alle anderen</b>: ${o.active ?? 0} gerade auf ytmp34, ${num(o.totals?.videos, 0)} Videos insgesamt.`,
      oracle: `<b>🦁 Oracle</b> wandelt die Videos um: ${num(o.cpu, 0)} % CPU, ${o.queue?.running ?? 0} in Arbeit, YouTube ${o.youtube_ok ? "zufrieden" : "blockiert"}.`,
      yt: `<b>▶️ YouTube</b> sieht nur deine Heim-Adresse, weil Oracle seine Anfragen durch PRISMO schickt. Gerade ↓ ${rate(p?.net?.rx || 0)}.`,
      pi: p ? `<b>🍓 PRISMO</b>: ${num(p.cpu_temp)} °C, ${num(p.cpu, 0)} % CPU, läuft seit ${dur(p.uptime)}. Das kleine Licht oben ist sein echtes grünes Licht.` : `<b>🍓 PRISMO</b> ist offline.`,
      untis: `<b>📚 WebUntis</b>: PRISMO schaut alle 5 Minuten für ${esc(p?.untis?.class || "?")} nach, zuletzt ${isoAgo(p?.untis?.checked)}.`,
      ntfy: `<b>🔔 ntfy</b> bringt PRISMOs Nachrichten auf dein Handy. Zuletzt: ${esc((p?.untis?.pushes || [])[0]?.title || "noch nichts")}.`,
      sites: `<b>🌐 Wachhund</b>: PRISMO pingt ${sites.length} Seiten, alle paar Sekunden eine. ${sites.filter(([, x]) => !x.ok).map(([n]) => "🚨 " + esc(n)).join(" · ") || "Alle online ✅"}`,
      sky: `<b>✈️ Himmel</b>: ${p?.planes?.list?.length ?? 0} Flugzeuge im Umkreis von ${num(p?.planes?.radius, 0)} km, heute schon ${p?.planes?.today ?? 0} gesehen. Echte Positionen von Hobby-Funkempfängern (adsb.lol).`,
    }[k];
  }

  function updateMap(d) {
    const p = d.pi, o = d.oracle || {}, now = Date.now() / 1000;
    ms.d = d;
    const rx = p?.net?.rx || 0, tx = p?.net?.tx || 0, conv = (o.queue?.running || 0) + (o.queue?.waiting || 0);
    const sites = Object.values(p?.prismo?.sites || {}), down = sites.filter(s => s.down_since).length;
    // only real work makes dots. steady streams only while youtube data really flows through PRISMO's proxy
    // (a conversion on oracle, or oracle asking youtube about a link); everything else is one dot per real event below.
    // [forward, back]: forward = the link's first node → second (e.g. youtube → PRISMO), back = the other way
    const yt = conv > 0 || ((p?.proxy_clients || 0) > 0 && rx > 30e3), flow = yt ? Math.min(9, 1.5 + rx / 60e3) : 0;
    ms.rates = {
      yt_pi: [flow, yt ? .6 : 0],              // video data comes in, small requests go out
      pi_oracle: [flow, yt ? .6 : 0],          // PRISMO hands it to oracle, oracle asks for more
      oracle_you: [conv ? 1.2 : 0, 0],         // oracle sends the finished file
    };
    const off = !p;
    ms.down = { yt_pi: off, pi_oracle: off, pi_untis: off, pi_ntfy: off, pi_sites: off || down > 0, sky_pi: off || !p?.planes?.at };
    Object.keys(LINKS).forEach(k => $p("pie-w-" + k)?.classList.toggle("down", !!ms.down[k]));
    ms.led = !!p?.led?.what;
    ms.io = (p?.io?.read || 0) + (p?.io?.write || 0) > 0;
    // events → bursts
    const videos = o.totals?.videos;
    if (ms.lastVideos != null && videos > ms.lastVideos) {
      burst([["yt_pi"], ["pi_oracle"], ["oracle_you"]], 6);
      flash("🎵 Gerade wurde ein Video konvertiert!");
    }
    ms.lastVideos = videos;
    const push = (p?.untis?.pushes || [])[0]?.at;
    if (ms.lastPush != null && push && push !== ms.lastPush) { burst([["pi_ntfy"], ["ntfy_you"]], 10); flash("🔔 PRISMO hat dir was geschickt"); }
    if (push) ms.lastPush = push;
    // PRISMO asks adsb.lol for the planes (out), the answer comes back (in)
    const pat = p?.planes?.at;
    if (ms.lastPlanes != null && pat && pat !== ms.lastPlanes) { spawn("sky_pi", true); setTimeout(() => spawn("sky_pi"), 700); }
    if (pat) ms.lastPlanes = pat;
    // the untis watcher asks webuntis every 5 minutes: one dot out, one back
    const uc = p?.untis?.checked;
    if (ms.lastUntis != null && uc && uc !== ms.lastUntis) { spawn("pi_untis"); setTimeout(() => spawn("pi_untis", true), 900); }
    if (uc) ms.lastUntis = uc;
    // PRISMO's ring: length = cpu, colour = temperature (cool cyan → hot red)
    const ring = $p("pie-ring");
    if (ring && p) {
      const C = 2 * Math.PI * 48, hot = Math.max(0, Math.min(1, ((p.cpu_temp || 40) - 40) / 30));
      ring.setAttribute("stroke-dashoffset", (C * (1 - Math.max(.04, (p.cpu || 0) / 100))).toFixed(1));
      ring.setAttribute("stroke", `hsl(${(180 - 180 * hot).toFixed(0)} 95% 60%)`);
    }
    setVal("you", `${o.active ?? 0} online`);
    setVal("oracle", conv ? `${conv} in Arbeit` : `${num(o.cpu, 0)} % CPU`);
    setVal("yt", yt ? "↓ " + rate(rx) : "ruhig");
    setVal("pi", p ? `${num(p.cpu_temp, 0)} °C · ${num(p.cpu, 0)} %` : "offline", !p);
    setVal("untis", p?.untis?.class ? `${p.untis.class} · ${isoAgo(p.untis.checked)}` : "");
    setVal("ntfy", (p?.untis?.pushes || [])[0] ? isoAgo(p.untis.pushes[0].at) : "");
    setVal("sites", sites.length ? (down ? `${down} offline!` : `${sites.length} online`) : "", down > 0);
    setVal("sky", p?.planes?.at ? `${p.planes.list.length} Flugzeuge` : "", !p?.planes?.at);
    const tip = $p("pie-tip"); if (tip) tip.innerHTML = tipText(ms.tip, d) || "";
    if (!raf) { lastT = 0; raf = requestAnimationFrame(frame); }
  }

  function bindMap() {
    document.querySelectorAll("#pie .map .node").forEach(n => n.onclick = () => {
      ms.tip = n.dataset.k;
      const k = n.dataset.k;
      if (ms.d) $p("pie-tip").innerHTML = tipText(k, ms.d);
    });
  }

  // --- the plane radar: real planes around PRISMO. the page only ever gets km east/north of home ---
  const R = { r: 182, radius: 50, data: null, recv: 0, lag: 0, sel: null, els: {}, trails: {}, lastOver: null, lastAt: 0 };
  const SVGNS = "http://www.w3.org/2000/svg";
  const el = (tag, attrs = {}) => { const e = document.createElementNS(SVGNS, tag); for (const k in attrs) e.setAttribute(k, attrs[k]); return e; };
  const altColor = a => `hsl(${(28 + 165 * Math.min(1, (a || 0) / 12000)).toFixed(0)} 95% 62%)`;
  const compass = deg => ["N", "NO", "O", "SO", "S", "SW", "W", "NW"][Math.round(((deg % 360) + 360) % 360 / 45) % 8];
  const PLANE = "M0,-9 L1.4,-3 L8,1.2 L8,3 L1.4,1.4 L1,6 L3.4,8 L3.4,9.2 L0,8.4 L-3.4,9.2 L-3.4,8 L-1,6 L-1.4,1.4 L-8,3 L-8,1.2 L-1.4,-3 Z";

  function radarSvg() {
    let sweep = "";
    for (let i = 0; i < 8; i++) {  // a fading wedge behind the sweep line
      const a0 = (-i * 5) * Math.PI / 180, a1 = (-(i + 1) * 5) * Math.PI / 180;
      sweep += `<path d="M200,200 L${(200 + 190 * Math.sin(a0)).toFixed(1)},${(200 - 190 * Math.cos(a0)).toFixed(1)} A190,190 0 0,0 ${(200 + 190 * Math.sin(a1)).toFixed(1)},${(200 - 190 * Math.cos(a1)).toFixed(1)} Z" fill="#38d6c4" opacity="${(.22 - i * .026).toFixed(3)}"/>`;
    }
    return `<div class="radarbox"><div class="flash" id="pie-rflash"></div>
      <svg class="radar" id="pie-radar" viewBox="0 0 400 400" role="img" aria-label="Flugzeug-Radar um PRISMO">
        <g id="pie-rgrid"></g>
        <g class="sweep">${sweep}<line x1="200" y1="200" x2="200" y2="10" stroke="#7ff0e2" stroke-width="1.5" opacity=".8"/></g>
        <g id="pie-rtr"></g><g id="pie-rpl"></g>
        <circle cx="200" cy="200" r="5" fill="#ff74c8"/><circle cx="200" cy="200" r="11" fill="none" stroke="#ff74c8" stroke-width="1" opacity=".6"/>
      </svg><div class="rinfo" id="pie-rinfo">Radar startet…</div><div class="plist" id="pie-plist"></div></div>`;
  }

  function radarGrid(radius) {
    const g = $p("pie-rgrid"); if (!g) return;
    const rings = radius > 40 ? [10, 25, radius] : [5, 10, radius];
    g.innerHTML = rings.map(k => { const r = R.r * k / radius;
      return `<circle class="rg" cx="200" cy="200" r="${r.toFixed(1)}"/><text class="rl" x="${(200 + r * .72).toFixed(1)}" y="${(200 - r * .7).toFixed(1)}">${k} km</text>`; }).join("")
      + `<line class="rx" x1="200" y1="${200 - R.r}" x2="200" y2="${200 + R.r}"/><line class="rx" x1="${200 - R.r}" y1="200" x2="${200 + R.r}" y2="200"/>`
      + [["N", 200, 200 - R.r - 6], ["S", 200, 200 + R.r + 14], ["O", 200 + R.r + 8, 204], ["W", 200 - R.r - 8, 204]].map(([t, x, y]) => `<text class="cd" x="${x}" y="${y}">${t}</text>`).join("")
      + `<text class="rl" x="200" y="222" text-anchor="middle">🏠 PRISMO</text>`;
  }

  // where a plane is right now: its last report + speed × time since then
  function planeNow(p) {
    const t = Math.min(40, (performance.now() - R.recv) / 1000 + R.lag + (p.age || 0)), v = (p.speed || 0) / 3600, a = (p.track || 0) * Math.PI / 180;
    return { x: p.x + v * Math.sin(a) * t, y: p.y + v * Math.cos(a) * t };
  }
  const planeName = p => [p.airline, p.iata || p.cs].filter(Boolean).join(" ") || p.cs || p.reg || p.id;

  function planeInfo(p) {
    if (!p) return R.data?.error ? `Radar hat gerade keine Daten (${esc(R.data.error)})` : R.data?.list?.length === 0 ? "Gerade ist kein Flugzeug in der Nähe. Ruhiger Himmel 🌌" : "Tipp auf ein Flugzeug ✈️";
    const pos = planeNow(p), dist = Math.hypot(pos.x, pos.y), dir = compass(Math.atan2(pos.x, pos.y) * 180 / Math.PI);
    const climb = p.ground ? "am Boden" : p.climb > 1.5 ? "↗ steigt" : p.climb < -1.5 ? "↘ sinkt" : "→ Reiseflug";
    const route = p.from && p.to ? `${esc(p.from)} → ${esc(p.to)}` : "Route unbekannt";
    return `<b>✈️ ${esc(planeName(p))}</b> · ${route}<br><small>${esc(p.type || "?")}${p.reg ? " · " + esc(p.reg) : ""} · <b>${num(p.alt, 0)} m</b> · ${num(p.speed, 0)} km/h · ${climb} · ${num(dist)} km ${dir}</small>`;
  }

  function radarData(d) {
    const pl = d.pi?.planes; if (!pl || !$p("pie-radar")) return;
    if (pl.radius !== R.radius || !$p("pie-rgrid").childNodes.length) { R.radius = pl.radius || 50; radarGrid(R.radius); }
    if (pl.at !== R.lastAt) {
      R.lastAt = pl.at; R.recv = performance.now(); R.lag = Math.max(0, (d.pi.time || pl.at) - pl.at);
      R.data = pl;
      const seen = new Set();
      for (const p of pl.list) {
        seen.add(p.id);
        const tr = R.trails[p.id] || (R.trails[p.id] = []);
        tr.push([p.x, p.y]); if (tr.length > 24) tr.shift();
        if (!R.els[p.id]) {
          const g = el("g", { class: "pl" }), body = el("g"), hit = el("circle", { r: 14, fill: "#fff", opacity: 0 }), ring = el("circle", { r: 13, fill: "none", stroke: "#fff", "stroke-width": 1.5, class: "selr" });
          const glyph = el("path", { d: PLANE, class: "gl" }), t1 = el("text", { x: 11, y: -3 }), t2 = el("text", { x: 11, y: 9, class: "a" });
          const trail = el("polyline", { class: "tr" });
          body.append(glyph); g.append(hit, ring, body, t1, t2);
          g.onclick = () => { R.sel = p.id; radarList(); $p("pie-rinfo").innerHTML = planeInfo(R.data.list.find(x => x.id === R.sel)); };
          $p("pie-rpl").append(g); $p("pie-rtr").append(trail);
          R.els[p.id] = { g, body, glyph, t1, t2, trail };
        }
        const e = R.els[p.id], c = altColor(p.alt);
        e.glyph.setAttribute("fill", c); e.trail.setAttribute("stroke", c);
        e.t1.textContent = p.iata || p.cs || p.reg || ""; e.t2.textContent = p.ground ? "Boden" : (p.alt / 1000).toLocaleString("de-AT", { maximumFractionDigits: 1 }) + " km";
        e.p = p;
      }
      for (const id of Object.keys(R.els)) if (!seen.has(id)) { R.els[id].g.remove(); R.els[id].trail.remove(); delete R.els[id]; delete R.trails[id]; }
      if (!R.sel || !seen.has(R.sel)) R.sel = pl.list[0]?.id || null;
      radarList();
      if (pl.overhead && pl.overhead.at !== R.lastOver) {
        if (R.lastOver !== null) { const f = $p("pie-rflash"); if (f) { f.textContent = `✈️ ${planeName(pl.overhead)} fliegt gerade über dich!`; f.classList.add("on"); setTimeout(() => f.classList.remove("on"), 6000); } }
        R.lastOver = pl.overhead.at;
      } else if (R.lastOver === null) R.lastOver = pl.overhead?.at || 0;
    }
    $p("pie-rinfo").innerHTML = planeInfo(R.data?.list.find(x => x.id === R.sel));
  }

  function radarList() {
    const box = $p("pie-plist"); if (!box || !R.data) return;
    box.innerHTML = R.data.list.slice(0, 8).map(p => `<button data-id="${esc(p.id)}" class="${p.id === R.sel ? "sel" : ""}">✈️ <b>${esc(p.iata || p.cs || p.reg || "?")}</b> ${p.from_code && p.to_code ? esc(p.from_code) + "→" + esc(p.to_code) : ""} · ${num(p.alt / 1000)} km · ${num(p.dist, 0)} km weg</button>`).join("")
      + `<div class="dim" style="align-self:center;font-size:12.5px;color:#8fb7ba">${R.data.list.length} in ${num(R.data.radius, 0)} km · heute ${R.data.today} gesehen</div>`;
    box.querySelectorAll("button").forEach(b => b.onclick = () => { R.sel = b.dataset.id; radarList(); $p("pie-rinfo").innerHTML = planeInfo(R.data.list.find(x => x.id === R.sel)); });
  }

  function radarFrame() {
    if (!R.data || !$p("pie-radar")) return;
    const k = R.r / R.radius;
    for (const [id, e] of Object.entries(R.els)) {
      const p = e.p, pos = planeNow(p), x = 200 + pos.x * k, y = 200 - pos.y * k;
      const out = Math.hypot(x - 200, y - 200) > R.r + 4;
      e.g.style.display = out ? "none" : "";
      e.g.setAttribute("transform", `translate(${x.toFixed(1)},${y.toFixed(1)})`);
      e.body.setAttribute("transform", `rotate(${p.track || 0})`);
      e.g.classList.toggle("sel", id === R.sel);
      const tr = R.trails[id] || [];
      e.trail.setAttribute("points", tr.map(([tx, ty]) => `${(200 + tx * k).toFixed(1)},${(200 - ty * k).toFixed(1)}`).concat(out ? [] : [`${x.toFixed(1)},${y.toFixed(1)}`]).join(" "));
    }
  }

  // --- watchdog live: every ping PRISMO sends to one of the sites flies out and back ---
  const W = { key: "", pos: {}, last: {}, pk: [] };
  const msText = s => s == null ? "" : s < 0 ? "Fehler" : s < 1 ? Math.round(s * 1000) + " ms" : num(s, 1) + " s";

  function watchBuild(names) {
    const box = $p("pie-watch"); if (!box) return;
    W.key = names.join("|"); W.pos = {}; W.pk = [];
    const n = names.length, cx = 300, cy = 160, rx = 172, ry = 112;
    let svg = "";
    names.forEach((name, i) => {
      const a = -Math.PI / 2 + i * 2 * Math.PI / n, x = cx + rx * Math.cos(a), y = cy + ry * Math.sin(a);
      W.pos[name] = { x, y };
      const side = Math.cos(a), anchor = side > .3 ? "start" : side < -.3 ? "end" : "middle", lx = x + side * 14, ly = y + (Math.abs(side) <= .3 ? (Math.sin(a) > 0 ? 24 : -16) : 0);
      const max = innerWidth < 520 ? 11 : 16, short = name.length > max ? name.slice(0, max - 1) + "…" : name;
      svg += `<line class="sp" x1="${cx}" y1="${cy}" x2="${x.toFixed(1)}" y2="${y.toFixed(1)}"/>
        <circle class="sn" id="pie-sn-${i}" cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="9"/>
        <text x="${lx.toFixed(1)}" y="${(ly + 1).toFixed(1)}" text-anchor="${anchor}">${esc(short)}</text>
        <text class="ms" id="pie-sm-${i}" x="${lx.toFixed(1)}" y="${(ly + 15).toFixed(1)}" text-anchor="${anchor}"></text>`;
    });
    box.innerHTML = `<svg class="watch" viewBox="0 0 600 320" role="img" aria-label="Wachhund live">${svg}<g id="pie-wpk"></g>
      <circle cx="${cx}" cy="${cy}" r="30" fill="rgba(255,255,255,.06)" stroke="#3dff9a" stroke-width="2" filter="url(#pie-glow)"/>
      <text x="${cx}" y="${cy + 10}" text-anchor="middle" style="font-size:28px">🐕</text></svg>`;
  }

  function watchPacket(x0, y0, x1, y1, dur, color, then) {
    const g = $p("pie-wpk"); if (!g) return;
    const glow = el("circle", { r: 6, fill: color, opacity: .4 }), dot = el("circle", { r: 3, fill: "#fff" });
    g.append(glow, dot);
    W.pk.push({ x0, y0, x1, y1, dur, t: 0, glow, dot, then });
  }

  function watchFrame(dt) {
    W.pk = W.pk.filter(p => {
      p.t += dt / p.dur;
      const f = Math.min(1, p.t), e = f < .5 ? 2 * f * f : 1 - (-2 * f + 2) ** 2 / 2, x = p.x0 + (p.x1 - p.x0) * e, y = p.y0 + (p.y1 - p.y0) * e;
      p.dot.setAttribute("cx", x.toFixed(1)); p.dot.setAttribute("cy", y.toFixed(1)); p.glow.setAttribute("cx", x.toFixed(1)); p.glow.setAttribute("cy", y.toFixed(1));
      if (p.t >= 1) { p.dot.remove(); p.glow.remove(); p.then?.(); return false; }
      return true;
    });
  }

  function wspark(h) {
    if (!h?.length) return `<svg></svg>`;
    const ok = h.filter(v => v >= 0), max = Math.max(.3, ...ok), step = 90 / 29, off = 90 - (h.length - 1) * step;
    const pts = h.map((v, i) => `${(off + i * step).toFixed(1)},${(17 - 15 * Math.min(1, Math.max(0, v) / max)).toFixed(1)}`).join(" ");
    const bad = h.map((v, i) => v < 0 ? `<circle cx="${(off + i * step).toFixed(1)}" cy="9" r="2.4" fill="#ff4d7a"/>` : "").join("");
    return `<svg viewBox="0 0 90 18" preserveAspectRatio="none"><polyline points="${pts}" fill="none" stroke="#38d6c4" stroke-width="1.6" vector-effect="non-scaling-stroke"/>${bad}</svg>`;
  }

  function watchData(d, list) {
    const sites = d.pi?.prismo?.sites || {}, names = Object.keys(sites);
    if (!$p("pie-watch")) return;
    if (!names.length) { $p("pie-watch").innerHTML = `<p class="dim" style="padding:16px">${d.pi ? "Wachhund startet gleich" : "PRISMO ist offline"}</p>`; W.key = ""; return; }
    if (names.join("|") !== W.key) watchBuild(names);
    const cx = 300, cy = 160;
    names.forEach((name, i) => {
      const s = sites[name], node = $p("pie-sn-" + i), pos = W.pos[name];
      if (!node) return;
      node.classList.toggle("ok", !!s.ok); node.classList.toggle("bad", s.ok === false);
      const fresh = W.last[name] != null && s.checked > W.last[name];
      if (W.last[name] == null) $p("pie-sm-" + i).textContent = msText(s.ok ? s.took : -1);
      if (fresh) {
        const color = s.ok ? "#3dff9a" : "#ff4d7a";
        watchPacket(cx, cy, pos.x, pos.y, .5, "#9f8cff", () => {
          node.classList.add("ping"); setTimeout(() => node.classList.remove("ping"), 250);
          $p("pie-sm-" + i).textContent = msText(s.ok ? s.took : -1);
          watchPacket(pos.x, pos.y, cx, cy, .35 + Math.min(2.5, s.took || 0), color);
        });
        spawn("pi_sites"); setTimeout(() => spawn("pi_sites", true, s.ok ? "#3dff9a" : "#ff4d7a"), 400 + Math.min(2500, (s.took || 0) * 1000));
      }
      W.last[name] = s.checked;
    });
    if (list) {
      $p("pie-wlist").innerHTML = names.map(name => { const s = sites[name], up = s.n ? 100 * s.n_ok / s.n : null;
        return `<div class="row"><span>${s.ok ? "✅" : s.down_since ? "🚨" : "⚠️"} ${esc(name)}</span><span>${wspark(s.hist)}<small>${msText(s.ok ? s.took : -1)}</small>${up == null ? "" : `<small class="${up > 99 ? "ok" : up > 90 ? "meh" : "bad"}">${num(up, up > 99.9 ? 0 : 1)} %</small>`}</span></div>`; }).join("");
    }
  }

  // --- live meters ---
  function meters(d) {
    const p = d.pi, o = d.oracle || {};
    const used = m => m.total - m.available;
    const m = (label, val, text, pct, extra = "", hot = false) => `<div class="m${hot ? " hot" : ""}"><small>${label}</small><b>${val}</b>${pct == null ? "" : bar(pct)}<small>${text}</small>${extra}</div>`;
    let out = "";
    if (p) {
      const t = p.cpu_temp, ram = 100 * used(p.memory) / p.memory.total, sd = 100 * (1 - p.disk.free / p.disk.total);
      out += m("🍓 CPU", num(p.cpu, 0) + " %", `${num(p.freq_mhz, 0)} MHz`, p.cpu, spark(hist.cpu, 100), p.cpu > 90)
        + m("🍓 Temperatur", num(t) + " °C", t > 65 ? "heiß 🔥" : t > 55 ? "warm" : "kühl 😎", t / 85 * 100, spark(hist.temp, 85, "#ff74c8"), t > 70)
        + m("🍓 RAM", num(ram, 0) + " %", `${mb(used(p.memory))} / ${mb(p.memory.total)}`, ram, "", ram > 92)
        + m("🍓 Internet", "↓ " + rate(p.net?.rx || 0), "↑ " + rate(p.net?.tx || 0), null, spark(hist.net, 0, "#38d6c4"))
        + m("🍓 SD-Karte", num(sd, 0) + " %", `${gb(p.disk.total - p.disk.free)} / ${gb(p.disk.total)}`, sd);
    }
    const oram = 100 * used(o.memory || { total: 1, available: 1 }) / (o.memory?.total || 1);
    out += m("🦁 CPU", num(o.cpu, 0) + " %", `${o.cpus ?? "?"} Kerne`, o.cpu, spark(hist.ocpu, 100))
      + m("🦁 RAM", num(oram, 0) + " %", `${gb(used(o.memory || { total: 0, available: 0 }))} / ${gb(o.memory?.total || 0)}`, oram);
    return `<div class="meters">${out}</div>`;
  }

  // --- 24 h chart ---
  function chart() {
    const h = history.filter(x => x[2] != null);
    if (h.length < 3) return `<p class="dim">PRISMO sammelt gerade Daten: alle 5 Minuten ein Punkt. In einer Stunde sieht man hier schon was 📈</p>`;
    const W = 600, H = 170, t0 = h[0][0], t1 = h[h.length - 1][0], span = Math.max(1, t1 - t0);
    const X = t => (8 + (W - 16) * (t - t0) / span).toFixed(1);
    const temps = h.map(x => x[2]), tmin = Math.min(...temps) - 2, tmax = Math.max(...temps) + 2;
    const Yt = v => (H - 22 - (H - 40) * (v - tmin) / (tmax - tmin)).toFixed(1);
    const Yc = v => (H - 22 - (H - 40) * Math.min(100, v) / 100).toFixed(1);
    const nmax = Math.max(...h.map(x => (x[3] || 0) + (x[4] || 0)), 1);
    const bw = Math.max(1, (W - 16) / h.length - 1);
    const bars = h.map(x => { const v = ((x[3] || 0) + (x[4] || 0)) / nmax * 40; return `<rect x="${X(x[0])}" y="${(H - 22 - v).toFixed(1)}" width="${bw.toFixed(1)}" height="${v.toFixed(1)}" fill="#38d6c4" opacity=".35"/>`; }).join("");
    const line = (f, Y) => h.map(x => `${X(x[0])},${Y(f(x))}`).join(" ");
    const marks = []; for (let t = Math.ceil(t0 / 10800) * 10800; t <= t1; t += 10800) marks.push(t);
    const labels = marks.map(t => `<text x="${X(t)}" y="${H - 6}" font-size="11" fill="currentColor" opacity=".55" text-anchor="middle">${new Date(t * 1000).toLocaleTimeString("de-AT", { hour: "2-digit", minute: "2-digit" })}</text>`).join("");
    return `<svg class="chart" viewBox="0 0 ${W} ${H}" preserveAspectRatio="none">${bars}
      <polyline points="${line(x => x[1], Yc)}" fill="none" stroke="#8d7bff" stroke-width="2" vector-effect="non-scaling-stroke"/>
      <polyline points="${line(x => x[2], Yt)}" fill="none" stroke="#ff74c8" stroke-width="2.5" vector-effect="non-scaling-stroke"/>${labels}</svg>
      <div class="legend"><span><i style="background:#ff74c8"></i>Temperatur ${num(Math.min(...temps), 0)}–${num(Math.max(...temps), 0)} °C</span><span><i style="background:#8d7bff"></i>CPU</span><span><i style="background:#38d6c4;opacity:.5"></i>Internet</span></div>`;
  }

  // --- the detail cards ---
  function services(svc) {
    const names = { "ytmp34": "Backup-Converter", "ytmp34-proxy": "Proxy", "untis-watch.timer": "Untis", "tailscaled": "Tailscale",
      "ytmp34-update.timer": "Update", "prismo-watchdog": "Wachhund", "prismo-briefing.timer": "Briefing", "prismo-scan": "Scanner" };
    return Object.entries(svc || {}).map(([k, v]) => `<span class="pill ${v === "active" ? "ok" : "bad"}">${v === "active" ? "●" : "○"} ${esc(names[k] || k)}</span>`).join("");
  }

  function cards(d) {
    const o = d.oracle || {}, p = d.pi, u = p?.untis || {}, th = p?.throttle, lastConv = (o.recent || [])[0];
    const sites = Object.entries(p?.prismo?.sites || {});
    return `
    <section class="card"><h2>🍓 Hardware</h2>
      ${p ? row("läuft seit", dur(p.uptime)) + row("Temperatur", `${num(p.cpu_temp)} °C`) + (p.volts ? row("Spannung", num(p.volts, 3) + " V") : "")
        + row("Strom & Hitze", th ? (th.now.length ? `<span class="bad">${th.now.map(x => THROTTLE[x] || x).join(", ")}</span>` : th.since_boot.length ? `<span class="meh">seit Start: ${th.since_boot.map(x => THROTTLE[x] || x).join(", ")}</span>` : `<span class="ok">alles gut</span>`) : "?")
        + row("WLAN", p.wifi ? `${p.wifi.dbm} dBm` : "?") + row("Prozesse", p.processes ?? "?") + row("System", esc(p.os || "?"))
        + `<div>${services(p.services)}</div>`
        : `<p class="bad">PRISMO ist offline.</p><small>${esc(d.pi_error || "")}</small>`}
    </section>
    <section class="card"><h2>🦁 Oracle & Converter</h2>
      ${row("YouTube", yes(o.youtube_ok, "zufrieden", "blockiert"))}${row("über PRISMO", o.proxy ? yes(o.proxy_ok, "ja", "Proxy weg") : "nein")}
      ${row("gerade", `${o.queue?.running ?? 0} konvertieren · ${o.queue?.waiting ?? 0} warten`)}${row("insgesamt", `${num(o.totals?.videos, 0)} Videos · ${gb(o.totals?.bytes || 0)}`)}
      ${row("zuletzt", lastConv ? `${lastConv.fmt === "mp3" ? "🎵" : "🎬"} ${esc(lastConv.title)} <small>${ago(lastConv.at)}</small>` : "—")}
      ${row("yt-dlp", esc(o.yt_dlp))}${row("Server läuft seit", dur(o.server_uptime || 0))}
      ${(o.errors || []).length ? `<small>letzte Fehler:</small><ul>${o.errors.slice(0, 3).map(e => `<li><small>${ago(e.at)}</small> ${esc(e.text)}</li>`).join("")}</ul>` : ""}
    </section>
    <section class="card"><h2>📚 WebUntis</h2>
      ${p ? row("Klasse", esc(u.class || "?")) + row("geschaut", isoAgo(u.checked)) + row("nächste Stunde", u.next ? `${esc(when(u.next.start))} · ${esc(u.next.subject)}` : "—")
        + (u.irregular?.length ? `<ul>${u.irregular.slice(0, 6).map(l => `<li>${ICON[l.status] || "•"} ${esc(when(l.start))} ${esc(l.subject)}</li>`).join("")}</ul>` : `<p class="dim">nichts Besonderes</p>`)
        : `<p class="dim">wohnt auf PRISMO</p>`}
    </section>
    <section class="card"><h2>☀️ Morgen-Briefing <small>Mo–Fr 6:08</small></h2>
      ${p?.prismo?.briefing ? `<small>${isoAgo(p.prismo.briefing.at)}</small><p style="white-space:pre-line;margin:6px 0 0">${esc(p.prismo.briefing.text)}</p>` : `<p class="dim">Das erste kommt um 6:08 🌅</p>`}
    </section>
    <section class="card"><h2>🔔 Letzte Pushes</h2>
      ${(u.pushes || []).length ? `<ul>${u.pushes.slice(0, 5).map(x => `<li><b>${esc(x.title)}</b> <small>${isoAgo(x.at)}</small><br><small style="white-space:pre-line">${esc(x.message)}</small></li>`).join("")}</ul>` : `<p class="dim">noch keine</p>`}
    </section>`;
  }

  function barcode() {
    let s = "", seed = 1907;
    for (let i = 0; i < 40; i++) { seed = seed * 16807 % 2147483647; s += `<i style="flex:${1 + seed % 3}"></i><span style="flex:${1 + (seed >> 3) % 2}"></span>`; }
    return `<div class="barcode">${s}</div>`;
  }

  // --- page ---
  function record(d) {
    if (d.history) history = d.history;
    const p = d.pi, o = d.oracle || {};
    pushH(hist.ocpu, o.cpu);
    if (p) { pushH(hist.cpu, p.cpu); pushH(hist.temp, p.cpu_temp); pushH(hist.net, (p.net?.rx || 0) + (p.net?.tx || 0)); }
  }

  function show(d) {
    record(d);
    root().innerHTML = `<div class="wrap">
      <header class="head"><div class="logo">prismo<small>fabios kleiner helfer</small></div>
        <div><span class="live"><i></i>live</span> <button class="ghost" type="button" data-x style="margin-left:8px">✕</button></div></header>
      <div class="alarmbar" id="pie-alarm" role="alert"><div>🚨 ALARM: PRISMO IST OFFLINE 🚨</div><small id="pie-alarmtxt"></small></div>
      <div class="okbar" id="pie-okbar" role="status">✅ PRISMO ist wieder da. Alles stabil 💚</div>
      <div class="grid">
        <section class="card wide"><h2>🗺️ PRISMO-Netz <small>live · tipp auf einen Punkt</small></h2>${mapSvg()}</section>
        <section class="card wide"><h2>✈️ Über PRISMO <small>echte Flugzeuge, live · tipp drauf</small></h2>${radarSvg()}</section>
        <section class="card wide"><h2>🐕 Wachhund live <small>jeder Punkt ist ein echter Ping</small></h2><div class="watchbox" id="pie-watch"></div><div class="wl" id="pie-wlist"></div></section>
        <section class="card wide"><h2>⚡ Live</h2><div id="pie-meters">${meters(d)}</div></section>
        ${ledCard(d)}
        <section class="card wide"><h2>📈 Die letzten 24 Stunden</h2><div id="pie-chart">${chart()}</div></section>
      </div>
      <div class="grid" id="pie-cards">${cards(d)}</div>
      <div class="foot"><b>©fabio inc.</b><br>Bitte mit Vorsicht umgehen · NICHT SCHÜTTELN du gundi<br>PRISMO ist nicht verantwortlich für Verletzungen oder Tod.${barcode()}</div>
    </div>`;
    const r = $p("pie");
    r.querySelector("[data-x]").onclick = close;
    r.querySelectorAll("[data-a]").forEach(b => b.onclick = () => act(b.dataset.a));
    $p("pie-morse").onsubmit = e => { e.preventDefault(); const i = e.target.querySelector("input"); if (i.value.trim()) { act("morse", i.value.trim()); i.value = ""; } };
    R.els = {}; R.trails = {}; R.lastAt = 0; W.key = ""; W.last = {};
    A.on = false; A.miss = 0; A.since = null;
    alarm(d);
    updateMap(d);
    bindMap();
    radarData(d);
    watchData(d, true);
    clearInterval(timer);
    tick = 0;
    timer = setInterval(() => { tick++; refresh(tick % 5 === 0, tick % 60 === 0); }, 1000);
  }

  async function refresh(all, full) {
    if (busy) return;
    busy = true;
    try {
      const res = await api(full ? { full: true } : {});
      if (!res.ok && res.status === 403) { clearInterval(timer); return gate("Der Code geht nicht mehr"); }
      if (!res.ok || !$p("pie-meters")) return;
      const d = res.body;
      record(d);
      alarm(d);
      updateMap(d);
      radarData(d);
      watchData(d, all);
      $p("pie-meters").innerHTML = meters(d);
      $p("pie-led")?.classList.toggle("on", !!d.pi?.led?.what);
      if (all) $p("pie-cards").innerHTML = cards(d);
      if (full) $p("pie-chart").innerHTML = chart();
    } catch {} finally { busy = false; }
  }

  window.openPie = () => {
    let code = "";
    try { code = sessionStorage.getItem(KEY) || ""; } catch {}
    code ? login(code) : gate();
  };
  openPie();
})();

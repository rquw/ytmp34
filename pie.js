// PRISMO — fabios kleiner helfer. the owner's page ("pie mode"): the pet, a live map of everything, stats.
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

  /* the pet */
  #pie .pet { display: grid; grid-template-columns: auto 1fr; gap: 18px; align-items: center; }
  #pie .face { width: 120px; height: 120px; border-radius: 34px; display: grid; place-items: center; font-size: 68px; position: relative;
    background: linear-gradient(145deg, rgba(141,123,255,.18), rgba(255,116,200,.18) 60%, rgba(56,214,196,.2)); }
  #pie .face span { display: inline-block; animation: pie-bob 3s ease-in-out infinite; }
  #pie .face.sleep span { animation-duration: 6s; }
  @keyframes pie-bob { 50% { transform: translateY(-6px) rotate(-3deg); } }
  #pie .led { position: absolute; right: 10px; top: 10px; width: 14px; height: 14px; border-radius: 50%; background: #2a6b3a; box-shadow: inset 0 0 0 2px rgba(0,0,0,.15); }
  #pie .led.on { background: #3dff7a; box-shadow: 0 0 12px #3dff7a, 0 0 24px #3dff7a; animation: pie-led .25s steps(1) infinite; }
  @keyframes pie-led { 50% { background: #2a6b3a; box-shadow: none; } }
  #pie .name { font: 800 24px/1 "Baloo 2", system-ui, sans-serif; }
  #pie .bubble { position: relative; margin: 10px 0; padding: 10px 14px; border-radius: 16px; background: var(--track); font-weight: 600; }
  #pie .bubble::before { content: ""; position: absolute; left: -7px; top: 14px; border: 7px solid transparent; border-right-color: var(--track); border-left: 0; }
  #pie .stats { display: grid; grid-template-columns: auto 1fr; gap: 6px 10px; align-items: center; font-size: 13px; color: var(--dim); }
  #pie .actions { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 14px; }
  #pie .morse { display: flex; gap: 8px; margin-top: 10px; }
  #pie .morse input { flex: 1 1 auto; min-width: 0; width: 100%; font: 600 16px system-ui, sans-serif; padding: 9px 14px; border-radius: 999px; border: 2px solid var(--line);
    background: transparent; color: var(--ink); text-transform: uppercase; }
  #pie .toast { min-height: 1.4em; margin-top: 8px; font-weight: 600; }
  @media (max-width: 520px) { #pie .pet { grid-template-columns: 1fr; justify-items: center; text-align: center; } #pie .bubble::before { display: none; }
    #pie .stats { width: 100%; text-align: left; } #pie .actions { justify-content: center; } #pie .logo { font-size: 32px; } #pie .logo small { display: none; } }

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

  // --- the pet's speech bubble: reacts to what is really going on ---
  function say(d) {
    const p = d.pi, pet = p?.pet, u = p?.untis || {}, o = d.oracle || {};
    if (!pet) return "…";
    const pick = arr => arr[Math.floor(Date.now() / 15000) % arr.length];  // changes every 15 s
    if (pet.led?.what) return `✨ Ich ${pet.led.what === "herzklopfen" ? "hab Herzklopfen" : pet.led.what} …`;
    if (pet.asleep) return pick(["Zzz… ich träume von MP3s 💤", "Zzz… *schnarch* … 512 MB RAM … zzz", "Pssst, ich schlafe. Um 6:08 gibt's Wetter ☀️", "Zzz… wer streichelt mich um diese Uhrzeit 🥱"]);
    const cancel = (u.irregular || []).find(l => l.status === "CANCELLED" && (l.start.startsWith(day(0)) || l.start.startsWith(day(1))));
    if (cancel) return `${cancel.start.startsWith(day(0)) ? "Heute" : "Morgen"} fällt ${cancel.subject} aus!! 🎉🎉`;
    if (pet.food < 25) return pick(["Ich hab soooo Hunger 🥺 konvertier mal ein Video für mich", "Gib mir ein MP3 zu essen bitte 🎵🍴", "Mein Magen knurrt in Binärcode 01101000"]);
    if (pet.love < 25) return pick(["Niemand streichelt mich 😢", "Hallo? Ist da wer? Streichel mich bitte 💜", "Ich fühl mich wie ein vergessener USB-Stick 🥲"]);
    if ((p.cpu_temp || 0) > 60) return `Puh, ${num(p.cpu_temp, 0)} °C… mir ist heiß 🥵`;
    if ((o.queue?.running || 0) > 0) return "Gerade fließt ein Video durch mich durch! 🎵➡️🦁";
    const exam = (u.irregular || []).find(l => l.status === "EXAM");
    return pick([
      `Ich bin Level ${pet.level} und ${pet.age_days} ${pet.age_days === 1 ? "Tag" : "Tage"} alt 🍓`,
      `Ich wurde schon ${pet.pets}× gestreichelt 💜`,
      `Mir geht's gut: ${num(p.cpu_temp, 0)} °C und ${num(p.cpu, 0)} % CPU 😎`,
      `Ich passe auf ${Object.keys(p.prismo?.sites || {}).length} Webseiten auf 🐕`,
      exam ? `Psst: ${when(exam.start)} ist ${exam.subject} Prüfung 📝` : "Keine Prüfungen in Sicht. Chillig 😌",
      `Schon ${num(o.totals?.videos, 0)} Videos konvertiert, und ich war bei vielen dabei 🎧`,
      "Ich wohne in einer TicTac-Schachtel und bin stolz drauf 🍬",
      `WLAN ${p.wifi ? p.wifi.dbm + " dBm" : "?"}: ${p.wifi?.dbm > -60 ? "Empfang ist top 📶" : "geht so 📶"}`,
    ]);
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

  function close() {
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

  // --- the pet ---
  function petView(d) {
    const p = d.pi, pet = p?.pet;
    if (!pet) return `<div class="face sleep"><span>💤</span></div><div><div class="name">PRISMO</div>
      <div class="bubble">${p ? "Ich wache gerade auf…" : "Ich bin gerade offline. Stecker? WLAN? 🔌"}</div></div>`;
    return `<div class="face ${pet.asleep ? "sleep" : ""}"><span>${pet.face}</span><div class="led ${pet.led?.what ? "on" : ""}" title="PRISMOs echtes Licht"></div></div>
      <div style="min-width:0;width:100%">
        <div class="name">PRISMO <small class="dim" style="font:600 14px system-ui">Level ${pet.level} · ${esc(pet.state)}</small></div>
        <div class="bubble">${esc(say(d))}</div>
        <div class="stats"><span>🍽️ Hunger</span>${bar(pet.food)}<span>💜 Liebe</span>${bar(pet.love)}</div>
      </div>`;
  }

  function diary(d) {
    const ev = d.pi?.pet?.events || [];
    return ev.length ? `<ul style="margin-top:10px">${ev.slice(0, 5).map(e => `<li><small>${ago(e.at)}</small> · PRISMO ${esc(e.text)}</li>`).join("")}</ul>` : "";
  }

  function petCard(d) {
    const pet = d.pi?.pet;
    return `<section class="card wide">
      <div class="pet" id="pie-pet">${petView(d)}</div>
      <div class="actions">
        <button data-a="pet">💜 Streicheln</button>
        <button data-a="snack" id="pie-snack">🍪 Snack${pet ? ` (${pet.snacks_left})` : ""}</button>
        <button data-a="wave" class="ghost">👋 Ins Zimmer winken</button>
      </div>
      <form class="morse" id="pie-morse"><input maxlength="24" placeholder="Morse-Nachricht ans Zimmer…" autocomplete="off"><button type="submit">📡</button></form>
      <div class="toast" id="pie-toast"></div>
      <small>Das passiert wirklich: PRISMOs grünes Licht blinkt in deinem Zimmer. Futter = konvertierte Videos.</small>
      <div id="pie-diary">${diary(d)}</div>
    </section>`;
  }

  async function act(action, text) {
    const t = $p("pie-toast");
    t.textContent = "…"; t.className = "toast";
    try {
      const res = await api({ action, text });
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
    sites: { x: 510, y: 360, e: "🌐", l: "deine Seiten", c: "#38d6c4", r: 28 },
  };
  // [from, to, bend]: packets fly from → to (rev = the other way)
  const LINKS = { yt_pi: ["yt", "pi", 40], pi_oracle: ["pi", "oracle", -30], oracle_you: ["oracle", "you", 26], pi_untis: ["pi", "untis", 30],
    pi_ntfy: ["pi", "ntfy", -18], ntfy_you: ["ntfy", "you", -120], pi_sites: ["pi", "sites", -30] };
  const ms = { rates: {}, burst: [], down: {}, led: false, io: false, temp: 45, cpu: 0, lastVideos: null, lastPush: null, tip: "pi", d: null };
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
      sites: `<b>🌐 Wachhund</b>: ${sites.map(([n, x]) => (x.ok ? "✅ " : "🚨 ") + esc(n)).join(" · ") || "startet gleich"}.`,
    }[k];
  }

  function updateMap(d) {
    const p = d.pi, o = d.oracle || {}, now = Date.now() / 1000;
    ms.d = d;
    const rx = p?.net?.rx || 0, tx = p?.net?.tx || 0, conv = (o.queue?.running || 0) + (o.queue?.waiting || 0);
    const checked = p?.untis?.checked ? now - new Date(p.untis.checked).getTime() / 1000 : 1e9;
    const sites = Object.values(p?.prismo?.sites || {}), down = sites.filter(s => s.down_since).length;
    const siteAge = sites.length ? now - Math.max(...sites.map(s => s.checked || 0)) : 1e9;
    ms.rates = {
      // a small baseline (tailscale, watchdog and proxy really do chatter all the time) + the real traffic on top
      yt_pi: Math.min(10, .7 + rx / 20e3 + conv * 3),
      pi_oracle: [Math.min(10, .8 + tx / 20e3 + conv * 3), .5 + conv],
      oracle_you: Math.min(10, .25 + (o.active || 0) * .8 + conv * 3),
      pi_untis: checked < 12 ? [6, 6] : [.12, .12],
      pi_ntfy: .05, ntfy_you: .05,
      pi_sites: siteAge < 8 ? [5, 5] : [.35, .35],
    };
    const off = !p;
    ms.down = { yt_pi: off, pi_oracle: off, pi_untis: off, pi_ntfy: off, pi_sites: off || down > 0 };
    Object.keys(LINKS).forEach(k => $p("pie-w-" + k)?.classList.toggle("down", !!ms.down[k]));
    ms.led = !!p?.pet?.led?.what;
    ms.io = (p?.io?.read || 0) + (p?.io?.write || 0) > 0;
    // events → bursts
    const videos = o.totals?.videos;
    if (ms.lastVideos != null && videos > ms.lastVideos) {
      burst([["yt_pi"], ["pi_oracle"], ["oracle_you"]], 14);
      flash("🎵 Gerade wurde ein Video konvertiert!");
    }
    ms.lastVideos = videos;
    const push = (p?.untis?.pushes || [])[0]?.at;
    if (ms.lastPush != null && push && push !== ms.lastPush) { burst([["pi_ntfy"], ["ntfy_you"]], 10); flash("🔔 PRISMO hat dir was geschickt"); }
    if (push) ms.lastPush = push;
    // PRISMO's ring: length = cpu, colour = temperature (cool cyan → hot red)
    const ring = $p("pie-ring");
    if (ring && p) {
      const C = 2 * Math.PI * 48, hot = Math.max(0, Math.min(1, ((p.cpu_temp || 40) - 40) / 30));
      ring.setAttribute("stroke-dashoffset", (C * (1 - Math.max(.04, (p.cpu || 0) / 100))).toFixed(1));
      ring.setAttribute("stroke", `hsl(${(180 - 180 * hot).toFixed(0)} 95% 60%)`);
    }
    setVal("you", `${o.active ?? 0} online`);
    setVal("oracle", conv ? `${conv} in Arbeit` : `${num(o.cpu, 0)} % CPU`);
    setVal("yt", rx > 20e3 ? "↓ " + rate(rx) : "ruhig");
    setVal("pi", p ? `${num(p.cpu_temp, 0)} °C · ${num(p.cpu, 0)} % · ${p.pet?.face || ""}` : "offline", !p);
    setVal("untis", p?.untis?.class ? `${p.untis.class} · ${isoAgo(p.untis.checked)}` : "");
    setVal("ntfy", (p?.untis?.pushes || [])[0] ? isoAgo(p.untis.pushes[0].at) : "");
    setVal("sites", sites.length ? (down ? `${down} offline!` : `${sites.length} online`) : "", down > 0);
    const tip = $p("pie-tip"); if (tip) tip.innerHTML = tipText(ms.tip, d) || "";
    if (!raf) { lastT = 0; raf = requestAnimationFrame(frame); }
  }

  function bindMap() {
    document.querySelectorAll("#pie .map .node").forEach(n => n.onclick = () => {
      ms.tip = n.dataset.k;
      const k = n.dataset.k;
      // tapping fires a little burst along that node's wires, just for fun
      Object.entries(LINKS).forEach(([key, [a, b]]) => { if (a === k) burst([[key]], 5); else if (b === k) burst([[key, true]], 5); });
      if (ms.d) $p("pie-tip").innerHTML = tipText(k, ms.d);
    });
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
      "ytmp34-update.timer": "Update", "prismo-watchdog.timer": "Wachhund", "prismo-briefing.timer": "Briefing" };
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
    <section class="card"><h2>🐕 Wachhund</h2>
      ${sites.length ? sites.map(([n, x]) => row(esc(n), x.ok ? `<span class="ok">online</span> <small>${num(x.took, 2)} s</small>` : `<span class="bad">${x.down_since ? "offline seit " + dur(Date.now() / 1000 - x.down_since) : "wackelt"}</span>`)).join("") : `<p class="dim">${p ? "startet gleich" : "wohnt auf PRISMO"}</p>`}
      <small>PRISMO selbst wird von Oracle bewacht 🦁</small>
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
      ${petCard(d)}
      <div class="grid">
        <section class="card wide"><h2>🗺️ PRISMO-Netz <small>live · tipp auf einen Punkt</small></h2>${mapSvg()}</section>
        <section class="card wide"><h2>⚡ Live</h2><div id="pie-meters">${meters(d)}</div></section>
        <section class="card wide"><h2>📈 Die letzten 24 Stunden</h2><div id="pie-chart">${chart()}</div></section>
      </div>
      <div class="grid" id="pie-cards">${cards(d)}</div>
      <div class="foot"><b>©fabio inc.</b><br>Bitte mit Vorsicht umgehen · NICHT SCHÜTTELN du gundi<br>PRISMO ist nicht verantwortlich für Verletzungen oder Tod.${barcode()}</div>
    </div>`;
    const r = $p("pie");
    r.querySelector("[data-x]").onclick = close;
    r.querySelectorAll("[data-a]").forEach(b => b.onclick = () => act(b.dataset.a));
    $p("pie-morse").onsubmit = e => { e.preventDefault(); const i = e.target.querySelector("input"); if (i.value.trim()) { act("morse", i.value.trim()); i.value = ""; } };
    updateMap(d);
    bindMap();
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
      updateMap(d);
      $p("pie-meters").innerHTML = meters(d);
      if (all) {
        $p("pie-pet").innerHTML = petView(d);
        $p("pie-diary").innerHTML = diary(d);
        const sn = $p("pie-snack"); if (sn && d.pi?.pet) sn.textContent = `🍪 Snack (${d.pi.pet.snacks_left})`;
        $p("pie-cards").innerHTML = cards(d);
      } else {
        const led = $p("pie").querySelector(".face .led"); if (led) led.classList.toggle("on", !!d.pi?.pet?.led?.what);
      }
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

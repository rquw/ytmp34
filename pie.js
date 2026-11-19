// 🥧 PIE MODE 🥧 — the owner's status page, in the style of a 2003 circus website.
// loaded by index.html after L ×5. the password is checked by the server (POST /pie), never here.
(() => {
  const S = typeof SERVER !== "undefined" ? SERVER : "";
  const KEY = "piepw";
  let timer = null, tick = null, left = 0;

  const css = `
  #pie, #pie * { box-sizing: border-box; }
  #pie { position: fixed; inset: 0; z-index: 99999; overflow: auto; color: #000;
    font: 15px/1.35 "Comic Sans MS", "Comic Sans", "Chalkboard SE", "Comic Neue", cursive;
    background: repeating-conic-gradient(from 0deg at 50% 0%, #ff0040 0 10deg, #fff200 10deg 20deg) fixed; }
  #pie .wrap { max-width: 980px; margin: 0 auto; padding: 12px 16px 60px; }
  #pie .bg { position: fixed; inset: 0; pointer-events: none; opacity: .25;
    background: radial-gradient(circle, #fff 2px, transparent 3px) 0 0 / 28px 28px; }
  #pie .marquee { overflow: hidden; white-space: nowrap; background: #000; color: #0f0;
    border: 3px ridge #c0c0c0; font: bold 16px "Courier New", monospace; padding: 4px 0; }
  #pie .marquee span { display: inline-block; padding-left: 100%; animation: pie-scroll 18s linear infinite; }
  @keyframes pie-scroll { to { transform: translateX(-100%); } }
  #pie h1 { margin: 14px 0 4px; text-align: center; font-size: clamp(34px, 8vw, 72px); line-height: 1;
    font-family: Impact, "Arial Black", sans-serif; letter-spacing: 2px; transform: rotate(-2deg);
    background: linear-gradient(90deg, red, orange, yellow, lime, cyan, blue, magenta, red) 0 0 / 200% 100%;
    -webkit-background-clip: text; background-clip: text; color: transparent;
    -webkit-text-stroke: 2px #000; filter: drop-shadow(5px 5px 0 #000); animation: pie-rainbow 2s linear infinite; }
  @keyframes pie-rainbow { to { background-position: 200% 0; } }
  #pie .sub { text-align: center; font-weight: bold; color: #fff; text-shadow: 2px 2px 0 #000, -1px -1px 0 #000;
    font-size: 18px; margin-bottom: 10px; }
  #pie .blink { animation: pie-blink 1s steps(1) infinite; }
  @keyframes pie-blink { 50% { visibility: hidden; } }
  #pie .wobble { display: inline-block; animation: pie-wobble .6s ease-in-out infinite alternate; }
  @keyframes pie-wobble { from { transform: rotate(-8deg) scale(1); } to { transform: rotate(8deg) scale(1.15); } }
  #pie .spin { display: inline-block; animation: pie-spin 3s linear infinite; }
  @keyframes pie-spin { to { transform: rotate(360deg); } }
  #pie .burst { position: absolute; width: 84px; height: 84px; font-size: 13px !important; display: grid; place-items: center; text-align: center;
    background: #fff200; color: #e00000; font: 900 16px/1 Impact, sans-serif; transform: rotate(14deg);
    clip-path: polygon(50% 0,61% 18%,82% 7%,79% 30%,100% 32%,86% 50%,100% 68%,79% 70%,82% 93%,61% 82%,50% 100%,39% 82%,18% 93%,21% 70%,0 68%,14% 50%,0 32%,21% 30%,18% 7%,39% 18%);
    animation: pie-pulse 1s ease-in-out infinite alternate; }
  @keyframes pie-pulse { to { transform: rotate(14deg) scale(1.12); } }
  #pie .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(290px, 1fr)); gap: 16px; margin-top: 14px; }
  #pie .act { position: relative; background: linear-gradient(#fff 0%, #ffe9fb 100%); border: 5px ridge #ff00cc;
    border-radius: 14px; padding: 12px 14px 14px; box-shadow: 8px 8px 0 #000; }
  #pie .act:nth-child(2n) { border-color: #00c3ff; transform: rotate(.6deg); }
  #pie .act:nth-child(3n) { border-color: #23d600; transform: rotate(-.6deg); }
  #pie .act h2 { margin: -12px -14px 10px; padding: 8px 12px; border-radius: 8px 8px 0 0; font-size: 20px;
    color: #fff; text-shadow: 2px 2px 0 #000; font-family: "Arial Black", Impact, sans-serif;
    background: linear-gradient(#ff6ad5 0%, #c700a1 49%, #a10082 51%, #ff3cc7 100%); }
  #pie .act:nth-child(2n) h2 { background: linear-gradient(#6ae1ff 0%, #0090c7 49%, #0074a1 51%, #3cc7ff 100%); }
  #pie .act:nth-child(3n) h2 { background: linear-gradient(#8dff6a 0%, #2fb100 49%, #238a00 51%, #58e83c 100%); }
  #pie .row { display: flex; justify-content: space-between; gap: 10px; padding: 3px 0; border-bottom: 2px dotted #c9a;
    overflow-wrap: anywhere; }
  #pie .row b { flex-shrink: 0; } #pie .row span { text-align: right; }
  #pie .big { font: 900 30px Impact, "Arial Black", sans-serif; text-align: center; margin: 4px 0 8px; letter-spacing: 1px; }
  #pie .on { color: #00b300; text-shadow: 0 0 8px #7f7; } #pie .off { color: #e00000; text-shadow: 0 0 8px #f77; }
  #pie .meh { color: #d98200; }
  #pie .pill { display: inline-block; padding: 1px 8px; border-radius: 99px; border: 2px solid #000; font-size: 13px;
    font-weight: bold; margin: 2px 2px 2px 0; }
  #pie .pill.on { background: #b6ffb0; text-shadow: none; } #pie .pill.off { background: #ffb0b0; text-shadow: none; }
  #pie .meter { height: 16px; border: 2px inset #999; background: #222; border-radius: 3px; overflow: hidden; margin: 2px 0 6px; }
  #pie .meter i { display: block; height: 100%; background: repeating-linear-gradient(45deg, #0f0 0 8px, #0c0 8px 16px); }
  #pie .meter.hot i { background: repeating-linear-gradient(45deg, #f40 0 8px, #c00 8px 16px); }
  #pie ul { margin: 4px 0; padding-left: 20px; } #pie li { margin: 3px 0; overflow-wrap: anywhere; }
  #pie small, #pie .dim { color: #555; }
  #pie .btn { font: bold 17px "Comic Sans MS", cursive; color: #fff; text-shadow: 1px 1px 0 #000; cursor: pointer;
    border: 2px solid #003a6e; border-radius: 99px; padding: 8px 22px;
    background: linear-gradient(#9fe0ff 0%, #2f9bff 50%, #0a6fd6 51%, #5ec2ff 100%); box-shadow: 0 3px 0 #003a6e, inset 0 1px 0 #fff; }
  #pie .btn:active { transform: translateY(2px); box-shadow: 0 1px 0 #003a6e; }
  #pie .btn.red { border-color: #6e0000; background: linear-gradient(#ffa0a0 0%, #ff2f2f 50%, #d60a0a 51%, #ff5e5e 100%);
    box-shadow: 0 3px 0 #6e0000, inset 0 1px 0 #fff; }
  #pie .top { display: flex; justify-content: space-between; align-items: center; gap: 8px; margin-top: 10px; flex-wrap: wrap; }
  #pie .counter { font: bold 20px "Courier New", monospace; background: #000; color: #f00; padding: 2px 8px;
    border: 3px inset #888; letter-spacing: 3px; }
  #pie .construction { margin-top: 18px; padding: 8px; text-align: center; font: 900 18px Impact, sans-serif; color: #000;
    background: repeating-linear-gradient(-45deg, #ffd000 0 20px, #000 20px 40px); border: 3px solid #000; }
  #pie .construction span { background: #ffd000; padding: 2px 10px; }
  #pie .gate { max-width: 420px; margin: 12vh auto 0; text-align: center; background: #fff; border: 6px ridge gold;
    border-radius: 20px; padding: 20px; box-shadow: 10px 10px 0 #000; }
  #pie .gate input { font: bold 34px "Courier New", monospace; width: 170px; text-align: center; letter-spacing: 10px;
    border: 4px inset #aaa; padding: 6px; margin: 12px 0; }
  #pie .err { color: #e00; font-weight: bold; min-height: 1.4em; }
  #pie .live { margin-top: 14px; background: #000; border: 5px outset #9a9a9a; border-radius: 10px; padding: 10px;
    box-shadow: 8px 8px 0 #000, inset 0 0 30px #0f04; color: #0f0; font-family: "Courier New", monospace; }
  #pie .ltitle { text-align: center; font: 900 20px Impact, sans-serif; color: #ff0; text-shadow: 0 0 8px #ff0; margin-bottom: 8px; }
  #pie .ltitle small { color: #0ff; font: bold 12px "Comic Sans MS", cursive; text-shadow: none; }
  #pie .machine { display: flex; gap: 10px; align-items: stretch; margin: 6px 0; flex-wrap: wrap; }
  #pie .mname { width: 96px; display: grid; place-items: center; font: 900 18px Impact, sans-serif; color: #f0f;
    text-shadow: 0 0 8px #f0f; border: 2px dashed #f0f; border-radius: 6px; }
  #pie .gauges { flex: 1; display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 8px; min-width: 220px; }
  #pie .gauge { border: 2px solid #0a0; border-radius: 6px; padding: 4px 8px; background: #010; }
  #pie .gl { font-weight: bold; color: #8f8; } #pie .gt { font-size: 12px; color: #6c6; }
  #pie .gv { font: 900 28px "Courier New", monospace; color: #0f0; text-shadow: 0 0 10px #0f0; }
  #pie .gv.hot { color: #f30; text-shadow: 0 0 10px #f30; animation: pie-blink .5s steps(1) infinite; }
  #pie .live .meter { margin: 2px 0; } #pie .live .meter i { transition: width .6s ease; }
  #pie .loading { text-align: center; font-size: 26px; color: #fff; text-shadow: 3px 3px 0 #000; margin-top: 30px; }
  @media (prefers-reduced-motion: reduce) { #pie * { animation: none !important; } }
  `;

  const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const mb = b => (b / 1e6).toLocaleString("de-AT", { maximumFractionDigits: 1 }) + " MB";
  const gb = b => (b / 1e9).toLocaleString("de-AT", { maximumFractionDigits: 1 }) + " GB";
  const dur = s => { s = Math.max(0, Math.round(s)); const d = Math.floor(s / 86400), h = Math.floor(s % 86400 / 3600), m = Math.floor(s % 3600 / 60);
    return d ? `${d}d ${h}h` : h ? `${h}h ${m}min` : m ? `${m}min` : `${s}s`; };
  const ago = t => t ? dur(Date.now() / 1000 - t) + " ago" : "never";
  const isoAgo = s => s ? ago(new Date(s).getTime() / 1000) : "never";
  const when = s => { if (!s) return ""; const d = new Date(s.replace("Z", ""));
    return d.toLocaleDateString("de-AT", { weekday: "short", day: "2-digit", month: "2-digit" }) + " " + d.toLocaleTimeString("de-AT", { hour: "2-digit", minute: "2-digit" }); };
  const row = (k, v) => `<div class="row"><b>${k}</b><span>${v}</span></div>`;
  const meter = (pct, hot) => `<div class="meter${pct > hot ? " hot" : ""}"><i style="width:${Math.min(100, Math.max(2, pct)).toFixed(0)}%"></i></div>`;
  const yes = (ok, a = "YES!!", b = "NOPE") => ok === null || ok === undefined ? `<span class="meh">???</span>` : ok ? `<span class="on">${a}</span>` : `<span class="off">${b}</span>`;
  const ICON = { CANCELLED: "❌", ADDITIONAL: "➕", SUBSTITUTION: "🔄", ROOMSUBSTITUTION: "🚪", SHIFT: "🔀", EXAM: "📝", IRREGULAR: "🔄", EVENT: "📅" };

  function el() {
    let root = document.getElementById("pie");
    if (!root) {
      const st = document.createElement("style"); st.textContent = css; document.head.appendChild(st);
      root = document.createElement("div"); root.id = "pie"; document.body.appendChild(root);
      addEventListener("keydown", e => { if (e.key === "Escape" && root.isConnected) close(); });
    }
    return root;
  }

  function close() {
    clearInterval(timer); clearInterval(tick);
    document.getElementById("pie")?.remove();
    document.documentElement.style.overflow = "";
  }

  function gate(msg = "") {
    const root = el();
    document.documentElement.style.overflow = "hidden";
    root.innerHTML = `<div class="bg"></div><div class="wrap">
      <div class="marquee"><span>★ STEP RIGHT UP ★ STEP RIGHT UP ★ ONLY RINGMASTERS BEYOND THIS POINT ★ NO CLOWNS ALLOWED ★ PLEASE KEEP YOUR HANDS INSIDE THE PIE ★</span></div>
      <div class="gate"><div style="font-size:54px"><span class="wobble">🎪</span></div>
        <h2 style="margin:6px 0;font-family:Impact,sans-serif;font-size:30px;color:#c700a1">THE SECRET PIE TENT</h2>
        <div>whisper the magic number to the clown 🤡</div>
        <form><input type="password" inputmode="numeric" autocomplete="off" maxlength="12" aria-label="Password"><br>
        <button class="btn" type="submit">🥧 LET ME IN 🥧</button> <button class="btn red" type="button" data-x>run away</button></form>
        <div class="err">${esc(msg)}</div></div></div>`;
    const input = root.querySelector("input");
    input.focus();
    root.querySelector("[data-x]").onclick = close;
    root.querySelector("form").onsubmit = e => { e.preventDefault(); login(input.value.trim()); };
  }

  async function fetchPie(pw) {
    const r = await fetch(S + "/pie", { method: "POST", body: JSON.stringify({ pw }), signal: AbortSignal.timeout(9000) });
    const body = await r.json().catch(() => ({}));
    return { ok: r.ok, body };
  }

  async function login(pw) {
    if (!pw) return gate("the clown heard nothing 🙉");
    // show something right away: the answer takes a moment (oracle asks the pi first)
    const root = el();
    document.documentElement.style.overflow = "hidden";
    root.innerHTML = `<div class="bg"></div><div class="loading"><span class="spin" style="font-size:60px">🎪</span><br>opening the big top…</div>`;
    let res;
    try { res = await fetchPie(pw); } catch { return gate("the big top is unreachable (oracle offline?) 🌧️"); }
    if (!res.ok) {
      try { sessionStorage.removeItem(KEY); } catch {}
      return gate(res.body.error === "locked" ? `🚨 TOO MANY WRONG GUESSES 🚨 try again in ${dur(res.body.wait)}`
        : "WRONG!!! the lion is now slightly annoyed 🦁");
    }
    try { sessionStorage.setItem(KEY, pw); } catch {}
    show(res.body, pw);
  }

  function services(svc) {
    const names = { "ytmp34": "backup ytmp34", "ytmp34-proxy": "proxy for oracle", "untis-watch.timer": "untis watcher",
      "tailscaled": "tailscale", "ytmp34-update.timer": "nightly update" };
    return Object.entries(svc || {}).map(([k, v]) => `<span class="pill ${v === "active" ? "on" : "off"}">${v === "active" ? "✔" : "✘"} ${esc(names[k] || k)}</span>`).join("");
  }

  function render(d) {
    const o = d.oracle || {}, p = d.pi, u = p?.untis || {};
    const piMem = p ? 100 * (1 - p.memory.available / p.memory.total) : 0;
    const oMem = 100 * (1 - (o.memory?.available || 0) / (o.memory?.total || 1));
    const temp = p?.cpu_temp;
    const last = (o.recent || [])[0];
    return `
    <div class="act"><div class="burst" style="right:-22px;top:-48px">100%<br>REAL<br>PI!!</div>
      <h2>🎪 THE AMAZING PI 🎪</h2>
      <div class="big">${p ? `<span class="on blink">● ONLINE ●</span>` : `<span class="off blink">● OFFLINE ●</span>`}</div>
      ${p ? row("name", esc(p.host)) + row("model", esc(p.model)) + row("awake for", dur(p.uptime))
        + row("cpu temp", temp == null ? "?" : `${temp.toFixed(1)}°C ${temp > 70 ? "🔥🔥🔥" : temp > 55 ? "🔥" : "🧊"}`) + meter(temp || 0, 70)
        + row("brain (RAM)", `${mb(p.memory.total - p.memory.available)} / ${mb(p.memory.total)}`) + meter(piMem, 85)
        + row("swap", `${mb(p.memory.swap_total - p.memory.swap_free)} used`)
        + row("SD card", `${gb(p.disk.total - p.disk.free)} / ${gb(p.disk.total)}`)
        + row("wifi", p.wifi ? `${p.wifi.dbm} dBm ${p.wifi.dbm > -60 ? "📶 great" : p.wifi.dbm > -72 ? "📶 ok" : "🥴 weak"}` : "?")
        + row("load", p.load.map(x => x.toFixed(2)).join(" · "))
        + row("power", p.throttled === "0x0" ? "✔ all good" : `<span class="off">⚡ ${esc(p.throttled || "?")}</span>`)
        + `<div style="margin-top:8px">${services(p.services)}</div>`
        : `<p>The Pi did not answer. Is it unplugged, moving rooms, or offline?</p><small>${esc(d.pi_error || "")}</small>`}
    </div>

    <div class="act"><h2>🦁 ORACLE THE LION TAMER</h2>
      <div class="big"><span class="on">● ROARING ●</span></div>
      ${row("YouTube happy?", yes(o.youtube_ok, "YES!! 🎉", "BLOCKED 😱"))
      + row("goes through the Pi?", o.proxy ? yes(o.proxy_ok, "YES 🥧➡️🦁", "PROXY DOWN") : `<span class="meh">no (direct)</span>`)
      + row("converting now", `${o.queue?.running ?? 0} / ${o.queue?.slots ?? "?"} slots · ${o.queue?.waiting ?? 0} waiting`)
      + row("people on the site", `${o.active ?? 0} 👀`)
      + row("yt-dlp", esc(o.yt_dlp))
      + row("server up for", dur(o.server_uptime || 0))
      + row("machine up for", dur(o.uptime || 0))
      + row("RAM", `${gb((o.memory?.total || 0) - (o.memory?.available || 0))} / ${gb(o.memory?.total || 0)}`) + meter(oMem, 85)
      + row("disk free", gb(o.disk?.free || 0))
      + row("load", (o.load || []).map(x => x.toFixed(2)).join(" · "))}
    </div>

    <div class="act"><div class="burst" style="right:-22px;top:-48px">NEW!!<br>HOT!!</div>
      <h2>🤹 THE LAST TRICK</h2>
      ${last ? `<div class="big" style="font-size:22px">${last.fmt === "mp3" ? "🎵" : "🎬"} ${esc(last.title)}</div>`
        + row("when", ago(last.at)) + row("format", last.fmt.toUpperCase()) + row("size", mb(last.size))
        + row("video length", dur(last.duration)) + row("took", `${last.took}s ${last.took < 20 ? "⚡" : "🐢"}`)
        : `<p>No tricks since the server started ${dur(o.server_uptime || 0)} ago. 🦗🦗🦗</p>`}
      ${(o.recent || []).length > 1 ? `<div class="dim" style="margin-top:6px">earlier:</div><ul>${o.recent.slice(1).map(r =>
        `<li>${r.fmt === "mp3" ? "🎵" : "🎬"} ${esc(r.title)} <small>(${ago(r.at)})</small></li>`).join("")}</ul>` : ""}
      <div class="top" style="margin-top:10px"><span>ALL-TIME:</span>
        <span class="counter">${String(o.totals?.videos ?? 0).padStart(6, "0")}</span><span>${mb(o.totals?.bytes || 0)}</span></div>
    </div>

    <div class="act"><h2>🔮 MADAME UNTIS, FORTUNE TELLER</h2>
      ${p ? row("class", esc(u.class || "?")) + row("crystal ball checked", isoAgo(u.checked))
        + row("health", u.fails ? `<span class="off">${u.fails} failed checks in a row 😵</span>` : `<span class="on">fine ✨</span>`)
        + row("lessons in view", u.lessons ?? "?")
        + row("next lesson", u.next ? `${esc(when(u.next.start))} · ${esc(u.next.subject)}` : "none 🏖️")
        + `<div class="dim" style="margin-top:6px">coming up that's not normal:</div>`
        + (u.irregular?.length ? `<ul>${u.irregular.map(l => `<li>${ICON[l.status] || "•"} ${esc(when(l.start))} ${esc(l.subject)}${l.rooms?.length ? ` <small>(${esc(l.rooms.join(", "))})</small>` : ""}</li>`).join("")}</ul>` : `<p>nothing! the future is boring 😴</p>`)
        + `<div class="dim">last pushes to your phone:</div>`
        + (u.pushes?.length ? `<ul>${u.pushes.map(x => `<li>${x.urgent ? "🚨" : "📣"} <b>${esc(x.title)}</b> <small>${isoAgo(x.at)}</small><br><small>${esc(x.message).replace(/\n/g, "<br>")}</small></li>`).join("")}</ul>` : `<p>none yet 📭</p>`)
        : `<p>Madame Untis lives on the Pi, and the Pi is not answering. 🔮💤</p>`}
    </div>

    <div class="act"><h2>💀 ACCIDENTS IN THE RING</h2>
      ${(o.errors || []).length ? `<ul>${o.errors.map(e => `<li>🤕 <b>${esc(e.code)}</b> ${esc(e.text)} <small>(${ago(e.at)})</small></li>`).join("")}</ul>`
        : `<p>No accidents since the server started! 🎉 The clowns are behaving.</p>`}
    </div>`;
  }

  function gauge(label, pct, text, hot) {
    pct = Math.max(0, Math.min(100, pct || 0));
    return `<div class="gauge"><div class="gl">${label}</div><div class="gv${pct > hot ? " hot" : ""}">${pct.toFixed(0)}%</div>
      ${meter(pct, hot)}<div class="gt">${text}</div></div>`;
  }

  function live(d) {
    const o = d.oracle || {}, p = d.pi;
    const used = m => m.total - m.available;
    const box = (name, m) => `<div class="machine"><div class="mname">${name}</div><div class="gauges">${m}</div></div>`;
    const pi = p ? box("🥧 PI", gauge("CPU", p.cpu, `${p.cpu_temp?.toFixed(1) ?? "?"}°C`, 80)
        + gauge("RAM", 100 * used(p.memory) / p.memory.total, `${mb(used(p.memory))} / ${mb(p.memory.total)}`, 85)
        + gauge("SD", 100 * (1 - p.disk.free / p.disk.total), `${gb(p.disk.total - p.disk.free)} / ${gb(p.disk.total)}`, 90))
      : box("🥧 PI", `<div class="big off blink" style="flex:1">OFFLINE 💤</div>`);
    const or = box("🦁 ORACLE", gauge("CPU", o.cpu, `${o.cpus ?? "?"} cores`, 80)
      + gauge("RAM", 100 * used(o.memory || { total: 1, available: 1 }) / (o.memory?.total || 1), `${gb(used(o.memory || { total: 0, available: 0 }))} / ${gb(o.memory?.total || 0)}`, 85)
      + gauge("SSD", 100 * (1 - (o.disk?.free || 0) / (o.disk?.total || 1)), `${gb((o.disk?.total || 0) - (o.disk?.free || 0))} / ${gb(o.disk?.total || 0)}`, 90));
    return pi + or;
  }

  function show(d, pw) {
    const root = el();
    document.documentElement.style.overflow = "hidden";
    root.innerHTML = `<div class="bg"></div><div class="wrap">
      <div class="marquee"><span>★★★ WELCOME TO PIE MODE ★★★ THE GREATEST SHOW ON A RASPBERRY PI ★★★ NOW WITH 512 MB OF RAM!!! ★★★ BEST VIEWED IN NETSCAPE NAVIGATOR 4.0 AT 800x600 ★★★ YOU ARE THE 1,000,000th VISITOR ★★★</span></div>
      <h1>PIE MODE!!!</h1>
      <div class="sub"><span class="spin">🥧</span> everything the pi is doing, live <span class="spin">🥧</span></div>
      <div class="top"><span class="sub" style="margin:0"><span class="blink" style="color:#f00">●</span> LIVE · acts refresh in <span id="pie-left">5</span>s <span class="wobble">🤡</span></span>
        <span><button class="btn" type="button" data-r>🔄 AGAIN!</button> <button class="btn red" type="button" data-x>🚪 EXIT THE BIG TOP</button></span></div>
      <div class="live"><div class="ltitle">⚡ THE LIVE-O-METER 3000 ⚡ <small>(updates every second!!)</small></div><div id="pie-live">${live(d)}</div></div>
      <div class="grid" id="pie-grid">${render(d)}</div>
      <div class="construction"><span>🚧 THIS PAGE IS UNDER CONSTRUCTION SINCE 2003 🚧</span></div>
      <p class="sub" style="margin-top:14px">© 2003 PIE CORP · <span class="blink">sign my guestbook!!</span> (there is no guestbook)</p></div>`;
    root.querySelector("[data-x]").onclick = close;
    root.querySelector("[data-r]").onclick = () => refresh(pw, true);
    clearInterval(timer); clearInterval(tick);
    left = 5;
    // every second: the live meters. every 5 s: the big acts (so their animations don't restart constantly)
    timer = setInterval(() => {
      left = left <= 1 ? 5 : left - 1;
      const l = document.getElementById("pie-left"); if (l) l.textContent = left;
      refresh(pw, left === 5);
    }, 1000);
  }

  let busy = false;
  async function refresh(pw, all) {
    if (busy) return;  // a slow answer shouldn't pile up requests
    busy = true;
    try {
      const res = await fetchPie(pw);
      if (!res.ok) { clearInterval(timer); return gate("the password stopped working 🤔"); }
      const lv = document.getElementById("pie-live"); if (lv) lv.innerHTML = live(res.body);
      const g = document.getElementById("pie-grid"); if (g && all) g.innerHTML = render(res.body);
    } catch {} finally { busy = false; }
  }

  window.openPie = () => {
    let pw = "";
    try { pw = sessionStorage.getItem(KEY) || ""; } catch {}
    pw ? login(pw) : gate();
  };
  openPie();
})();

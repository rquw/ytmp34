// PRISMO — fabios kleiner helfer. the owner's status page ("pie mode"), styled like the prismo packaging.
// loaded by index.html after L ×5 / 5 taps on the logo. the password is checked by the server (POST /pie), never here.
(() => {
  const S = typeof SERVER !== "undefined" ? SERVER : "";
  const KEY = "piepw";
  const HIST = 60;  // seconds of history for the little graphs
  let timer = null, left = 5, busy = false;
  const hist = { cpu: [], temp: [], rx: [], tx: [], ocpu: [] };

  const font = document.createElement("link");
  font.rel = "stylesheet";
  font.href = "https://fonts.googleapis.com/css2?family=Baloo+2:wght@700;800&display=swap";

  const css = `
  #pie, #pie * { box-sizing: border-box; }
  #pie { position: fixed; inset: 0; z-index: 99999; overflow: auto; color: #0b0b2a;
    font: 700 15px/1.35 Arial, Helvetica, sans-serif; background: #8fa8ff; }
  #pie .holo, #pie .panel::before { background:
      repeating-linear-gradient(100deg, rgba(255,255,255,0) 0 9px, rgba(255,255,255,.45) 12px, rgba(255,255,255,0) 16px 31px),
      repeating-linear-gradient(97deg, rgba(90,40,255,0) 0 23px, rgba(90,40,255,.18) 27px, rgba(90,40,255,0) 33px 57px),
      linear-gradient(115deg, #a77bff 0%, #ff7fd0 16%, #6fc3ff 30%, #b98cff 44%, #57e8ff 58%, #ff74c8 72%, #4f8cff 88%, #9b6bff 100%);
    background-size: 220% 220%, 180% 180%, 260% 260%; animation: pie-shimmer 14s ease-in-out infinite alternate; }
  @keyframes pie-shimmer { to { background-position: 100% 50%, 0% 100%, 100% 0%; } }
  #pie .holo { position: fixed; inset: 0; pointer-events: none; }
  #pie .wrap { position: relative; max-width: 1100px; margin: 0 auto; padding: 14px 16px 60px; }

  /* the packaging lettering: white, thick mint glow, soft shadow */
  #pie .glow { font-family: "Baloo 2", "Arial Rounded MT Bold", "Arial Black", sans-serif; font-weight: 800; color: #fff;
    text-shadow: 0 0 2px #fff, 0 0 0 #000, -4px -4px 0 #8ff3e6, 4px -4px 0 #8ff3e6, -4px 4px 0 #8ff3e6, 4px 4px 0 #8ff3e6,
      0 -6px 0 #8ff3e6, 0 6px 0 #8ff3e6, -6px 0 0 #8ff3e6, 6px 0 0 #8ff3e6, 0 0 26px #a8fff3, 0 0 40px #c8fff8, 6px 9px 16px rgba(20,20,90,.45); }
  #pie .glow.small { text-shadow: -2px -2px 0 #8ff3e6, 2px -2px 0 #8ff3e6, -2px 2px 0 #8ff3e6, 2px 2px 0 #8ff3e6,
      0 0 12px #a8fff3, 3px 5px 8px rgba(20,20,90,.4); }
  #pie .outline { color: #0b0b2a; text-shadow: -1px -1px 0 #fff, 1px -1px 0 #fff, -1px 1px 0 #fff, 1px 1px 0 #fff, 0 0 6px #fff; }

  #pie .hero { display: grid; grid-template-columns: 1fr auto; gap: 10px; align-items: center; }
  #pie .logo { font-size: clamp(64px, 14vw, 150px); line-height: .85; letter-spacing: -2px; transform: rotate(-3deg); margin: 6px 0 0; }
  #pie .slogan { font-size: clamp(20px, 4vw, 34px); transform: rotate(-3deg); margin: 4px 0 0 6px; }
  #pie .prism { width: clamp(110px, 20vw, 190px); aspect-ratio: 1.25; position: relative; filter: drop-shadow(0 18px 18px rgba(60,0,120,.35)); }
  #pie .prism i { position: absolute; inset: 0; clip-path: polygon(50% 0, 100% 78%, 62% 100%, 0 82%);
    background: conic-gradient(from 200deg at 50% 70%, #ff4fd8, #ffe14f, #4fff9b, #4fd8ff, #a14fff, #ff4fd8);
    animation: pie-hue 6s linear infinite; }
  #pie .prism i + i { clip-path: polygon(50% 0, 62% 100%, 0 82%); background: linear-gradient(160deg, rgba(255,255,255,.75), rgba(255,255,255,0) 70%); animation: none; }
  @keyframes pie-hue { to { filter: hue-rotate(360deg); } }

  #pie .pbar { display: flex; justify-content: space-between; align-items: center; gap: 10px; flex-wrap: wrap; margin: 12px 0 6px; }
  #pie .btn { font: 800 17px "Baloo 2", "Arial Black", sans-serif; color: #fff; cursor: pointer; border-radius: 999px;
    padding: 6px 20px 4px; border: 2px solid #fff; text-shadow: 0 1px 2px rgba(0,0,60,.6);
    background: linear-gradient(#ffffff88, #ffffff00 50%, #00000014 51%), linear-gradient(90deg, #6f8cff, #c66bff, #ff6fcf);
    box-shadow: 0 4px 14px rgba(40,0,120,.35), inset 0 1px 0 #fff; }
  #pie .btn:active { transform: translateY(2px); }
  #pie .btn.mint { background: linear-gradient(#ffffff99, #ffffff00 50%, #00000010 51%), linear-gradient(90deg, #3fd8c6, #6fb8ff); }

  #pie .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 14px; }
  #pie .panel { position: relative; overflow: hidden; border: 3px solid #0b0b2a; border-radius: 4px; padding: 12px 14px 14px;
    box-shadow: 0 10px 30px rgba(40,0,110,.35); isolation: isolate; }
  #pie .panel::before { content: ""; position: absolute; inset: 0; z-index: -1; opacity: .95; }
  #pie .panel h2 { margin: 0 0 8px; font-size: 26px; line-height: 1.05; }
  #pie .panel.wide { grid-column: 1 / -1; }
  #pie .row { display: flex; justify-content: space-between; gap: 10px; padding: 3px 0; border-bottom: 1px solid rgba(255,255,255,.55); }
  #pie .row > :first-child { flex-shrink: 0; } #pie .row > :last-child { text-align: right; overflow-wrap: anywhere; }
  #pie .big { font-size: 34px; text-align: center; margin: 2px 0 8px; }
  #pie .ok { color: #0a8f3a; } #pie .bad { color: #d4004f; } #pie .meh { color: #b86e00; }
  #pie .pill { display: inline-block; margin: 3px 3px 0 0; padding: 2px 10px; border-radius: 999px; font-size: 13px;
    border: 2px solid #fff; background: rgba(255,255,255,.55); }
  #pie .pill.ok { background: #b9ffdc; } #pie .pill.bad { background: #ffc0d8; }
  #pie ul { margin: 4px 0; padding-left: 18px; } #pie li { margin: 3px 0; overflow-wrap: anywhere; }
  #pie small { font-weight: 400; opacity: .8; }

  /* live gauges */
  #pie .gauges { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 10px; }
  #pie .g { background: rgba(255,255,255,.45); border: 2px solid #fff; border-radius: 16px; padding: 6px 10px 8px;
    box-shadow: inset 0 0 18px rgba(255,255,255,.6); }
  #pie .g .gl { font-size: 13px; text-transform: uppercase; letter-spacing: .5px; }
  #pie .g .gv { font: 800 30px/1 "Baloo 2", "Arial Black", sans-serif; }
  #pie .g .gt { font-size: 12px; font-weight: 400; }
  #pie .g.hot .gv { color: #d4004f; animation: pie-pulse .8s ease-in-out infinite alternate; }
  @keyframes pie-pulse { to { transform: scale(1.06); } }
  #pie .meter { height: 12px; border-radius: 99px; background: rgba(11,11,42,.18); overflow: hidden; margin-top: 4px; border: 1px solid #fff; }
  #pie .meter i { display: block; height: 100%; border-radius: 99px; transition: width .6s ease;
    background: linear-gradient(#ffffffaa, #ffffff00 55%), linear-gradient(90deg, #4fe3d0, #7f8cff, #ff6fcf); }
  #pie svg.spark { display: block; width: 100%; height: 30px; margin-top: 4px; }
  #pie .cores { display: flex; gap: 3px; align-items: flex-end; height: 26px; margin-top: 4px; }
  #pie .cores i { flex: 1; background: linear-gradient(#ff6fcf, #7f8cff); border-radius: 3px 3px 0 0; transition: height .6s ease; min-height: 2px; }
  #pie .machine { margin-top: 10px; }
  #pie .machine > .glow { font-size: 22px; margin-bottom: 4px; }

  /* the side flap of the box */
  #pie .flap { display: flex; flex-wrap: wrap; gap: 14px; align-items: center; justify-content: space-around; text-align: center; }
  #pie .flap .smile { font-size: 46px; line-height: 1; }
  #pie .flap .label { font-size: 22px; font-style: italic; }
  #pie .care { font: 800 italic 18px/1.15 "Baloo 2", sans-serif; }
  #pie .back p { margin: 0 0 6px; font-size: 17px; }
  #pie .barcode { height: 70px; max-width: 360px; background: #fff; padding: 6px 8px; margin: 10px auto 0; display: flex; gap: 0; align-items: stretch; }
  #pie .barcode i { background: #000; }
  #pie .vert { writing-mode: vertical-rl; transform: rotate(180deg); font-size: 34px; text-align: center; }

  #pie .gate { max-width: 440px; margin: 10vh auto 0; text-align: center; }
  #pie .gate input { font: 800 36px "Baloo 2", monospace; width: 190px; text-align: center; letter-spacing: 12px;
    border: 3px solid #fff; border-radius: 16px; padding: 4px; margin: 14px 0; background: rgba(255,255,255,.7); color: #0b0b2a; }
  #pie .err { color: #d4004f; min-height: 1.4em; margin-top: 8px; }
  #pie .loading { text-align: center; margin-top: 22vh; font-size: 32px; }
  @media (max-width: 560px) { #pie .hero { grid-template-columns: 1fr; justify-items: center; text-align: center; } }
  @media (prefers-reduced-motion: reduce) { #pie *, #pie .holo { animation: none !important; } }
  `;

  // --- helpers ---
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
  const meter = pct => `<div class="meter"><i style="width:${Math.min(100, Math.max(2, pct || 0)).toFixed(0)}%"></i></div>`;
  const yes = (ok, a = "JA 😁", b = "NEIN 😠") => ok == null ? `<span class="meh">??? 🤔</span>` : ok ? `<span class="ok">${a}</span>` : `<span class="bad">${b}</span>`;
  const ICON = { CANCELLED: "❌", ADDITIONAL: "➕", SUBSTITUTION: "🔄", ROOMSUBSTITUTION: "🚪", SHIFT: "🔀", EXAM: "📝", IRREGULAR: "🔄", EVENT: "📅" };
  const THROTTLE = { undervoltage: "Unterspannung ⚡", freq_capped: "Takt gedrosselt 🐌", throttled: "gebremst 🛑", soft_temp_limit: "zu heiß 🔥" };

  function push(arr, v) { if (v == null || Number.isNaN(v)) return; arr.push(v); if (arr.length > HIST) arr.shift(); }
  function spark(arr, max) {
    if (arr.length < 2) return `<svg class="spark" viewBox="0 0 100 30"></svg>`;
    const m = max || Math.max(...arr, 1), step = 100 / (HIST - 1), off = 100 - (arr.length - 1) * step;
    const pts = arr.map((v, i) => `${(off + i * step).toFixed(1)},${(28 - 26 * Math.min(1, v / m)).toFixed(1)}`).join(" ");
    return `<svg class="spark" viewBox="0 0 100 30" preserveAspectRatio="none">
      <polyline points="${off.toFixed(1)},30 ${pts} 100,30" fill="rgba(255,255,255,.45)" stroke="none"/>
      <polyline points="${pts}" fill="none" stroke="#0b0b2a" stroke-width="1.6" vector-effect="non-scaling-stroke"/></svg>`;
  }
  function barcode() {
    let s = "", seed = 1907;
    for (let i = 0; i < 60; i++) { seed = seed * 16807 % 2147483647; const w = 1 + seed % 4; s += `<i style="flex:${w}"></i><span style="flex:${1 + (seed >> 3) % 3}"></span>`; }
    return `<div class="barcode">${s}</div>`;
  }

  // --- screens ---
  function el() {
    let root = document.getElementById("pie");
    if (!root) {
      if (!font.isConnected) document.head.appendChild(font);
      const st = document.createElement("style"); st.id = "pie-css"; st.textContent = css;
      if (!document.getElementById("pie-css")) document.head.appendChild(st);
      root = document.createElement("div"); root.id = "pie"; document.body.appendChild(root);
      addEventListener("keydown", e => { if (e.key === "Escape" && document.getElementById("pie")) close(); });
    }
    document.documentElement.style.overflow = "hidden";
    return root;
  }

  function close() {
    clearInterval(timer);
    document.getElementById("pie")?.remove();
    document.documentElement.style.overflow = "";
  }

  function gate(msg = "") {
    const root = el();
    root.innerHTML = `<div class="holo"></div><div class="wrap"><div class="gate">
      <div class="prism" style="margin:0 auto"><i></i><i></i></div>
      <div class="glow logo" style="font-size:84px">prismo</div>
      <div class="glow small slogan" style="font-size:22px">fabios kleiner helfer</div>
      <form><input type="password" inputmode="numeric" autocomplete="off" maxlength="12" aria-label="Geheimcode"><br>
        <button class="btn mint" type="submit">AUSPACKEN 📦</button> <button class="btn" type="button" data-x>lieber nicht</button></form>
      <div class="err outline">${esc(msg)}</div>
      <p class="care glow small" style="margin-top:18px">Bitte mit Vorsicht umgehen<br>NICHT SCHÜTTELN du gundi</p></div></div>`;
    const input = root.querySelector("input");
    input.focus();
    root.querySelector("[data-x]").onclick = close;
    root.querySelector("form").onsubmit = e => { e.preventDefault(); login(input.value.trim()); };
  }

  async function fetchPie(pw) {
    const r = await fetch(S + "/pie", { method: "POST", body: JSON.stringify({ pw }), signal: AbortSignal.timeout(9000) });
    return { ok: r.ok, body: await r.json().catch(() => ({})) };
  }

  async function login(pw) {
    if (!pw) return gate("da steht ja gar nix 🙄");
    el().innerHTML = `<div class="holo"></div><div class="loading glow"><div class="prism" style="margin:0 auto"><i></i><i></i></div>wird ausgepackt…</div>`;
    let res;
    try { res = await fetchPie(pw); } catch { return gate("Oracle antwortet nicht. Offline? 🌧️"); }
    if (!res.ok) {
      try { sessionStorage.removeItem(KEY); } catch {}
      return gate(res.body.error === "locked" ? `🚨 zu oft falsch geraten 🚨 nochmal in ${dur(res.body.wait)}` : "FALSCH!!! 😠 PRISMO ist enttäuscht.");
    }
    try { sessionStorage.setItem(KEY, pw); } catch {}
    show(res.body, pw);
  }

  // --- the live strip (every second) ---
  function record(d) {
    const p = d.pi, o = d.oracle || {};
    push(hist.ocpu, o.cpu);
    if (p) { push(hist.cpu, p.cpu); push(hist.temp, p.cpu_temp); push(hist.rx, p.net?.rx); push(hist.tx, p.net?.tx); }
  }

  function gauge(label, value, text, pct, extra = "", hot = false) {
    return `<div class="g${hot ? " hot" : ""}"><div class="gl">${label}</div><div class="gv">${value}</div>${pct == null ? "" : meter(pct)}${extra}<div class="gt">${text}</div></div>`;
  }

  function live(d) {
    const p = d.pi, o = d.oracle || {};
    const used = m => m.total - m.available;
    let pi;
    if (p) {
      const t = p.cpu_temp, ram = 100 * used(p.memory) / p.memory.total, sd = 100 * (1 - p.disk.free / p.disk.total);
      const cores = (p.cores || []).map(c => `<i style="height:${Math.max(4, c)}%" title="${num(c, 0)}%"></i>`).join("");
      pi = `<div class="gauges">
        ${gauge("CPU", num(p.cpu, 0) + "%", `${p.freq_mhz ? num(p.freq_mhz, 0) + " MHz" : ""}${p.freq_max_mhz ? " / " + num(p.freq_max_mhz, 0) : ""}`, p.cpu,
          (cores ? `<div class="cores">${cores}</div>` : "") + spark(hist.cpu, 100), p.cpu > 90)}
        ${gauge("Temperatur", t == null ? "?" : num(t) + " °C", t > 70 ? "🔥 heiß!!" : t > 55 ? "warm 🥵" : "chillig 😎", t == null ? null : t / 85 * 100, spark(hist.temp, 85), t > 70)}
        ${gauge("RAM", num(ram, 0) + "%", `${mb(used(p.memory))} / ${mb(p.memory.total)}`, ram, "", ram > 90)}
        ${gauge("SD-Karte", num(sd, 0) + "%", `${gb(p.disk.total - p.disk.free)} / ${gb(p.disk.total)}`, sd,
          p.io ? `<div class="gt">lesen ${rate(p.io.read)} · schreiben ${rate(p.io.write)}</div>` : "", sd > 90)}
        ${p.net ? gauge("Netzwerk", "↓ " + rate(p.net.rx), "↑ " + rate(p.net.tx), null, spark(hist.rx.map((v, i) => v + (hist.tx[i] || 0)))) : ""}
      </div>`;
    } else {
      pi = `<div class="big glow">OFFLINE 💤</div><p class="outline" style="text-align:center">PRISMO schläft oder ist ausgesteckt.</p>`;
    }
    const oram = 100 * used(o.memory || { total: 1, available: 1 }) / (o.memory?.total || 1);
    const ossd = 100 * (1 - (o.disk?.free || 0) / (o.disk?.total || 1));
    const or = `<div class="gauges">
      ${gauge("CPU", num(o.cpu, 0) + "%", `${o.cpus ?? "?"} Kerne`, o.cpu, spark(hist.ocpu, 100), o.cpu > 90)}
      ${gauge("RAM", num(oram, 0) + "%", `${gb(used(o.memory || { total: 0, available: 0 }))} / ${gb(o.memory?.total || 0)}`, oram)}
      ${gauge("SSD", num(ossd, 0) + "%", `${gb((o.disk?.total || 0) - (o.disk?.free || 0))} / ${gb(o.disk?.total || 0)}`, ossd)}
    </div>`;
    return `<div class="machine"><div class="glow">🍓 prismo (pi)</div>${pi}</div><div class="machine"><div class="glow">☁️ oracle</div>${or}</div>`;
  }

  // --- the big panels (every 5 seconds) ---
  function services(svc) {
    const names = { "ytmp34": "Backup-Converter", "ytmp34-proxy": "Proxy für Oracle", "untis-watch.timer": "WebUntis Tracker",
      "tailscaled": "Tailscale", "ytmp34-update.timer": "nächtliches Update" };
    return Object.entries(svc || {}).map(([k, v]) => `<span class="pill ${v === "active" ? "ok" : "bad"}">${v === "active" ? "😁" : "😠"} ${esc(names[k] || k)}</span>`).join("");
  }

  function render(d) {
    const o = d.oracle || {}, p = d.pi, u = p?.untis || {};
    const last = (o.recent || [])[0];
    const th = p?.throttle;
    const throttleNow = th ? (th.now.length ? `<span class="bad">${th.now.map(x => THROTTLE[x] || x).join(", ")}</span>` : `<span class="ok">alles gut 😁</span>`) : "?";
    const throttleBoot = th ? (th.since_boot.length ? `<span class="meh">${th.since_boot.map(x => THROTTLE[x] || x).join(", ")}</span>` : `<span class="ok">nie 👍</span>`) : "?";
    return `
    <section class="panel"><h2 class="glow">prismo hardware</h2>
      <div class="big glow">${p ? `<span class="ok">● ONLINE</span>` : `<span class="bad">● OFFLINE</span>`}</div>
      ${p ? row("Modell", esc(p.model)) + row("Name", esc(p.host))
        + row("läuft seit", dur(p.uptime))
        + row("Chip-Temperatur", p.cpu_temp == null ? "?" : num(p.cpu_temp) + " °C")
        + (p.gpu_temp != null ? row("GPU-Sensor", num(p.gpu_temp) + " °C") : "")
        + (p.volts != null ? row("Kernspannung", num(p.volts, 3) + " V") : "")
        + (p.arm_clock != null ? row("CPU-Takt", num(p.arm_clock / 1e6, 0) + " MHz") : "")
        + (p.core_clock != null ? row("GPU-Takt", num(p.core_clock / 1e6, 0) + " MHz") : "")
        + row("Strom & Hitze jetzt", throttleNow) + row("seit dem Start", throttleBoot)
        + row("WLAN", p.wifi ? `${esc(p.ssid || p.wifi.iface)} · ${p.wifi.dbm} dBm ${p.wifi.dbm > -60 ? "📶 super" : p.wifi.dbm > -72 ? "📶 ok" : "🥴 schwach"}` : "?")
        + (p.net?.rx_total != null ? row("Daten seit Start", `↓ ${gb(p.net.rx_total)} · ↑ ${gb(p.net.tx_total)}`) : "")
        + row("Swap", `${mb(p.memory.swap_total - p.memory.swap_free)} benutzt`)
        + row("Load", (p.load || []).map(x => num(x, 2)).join(" · "))
        + (p.processes ? row("Prozesse", p.processes) : "")
        + (p.os ? row("System", `${esc(p.os)} · Kernel ${esc(p.kernel)}`) : "")
        + `<div style="margin-top:8px">${services(p.services)}</div>`
        : `<p class="outline">PRISMO antwortet nicht. Ausgesteckt, umgezogen oder kein WLAN? 🔌</p><small>${esc(d.pi_error || "")}</small>`}
    </section>

    ${p?.top?.length ? `<section class="panel"><h2 class="glow">was läuft gerade</h2>
      ${p.top.map(x => row(esc(x.name), `${num(x.cpu)}% CPU · ${mb(x.rss)}`)).join("")}
      <small>Top-Prozesse nach CPU (Durchschnitt seit Prozessstart)</small></section>` : ""}

    <section class="panel"><h2 class="glow">oracle cloud</h2>
      ${row("YouTube zufrieden?", yes(o.youtube_ok, "JA 😁", "BLOCKIERT 😱"))
      + row("Umweg über PRISMO?", o.proxy ? yes(o.proxy_ok, "JA 🍓➡️☁️", "PROXY WEG 😠") : `<span class="meh">nein (direkt)</span>`)
      + row("konvertiert gerade", `${o.queue?.running ?? 0} / ${o.queue?.slots ?? "?"} · ${o.queue?.waiting ?? 0} warten`)
      + row("Leute auf der Seite", `${o.active ?? 0} 👀`)
      + row("yt-dlp", esc(o.yt_dlp))
      + row("Server läuft seit", dur(o.server_uptime || 0))
      + row("Maschine läuft seit", dur(o.uptime || 0))
      + row("Load", (o.load || []).map(x => num(x, 2)).join(" · "))}
    </section>

    <section class="panel"><h2 class="glow">youtube converter</h2>
      ${last ? `<div class="big glow small" style="font-size:22px">${last.fmt === "mp3" ? "🎵" : "🎬"} ${esc(last.title)}</div>`
        + row("wann", ago(last.at)) + row("Format", last.fmt.toUpperCase()) + row("Größe", mb(last.size))
        + row("Videolänge", dur(last.duration)) + row("gedauert", `${num(last.took)} s ${last.took < 20 ? "⚡" : "🐢"}`)
        : `<p class="outline">Seit dem Serverstart (${dur(o.server_uptime || 0)}) noch nichts konvertiert. 🦗</p>`}
      ${(o.recent || []).length > 1 ? `<small>davor:</small><ul>${o.recent.slice(1).map(r => `<li>${r.fmt === "mp3" ? "🎵" : "🎬"} ${esc(r.title)} <small>(${ago(r.at)})</small></li>`).join("")}</ul>` : ""}
      ${row("insgesamt", `${num(o.totals?.videos ?? 0, 0)} Videos · ${mb(o.totals?.bytes || 0)}`)}
    </section>

    <section class="panel"><h2 class="glow">webuntis tracker</h2>
      ${p ? row("Klasse", esc(u.class || "?")) + row("zuletzt geschaut", isoAgo(u.checked))
        + row("Zustand", u.fails ? `<span class="bad">${u.fails}× hintereinander fehlgeschlagen 😵</span>` : `<span class="ok">läuft 😁</span>`)
        + row("Stunden im Blick", u.lessons ?? "?")
        + row("nächste Stunde", u.next ? `${esc(when(u.next.start))} · ${esc(u.next.subject)}` : "keine 🏖️")
        + `<small>was demnächst anders ist:</small>`
        + (u.irregular?.length ? `<ul>${u.irregular.map(l => `<li>${ICON[l.status] || "•"} ${esc(when(l.start))} ${esc(l.subject)}${l.rooms?.length ? ` <small>(${esc(l.rooms.join(", "))})</small>` : ""}</li>`).join("")}</ul>` : `<p>nix, alles normal 😴</p>`)
        + `<small>letzte Benachrichtigungen:</small>`
        + (u.pushes?.length ? `<ul>${u.pushes.map(x => `<li>${x.urgent ? "🚨" : "📣"} ${esc(x.title)} <small>${isoAgo(x.at)}</small><br><small>${esc(x.message).replace(/\n/g, "<br>")}</small></li>`).join("")}</ul>` : `<p>noch keine 📭</p>`)
        : `<p class="outline">Der Tracker wohnt auf PRISMO, und PRISMO schläft gerade. 💤</p>`}
    </section>

    <section class="panel"><h2 class="glow">unfälle</h2>
      ${(o.errors || []).length ? `<ul>${o.errors.map(e => `<li>🤕 <b>${esc(e.code)}</b> ${esc(e.text)} <small>(${ago(e.at)})</small></li>`).join("")}</ul>`
        : `<p class="outline">Keine Unfälle seit dem Serverstart. 😁👍</p>`}
    </section>`;
  }

  function show(d, pw) {
    record(d);
    const root = el();
    root.innerHTML = `<div class="holo"></div><div class="wrap">
      <header class="hero">
        <div><div class="glow logo">prismo</div><div class="glow slogan">fabios kleiner helfer</div></div>
        <div class="prism"><i></i><i></i></div>
      </header>
      <div class="pbar"><span class="glow small" style="font-size:20px">🔴 LIVE · Rest in <span id="pie-left">5</span> s</span>
        <span><button class="btn mint" type="button" data-r>NOCHMAL 🔄</button> <button class="btn" type="button" data-x>ZUMACHEN 📦</button></span></div>
      <section class="panel wide"><h2 class="glow">live-o-meter</h2><div id="pie-live">${live(d)}</div></section>
      <div class="grid" id="pie-grid" style="margin-top:14px">${render(d)}</div>
      <section class="panel wide" style="margin-top:14px">
        <div class="flap">
          <div><div class="smile">👍😁</div><div class="glow small label">Micro-USB</div></div>
          <div><div class="smile">😠</div><div class="glow small label">USB-C</div></div>
          <div class="glow small label" style="font-size:30px">USB · PWR</div>
          <div class="care glow small">Bitte mit Vorsicht umgehen<br>NICHT SCHÜTTELN du gundi</div>
          <div class="vert glow small">assembled 19.11.2026</div>
        </div>
        <div class="back outline" style="margin-top:12px">
          <p>„PRISMO“, Fabios erstes physisches Projekt, ist ein kleines aber feines Stück Technologie: ein Raspberry Pi Zero 2 W in einer TicTac-Schachtel.</p>
          <p>ENTHALTEN IST: ein WebUntis Tracker, ein YouTube zu MP3/MP4 Converter, ein Proxy, und diese Seite hier. Bleib unglaublich gespannt auf neue Aktualisierungen.</p>
          <p style="font-size:12px">PRISMO ist nicht verantwortlich für Verletzungen oder Tod.</p>
        </div>
        ${barcode()}
        <div class="glow" style="text-align:center;font-size:34px;margin-top:8px">©fabio inc.</div>
      </section></div>`;
    root.querySelector("[data-x]").onclick = close;
    root.querySelector("[data-r]").onclick = () => refresh(pw, true);
    clearInterval(timer);
    left = 5;
    // every second: the live strip. every 5 s: the big panels
    timer = setInterval(() => {
      left = left <= 1 ? 5 : left - 1;
      const l = document.getElementById("pie-left"); if (l) l.textContent = left;
      refresh(pw, left === 5);
    }, 1000);
  }

  async function refresh(pw, all) {
    if (busy) return;  // a slow answer shouldn't pile up requests
    busy = true;
    try {
      const res = await fetchPie(pw);
      if (!res.ok) { clearInterval(timer); return gate("der Code geht plötzlich nicht mehr 🤔"); }
      record(res.body);
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

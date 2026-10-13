(function () {
  const s = document.currentScript;
  const SITE = s.dataset.site;
  const API = s.dataset.api || new URL(s.src).origin;
  const history = [];
  let tagline = "Happy to help";
  let actions = [];          // booking/order links this business really has
  let voiceTurn = false;     // last question came from the mic
  let readAloud = false;     // header speaker toggle
  const SHOW_STATS = s.dataset.stats === "1";   // our own pages show model + speed under answers
  let OWNER_TOKEN = "";                          // set only on our preview page, for the owner
  if (s.dataset.owner === "1") {
    try { OWNER_TOKEN = (JSON.parse(localStorage.getItem("fa_tokens") || "{}"))[SITE] || ""; } catch (e) {}
  }

  /* ---------- line icons (same family as the landing page) ---------- */
  const P = d => `<path d="${d}"/>`;
  const C = (x, y, r) => `<circle cx="${x}" cy="${y}" r="${r}"/>`;
  const ICONS = {
    coffee: P("M5 10h11v4a5 5 0 0 1-5 5h-1a5 5 0 0 1-5-5z") + P("M16 11h1.5a2.5 2.5 0 0 1 0 5H16") + P("M8 3c-1 1.2 1 2 0 3.4M11 3c-1 1.2 1 2 0 3.4M14 3c-1 1.2 1 2 0 3.4") + P("M3 21h16"),
    book: P("M3 5.5c3-1.3 6-1.3 9 .8 3-2.1 6-2.1 9-.8V19c-3-1.3-6-1.3-9 .8-3-2.1-6-2.1-9-.8z") + P("M12 6.3v13.5"),
    polish: P("M10 2.5h4v5.5h-4z") + P("M7 11a3 3 0 0 1 3-3h4a3 3 0 0 1 3 3v8a3 3 0 0 1-3 3h-4a3 3 0 0 1-3-3z") + P("M10 13v5"),
    pizza: P("M12 21.5 3.5 5.5a17 17 0 0 1 17 0z") + P("M4.7 7.8a15 15 0 0 1 14.6 0") + C(10, 11.5, 1.2) + C(14, 12.5, 1.1) + C(12, 16, 1),
    hanger: P("M10.4 5.2A1.7 1.7 0 1 1 12 7v1.2") + P("M12 8.2 3 14.5h18z") + P("M5 14.5v5h14v-5"),
    sparkle: P("M12 3l1.8 5.4L19 10l-5.2 1.6L12 17l-1.8-5.4L5 10l5.2-1.6z") + P("M19 16l.7 2 2 .7-2 .7-.7 2-.7-2-2-.7 2-.7z"),
    cloche: P("M3.5 17.5h17") + P("M5 17.5a7 7 0 0 1 14 0") + P("M12 10.5V9") + P("M10.5 9h3"),
    glass: P("M7 3h10l-1 8a4 4 0 0 1-8 0z") + P("M12 15v6") + P("M8.5 21h7"),
    cap: P("M2 9l10-5 10 5-10 5z") + P("M6 11v5c3 2 9 2 12 0v-5") + P("M22 9v5"),
    flower: C(12, 7.5, 2.8) + C(7.8, 11, 2.8) + C(16.2, 11, 2.8) + C(9.5, 15.5, 2.8) + C(14.5, 15.5, 2.8) + C(12, 11.8, 1.4),
    chat: P("M4 5h16v10H10l-5 4v-4H4z"),
    mic: P("M12 3a3 3 0 0 1 3 3v5a3 3 0 0 1-6 0V6a3 3 0 0 1 3-3z") + P("M5.5 11a6.5 6.5 0 0 0 13 0") + P("M12 17.5V21"),
    sun: C(12, 12, 4) + P("M12 2.5v2M12 19.5v2M4.6 4.6l1.4 1.4M18 18l1.4 1.4M2.5 12h2M19.5 12h2M4.6 19.4 6 18M18 6l1.4-1.4"),
    moon: P("M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5z"),
    speaker: P("M4 9.5h3.5L12 6v12l-4.5-3.5H4z") + P("M15.5 9a4 4 0 0 1 0 6") + P("M18 6.5a7.5 7.5 0 0 1 0 11"),
    send: P("M4 12l16-8-6 16-2.5-6.5z") + P("M11.5 13.5 20 4"),
    cal: P("M4 6h16v14H4z") + P("M4 10h16") + P("M8 3.5v4M16 3.5v4"),
    bag: P("M5 8h14l-1 12H6z") + P("M9 8a3 3 0 0 1 6 0"),
  };
  const EMOJI_ICON = { "☕": "coffee", "📚": "book", "📖": "book", "💅": "polish", "🍕": "pizza", "👗": "hanger", "👕": "hanger",
    "✦": "sparkle", "✨": "sparkle", "🍽️": "cloche", "🍔": "cloche", "🥐": "cloche", "🍰": "cloche", "🍦": "cloche",
    "🍷": "glass", "🍺": "glass", "🍸": "glass", "🧋": "glass", "🎓": "cap", "🌸": "flower", "💐": "flower" };
  const TYPE_ICON = { food: "cloche", drinks: "glass", beauty: "polish", fashion: "hanger", books: "book", education: "cap", other: "sparkle" };
  const svg = (k, cls = "") => `<svg class="fa-i ${cls}" viewBox="0 0 24 24" aria-hidden="true">${ICONS[k] || ICONS.sparkle}</svg>`;

  document.getElementById("fa-root")?.remove();
  document.getElementById("fa-style")?.remove();
  const style = document.createElement("style");
  style.id = "fa-style";
  style.textContent = `
  #fa-root{--fa-brand:#24211D;--fa-ink:#24211D;--fa-ivory:#F3EEE4;--fa-line:rgba(36,33,29,.1);
    --fa-bg:#EDE9E3;--fa-card:#fff;--fa-text:#1A1714;--fa-sub:#5C564D;--fa-bar:#fff;--fa-field:#fff;--fa-edge:rgba(36,33,29,.14);--fa-glow:10%;
    font:14px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;color:var(--fa-ink)}
  #fa-root.fa-night{--fa-ink:#EFE8DC;--fa-line:rgba(239,232,220,.1);
    --fa-bg:#181612;--fa-card:#24211C;--fa-text:#EFE8DC;--fa-sub:#ABA396;--fa-bar:#1E1B17;--fa-field:#2A2621;--fa-edge:rgba(239,232,220,.16);--fa-glow:18%}
  #fa-root *{box-sizing:border-box}
  #fa-root .fa-i{width:1.15em;height:1.15em;fill:none;stroke:currentColor;stroke-width:1.6;stroke-linecap:round;stroke-linejoin:round;flex:none}

  /* ---------- bubble: floats, flips logo <-> signature icon ---------- */
  #fa-bubble{position:fixed;bottom:24px;right:24px;width:64px;height:64px;border-radius:50%;padding:3px;border:none;
    background:var(--fa-brand);box-shadow:0 10px 24px -6px rgba(0,0,0,.35);cursor:pointer;z-index:2147483000;perspective:300px;
    transition:transform .3s;animation:fa-float 5s ease-in-out infinite}
  #fa-bubble:hover{transform:scale(1.06)}
  @keyframes fa-float{50%{translate:0 -6px}}
  #fa-flip{position:relative;width:100%;height:100%;transform-style:preserve-3d}
  #fa-flip.fa-on{animation:fa-flip 10s ease-in-out infinite}
  @keyframes fa-flip{0%,70%{transform:rotateY(0)}77%,90%{transform:rotateY(180deg)}97%,100%{transform:rotateY(360deg)}}
  .fa-front,.fa-back{position:absolute;inset:0;backface-visibility:hidden;-webkit-backface-visibility:hidden}
  .fa-back{transform:rotateY(180deg);border-radius:50%;background:var(--fa-brand);color:var(--fa-ivory);display:grid;place-items:center;
    box-shadow:inset 0 0 0 1px rgba(255,255,255,.25)}
  .fa-back .fa-i{width:56%;height:56%;stroke-width:1.2}
  .fa-logo{width:100%;height:100%;border-radius:50%;background:#fff;display:grid;place-items:center;overflow:hidden;color:#24211D}
  .fa-logo > .fa-i{width:50%;height:50%}
  .fa-logo.fa-dark{background:#24211D}
  .fa-logo img{width:78%;height:78%;object-fit:contain}

  /* ---------- small effect above bubble ---------- */
  #fa-fx{position:fixed;right:24px;bottom:84px;width:64px;height:60px;pointer-events:none;z-index:2147482999;animation:fa-float 5s ease-in-out infinite;color:var(--fa-brand)}
  #fa-fx span{position:absolute;bottom:0;opacity:0;width:14px;height:14px;display:grid;place-items:center}
  #fa-fx span .fa-i{width:14px;height:14px;stroke-width:1.5}
  .fa-steam span{width:7px;height:26px;border-radius:50%;background:linear-gradient(to top,rgba(120,120,120,.45),transparent);
    filter:blur(3px);animation:fa-steam 3.6s ease-in-out infinite}
  @keyframes fa-steam{0%{transform:translateY(8px);opacity:0}30%{opacity:.8}100%{transform:translate(4px,-34px) scaleX(1.8);opacity:0}}
  .fa-steam span.fa-emo{width:14px;height:14px;background:none;filter:none;animation:fa-rise 3.6s ease-in infinite}
  .fa-rise span{animation:fa-rise 3.2s ease-in infinite}
  @keyframes fa-rise{0%{transform:translateY(6px) scale(.7);opacity:0}20%{opacity:.9}100%{transform:translate(-3px,-42px) scale(1);opacity:0}}
  .fa-fall span{animation:fa-fall 4.5s ease-in-out infinite}
  @keyframes fa-fall{0%{transform:translateY(-44px) rotate(-15deg);opacity:0}25%{opacity:.9}100%{transform:translate(6px,0) rotate(20deg);opacity:0}}
  .fa-twinkle span{animation:fa-twinkle 2.8s ease-in-out infinite}
  @keyframes fa-twinkle{0%,100%{opacity:0;transform:scale(.4) rotate(0)}50%{opacity:.9;transform:scale(1) rotate(20deg)}}
  #fa-fx span:nth-child(1){left:12px;animation-delay:0s}
  #fa-fx span:nth-child(2){left:26px;animation-delay:1.2s}
  #fa-fx span:nth-child(3){left:40px;animation-delay:2.4s}
  .fa-twinkle span:nth-child(1){bottom:6px}.fa-twinkle span:nth-child(2){bottom:28px}.fa-twinkle span:nth-child(3){bottom:14px}
  #fa-root.fa-is-open #fa-fx{display:none}
  #fa-root.fa-is-open #fa-bubble,#fa-root.fa-is-open #fa-flip{animation:none}

  /* ---------- panel ---------- */
  #fa-panel{position:fixed;bottom:100px;right:24px;width:370px;max-width:calc(100vw - 32px);height:560px;max-height:calc(100vh - 120px);
    display:flex;flex-direction:column;overflow:hidden;border-radius:22px;z-index:2147483000;
    background:var(--fa-bg);
    border:1px solid var(--fa-line);box-shadow:0 30px 60px -24px rgba(36,33,29,.45);
    opacity:0;transform:translateY(16px) scale(.98);visibility:hidden;transition:opacity .3s,transform .3s,visibility .3s}
  #fa-panel.fa-open{opacity:1;transform:none;visibility:visible}
  #fa-head{display:flex;align-items:center;gap:10px;padding:14px 14px 14px 16px;color:#fff;
    background:linear-gradient(135deg,var(--fa-brand),color-mix(in srgb,var(--fa-brand) 62%,#000))}
  #fa-title{font-weight:600;font-size:15px;line-height:1.2}
  #fa-sub{font-size:12px;opacity:.75}
  .fa-hbtn{background:none;border:none;color:#fff;cursor:pointer;opacity:.7;width:32px;height:32px;border-radius:50%;display:grid;place-items:center;font-size:16px;transition:opacity .2s,background .2s}
  .fa-hbtn:hover{opacity:1;background:rgba(255,255,255,.12)}
  .fa-hbtn[aria-pressed=true]{opacity:1;background:rgba(255,255,255,.2)}
  #fa-mode{margin-left:auto}
  #fa-mode .fa-sun{display:none}
  #fa-root.fa-night #fa-mode .fa-sun{display:block}
  #fa-root.fa-night #fa-mode .fa-moon{display:none}
  #fa-close{font-size:22px}

  /* ---------- avatar states: idle / listening / thinking / answering ---------- */
  #fa-avatar{position:relative;width:36px;height:36px;flex:none}
  #fa-avatar .fa-logo{box-shadow:0 0 0 2px rgba(255,255,255,.35)}
  #fa-avatar::after{content:"";position:absolute;inset:-5px;border-radius:50%;border:2px solid transparent;opacity:0;transition:opacity .2s}
  .fa-st-idle #fa-avatar{animation:fa-breathe 3.5s ease-in-out infinite}
  @keyframes fa-breathe{50%{transform:scale(1.05)}}
  .fa-st-listening #fa-avatar::after{opacity:1;border-color:rgba(255,255,255,.6);animation:fa-ping 1.4s ease-out infinite}
  @keyframes fa-ping{0%{transform:scale(.9);opacity:.9}100%{transform:scale(1.3);opacity:0}}
  .fa-st-thinking #fa-avatar::after{opacity:1;border-color:#fff transparent transparent transparent;animation:fa-orbit .9s linear infinite}
  @keyframes fa-orbit{to{transform:rotate(360deg)}}
  .fa-st-answering #fa-avatar{animation:fa-pop .5s ease}
  @keyframes fa-pop{40%{transform:scale(1.14)}}

  /* ---------- messages ---------- */
  #fa-msgs{flex:1;overflow-y:auto;padding:16px;display:flex;flex-direction:column;gap:10px;background:radial-gradient(120% 55% at 100% 0%,color-mix(in srgb,var(--fa-brand) var(--fa-glow),transparent),transparent 65%),var(--fa-bg)}
  .fa-m{max-width:86%;padding:10px 14px;border-radius:16px;word-wrap:break-word;font-size:14.5px;line-height:1.5;animation:fa-in .3s ease}
  @keyframes fa-in{from{opacity:0;transform:translateY(6px)}}
  .fa-u{align-self:flex-end;background:var(--fa-brand);color:#fff;font-weight:500;border-bottom-right-radius:4px}
  .fa-b{align-self:flex-start;background:var(--fa-card);color:var(--fa-text);border:1px solid var(--fa-edge);border-bottom-left-radius:4px;box-shadow:0 1px 2px rgba(36,33,29,.06)}
  .fa-m p{margin:0 0 6px}.fa-m p:last-child{margin:0}
  .fa-m ul{margin:4px 0 6px;padding-left:18px}.fa-m li{margin:2px 0}
  .fa-links{display:flex;flex-wrap:wrap;gap:6px;margin-top:8px}
  .fa-src{display:inline-flex;align-items:center;font-size:12px;text-decoration:none;border-radius:999px;padding:3px 10px;
    color:var(--fa-text);border:1px solid var(--fa-edge);transition:background .2s}
  .fa-src:hover{background:var(--fa-line)}
  .fa-act{display:inline-flex;align-items:center;gap:6px;font-size:13px;font-weight:600;text-decoration:none;border-radius:999px;padding:6px 14px;
    background:var(--fa-brand);color:#fff;transition:filter .2s,transform .2s}
  .fa-act:hover{filter:brightness(1.15);transform:translateY(-1px)}
  .fa-meta{margin-top:8px;padding-top:7px;border-top:1px solid var(--fa-line);font-size:11.5px;color:var(--fa-sub);letter-spacing:.01em}
  .fa-fix{display:inline-block;margin-top:7px;margin-left:8px;background:none;border:none;padding:0;font:inherit;font-size:12px;color:var(--fa-brand);text-decoration:underline;text-underline-offset:2px;cursor:pointer}
  .fa-edit{margin-top:8px;display:grid;gap:6px}
  .fa-edit textarea{width:100%;min-height:76px;resize:vertical;border:1px solid var(--fa-edge);border-radius:10px;padding:8px 10px;font:inherit;color:var(--fa-text);background:var(--fa-field)}
  .fa-edit div{display:flex;gap:6px;align-items:center}
  .fa-edit button{border:none;border-radius:999px;padding:5px 12px;font:inherit;font-size:12.5px;cursor:pointer}
  .fa-edit .fa-save{background:var(--fa-brand);color:#fff}
  .fa-edit .fa-cancel{background:var(--fa-line);color:var(--fa-text)}
  .fa-edit small{font-size:11.5px;color:var(--fa-sub)}
  .fa-dots span{display:inline-block;width:6px;height:6px;margin:0 2px;border-radius:50%;background:var(--fa-brand);animation:fa-blink 1.2s infinite}
  .fa-dots span:nth-child(2){animation-delay:.2s}.fa-dots span:nth-child(3){animation-delay:.4s}
  @keyframes fa-blink{0%,80%,100%{opacity:.25}40%{opacity:1}}

  /* ---------- input row ---------- */
  #fa-row{display:flex;gap:8px;padding:12px;border-top:1px solid var(--fa-line);background:var(--fa-bar);align-items:center}
  #fa-in{flex:1;min-width:0;border:1px solid var(--fa-edge);border-radius:999px;padding:10px 14px;font:inherit;outline:none;background:var(--fa-field);color:var(--fa-text)}
  #fa-in::placeholder{color:var(--fa-sub)}
  #fa-in:focus{border-color:var(--fa-brand)}
  .fa-rbtn{width:40px;height:40px;flex:none;border-radius:50%;display:grid;place-items:center;cursor:pointer;font-size:17px;transition:all .25s}
  #fa-mic{border:1px solid var(--fa-edge);background:var(--fa-field);color:var(--fa-text)}
  #fa-mic:hover{border-color:var(--fa-brand)}
  #fa-mic.fa-on{background:var(--fa-brand);color:#fff;border-color:var(--fa-brand);animation:fa-micpulse 1.3s ease-out infinite}
  @keyframes fa-micpulse{0%{box-shadow:0 0 0 0 color-mix(in srgb,var(--fa-brand) 45%,transparent)}100%{box-shadow:0 0 0 12px transparent}}
  #fa-send{border:none;background:var(--fa-brand);color:#fff}
  #fa-send:hover{filter:brightness(1.15)}
  #fa-foot{text-align:center;font-size:11px;line-height:1.4;color:var(--fa-sub);padding:0 12px 8px;background:var(--fa-bar)}
  @media (prefers-reduced-motion:reduce){#fa-bubble,#fa-flip,#fa-avatar,#fa-avatar::after,.fa-m,#fa-mic.fa-on{animation:none!important}#fa-fx{display:none}}`;
  document.head.appendChild(style);

  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  const canSpeak = "speechSynthesis" in window;

  const root = document.createElement("div");
  root.id = "fa-root";
  root.className = "fa-st-idle";
  root.innerHTML = `
    <button id="fa-bubble" aria-label="Open chat">
      <div id="fa-flip"><div class="fa-logo fa-front">${svg("chat")}</div><div class="fa-back"></div></div>
    </button>
    <div id="fa-panel" role="dialog" aria-label="Chat with us">
      <div id="fa-head">
        <div id="fa-avatar"><div class="fa-logo">${svg("chat")}</div></div>
        <div><div id="fa-title">Ask us anything</div><div id="fa-sub">Happy to help</div></div>
        <button class="fa-hbtn" id="fa-mode" aria-label="Switch to dark" title="Light or dark">${svg("moon", "fa-moon")}${svg("sun", "fa-sun")}</button>
        ${canSpeak ? `<button class="fa-hbtn" id="fa-spk" aria-pressed="false" aria-label="Read answers aloud" title="Read answers aloud">${svg("speaker")}</button>` : ""}
        <button class="fa-hbtn" id="fa-close" aria-label="Close">×</button>
      </div>
      <div id="fa-msgs" aria-live="polite"></div>
      <div id="fa-row">
        <input id="fa-in" placeholder="Ask us anything…" aria-label="Your question">
        ${SR ? `<button class="fa-rbtn" id="fa-mic" aria-label="Ask by voice" title="Ask by voice">${svg("mic")}</button>` : ""}
        <button class="fa-rbtn" id="fa-send" aria-label="Send">${svg("send")}</button>
      </div>
      <div id="fa-foot">AI answers from our website. Please confirm allergies and anything important with us.</div>
    </div>`;
  document.body.appendChild(root);

  const panel = root.querySelector("#fa-panel");
  const msgs = root.querySelector("#fa-msgs");
  const input = root.querySelector("#fa-in");
  const sub = root.querySelector("#fa-sub");
  const mic = root.querySelector("#fa-mic");
  const spk = root.querySelector("#fa-spk");
  let state = "idle";

  /* ---------- light / dark ---------- */
  let ownerTheme = "auto", pageTheme = "", visitorTheme = "";
  try { const v = localStorage.getItem("fa_chat_theme"); if (v === "light" || v === "dark") visitorTheme = v; } catch (e) {}
  const nightQuery = window.matchMedia ? matchMedia("(prefers-color-scheme: dark)") : null;
  function applyTheme() {
    // the visitor's own choice wins, then the owner's default, then the page or device
    const night = visitorTheme ? visitorTheme === "dark"
      : ownerTheme !== "auto" ? ownerTheme === "dark"
      : pageTheme ? pageTheme === "dark" : !!(nightQuery && nightQuery.matches);
    root.classList.toggle("fa-night", night);
    const mode = root.querySelector("#fa-mode");
    if (mode) mode.setAttribute("aria-label", night ? "Switch to light" : "Switch to dark");
  }
  nightQuery?.addEventListener?.("change", applyTheme);
  // our own landing page tells the chat when its light/dark switch changes
  window.addEventListener("fa-theme", e => { pageTheme = e.detail === "dark" || e.detail === "light" ? e.detail : ""; applyTheme(); });
  if (s.dataset.theme) pageTheme = s.dataset.theme;
  applyTheme();

  function setState(st) {
    state = st;
    root.classList.remove("fa-st-idle", "fa-st-listening", "fa-st-thinking", "fa-st-answering");
    root.classList.add("fa-st-" + st);
    sub.textContent = st === "thinking" ? "Thinking…" : st === "listening" ? "Listening…" : tagline;
  }

  fetch(`${API}/site/${SITE}`).then(r => r.json()).then(d => {
    if (d.name) root.querySelector("#fa-title").textContent = d.name;
    if (d.tagline) { tagline = d.tagline; if (state === "idle") sub.textContent = tagline; }
    if (d.brand) root.style.setProperty("--fa-brand", d.brand);
    ownerTheme = d.theme || "auto";
    applyTheme();
    actions = d.actions || [];
    if (d.logo) root.querySelectorAll(".fa-logo").forEach(box => {
      const img = new Image();
      img.onload = () => { box.textContent = ""; box.appendChild(img); if (d.light_logo) box.classList.add("fa-dark"); };
      img.src = d.logo;
    });
    const eff = d.effect || {};
    const icon = EMOJI_ICON[eff.emoji] || TYPE_ICON[d.type] || "sparkle";
    if (eff.motion) {
      root.querySelector(".fa-back").innerHTML = svg(icon);   // logo flips to the signature icon and back
      root.querySelector("#fa-flip").classList.add("fa-on");
      const fx = document.createElement("div");
      fx.id = "fa-fx";
      fx.className = "fa-" + eff.motion;
      for (let i = 0; i < 3; i++) {
        const sp = document.createElement("span");
        if (eff.motion !== "steam") sp.innerHTML = svg(icon);
        else if (i === 1) { sp.innerHTML = svg(icon); sp.className = "fa-emo"; }
        fx.appendChild(sp);
      }
      root.appendChild(fx);
    }
  }).catch(() => {});

  const norm = u => u.replace(/[).,]+$/, "").replace(/\/$/, "");
  const ACT_LABEL = { order: ["Order online", "bag"], reserve: ["Reserve a table", "cal"], book: ["Book now", "cal"] };

  function render(div, text) {
    div.textContent = "";
    text = text.replace(/\[([^\]]+)\]\((https?:\/\/[^)]+)\)/g, "$2").replace(/\*\*/g, "");
    const sm = text.match(/Source:\s*(https?:\/\/\S+)/i);
    const am = text.match(/Action:\s*(https?:\/\/\S+)/i);
    const src = sm ? norm(sm[1]) : null;
    // only show a booking button for links that really exist on their site
    const act = am ? actions.find(a => norm(a.url) === norm(am[1])) : null;
    text = text.replace(/(Source|Action):\s*\S*/gi, "").replace(/https?:\/\/\S+/g, "").trim();
    let ul = null;
    text.split("\n").forEach(line => {
      line = line.trim();
      if (!line) { ul = null; return; }
      if (/^[-•*]\s+/.test(line)) {
        if (!ul) { ul = document.createElement("ul"); div.appendChild(ul); }
        const li = document.createElement("li"); li.textContent = line.replace(/^[-•*]\s+/, ""); ul.appendChild(li);
      } else {
        ul = null; const p = document.createElement("p"); p.textContent = line; div.appendChild(p);
      }
    });
    if (act || src) {
      const box = document.createElement("div"); box.className = "fa-links";
      if (act) {
        const [label, ic] = ACT_LABEL[act.kind] || ACT_LABEL.book;
        const a = document.createElement("a");
        a.className = "fa-act"; a.href = act.url; a.target = "_blank"; a.rel = "noopener";
        a.innerHTML = svg(ic); a.append(label + " ↗");
        box.appendChild(a);
      }
      if (src) {
        const a = document.createElement("a");
        a.className = "fa-src"; a.href = src; a.target = "_blank"; a.rel = "noopener";
        a.textContent = src.toLowerCase().endsWith(".pdf") ? "View PDF ↗" : "View source ↗";
        box.appendChild(a);
      }
      div.appendChild(box);
    }
    return text;
  }

  function addMsg(text, who) {
    const div = document.createElement("div");
    div.className = "fa-m " + (who === "user" ? "fa-u" : "fa-b");
    if (who === "user") div.textContent = text; else render(div, text);
    msgs.appendChild(div);
    msgs.scrollTop = msgs.scrollHeight;
    return div;
  }

  /* ---------- voice out: pick the most natural voice this device has ---------- */
  let voice = null;
  function pickVoice() {
    const all = speechSynthesis.getVoices();
    if (!all.length) return;
    const lang = (navigator.language || "en-US").toLowerCase(), base = lang.split("-")[0];
    const score = v => {
      const n = v.name.toLowerCase(), l = (v.lang || "").toLowerCase();
      let p = 0;
      if (l === lang) p += 40; else if (l.startsWith(base)) p += 25; else return -1;
      if (/natural|neural|online/.test(n)) p += 50;          // Edge's natural voices
      if (/google/.test(n)) p += 30;                          // Chrome's voices
      if (/samantha|ava|allison|aria|jenny|guy|libby|sonia|serena|daniel/.test(n)) p += 15;
      if (/david|zira|mark|espeak/.test(n)) p -= 20;          // older robotic voices
      return p;
    };
    voice = all.map(v => [score(v), v]).filter(x => x[0] >= 0).sort((a, b) => b[0] - a[0])[0]?.[1] || null;
  }
  if (canSpeak) { pickVoice(); speechSynthesis.addEventListener?.("voiceschanged", pickVoice); }
  function speak(text) {
    if (!canSpeak || !text) return;
    speechSynthesis.cancel();
    const u = new SpeechSynthesisUtterance(text.replace(/^[-•*]\s+/gm, ""));
    if (voice) { u.voice = voice; u.lang = voice.lang; }
    u.rate = 0.98;
    speechSynthesis.speak(u);
  }
  root.querySelector("#fa-mode").onclick = () => {
    visitorTheme = root.classList.contains("fa-night") ? "light" : "dark";
    try { localStorage.setItem("fa_chat_theme", visitorTheme); } catch (e) {}
    applyTheme();
  };
  if (spk) spk.onclick = () => {
    readAloud = !readAloud;
    spk.setAttribute("aria-pressed", String(readAloud));
    if (!readAloud) speechSynthesis.cancel();
  };

  /* ---------- our own pages: show which model answered, and how fast ---------- */
  function addMeta(div, m) {
    const el = document.createElement("div");
    el.className = "fa-meta";
    let t = `${m.model} on ${m.host} · ${(m.ms / 1000).toFixed(1)}s · ${Number(m.tokens).toLocaleString()} tokens`;
    if (typeof m.cost === "number") t += ` · $${m.cost.toFixed(4)}`;
    el.textContent = t;
    div.appendChild(el);
  }

  /* ---------- owner only: fix an answer right here ---------- */
  function addFix(div, q, answerText) {
    const btn = document.createElement("button");
    btn.className = "fa-fix"; btn.type = "button"; btn.textContent = "Fix this answer";
    btn.onclick = () => {
      btn.remove();
      const box = document.createElement("div"); box.className = "fa-edit";
      const ta = document.createElement("textarea"); ta.value = answerText; ta.setAttribute("aria-label", "Your answer");
      const row = document.createElement("div");
      const save = document.createElement("button"); save.className = "fa-save"; save.type = "button"; save.textContent = "Save";
      const cancel = document.createElement("button"); cancel.className = "fa-cancel"; cancel.type = "button"; cancel.textContent = "Cancel";
      const note = document.createElement("small");
      row.append(save, cancel, note); box.append(ta, row); div.appendChild(box); ta.focus();
      cancel.onclick = () => { box.remove(); div.appendChild(btn); };
      save.onclick = async () => {
        save.disabled = true; note.textContent = "Saving…";
        try {
          const r = await fetch(`${API}/office/${SITE}`, { method: "POST", headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ token: OWNER_TOKEN, action: "add_correction", q, a: ta.value }) });
          const d = await r.json().catch(() => ({}));
          if (!r.ok) { note.textContent = typeof d.detail === "string" ? d.detail : "Couldn't save."; save.disabled = false; return; }
          box.remove();
          const ok = document.createElement("div"); ok.className = "fa-meta";
          ok.textContent = "Saved. From now on, I'll answer this the way you wrote it.";
          div.appendChild(ok);
        } catch (e) { note.textContent = "Couldn't reach the server."; save.disabled = false; }
      };
    };
    div.appendChild(btn);
  }

  async function send() {
    const q = input.value.trim();
    if (!q || state === "thinking") return;
    input.value = "";
    addMsg(q, "user");
    setState("thinking");
    const wait = addMsg("", "bot");
    wait.innerHTML = `<span class="fa-dots"><span></span><span></span><span></span></span>`;
    let spoken = "";
    try {
      const r = await fetch(`${API}/chat`, { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ site_id: SITE, question: q, history }) });
      const d = await r.json();
      const a = d.answer || d.detail || "Sorry, something went wrong.";
      spoken = render(wait, a);
      if (d.answer) {
        history.push({ role: "user", content: q }, { role: "assistant", content: a });
        if (SHOW_STATS && d.meta) addMeta(wait, d.meta);
        if (OWNER_TOKEN) addFix(wait, q, spoken);
      }
    } catch (e) { spoken = render(wait, "Can't reach the server right now."); }
    msgs.scrollTop = msgs.scrollHeight;
    if (voiceTurn || readAloud) speak(spoken);
    voiceTurn = false;
    setState("answering");
    setTimeout(() => { if (state === "answering") setState(input.value ? "listening" : "idle"); }, 600);
  }

  /* ---------- voice in ---------- */
  let rec = null;
  if (mic) mic.onclick = () => {
    if (rec) { rec.stop(); return; }
    if (canSpeak) speechSynthesis.cancel();
    rec = new SR();
    rec.lang = navigator.language || "en-US";
    rec.interimResults = true;
    rec.onresult = e => {
      input.value = Array.from(e.results).map(r => r[0].transcript).join("");
      if (e.results[e.results.length - 1].isFinal) { voiceTurn = true; rec.stop(); send(); }
    };
    rec.onerror = e => {
      const why = e.error === "not-allowed" ? "Microphone access is blocked. You can type your question instead."
        : e.error === "network" ? "Voice isn't available in this browser. Try Chrome or Edge, or type your question."
        : e.error === "no-speech" ? "" : "Couldn't hear that. Try again or type your question.";
      if (why) addMsg(why, "bot");
    };
    rec.onend = () => { mic.classList.remove("fa-on"); rec = null; if (state === "listening" && !input.value.trim()) setState("idle"); };
    mic.classList.add("fa-on");
    setState("listening");
    rec.start();
  };

  input.addEventListener("input", () => {
    if (state !== "thinking") setState(input.value.trim() ? "listening" : "idle");
  });

  const toggle = () => {
    const open = panel.classList.toggle("fa-open");
    root.classList.toggle("fa-is-open", open);
    if (open && !msgs.children.length) addMsg("Hi! Ask us anything: menu, prices, hours, bookings." + (SR ? " Type or tap the mic." : ""), "bot");
    if (open) input.focus();
    else if (canSpeak) speechSynthesis.cancel();
  };
  root.querySelector("#fa-bubble").onclick = toggle;
  root.querySelector("#fa-close").onclick = toggle;
  root.querySelector("#fa-send").onclick = send;
  input.addEventListener("keydown", e => { if (e.key === "Enter") send(); });
})();
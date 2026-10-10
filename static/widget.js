(function () {
  const s = document.currentScript;
  const SITE = s.dataset.site;
  const API = s.dataset.api || new URL(s.src).origin;
  const history = [];

  const style = document.createElement("style");
  style.textContent = `
  #fa-root{--fa-brand:#1f2328;--fa-ink:#1f2328;--fa-line:rgba(0,0,0,.08);
    font:14px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;color:var(--fa-ink)}
  #fa-root *{box-sizing:border-box}
  #fa-bubble{position:fixed;bottom:24px;right:24px;width:64px;height:64px;border-radius:50%;padding:3px;border:none;
    background:var(--fa-brand);box-shadow:0 6px 18px rgba(0,0,0,.22);cursor:pointer;z-index:2147483000;transition:transform .2s}
  #fa-bubble:hover{transform:scale(1.07)}
  .fa-logo{width:100%;height:100%;border-radius:50%;background:#fff;display:flex;align-items:center;justify-content:center;overflow:hidden;font-size:24px}
  .fa-logo.fa-dark{background:var(--fa-ink)}
  .fa-logo img{width:78%;height:78%;object-fit:contain}
  #fa-panel{position:fixed;bottom:100px;right:24px;width:370px;max-width:calc(100vw - 32px);height:540px;max-height:calc(100vh - 120px);
    display:flex;flex-direction:column;overflow:hidden;border-radius:20px;z-index:2147483000;
    background:rgba(250,249,247,.85);backdrop-filter:blur(18px) saturate(160%);-webkit-backdrop-filter:blur(18px) saturate(160%);
    border:1px solid var(--fa-line);box-shadow:0 16px 40px rgba(0,0,0,.18);
    opacity:0;transform:translateY(16px) scale(.98);visibility:hidden;transition:opacity .25s,transform .25s,visibility .25s}
  #fa-panel.fa-open{opacity:1;transform:none;visibility:visible}
  #fa-head{display:flex;align-items:center;gap:10px;padding:14px 16px;color:#fff;
    background:linear-gradient(135deg,var(--fa-brand),color-mix(in srgb,var(--fa-brand) 60%,#000))}
  #fa-head .fa-logo{width:36px;height:36px;flex:none;font-size:16px;box-shadow:0 0 0 2px rgba(255,255,255,.35)}
  #fa-title{font-weight:600;font-size:15px;line-height:1.2}
  #fa-sub{font-size:12px;opacity:.75}
  #fa-close{margin-left:auto;background:none;border:none;color:#fff;font-size:22px;cursor:pointer;opacity:.75}
  #fa-msgs{flex:1;overflow-y:auto;padding:16px;display:flex;flex-direction:column;gap:10px}
  .fa-m{max-width:85%;padding:10px 14px;border-radius:16px;word-wrap:break-word;animation:fa-in .25s ease}
  @keyframes fa-in{from{opacity:0;transform:translateY(6px)}}
  .fa-u{align-self:flex-end;background:var(--fa-brand);color:#fff;font-weight:500;border-bottom-right-radius:4px}
  .fa-b{align-self:flex-start;background:#fff;border:1px solid var(--fa-line);border-bottom-left-radius:4px}
  .fa-m p{margin:0 0 6px}.fa-m p:last-child{margin:0}
  .fa-m ul{margin:4px 0 6px;padding-left:18px}.fa-m li{margin:2px 0}
  .fa-src{display:inline-block;margin-top:8px;font-size:12px;text-decoration:none;border-radius:999px;padding:2px 10px;
    color:var(--fa-ink);border:1px solid rgba(0,0,0,.18)}
  .fa-src:hover{background:rgba(0,0,0,.05)}
  .fa-dots span{display:inline-block;width:6px;height:6px;margin:0 2px;border-radius:50%;background:var(--fa-brand);animation:fa-blink 1.2s infinite}
  .fa-dots span:nth-child(2){animation-delay:.2s}.fa-dots span:nth-child(3){animation-delay:.4s}
  @keyframes fa-blink{0%,80%,100%{opacity:.25}40%{opacity:1}}
  #fa-row{display:flex;gap:8px;padding:12px;border-top:1px solid var(--fa-line);background:#fff}
  #fa-in{flex:1;border:1px solid rgba(0,0,0,.15);border-radius:999px;padding:10px 14px;font:inherit;outline:none;background:#fff;color:var(--fa-ink)}
  #fa-in:focus{border-color:var(--fa-brand)}
  #fa-send{border:none;background:var(--fa-brand);color:#fff;font-weight:600;border-radius:999px;padding:0 18px;font:inherit;font-weight:600;cursor:pointer}
  #fa-send:hover{filter:brightness(1.15)}
  #fa-foot{text-align:center;font-size:11px;color:#8a8f96;padding:0 0 8px;background:#fff}
  @media (prefers-reduced-motion:reduce){.fa-m{animation:none}}`;
  document.head.appendChild(style);

  const root = document.createElement("div");
  root.id = "fa-root";
  root.innerHTML = `
    <button id="fa-bubble" aria-label="Open chat"><div class="fa-logo">💬</div></button>
    <div id="fa-panel" role="dialog">
      <div id="fa-head"><div class="fa-logo">💬</div>
        <div><div id="fa-title">Ask us anything</div><div id="fa-sub">Here to Help</div></div>
        <button id="fa-close" aria-label="Close">×</button></div>
      <div id="fa-msgs"></div>
      <div id="fa-row"><input id="fa-in" placeholder="Ask a question..."><button id="fa-send">Send</button></div>
      <div id="fa-foot">Powered by FreeAgent</div>
    </div>`;
  document.body.appendChild(root);

  const panel = root.querySelector("#fa-panel");
  const msgs = root.querySelector("#fa-msgs");
  const input = root.querySelector("#fa-in");

  fetch(`${API}/site/${SITE}`).then(r => r.json()).then(d => {
    if (d.name) root.querySelector("#fa-title").textContent = d.name;
    if (d.tagline) root.querySelector("#fa-sub").textContent = d.tagline;
    if (d.brand) root.style.setProperty("--fa-brand", d.brand);
    if (d.logo) root.querySelectorAll(".fa-logo").forEach(box => {
      const img = new Image();
      img.onload = () => { box.textContent = ""; box.appendChild(img); if (d.light_logo) box.classList.add("fa-dark"); };
      img.src = d.logo;
    });
  }).catch(() => {});

  function render(div, text) {
    div.textContent = "";
    text = text.replace(/\[([^\]]+)\]\((https?:\/\/[^)]+)\)/g, "$2").replace(/\*\*/g, "");
    const m = text.match(/Source:\s*(https?:\/\/\S+)/i);
    const src = m ? m[1].replace(/[).,]+$/, "") : null;
    text = text.replace(/Source:\s*\S*/gi, "").replace(/https?:\/\/\S+/g, "").trim();
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
    if (src) {
      const a = document.createElement("a");
      a.className = "fa-src"; a.href = src; a.target = "_blank"; a.rel = "noopener";
      a.textContent = src.toLowerCase().endsWith(".pdf") ? "View PDF ↗" : "View source ↗";
      div.appendChild(a);
    }
  }

  function addMsg(text, who) {
    const div = document.createElement("div");
    div.className = "fa-m " + (who === "user" ? "fa-u" : "fa-b");
    if (who === "user") div.textContent = text; else render(div, text);
    msgs.appendChild(div);
    msgs.scrollTop = msgs.scrollHeight;
    return div;
  }

  async function send() {
    const q = input.value.trim();
    if (!q) return;
    input.value = "";
    addMsg(q, "user");
    const wait = addMsg("", "bot");
    wait.innerHTML = `<span class="fa-dots"><span></span><span></span><span></span></span>`;
    try {
      const r = await fetch(`${API}/chat`, { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ site_id: SITE, question: q, history }) });
      const d = await r.json();
      const a = d.answer || d.detail || "Sorry, something went wrong.";
      render(wait, a);
      history.push({ role: "user", content: q }, { role: "assistant", content: a });
    } catch (e) { render(wait, "Can't reach the server right now."); }
    msgs.scrollTop = msgs.scrollHeight;
  }

  const toggle = () => {
    const open = panel.classList.toggle("fa-open");
    if (open && !msgs.children.length) addMsg("Hi! Ask me anything about us: menu, prices, hours, and more.", "bot");
    if (open) input.focus();
  };
  root.querySelector("#fa-bubble").onclick = toggle;
  root.querySelector("#fa-close").onclick = toggle;
  root.querySelector("#fa-send").onclick = send;
  input.addEventListener("keydown", e => { if (e.key === "Enter") send(); });
})();
(function () {
  const s = document.currentScript;
  const SITE = s.dataset.site;
  const API = s.dataset.api || new URL(s.src).origin;
  const history = [];

  const style = document.createElement("style");
  style.textContent = `
    #fa-bubble{position:fixed;bottom:20px;right:20px;width:60px;height:60px;border-radius:50%;
      background:#fff;box-shadow:0 4px 14px rgba(0,0,0,.25);cursor:pointer;z-index:99999;
      display:flex;align-items:center;justify-content:center;font-size:28px;overflow:hidden;border:none}
    #fa-bubble img{width:100%;height:100%;object-fit:contain}
    #fa-panel{position:fixed;bottom:90px;right:20px;width:340px;max-width:calc(100vw - 40px);height:460px;
      background:#fff;border-radius:12px;box-shadow:0 6px 24px rgba(0,0,0,.25);z-index:99999;
      display:none;flex-direction:column;font-family:sans-serif;font-size:14px;color:#222}
    #fa-head{padding:12px;background:#222;color:#fff;border-radius:12px 12px 0 0;font-weight:bold}
    #fa-msgs{flex:1;overflow-y:auto;padding:10px}
    .fa-m{margin:6px 0;padding:8px 10px;border-radius:10px;max-width:85%;white-space:pre-wrap;word-wrap:break-word}
    .fa-u{background:#e8f0fe;margin-left:auto}
    .fa-b{background:#f1f1f1}
    #fa-row{display:flex;border-top:1px solid #ddd}
    #fa-in{flex:1;border:none;padding:10px;font-size:14px;outline:none}
    #fa-send{border:none;background:#222;color:#fff;padding:0 14px;cursor:pointer;border-radius:0 0 12px 0}`;
  document.head.appendChild(style);

  const bubble = document.createElement("button");
  bubble.id = "fa-bubble";
  bubble.textContent = "💬";
  const panel = document.createElement("div");
  panel.id = "fa-panel";
  panel.innerHTML = `<div id="fa-head">Ask us anything</div><div id="fa-msgs"></div>
    <div id="fa-row"><input id="fa-in" placeholder="Type a question..."><button id="fa-send">Send</button></div>`;
  document.body.append(bubble, panel);

  const msgs = panel.querySelector("#fa-msgs");
  const input = panel.querySelector("#fa-in");

  fetch(`${API}/site/${SITE}`).then(r => r.json()).then(d => {
    if (d.logo) {
      const img = document.createElement("img");
      img.src = d.logo;
      img.onerror = () => { bubble.textContent = "💬"; };
      bubble.textContent = "";
      bubble.appendChild(img);
    }
  }).catch(() => {});

  function addMsg(text, who) {
    const div = document.createElement("div");
    div.className = "fa-m " + (who === "user" ? "fa-u" : "fa-b");
    setText(div, text);
    msgs.appendChild(div);
    msgs.scrollTop = msgs.scrollHeight;
    return div;
  }

  function setText(div, text) {
    text = text.replace(/\[([^\]]+)\]\((https?:\/\/[^)]+)\)/g, "$2").replace(/\*\*/g, "");
    div.textContent = "";
    text.split(/(https?:\/\/[^\s)]+)/g).forEach(part => {
      if (/^https?:\/\//.test(part)) {
        const a = document.createElement("a");
        a.href = part; a.target = "_blank"; a.textContent = "link";
        div.appendChild(a);
      } else {
        div.appendChild(document.createTextNode(part));
      }
    });
  }

  async function send() {
    const q = input.value.trim();
    if (!q) return;
    input.value = "";
    addMsg(q, "user");
    const wait = addMsg("...", "bot");
    try {
      const r = await fetch(`${API}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ site_id: SITE, question: q, history })
      });
      const d = await r.json();
      const a = d.answer || "Sorry, something went wrong.";
      setText(wait, a);
      history.push({ role: "user", content: q }, { role: "assistant", content: a });
    } catch (e) {
      setText(wait, "Can't reach the server right now.");
    }
  }

  bubble.onclick = () => {
    const open = panel.style.display === "flex";
    panel.style.display = open ? "none" : "flex";
    if (!open && !msgs.children.length) addMsg("Hi! Ask me anything about this site.", "bot");
  };
  panel.querySelector("#fa-send").onclick = send;
  input.addEventListener("keydown", e => { if (e.key === "Enter") send(); });
})();
import os
import time
import json
from typing import Dict, Any, List
import subprocess

def _try_import(name: str):
    try:
        import importlib
        return importlib.import_module(name)
    except Exception:
        return None

st = _try_import("streamlit")
psutil = _try_import("psutil")
dotenv = _try_import("dotenv")
pd = _try_import("pandas")
if dotenv:
    try:
        dotenv.load_dotenv()
    except Exception:
        pass

from arkon_swarm import _load as swarm_load, register_node, ping_swarm  # type: ignore
from arkon_memory import _load as memory_load, ingest_document, rag_query, get_evolution_score  # type: ignore
import infinity_mode as infinity  # type: ignore
import urllib.request

def _css():
    return """
    <style>
    body { background: #0b0f1a; }
    .palace { color: #cdd9ff; }
    .glass {
        background: rgba(20, 24, 40, 0.55);
        backdrop-filter: blur(8px);
        border: 1px solid rgba(139,92,246,0.35);
        border-radius: 16px;
        padding: 16px;
        box-shadow: 0 0 20px rgba(139,92,246,0.25);
        transition: transform .2s ease, box-shadow .2s ease, opacity .3s ease;
        opacity: 0; animation: fadeIn .4s forwards;
    }
    .glass:hover { transform: translateY(-2px); box-shadow: 0 0 28px rgba(139,92,246,0.45); }
    .title { font-size: 22px; color: #93c5fd; border-left: 4px solid #8b5cf6; padding-left: 8px; margin: 8px 0; }
    .metric-bar { height: 18px; border-radius: 10px; background: #141a2e; overflow: hidden; border: 1px solid #26345c; }
    .metric-fill { height: 100%; border-radius: 10px; background: linear-gradient(90deg, #3b82f6, #8b5cf6); }
    .pulse { width: 12px; height: 12px; border-radius: 50%; background: #22c55e; box-shadow: 0 0 12px #22c55e; animation: p 1.6s infinite; display: inline-block; margin-right:8px; }
    @keyframes p { 0% {opacity:.5} 50% {opacity:1} 100% {opacity:.5} }
    @keyframes fadeIn { to { opacity:1 } }
    .room { margin-bottom: 18px; }
    </style>
    """

def _auth_ok() -> bool:
    key = os.getenv("ARCHITECT_KEY", "").strip()
    if not st:
        return False
    if "auth_ok" not in st.session_state:
        st.session_state["auth_ok"] = False
    if st.session_state.get("auth_ok"):
        return True
    with st.form("gate"):
        inp = st.text_input("Architect Key", type="password")
        ok = st.form_submit_button("Unlock Gate")
        if ok and key and inp == key:
            st.session_state["auth_ok"] = True
    return st.session_state.get("auth_ok", False)

def _metric(label: str, value: int):
    if not st:
        return
    st.write(f"{label}: {value}")
    st.markdown(f"<div class='metric-bar'><div class='metric-fill' style='width:{max(0,min(100,value))}%;'></div></div>", unsafe_allow_html=True)

def _stats() -> Dict[str, int]:
    cpu = 0
    ram = 0
    try:
        if psutil:
            cpu = int(psutil.cpu_percent(interval=0.2))
            ram = int(psutil.virtual_memory().percent)
    except Exception:
        pass
    ping_ms = 0
    base = os.getenv("ARKON_SELF_URL", "").strip() or os.getenv("APP_URL", "").strip()
    if base:
        try:
            t0 = time.perf_counter()
            req = urllib.request.Request(f"{base.rstrip('/')}/health", headers={"User-Agent": infinity._ua()})  # type: ignore
            with urllib.request.urlopen(req, timeout=6) as resp:
                _ = resp.read()
            t1 = time.perf_counter()
            ping_ms = int((t1 - t0) * 1000)
        except Exception:
            ping_ms = 999
    # Map to STR, AGI, INT (higher=better). For ping, invert.
    STR = cpu
    AGI = max(0, min(100, 100 - abs(ram - 50)))  # center balance
    INT = max(0, min(100, 100 - min(ping_ms // 5, 100)))
    return {"STR": STR, "AGI": AGI, "INT": INT, "ping_ms": ping_ms}

def _shadow_nodes() -> List[Dict[str, Any]]:
    try:
        db = swarm_load()
        nodes = db.get("nodes", [])
        return nodes
    except Exception:
        return []

def _events(n: int = 20) -> List[Dict[str, Any]]:
    try:
        db = memory_load()
        evs = db.get("events", [])
        return list(reversed(evs))[:n]
    except Exception:
        return []

def main():
    if not st:
        print("Streamlit not installed")
        return
    st.set_page_config(page_title="Sovereign Digital Palace", page_icon="🔱", layout="wide")
    st.markdown(_css(), unsafe_allow_html=True)
    if not _auth_ok():
        st.stop()
    st.sidebar.title("Sovereign Rooms")
    room = st.sidebar.radio("Navigate", ["🏛️ Throne Room", "⚔️ War Room", "👤 Shadow Realm", "📚 Archives", "🛡️ The Forge"])
    st.markdown('<div class="palace">', unsafe_allow_html=True)
    if room.startswith("🏛️"):
        st.markdown("<div class='glass room'>", unsafe_allow_html=True)
        st.markdown("<div class='title'>Throne Room</div>", unsafe_allow_html=True)
        st.success("System: Welcome, Architect Krishna")
        s = _stats()
        cpu = s.get("STR", 0)
        ram_bal = s.get("AGI", 0)
        _metric("STR (CPU)", cpu)
        _metric("AGI (RAM balance)", ram_bal)
        _metric("INT (Ping quality)", s.get("INT", 0))
        st.caption(f"Ping: {s.get('ping_ms',0)} ms")
        es = get_evolution_score(200)
        _metric("Evolution", es.get("score", 0))
        if "cpu_hist" not in st.session_state:
            st.session_state["cpu_hist"] = []
        if "ram_hist" not in st.session_state:
            st.session_state["ram_hist"] = []
        st.session_state["cpu_hist"].append(s.get("STR",0))
        st.session_state["ram_hist"].append(100 - abs(s.get("AGI",0) - 50))
        st.session_state["cpu_hist"] = st.session_state["cpu_hist"][-50:]
        st.session_state["ram_hist"] = st.session_state["ram_hist"][-50:]
        data = {"CPU": st.session_state["cpu_hist"], "RAM": st.session_state["ram_hist"]}
        try:
            if pd:
                df = pd.DataFrame(data)
                st.line_chart(df)
            else:
                st.line_chart(data)
        except Exception:
            pass
        st.markdown("<span class='pulse'></span> Online", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)
    elif room.startswith("⚔️"):
        st.markdown("<div class='glass room'>", unsafe_allow_html=True)
        st.markdown("<div class='title'>War Room</div>", unsafe_allow_html=True)
        topic = st.text_input("Reel topic", "")
        if st.button("Prepare Instagram Asset"):
            r = infinity.instagram_prepare_reel(topic or "Sovereign systems online")
            st.write(r)
            if r.get("image") and os.path.exists(r["image"]):
                st.image(r["image"])
        rows = infinity.trend_hijack().get("topics", [])
        st.write({"topics": rows})
        st.markdown("</div>", unsafe_allow_html=True)
    elif room.startswith("👤"):
        st.markdown("<div class='glass room'>", unsafe_allow_html=True)
        st.markdown("<div class='title'>Shadow Realm</div>", unsafe_allow_html=True)
        nodes = _shadow_nodes()
        if nodes:
            st.table([{"url": n.get("url",""), "status": n.get("status",""), "last_seen": n.get("last_seen","")} for n in nodes])
        u = st.text_input("Register Clone URL", "")
        c1 = st.columns(2)
        if c1[0].button("Register"):
            if u.strip():
                register_node(u.strip())
        if c1[1].button("Ping Swarm"):
            try:
                ping_swarm()
            except Exception:
                pass
        st.markdown("</div>", unsafe_allow_html=True)
    elif room.startswith("📚"):
        st.markdown("<div class='glass room'>", unsafe_allow_html=True)
        st.markdown("<div class='title'>Archives</div>", unsafe_allow_html=True)
        up = st.file_uploader("Drop a file", type=["txt","md","py","json"])
        if up is not None:
            try:
                content = up.read().decode("utf-8", "ignore")
                ingest_document(content, {"name": up.name})
                st.success("Ingested")
            except Exception:
                st.warning("Failed")
        q = st.text_input("RAG Ask", "")
        if q:
            ctx = rag_query(q, top_k=3)
            st.write({"matches": [{"meta": c.get("meta",""), "excerpt": (c.get("text","")[:300])} for c in ctx]})
        e_topic = st.text_input("Ghost Author Topic", "")
        e_out = st.text_input("Output HTML", value="ebook.html")
        if st.button("Compile E-book"):
            ok = infinity.compile_ebook_html(e_topic or "Sovereign Systems", e_out)
            st.success("Compiled" if ok else "Failed")
        st.markdown("</div>", unsafe_allow_html=True)
    else:
        st.markdown("<div class='glass room'>", unsafe_allow_html=True)
        st.markdown("<div class='title'>The Forge</div>", unsafe_allow_html=True)
        mode = st.selectbox("Mode", ["Stealth","Balanced","Aggressive"])
        kname = st.text_input("Key Name")
        kval = st.text_input("Key Value", type="password")
        if st.button("Inject Key"):
            if kname and kval:
                os.environ[kname] = kval
                try:
                    from arkon_memory import record_event  # type: ignore
                    record_event(url="local", goal="key-inject", selector="", hint=mode, action="set", result="success", notes=f"{kname}")
                except Exception:
                    pass
                st.success("Injected")
            else:
                st.warning("Missing name/value")
        code = st.text_area("Proposed main.py", height=200)
        owner = st.text_input("GitHub Owner", value="")
        repo = st.text_input("GitHub Repo", value="")
        if st.button("Test & Commit"):
            try:
                base = os.path.dirname(__file__)
                clone_path = os.path.join(base, "main_clone.py")
                master_path = os.path.join(base, "main.py")
                if code.strip():
                    with open(clone_path, "w", encoding="utf-8") as f:
                        f.write(code)
                proc = subprocess.run([os.sys.executable, clone_path, "--probe"], capture_output=True, text=True, timeout=120)
                out = (proc.stdout or "") + "\n" + (proc.stderr or "")
                ok = ("STATUS_SUCCESS" in out and proc.returncode == 0)
                st.write({"probe_output": out})
                if ok and owner and repo:
                    try:
                        from arkon_cloud import github_put_file  # type: ignore
                        with open(master_path, "rb") as fh:
                            b = fh.read()
                        pushed = github_put_file(owner, repo, "main.py", b, message="Shadow-Test pass: update main.py")
                        st.success("Committed" if pushed else "Commit failed")
                    except Exception:
                        st.warning("GitHub commit failed")
                elif ok:
                    st.success("Shadow-Test success")
                else:
                    st.warning("Shadow-Test failed")
            except Exception as e:
                st.warning(str(e))
        st.markdown("<div class='title'>System Logs</div>", unsafe_allow_html=True)
        evs = _events(40)
        for ev in evs:
            st.write(json.dumps(ev, ensure_ascii=False))
        st.markdown("</div>", unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

if __name__ == "__main__":
    main()

# app.py
import streamlit as st
import threading
import queue
import time
from datetime import datetime

from scenarios import ALL_SCENARIOS
from crew import NegotiationCrew
from utils.formatter import (
    format_ledger_panel,
    format_transcript_entry,
    format_final_report,
)

# ── Page config ────────────────────────────────────────────
st.set_page_config(
    page_title="AI Negotiation System",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ─────────────────────────────────────────────
st.markdown("""
<style>
  .main { background-color: #0e1117; }

  .chat-bubble {
    padding: 12px 16px;
    border-radius: 12px;
    margin: 8px 0;
    font-size: 14px;
    line-height: 1.6;
    border-left: 4px solid;
  }
  .bubble-a        { background:#0d1f33; border-color:#1f6feb; color:#cdd9e5; }
  .bubble-b        { background:#0d1f0d; border-color:#238636; color:#cdd9e5; }
  .bubble-mediator { background:#1f0d33; border-color:#8957e5; color:#cdd9e5; }
  .bubble-report   { background:#1f1f0d; border-color:#d29922; color:#cdd9e5; }

  .speaker-label {
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    margin-bottom: 4px;
    opacity: 0.7;
  }

  .ledger-card {
    background: #161b22;
    border: 1px solid #30363d;
    border-radius: 10px;
    padding: 14px;
    margin-bottom: 10px;
  }

  .agreed-point {
    background: #0d2b1a;
    border: 1px solid #238636;
    border-radius: 6px;
    padding: 6px 10px;
    margin: 4px 0;
    font-size: 13px;
    color: #3fb950;
  }

  .open-issue {
    background: #2b1a0d;
    border: 1px solid #d29922;
    border-radius: 6px;
    padding: 6px 10px;
    margin: 4px 0;
    font-size: 13px;
    color: #e3b341;
  }

  .status-badge {
    display: inline-block;
    padding: 4px 12px;
    border-radius: 20px;
    font-size: 12px;
    font-weight: 600;
  }
  .badge-settled    { background:#0d2b1a; color:#3fb950; border:1px solid #238636; }
  .badge-in_progress{ background:#2b1a0d; color:#e3b341; border:1px solid #d29922; }
  .badge-failed     { background:#2b0d0d; color:#f85149; border:1px solid #da3633; }

  div[data-testid="metric-container"] {
    background: #161b22;
    border: 1px solid #30363d;
    border-radius: 10px;
    padding: 12px;
  }
</style>
""", unsafe_allow_html=True)


# ── Session state init ─────────────────────────────────────
def init_state():
    defaults = {
        "running":       False,
        "done":          False,
        "transcript":    [],
        "ledger_data":   None,
        "final_report":  None,
        "result":        None,
        "msg_queue":     queue.Queue(),
        "scenario":      None,
        "error":         None,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

init_state()


# ── Sidebar — scenario builder ─────────────────────────────
with st.sidebar:
    st.title("⚖️ Negotiation Setup")
    st.markdown("---")

    mode = st.radio(
        "Scenario mode",
        ["Use a preset scenario", "Build a custom scenario"],
        index=0,
    )

    if mode == "Use a preset scenario":
        scenario_name = st.selectbox(
            "Choose scenario",
            list(ALL_SCENARIOS.keys())
        )
        selected_scenario = ALL_SCENARIOS[scenario_name]

        st.markdown("**Preview**")
        st.caption(f"Party A: {selected_scenario['party_a']['name']}")
        st.caption(f"Party B: {selected_scenario['party_b']['name']}")
        st.caption(f"Mediator: {selected_scenario['mediator_name']}")
        st.caption(f"Issues: {', '.join(selected_scenario['open_issues'])}")
        final_scenario = selected_scenario

    else:
        st.markdown("### Custom Scenario")
        title       = st.text_input("Negotiation title", "Trade Deal Negotiation")
        med_name    = st.text_input("Mediator name", "UN Mediator")

        st.markdown("**Party A**")
        pa_name     = st.text_input("Party A name", "Country Alpha")
        pa_goals    = st.text_area("Party A goals (one per line)",
                                   "Lower tariffs to 5%\nMarket access for tech exports")
        pa_redlines = st.text_area("Party A red lines (one per line)",
                                   "No tariffs above 15%")

        st.markdown("**Party B**")
        pb_name     = st.text_input("Party B name", "Country Beta")
        pb_goals    = st.text_area("Party B goals (one per line)",
                                   "Protect domestic manufacturing\nTariffs at 20%")
        pb_redlines = st.text_area("Party B red lines (one per line)",
                                   "Will not drop tariffs below 12%")

        st.markdown("**Open Issues**")
        issues_raw  = st.text_area("Issues to negotiate (one per line)",
                                   "tariff rate\nmarket access\ntrade dispute mechanism")

        final_scenario = {
            "title":        title,
            "mediator_name": med_name,
            "party_a": {
                "name":      pa_name,
                "goals":     [g.strip() for g in pa_goals.splitlines() if g.strip()],
                "red_lines": [r.strip() for r in pa_redlines.splitlines() if r.strip()],
            },
            "party_b": {
                "name":      pb_name,
                "goals":     [g.strip() for g in pb_goals.splitlines() if g.strip()],
                "red_lines": [r.strip() for r in pb_redlines.splitlines() if r.strip()],
            },
            "open_issues": [i.strip() for i in issues_raw.splitlines() if i.strip()],
        }

    st.markdown("---")

    start_btn = st.button(
        "🚀 Start Negotiation",
        disabled=st.session_state.running,
        use_container_width=True,
        type="primary",
    )

    if st.session_state.running:
        st.info("Negotiation in progress...")

    if st.session_state.done:
        if st.button("🔄 Reset", use_container_width=True):
            for k in ["running","done","transcript","ledger_data",
                      "final_report","result","error","scenario"]:
                del st.session_state[k]
            st.rerun()


# ── Background thread runner ───────────────────────────────
def run_negotiation_thread(scenario: dict, q: queue.Queue):
    """
    Runs the full NegotiationCrew in a background thread.
    Puts status updates into the queue so Streamlit can
    display progress without freezing.
    """
    try:
        q.put({"type": "status", "text": "Initializing agents..."})
        crew = NegotiationCrew(scenario)

        # Monkey-patch _log so it also sends to queue
        original_log = crew._log
        def patched_log(speaker, text):
            original_log(speaker, text)
            q.put({
                "type":    "transcript",
                "speaker": speaker,
                "text":    text,
                "ledger":  format_ledger_panel(crew.ledger),
            })
        crew._log = patched_log

        q.put({"type": "status", "text": "Negotiation started. Waiting for first offer..."})
        result = crew.run()

        q.put({
            "type":   "done",
            "result": result,
            "report": format_final_report(crew.ledger, result["final_report"]),
        })
    except Exception as e:
        q.put({"type": "error", "text": str(e)})


# ── Start handler ──────────────────────────────────────────
if start_btn and not st.session_state.running:
    st.session_state.running    = True
    st.session_state.done       = False
    st.session_state.transcript = []
    st.session_state.ledger_data = None
    st.session_state.final_report = None
    st.session_state.error      = None
    st.session_state.scenario   = final_scenario
    st.session_state.msg_queue  = queue.Queue()

    t = threading.Thread(
        target=run_negotiation_thread,
        args=(final_scenario, st.session_state.msg_queue),
        daemon=True,
    )
    t.start()
    st.rerun()


# ── Main area ──────────────────────────────────────────────
st.title("⚖️ AI Mediated Negotiation System")

if not st.session_state.running and not st.session_state.done:
    # Landing state
    st.markdown("### Configure your negotiation in the sidebar and press **Start**.")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("""
        **🤖 Three AI Agents**
        Party A · Party B · Mediator
        Each with distinct goals and red lines
        """)
    with col2:
        st.markdown("""
        **📋 Agreement Ledger**
        Live state tracking across all turns
        Deadlock detection and trade-off injection
        """)
    with col3:
        st.markdown("""
        **🌍 Any Scenario**
        Geopolitical · Business · Custom
        Pick a preset or build your own
        """)

elif st.session_state.running or st.session_state.done:

    # Poll queue and update session state
    if st.session_state.running:
        q = st.session_state.msg_queue
        try:
            while True:
                msg = q.get_nowait()

                if msg["type"] == "transcript":
                    st.session_state.transcript.append(msg)
                    if msg.get("ledger"):
                        st.session_state.ledger_data = msg["ledger"]

                elif msg["type"] == "done":
                    st.session_state.result       = msg["result"]
                    st.session_state.final_report = msg["report"]
                    st.session_state.running      = False
                    st.session_state.done         = True

                elif msg["type"] == "error":
                    st.session_state.error   = msg["text"]
                    st.session_state.running = False
                    st.session_state.done    = True

                elif msg["type"] == "status":
                    pass   # shown via spinner below

        except queue.Empty:
            pass

    # Layout — transcript left, ledger right
    col_chat, col_ledger = st.columns([3, 2])

    # ── Left: transcript ───────────────────────────────────
    with col_chat:
        if st.session_state.running:
            st.markdown("### 💬 Live Transcript")
            with st.spinner("Agents are negotiating..."):
                time.sleep(2)
                st.rerun()
        else:
            st.markdown("### 💬 Transcript")

        if st.session_state.error:
            st.error(f"Error: {st.session_state.error}")

        scenario = st.session_state.scenario or {}
        pa_name  = scenario.get("party_a", {}).get("name", "Party A")
        pb_name  = scenario.get("party_b", {}).get("name", "Party B")

        for msg in st.session_state.transcript:
            speaker = msg.get("speaker", "")
            text    = msg.get("text", "")

            if pa_name in speaker:
                bubble_class = "bubble-a"
            elif pb_name in speaker:
                bubble_class = "bubble-b"
            elif "FINAL" in speaker.upper():
                bubble_class = "bubble-report"
            else:
                bubble_class = "bubble-mediator"

            st.markdown(f"""
            <div class="chat-bubble {bubble_class}">
              <div class="speaker-label">{speaker}</div>
              {text}
            </div>
            """, unsafe_allow_html=True)

    # ── Right: live ledger panel ───────────────────────────
    with col_ledger:
        st.markdown("### 📋 Agreement Ledger")

        ld = st.session_state.ledger_data
        if ld:
            # Status + metrics row
            badge_class = f"badge-{ld['status_label'].lower().replace(' ','_')}"
            st.markdown(
                f"<span class='status-badge {badge_class}'>"
                f"{ld['status_icon']} {ld['status_label']}</span>",
                unsafe_allow_html=True
            )
            st.markdown("")

            m1, m2, m3 = st.columns(3)
            m1.metric("Turn",      ld["turn"])
            m2.metric("Deadlocks", ld["deadlocks"])
            m3.metric("Agreed",    len(ld["agreed"]))

            # Agreed points
            st.markdown("**✅ Agreed Points**")
            if ld["agreed"]:
                for pt in ld["agreed"]:
                    st.markdown(
                        f"<div class='agreed-point'>✓ {pt}</div>",
                        unsafe_allow_html=True
                    )
            else:
                st.caption("None yet")

            # Open issues
            st.markdown("**⚠️ Open Issues**")
            if ld["open"]:
                for issue in ld["open"]:
                    st.markdown(
                        f"<div class='open-issue'>◦ {issue}</div>",
                        unsafe_allow_html=True
                    )
            else:
                st.markdown(
                    "<div class='agreed-point'>All issues resolved</div>",
                    unsafe_allow_html=True
                )

            # Trade-off
            if ld["trade_off"] and ld["trade_off"] != "None proposed yet":
                st.markdown("**💡 Active Trade-off**")
                st.info(ld["trade_off"])

        else:
            st.caption("Ledger will appear after the first mediator turn.")

    # ── Final report tab ───────────────────────────────────
    if st.session_state.done and st.session_state.final_report:
        st.markdown("---")
        st.markdown("## 📄 Final Report")

        rpt = st.session_state.final_report
        r1, r2, r3, r4 = st.columns(4)
        r1.metric("Outcome",      rpt["status"])
        r2.metric("Total Turns",  rpt["total_turns"])
        r3.metric("Deadlocks",    rpt["deadlocks"])
        r4.metric("Agreed Points",len(rpt["agreed"]))

        tab1, tab2, tab3 = st.tabs(["📝 Narrative", "✅ Agreed Points", "⚠️ Unresolved"])

        with tab1:
            st.markdown(rpt["narrative"])

        with tab2:
            if rpt["agreed"]:
                for pt in rpt["agreed"]:
                    st.success(pt)
            else:
                st.warning("No points were agreed upon.")

        with tab3:
            if rpt["unresolved"]:
                for issue in rpt["unresolved"]:
                    st.warning(issue)
            else:
                st.success("All issues were resolved.")

        # Download button
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        download_text = f"""
NEGOTIATION REPORT — {rpt['title']}
Generated: {timestamp}
Outcome: {rpt['status']}
Total Turns: {rpt['total_turns']}
Deadlocks: {rpt['deadlocks']}

AGREED POINTS:
{chr(10).join(f'- {p}' for p in rpt['agreed']) or 'None'}

UNRESOLVED ISSUES:
{chr(10).join(f'- {i}' for i in rpt['unresolved']) or 'None'}

TRADE-OFF USED:
{rpt['trade_off'] or 'None'}

FULL NARRATIVE:
{rpt['narrative']}
        """.strip()

        st.download_button(
            label="⬇️ Download Report",
            data=download_text,
            file_name=f"negotiation_{timestamp}.txt",
            mime="text/plain",
            use_container_width=True,
        )
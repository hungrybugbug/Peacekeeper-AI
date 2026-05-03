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
    format_final_report,
)

st.set_page_config(
    page_title = "AI Negotiation System",
    page_icon  = "⚖️",
    layout     = "wide",
)

st.markdown("""
<style>
.chat-bubble {
    padding: 12px 16px; border-radius: 12px;
    margin: 6px 0; font-size: 14px; line-height: 1.6;
    border-left: 4px solid;
}
.bubble-a        { background:#0d1f33; border-color:#1f6feb; color:#cdd9e5; }
.bubble-b        { background:#0d1f0d; border-color:#238636; color:#cdd9e5; }
.bubble-mediator { background:#1f0d33; border-color:#8957e5; color:#cdd9e5; }
.bubble-human    { background:#33200d; border-color:#d29922; color:#cdd9e5; }
.bubble-report   { background:#1a1a1a; border-color:#6e7681; color:#cdd9e5; }
.speaker-label {
    font-size:11px; font-weight:600; letter-spacing:0.08em;
    text-transform:uppercase; margin-bottom:4px; opacity:0.7;
}
.agreed-point {
    background:#0d2b1a; border:1px solid #238636; border-radius:6px;
    padding:6px 10px; margin:3px 0; font-size:13px; color:#3fb950;
}
.open-issue {
    background:#2b1a0d; border:1px solid #d29922; border-radius:6px;
    padding:6px 10px; margin:3px 0; font-size:13px; color:#e3b341;
}
.hitl-box {
    background:#1a1200; border:1px solid #d29922;
    border-radius:10px; padding:16px 20px; margin:12px 0;
}
div[data-testid="metric-container"] {
    background:#161b22; border:1px solid #30363d;
    border-radius:10px; padding:12px;
}
</style>
""", unsafe_allow_html=True)


# ── Session state ──────────────────────────────────────────
def init_state():
    defaults = {
        "running"            : False,
        "done"               : False,
        "transcript"         : [],
        "ledger_data"        : None,
        "final_report"       : None,
        "status_text"        : "",
        "event_queue"        : None,
        "response_queue"     : None,
        "hitl_pending"       : False,
        "hitl_trigger"       : None,
        "hitl_context"       : None,
        "hitl_options"       : [],
        "scenario"           : None,
        "error"              : None,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

init_state()


# ── Helpers ────────────────────────────────────────────────
def bubble_class(speaker: str) -> str:
    pa = (st.session_state.scenario or {}).get("party_a", {}).get("name", "")
    pb = (st.session_state.scenario or {}).get("party_b", {}).get("name", "")
    s  = speaker.upper()
    if pa.upper() in s:          return "bubble-a"
    if pb.upper() in s:          return "bubble-b"
    if "HUMAN" in s:             return "bubble-human"
    if "FINAL" in s or "REPORT" in s: return "bubble-report"
    return "bubble-mediator"


def render_bubble(speaker: str, text: str):
    cls = bubble_class(speaker)
    st.markdown(
        f'<div class="chat-bubble {cls}">'
        f'<div class="speaker-label">{speaker}</div>'
        f'{text}</div>',
        unsafe_allow_html=True,
    )


def render_ledger(ld: dict):
    if not ld:
        st.caption("Ledger will appear after the first mediator turn.")
        return

    status_colors = {
        "In Progress": "🟡", "Settled": "🟢", "Failed": "🔴"
    }
    icon = status_colors.get(ld["status_label"], "⚪")
    st.markdown(f"**{icon} {ld['status_label']}**")

    c1, c2, c3 = st.columns(3)
    c1.metric("Turn",      ld["turn"])
    c2.metric("Deadlocks", ld["deadlocks"])
    c3.metric("Agreed",    len(ld["agreed"]))

    st.markdown("**Agreed points**")
    if ld["agreed"]:
        for pt in ld["agreed"]:
            st.markdown(
                f'<div class="agreed-point">✓ {pt}</div>',
                unsafe_allow_html=True)
    else:
        st.caption("None yet")

    st.markdown("**Open issues**")
    if ld["open"]:
        for issue in ld["open"]:
            st.markdown(
                f'<div class="open-issue">◦ {issue}</div>',
                unsafe_allow_html=True)
    else:
        st.markdown(
            '<div class="agreed-point">All issues resolved</div>',
            unsafe_allow_html=True)

    if ld["trade_off"] and ld["trade_off"] != "None proposed yet":
        st.markdown("**Active trade-off**")
        st.info(ld["trade_off"])


def poll_queue():
    """
    Drain the event queue and update session state.
    Returns True if a rerun should happen.
    """
    eq = st.session_state.event_queue
    if not eq:
        return False

    changed = False
    try:
        while True:
            msg = eq.get_nowait()
            t   = msg["type"]

            if t == "transcript":
                st.session_state.transcript.append(msg)
                if msg.get("ledger"):
                    st.session_state.ledger_data = msg["ledger"]
                changed = True

            elif t == "status":
                st.session_state.status_text = msg["text"]
                changed = True

            elif t == "human_input_required":
                st.session_state.hitl_pending = True
                st.session_state.hitl_trigger = msg["trigger"]
                st.session_state.hitl_context = msg["context"]
                st.session_state.hitl_options = msg.get("options", [])
                changed = True

            elif t == "done":
                st.session_state.running      = False
                st.session_state.done         = True
                st.session_state.status_text  = "Negotiation complete."
                changed = True

            elif t == "error":
                st.session_state.error        = msg["text"]
                st.session_state.running      = False
                st.session_state.done         = True
                changed = True

    except queue.Empty:
        pass

    return changed


# ── Sidebar ────────────────────────────────────────────────
with st.sidebar:
    st.title("⚖️ Setup")
    st.markdown("---")

    mode = st.radio("Scenario mode",
                    ["Preset scenario", "Custom scenario"], index=0)

    if mode == "Preset scenario":
        name = st.selectbox("Choose scenario", list(ALL_SCENARIOS.keys()))
        final_scenario = ALL_SCENARIOS[name]
        st.caption(f"Party A: {final_scenario['party_a']['name']}")
        st.caption(f"Party B: {final_scenario['party_b']['name']}")
        st.caption(f"Mediator: {final_scenario['mediator_name']}")
        st.caption(f"Issues: {', '.join(final_scenario['open_issues'])}")
    else:
        title    = st.text_input("Title", "Trade Deal Negotiation")
        med_name = st.text_input("Mediator name", "UN Mediator")
        st.markdown("**Party A**")
        pa_name  = st.text_input("Name", "Country Alpha")
        pa_goals = st.text_area("Goals (one per line)",
                                "Lower tariffs to 5%\nMarket access")
        pa_rl    = st.text_area("Red lines (one per line)",
                                "No tariffs above 15%")
        st.markdown("**Party B**")
        pb_name  = st.text_input("Name", "Country Beta")
        pb_goals = st.text_area("Goals (one per line)",
                                "Protect manufacturing\nTariffs at 20%")
        pb_rl    = st.text_area("Red lines (one per line)",
                                "Will not drop below 12%")
        issues   = st.text_area("Open issues (one per line)",
                                "tariff rate\nmarket access")
        final_scenario = {
            "title"        : title,
            "mediator_name": med_name,
            "party_a"      : {
                "name"     : pa_name,
                "goals"    : [g.strip() for g in pa_goals.splitlines() if g.strip()],
                "red_lines": [r.strip() for r in pa_rl.splitlines() if r.strip()],
            },
            "party_b"      : {
                "name"     : pb_name,
                "goals"    : [g.strip() for g in pb_goals.splitlines() if g.strip()],
                "red_lines": [r.strip() for r in pb_rl.splitlines() if r.strip()],
            },
            "open_issues"  : [i.strip() for i in issues.splitlines() if i.strip()],
        }

    st.markdown("---")
    can_start = not st.session_state.running and not st.session_state.hitl_pending
    start_btn = st.button("🚀 Start Negotiation",
                          disabled=not can_start,
                          use_container_width=True,
                          type="primary")

    if st.session_state.running:
        st.info(st.session_state.status_text or "Running...")

    if st.session_state.done:
        if st.button("🔄 Reset", use_container_width=True):
            for k in list(st.session_state.keys()):
                del st.session_state[k]
            st.rerun()


# ── Start handler ──────────────────────────────────────────
if start_btn:
    eq = queue.Queue()
    rq = queue.Queue()

    st.session_state.running        = True
    st.session_state.done           = False
    st.session_state.transcript     = []
    st.session_state.ledger_data    = None
    st.session_state.final_report   = None
    st.session_state.status_text    = "Starting..."
    st.session_state.hitl_pending   = False
    st.session_state.error          = None
    st.session_state.scenario       = final_scenario
    st.session_state.event_queue    = eq
    st.session_state.response_queue = rq

    def _thread_target():
        crew = NegotiationCrew(final_scenario, eq, rq)
        try:
            crew.run()
        except Exception as e:
            eq.put({"type": "error", "text": str(e)})

    threading.Thread(target=_thread_target, daemon=True).start()
    st.rerun()


# ── Main layout ────────────────────────────────────────────
st.title("⚖️ AI Mediated Negotiation System")

if not st.session_state.running and not st.session_state.done:
    st.markdown("### Configure your negotiation in the sidebar and press Start.")
    c1, c2, c3 = st.columns(3)
    c1.info("**Three AI agents**\nParty A · Party B · Mediator")
    c2.info("**Live ledger**\nDeadlock detection · Trade-offs")
    c3.info("**Human-in-the-loop**\nIntervene at critical moments")

else:
    # Poll for new events
    poll_queue()

    col_chat, col_ledger = st.columns([3, 2])

    with col_chat:
        st.markdown("### 💬 Transcript")

        # Status bar
        if st.session_state.running and not st.session_state.hitl_pending:
            st.info(f"⏳ {st.session_state.status_text or 'Agents thinking...'}")

        # Error
        if st.session_state.error:
            st.error(f"Error: {st.session_state.error}")

        # ── HITL panel ─────────────────────────────────────
        if st.session_state.hitl_pending:
            trigger = st.session_state.hitl_trigger
            context = st.session_state.hitl_context
            options = st.session_state.hitl_options

            with st.container():
                st.markdown('<div class="hitl-box">', unsafe_allow_html=True)

                if trigger == "deadlock":
                    st.warning(
                        "🔴 Deadlock detected — agents are stuck. "
                        "Your intervention is needed to break the impasse."
                    )
                elif trigger == "red_line":
                    st.warning(
                        "⚠️ Red line under pressure — an agent may be "
                        "forced to compromise a core position."
                    )

                st.markdown("**Situation:**")
                st.markdown(
                    f'<div style="background:#0d0d0d;padding:10px;'
                    f'border-radius:6px;font-size:13px;color:#cdd9e5;">'
                    f'{context}</div>',
                    unsafe_allow_html=True
                )

                st.markdown("**Choose an action or write your own:**")
                selected = st.radio(
                    "Suggested interventions:",
                    options + ["Write my own instruction"],
                    key="hitl_radio",
                    label_visibility="collapsed",
                )

                custom = ""
                if selected == "Write my own instruction":
                    custom = st.text_area(
                        "Your instruction to the mediator:",
                        placeholder=(
                            "e.g. Tell both parties that if they cannot agree "
                            "on enrichment percentage within one more turn, "
                            "a compromise of exactly 7.5% will be imposed."
                        ),
                        key="hitl_custom",
                    )

                if st.button("Submit and Resume Negotiation",
                             type="primary",
                             use_container_width=True):
                    instruction = custom if selected == "Write my own instruction" \
                                  else selected

                    # Send response back to the waiting thread
                    st.session_state.response_queue.put(instruction)
                    st.session_state.hitl_pending = False
                    st.rerun()

                st.markdown("</div>", unsafe_allow_html=True)

        # Render transcript entries as they arrive
        for entry in st.session_state.transcript:
            render_bubble(entry["speaker"], entry["text"])

    with col_ledger:
        st.markdown("### 📋 Agreement Ledger")
        render_ledger(st.session_state.ledger_data)

    # ── Final report ───────────────────────────────────────
    if st.session_state.done and not st.session_state.error:
        # Find final report entry in transcript
        final_text = ""
        for entry in reversed(st.session_state.transcript):
            if "final" in entry["speaker"].lower() or \
               "report" in entry["speaker"].lower():
                final_text = entry["text"]
                break

        if final_text:
            st.markdown("---")
            st.markdown("## 📄 Final Report")
            ld = st.session_state.ledger_data or {}

            r1, r2, r3 = st.columns(3)
            r1.metric("Outcome",      ld.get("status_label", "—"))
            r2.metric("Total Turns",  ld.get("turn", "—"))
            r3.metric("Agreed Points",len(ld.get("agreed", [])))

            tab1, tab2, tab3 = st.tabs(
                ["Narrative", "Agreed Points", "Unresolved"])

            with tab1:
                st.markdown(final_text)
            with tab2:
                agreed = ld.get("agreed", [])
                if agreed:
                    for pt in agreed: st.success(pt)
                else:
                    st.warning("No points agreed.")
            with tab3:
                open_i = ld.get("open", [])
                if open_i:
                    for i in open_i: st.warning(i)
                else:
                    st.success("All issues resolved.")

            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            dl = "\n".join(
                f"[{e['speaker']}]\n{e['text']}\n"
                for e in st.session_state.transcript
            )
            st.download_button(
                "⬇️ Download Full Transcript",
                data      = dl,
                file_name = f"negotiation_{ts}.txt",
                mime      = "text/plain",
                use_container_width=True,
            )

    # ── Auto-rerun while running ───────────────────────────
    if st.session_state.running and not st.session_state.hitl_pending:
        time.sleep(1)
        st.rerun()
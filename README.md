# ⚖️ Peacekeeper AI
### AI-Mediated Multi-Agent Negotiation System

**Live Demo → [peacekeeper-ai.tech](https://peacekeeper-ai.tech)**

Peacekeeper AI is a multi-agent system where two AI negotiating parties bargain over a set of disputed issues while a neutral AI mediator facilitates the process using real diplomatic frameworks. Humans can intervene at critical moments — deadlocks and red line violations — to steer the negotiation.

Built with CrewAI, Groq, and Google Gemini. Deployed on DigitalOcean.

---

## What It Does

Two AI agents represent opposing parties in a negotiation scenario. A third AI agent acts as a neutral mediator. The system runs autonomously turn by turn, tracking what has been agreed, what is still disputed, and whether the negotiation is progressing or stuck.

When a deadlock is detected or an agent crosses a stated red line, the system pauses and hands control to a human mediator who can intervene with a custom instruction. The agents then continue with that instruction as their highest-priority directive.

The system ships with three built-in scenarios and supports fully custom scenarios through the UI.

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Streamlit Frontend                    │
│         Live transcript · Ledger panel · HITL UI        │
└──────────────────────────┬──────────────────────────────┘
                           │  event_queue / response_queue
┌──────────────────────────▼──────────────────────────────┐
│                   NegotiationCrew                        │
│                                                          │
│   Party A Agent          Party B Agent                  │
│   (Groq Llama 70B)       (Google Gemini 2.0 Flash)      │
│         │                       │                        │
│         └──────────┬────────────┘                        │
│                    │                                     │
│            Mediator Agent                               │
│            (Groq Llama 3.3 70B)                         │
│                    │                                     │
│         Agreement Ledger (Python)                       │
│         Single source of truth for all state            │
└──────────────────────────┬──────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────┐
│              Red Line Validator                          │
│         Isolated LLM · Llama 3.1 8B · temp=0.0         │
│         Runs after every agent offer                    │
│         Hard violations → HITL · Soft → log only        │
└─────────────────────────────────────────────────────────┘
```

### Hub-and-Spoke Topology

Unlike peer-to-peer agent loops where two LLMs chat directly (leading to hallucinated consensus and circular logic), this system uses a mediated topology. Party A and Party B never communicate directly. All offers pass through the Mediator which sanitizes emotional language, tracks agreements, and detects deadlocks before routing to the next party.

### Agreement Ledger

The ledger is a Python dataclass — not LLM memory — that holds the full negotiation state across all turns:

- Agreed points accumulated so far
- Open issues still under negotiation
- Last offer from each party
- Deadlock count
- Active trade-off proposal
- Negotiation status (in progress / settled / failed)

The ledger is injected into every agent's prompt as a context string so agents always know the current state of the deal without relying on context window memory.

### Model Diversity

Each agent runs on a different model to introduce genuine cognitive diversity:

| Agent | Model | Provider | Temperature |
|-------|-------|----------|-------------|
| Party A | llama-3.1-70b-versatile | Groq | 0.85 |
| Party B | gemini-2.0-flash | Google AI Studio | 0.85 |
| Mediator | llama-3.3-70b-versatile | Groq | 0.35 |
| Validator | llama-3.1-8b-instant | Groq | 0.00 |

Parties use higher temperature for assertive, less predictable negotiating behavior. The mediator uses lower temperature for reliable structured output parsing. The validator uses zero temperature for deterministic compliance checking.

---

## Features

### Three-Agent Mediated Negotiation
Party A and Party B negotiate autonomously across multiple turns. The Mediator applies Harvard Principled Negotiation, ZOPA analysis, BATNA awareness, and deadlock-breaking tactics from real diplomatic practice.

### Agreement Ledger with State Tracking
A centralized Python state object tracks every agreed point, every open issue, and every offer. Prevents agents from contradicting previously agreed terms or negotiating against stale offers.

### Deadlock Detection
Two parallel detection mechanisms run every turn. The mediator's own judgment plus an independent Python detector that compares numeric positions across the last two turns. If both parties repeat the same numbers, deadlock is confirmed regardless of the mediator's assessment.

### Red Line Validator
An isolated LLM (outside CrewAI) checks every agent offer against that party's stated red lines before the offer is recorded in the ledger. Catches explicit numeric violations (offering 7% when the red line is 5%) while avoiding false positives from inference chains.

### Human-in-the-Loop Intervention
The negotiation pauses and presents a human decision panel when:
- **Deadlock**: Both parties have repeated positions for 2+ turns
- **Red line violation**: An agent's offer explicitly breaches a stated limit

The human can choose from suggested interventions or write a custom instruction. The false positive option dismisses validator alerts without disrupting the negotiation flow.

### Live Transcript Streaming
Agent responses appear in the UI as they are generated, not as a batch at the end. A background thread runs the negotiation and pushes events to a queue that the UI polls every second.

### Custom Scenario Builder
Any negotiation domain works — geopolitical, business acquisition, salary negotiation, trade deals. Set party names, goals, red lines, and open issues through the sidebar without touching code.

### Pre-Built Scenarios
- USA–Iran Nuclear Talks (2 issues — quick demo)
- USA–Iran Nuclear Talks (4 issues — full simulation)
- TechCorp Acquisition of StartupXYZ (business negotiation)

### Download Transcript
Full negotiation transcript downloadable as a timestamped `.txt` file after each session.

---

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Agent framework | CrewAI |
| Primary LLM | Groq API (Llama 3.1, 3.3) |
| Secondary LLM | Google Gemini 2.0 Flash (AI Studio) |
| Frontend | Streamlit |
| State management | Python dataclass (Agreement Ledger) |
| Red line validation | Groq direct API (isolated from CrewAI) |
| Deployment | DigitalOcean App Platform |
| Domain | peacekeeper-ai.tech |

---

## Project Structure

```
peacekeeper-ai/
│
├── agents/
│   ├── __init__.py
│   ├── party_a.py           # Party A agent factory
│   ├── party_b.py           # Party B agent factory
│   └── mediator.py          # Mediator agent with negotiation frameworks
│
├── tasks/
│   ├── __init__.py
│   └── negotiation_tasks.py # All CrewAI task definitions
│
├── scenarios/
│   ├── __init__.py
│   ├── iran_usa_short.py    # 2-issue quick scenario
│   ├── iran_usa_nuclear.py  # 4-issue full scenario
│   └── company_acquisition.py
│
├── utils/
│   ├── __init__.py
│   ├── parser.py            # Ledger update block parser
│   ├── formatter.py         # Ledger → display-ready dict
│   └── red_line_validator.py # Isolated LLM compliance checker
│
├── ledger.py                # Agreement Ledger dataclass
├── config.py                # LLM configuration and constants
├── crew.py                  # NegotiationCrew orchestration class
├── main.py                  # CLI entry point
├── app.py                   # Streamlit frontend
├── requirements.txt
├── runtime.txt
├── .gitignore
└── README.md
```

---

## Local Setup

### Prerequisites
- Python 3.11+
- Groq API key (free at [console.groq.com](https://console.groq.com))
- Google AI Studio API key (free at [aistudio.google.com](https://aistudio.google.com))

### Installation

```bash
git clone https://github.com/hungrybugbug/Peacekeeper-AI.git
cd Peacekeeper-AI
pip install -r requirements.txt
```

### Environment Variables

Create a `.env` file in the project root:

```
GROQ_API_KEY=your_groq_api_key_here
GEMINI_API_KEY=your_google_ai_studio_key_here
```

### Run Locally

```bash
streamlit run app.py
```

Open [http://localhost:8501](http://localhost:8501) in your browser.

### Run via CLI (no UI)

```bash
python main.py
```

Select a scenario from the menu. Full transcript is saved to a timestamped `.txt` file.

---

## How to Use

**1. Select a scenario** in the left sidebar or build a custom one by switching to Custom mode and filling in party names, goals, red lines, and open issues.

**2. Click Start Negotiation.** The transcript panel on the left shows each agent's response as it is generated. The ledger panel on the right updates after each mediator turn.

**3. Monitor the ledger.** Watch agreed points accumulate and open issues resolve. The deadlock count and trade-off field show when the mediator is intervening.

**4. Intervene when prompted.** If a deadlock is detected or a red line is violated, a yellow intervention panel appears. Choose a suggested action or write your own instruction. Click Submit to resume.

**5. Review the final report** when the negotiation concludes. Download the full transcript for analysis.

---

## Key Design Decisions

**Why not peer-to-peer agents?**
Direct LLM-to-LLM negotiation loops produce hallucinated consensus — both agents agree to nonsense because they are optimized to be helpful. The hub-and-spoke topology with a mediator as the communication gateway prevents this.

**Why Python state instead of LLM memory?**
LLM context window memory is unreliable across many turns. Agents forget earlier agreements, contradict themselves, and backtrack. The Agreement Ledger stores all state in Python and injects it as a context string into every prompt, making state explicit and verifiable.

**Why different models per agent?**
Using the same model for all agents creates an echo chamber where shared biases reduce negotiation realism. Party A on Groq Llama and Party B on Google Gemini means different underlying architectures with genuinely different response tendencies — making the negotiation more dynamic.

**Why an isolated validator instead of prompt rules?**
Asking negotiating agents to self-police their red lines fails because agents are optimized to complete the negotiation. A separate LLM with a single classification task and zero temperature is substantially more reliable at catching violations without false positives.

---

## Limitations

- Rate limits on free API tiers can cause delays between turns (handled with exponential backoff retry)
- The validator occasionally produces false positives for soft violations — the HITL false positive option handles this
- Complex multi-issue negotiations with 4+ issues are slower due to larger ledger context injected each turn
- Settlement quality depends on scenario design — very asymmetric red lines may result in failed negotiations

---

## Future Work

- **Multi-human platform**: Two human players set their own party parameters and watch their agents negotiate in real time via WebSockets
- **DeepEval integration**: Automated evaluation of negotiation quality — goal alignment, red line adherence, settlement fairness
- **RAG-powered mediator**: Mediator retrieves real treaty precedents and historical negotiation outcomes from a vector database
- **MCP tool integration**: Agents fetch live data (sanctions lists, market prices, treaty databases) during negotiation
- **Negotiation analytics dashboard**: Turn-by-turn position tracking, convergence visualization, deadlock frequency analysis

---

## Acknowledgements

Built as a semester project for an Agentic AI course. Frameworks and concepts referenced:

- Fisher, R. & Ury, W. — *Getting to Yes* (Harvard Principled Negotiation)
- CrewAI documentation — [docs.crewai.com](https://docs.crewai.com)
- Groq API — [console.groq.com](https://console.groq.com)
- Google AI Studio — [aistudio.google.com](https://aistudio.google.com)

---

## License

MIT License — see `LICENSE` for details.

---

*Deployed at [peacekeeper-ai.tech](https://peacekeeper-ai.tech)*
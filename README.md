# Peacekeeper AI

An AI-powered multi-party negotiation simulation system built with CrewAI and Groq. Peacekeeper AI simulates complex negotiations between two parties with an autonomous mediator agent facilitating the process toward agreement.

---

## Table of Contents

1. [Overview](#overview)
2. [Features](#features)
3. [Architecture](#architecture)
4. [Project Structure](#project-structure)
5. [Installation](#installation)
6. [Configuration](#configuration)
7. [Usage](#usage)
8. [Scenarios](#scenarios)
9. [Technical Details](#technical-details)
10. [Troubleshooting](#troubleshooting)

---

## Overview

Peacekeeper AI is a sophisticated negotiation simulation that uses multi-agent systems to model real-world diplomatic and business negotiations. The system creates three autonomous AI agents:

- **Party A** — The first negotiating party with specific goals and constraints
- **Party B** — The opposing party with their own objectives and red lines
- **Mediator** — A neutral facilitator that guides both parties toward agreement

Each agent operates with distinct goals, "red lines" (non-negotiable constraints), and decision-making frameworks. The mediator applies established negotiation methodologies including Harvard Principled Negotiation, ZOPA (Zone of Possible Agreement), BATNA awareness, and deadlock-breaking tactics.

---

## Features

### Core Capabilities

- **Multi-Agent Negotiation System** — Three autonomous agents (Party A, Party B, Mediator) work in concert
- **Agreement Ledger** — Tracks all offers, counter-offers, agreed points, and negotiation status in real-time
- **Configurable Scenarios** — Pre-built scenarios for different negotiation contexts
- **Turn-Based Negotiation** — Structured negotiation flow with configurable maximum turns
- **Deadlock Detection** — Automatic detection and recovery from negotiation stalls

### User Interface

- **Command-Line Interface** — Run negotiations from terminal with full logging
- **Streamlit Web UI** — Interactive browser-based interface with real-time transcript display
- **Visual Ledger Panel** — See agreement progress and open issues at a glance
- **Formatted Output** — Color-coded chat bubbles and status badges

### Technical Features

- **Rate Limit Handling** — Automatic retry with exponential backoff for API limits
- **Timestamped Logging** — All negotiation outputs saved with timestamps
- **Token Optimization** — Compact context formatting to reduce API costs
- **Model Tiering** — Different LLM models for parties vs. mediator

---

## Architecture

### System Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                        NEGOTIATION LOOP                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────┐    offer    ┌──────────┐    offer    ┌────────┐ │
│  │ Party A  │ ──────────► │ Mediator │ ──────────► │Party B │ │
│  │ (Llama   │   process  │ (Llama   │   process   │(Llama  │ │
│  │ 3.1 8B)  │   & relay  │   3.3    │  & relay    │ 3.1    │ │
│  │          │            │   70B)   │             │  8B)   │ │
│  └──────────┘            └──────────┘             └────────┘ │
│       │                       │                        │      │
│       └───────────────────────┼────────────────────────┘      │
│                               │                                 │
│                    ┌──────────▼──────────┐                    │
│                    │  Agreement Ledger    │                    │
│                    │  - Agreed points    │                    │
│                    │  - Open issues      │                    │
│                    │  - Turn history     │                    │
│                    │  - Deadlock count   │                    │
│                    └───────────────────────┘                    │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Negotiation Frameworks Used by Mediator

1. **Harvard Principled Negotiation** — Separate people from the problem; focus on interests over positions
2. **ZOPA (Zone of Possible Agreement)** — Identify overlapping ranges between party minimums
3. **BATNA Awareness** — Remind parties of their Best Alternative To Negotiated Agreement
4. **Deadlock Breaking Tactics** — Reframing, issue trading, contingent agreements, time sequencing

### Agent Design

- **Party Agents** — Use Llama 3.1 8B for fast, direct, slightly assertive tone
- **Mediator Agent** — Uses Llama 3.3 70B for more nuanced reasoning and structured output
- **Backstory System** — Each agent receives contextual backstory defining their negotiation style

---

## Project Structure

```
Peacekeeper AI/
├── agents/                      # AI agent definitions
│   ├── __init__.py             # Agent factory exports
│   ├── party_a.py              # Party A negotiator agent
│   ├── party_b.py              # Party B negotiator agent
│   └── mediator.py             # Mediator agent with negotiation frameworks
│
├── scenarios/                   # Negotiation scenario definitions
│   ├── __init__.py             # Scenario registry
│   ├── company_acquisition.py  # M&A scenario
│   ├── iran_usa_nuclear.py    # Nuclear deal scenario
│   └── iran_usa_short.py       # Short nuclear scenario
│
├── tasks/                       # CrewAI task definitions
│   ├── __init__.py             # Task factory exports
│   └── negotiation_tasks.py   # Opening, counter-offer, mediation tasks
│
├── utils/                       # Utility functions
│   ├── __init__.py             # Utility exports
│   ├── formatter.py            # Streamlit UI formatting
│   └── parser.py               # Response parsing utilities
│
├── config.py                    # Configuration settings (LLMs, limits)
├── crew.py                     # Crew orchestration and negotiation loop
├── ledger.py                    # Agreement tracking data class
├── main.py                      # CLI entry point
├── app.py                       # Streamlit web interface
├── output_cleaner.py           # Log file cleanup utility
│
├── test_agents.py              # Agent unit tests
├── test_tasks.py               # Task unit tests
│
├── README.md                   # This file
├── .env                        # Environment variables (GROQ_API_KEY)
└── output_*.txt                # Timestamped negotiation logs
```

---

## Installation

### Prerequisites

- **Python 3.9+**
- **Groq API Key** — Get one at [console.groq.com](https://console.groq.com)

### Install Dependencies

```bash
# Clone or navigate to the project directory
cd "Peacekeeper AI"

# Create virtual environment (recommended)
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac

# Install required packages
pip install crewai python-dotenv groq streamlit
```

### Environment Setup

Create a `.env` file in the project root:

```env
GROQ_API_KEY=your_groq_api_key_here
```

---

## Configuration

### config.py Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `MAX_TURNS` | 5 | Maximum negotiation rounds |
| `DEADLOCK_THRESHOLD` | 2 | Consecutive deadlocks before mediation escalation |
| `INTER_CALL_DELAY` | 15 | Seconds between API calls (rate limit buffer) |

### LLM Configuration

**Party Agents** (Party A & B):
- Model: `meta-llama/llama-4-scout-17b-16e-instruct`
- Temperature: 0.8 (assertive, less agreeable)

**Mediator Agent**:
- Model: `llama-3.3-70b-versatile`
- Temperature: 0.4 (consistent, structured)

---

## Usage

### Option 1: Command-Line Interface

Run a negotiation from the terminal:

```bash
python main.py
```

**Sample Output:**
```
Available scenarios:
  [1] USA-Iran Quick Talks (2 issues)
  [2] USA-Iran Nuclear (4 issues)
  [3] TechCorp Acquisition (4 issues)

Pick a scenario (number) or press Enter for default: 3

Loading: TechCorp Acquisition (4 issues)

============================================================
  TechCorp (Buyer)
============================================================
[Party A's opening offer...]

============================================================
  Neutral M&A Arbitrator
============================================================
[Mediator's processing...]

============================================================
  StartupXYZ (Seller)
============================================================
[Party B's response...]

...

************************************************************
  NEGOTIATION COMPLETE — SETTLED
************************************************************
[Final agreement report]

Full log saved to: output_20260430_123456.txt
```

### Option 2: Streamlit Web Interface

Launch the interactive web UI:

```bash
streamlit run app.py
```

**Features:**
- Scenario selector dropdown
- Real-time transcript with color-coded messages
- Ledger panel showing agreed points and open issues
- Final agreement summary
- Status badges (settled/in_progress/failed)

---

## Scenarios

### Pre-built Scenarios

#### 1. TechCorp Acquisition (4 issues)
- **Parties:** TechCorp (Buyer) vs. StartupXYZ (Seller)
- **Issues:** Acquisition price, founder roles, employee retention, IP transfer
- **Use Case:** M&A negotiations

#### 2. USA-Iran Nuclear (4 issues)
- **Parties:** USA vs. Iran
- **Issues:** Enrichment cap, inspection rights, sanctions relief, centrifuge dismantlement
- **Use Case:** International diplomacy

#### 3. USA-Iran Quick Talks (2 issues)
- **Parties:** USA vs. Iran
- **Issues:** Simplified 2-issue version for faster negotiations
- **Use Case:** Quick demonstrations

### Creating Custom Scenarios

Add new scenarios to the `scenarios/` directory:

```python
# scenarios/my_scenario.py
SCENARIO = {
    "title": "My Custom Negotiation",
    "mediator_name": "Neutral Mediator",
    "party_a": {
        "name": "Party A Name",
        "goals": ["Goal 1", "Goal 2", "Goal 3"],
        "red_lines": ["Never accept X", "Never go below Y"],
    },
    "party_b": {
        "name": "Party B Name",
        "goals": ["Goal 1", "Goal 2"],
        "red_lines": ["Never accept Y"],
    },
    "open_issues": ["issue 1", "issue 2", "issue 3"]
}
```

Then register in `scenarios/__init__.py`.

---

## Technical Details

### Token Optimization

The system uses compact context formatting to minimize token usage:
- Parties receive abbreviated ledger state (~200 tokens saved per call)
- Mediator receives full context for complete oversight
- Recent trajectory shows last 2 turns for context without full history

### Rate Limit Handling

When Groq API returns 429 (rate limit):
1. Wait 60 seconds, retry
2. Wait 120 seconds, retry
3. Wait 180 seconds, retry
4. If all fail, raise runtime error

### Output Logging

All negotiations are logged with timestamps:
- Filename format: `output_YYYYMMDD_HHMMSS.txt`
- Dual output: Terminal + File simultaneously
- Immediate flush for real-time monitoring

---

## Troubleshooting

### Common Issues

**"GROQ_API_KEY not found"**
- Ensure `.env` file exists with valid API key
- Verify key has no leading/trailing spaces

**"Rate limit exceeded"**
- Increase `INTER_CALL_DELAY` in config.py
- Check Groq console for account limits

**"Negotiation stuck in deadlock"**
- Reduce `DEADLOCK_THRESHOLD` for faster intervention
- Review scenario red lines for conflicts

**"Streamlit UI not loading"**
- Ensure Streamlit is installed: `pip install streamlit`
- Try: `streamlit run app.py --server.port 8501`

### Debug Mode

Enable verbose agent output in `config.py`:
```python
# In agent creation, set verbose=True
```

---

## License

This project is provided as-is for educational and research purposes.

---

## Credits

Built with:
- [CrewAI](https://crewai.com) — Multi-agent framework
- [Groq](https://groq.com) — LLM inference
- [Streamlit](https://streamlit.io) — Web UI
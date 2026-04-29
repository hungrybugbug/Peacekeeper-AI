# Peacekeeper AI

An AI-powered negotiation simulation system using CrewAI and Groq. The project simulates multi-party negotiations with autonomous agents representing different parties and a mediator.

## Overview

Peacekeeper AI uses multi-agent systems to simulate negotiation scenarios between parties. Each party is represented by an AI agent with specific goals, positions, and red lines. A mediator agent helps facilitate the negotiation toward agreement.

## Features

- **Multi-Agent Negotiation**: Party A, Party B, and a Mediator agent work together
- **Multiple Scenarios**: Pre-built scenarios including company acquisitions and Iran-USA nuclear discussions
- **Agreement Ledger**: Tracks all offers, counter-offers, and agreements made
- **Configurable Parameters**: Adjust max turns, deadlock thresholds, and timing

## Project Structure

```
Peacekeeper AI/
├── agents/              # AI agent definitions
│   ├── party_a.py       # Party A negotiator agent
│   ├── party_b.py       # Party B negotiator agent
│   └── mediator.py      # Mediator agent
├── scenarios/           # Negotiation scenario definitions
│   ├── company_acquisition.py
│   └── iran_usa_nuclear.py
├── tasks/               # CrewAI task definitions
│   └── negotiation_tasks.py
├── utils/               # Utility functions
│   └── parser.py        # Response parsing utilities
├── config.py            # Configuration settings
├── crew.py              # Crew orchestration
├── ledger.py            # Agreement tracking
├── main.py              # Entry point
└── test_*.py            # Test files
```

## Requirements

- Python 3.9+
- Groq API key
- crewai
- python-dotenv

Install dependencies:

```bash
pip install crewai python-dotenv groq
```

## Configuration

Set your Groq API key in the `.env` file:

```
GROQ_API_KEY=your_api_key_here
```

Adjust settings in `config.py`:
- `MAX_TURNS`: Maximum negotiation rounds
- `DEADLOCK_THRESHOLD`: Turns before declaring deadlock
- `INTER_CALL_DELAY`: Delay between API calls (seconds)

## Usage

Run the main script:

```bash
python main.py
```

Select a scenario when prompted, and watch the negotiation unfold.

## License

MIT
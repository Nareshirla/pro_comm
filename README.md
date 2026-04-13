# Proactive Package Communication — POC Demo

A visual demo of a proactive communication engine that detects package milestones from scan & BLE data and triggers customer emails + ops team alerts.

## Quick Start

```bash
# 1. Activate virtual environment
.venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run the server
python main.py
```

Open **http://localhost:8000** in your browser.

## Demo Script (2-3 min)

1. Select a tracking number from the dropdown
2. Click **Start Simulation** — watch raw scan & BLE data stream in
3. Milestones are auto-detected and cards appear in real-time
4. Customer emails and ops alerts fire for each milestone
5. Click **Inject Delay** — watch delay detection trigger dual notifications
6. Observe the EDD Risk gauge shift from green to amber/red

## Sample Packages

| Tracking | Scenario | Customer |
|---|---|---|
| 7922100001 | Happy path — full delivery | Sarah Johnson |
| 7922100002 | Delay at hub + clearance issue | Michael Chen |
| 7922100003 | Failed delivery / exception | Emily Rodriguez |

## Architecture

```
Data Sources (Scan + BLE)
    → Layer 1: Ingest & Normalize (BLE sessionization)
    → Layer 2: Milestone Detection Engine (rules + delay analysis)
    → Layer 3: Dual Communication (Customer Email + Ops Alert)
```

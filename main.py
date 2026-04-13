"""FastAPI application — serves the dashboard and SSE simulation endpoints."""

import asyncio
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import AsyncGenerator

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from config import FACILITY_NAMES, SIM_EVENT_DELAY_SEC, SIM_BLE_BATCH_SIZE
from models import MilestoneType
from synthetic_data import generate_packages
from milestone_engine import (
    classify_scan, detect_scan_milestones, sessionize_ble,
    detect_ble_delays, calculate_edd_risk, generate_email,
    generate_ops_alert,
)

app = FastAPI(title="Proactive Package Communication POC")

# Load synthetic data at startup
PACKAGES = generate_packages()

# Simulation state: track active simulations and delay injection flags
_sim_inject_flags: dict[str, asyncio.Event] = {}


# ── HTML dashboard ───────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def serve_dashboard():
    html_path = Path(__file__).parent / "static" / "index.html"
    return HTMLResponse(html_path.read_text(encoding="utf-8"))


# ── REST API endpoints ───────────────────────────────────────────────────────

@app.get("/api/packages")
async def list_packages():
    """Return list of available tracking numbers with summary info."""
    result = []
    for tn, pkg in PACKAGES.items():
        result.append({
            "tracking_number": tn,
            "customer_name": pkg.customer.name,
            "origin": pkg.origin,
            "origin_name": FACILITY_NAMES.get(pkg.origin, pkg.origin),
            "destination": pkg.destination,
            "destination_name": FACILITY_NAMES.get(pkg.destination, pkg.destination),
            "edd": pkg.edd.isoformat(),
            "route": [{"code": r, "name": FACILITY_NAMES.get(r, r)} for r in pkg.route],
            "scan_count": len(pkg.scan_events),
            "ble_count": len(pkg.ble_events),
        })
    return result


@app.get("/api/package/{tracking_number}")
async def get_package(tracking_number: str):
    """Return full package details."""
    pkg = PACKAGES.get(tracking_number)
    if not pkg:
        raise HTTPException(404, "Package not found")
    return {
        "tracking_number": pkg.tracking_number,
        "customer": pkg.customer.model_dump(),
        "origin": pkg.origin,
        "origin_name": FACILITY_NAMES.get(pkg.origin, pkg.origin),
        "destination": pkg.destination,
        "destination_name": FACILITY_NAMES.get(pkg.destination, pkg.destination),
        "edd": pkg.edd.isoformat(),
        "edd_display": pkg.edd.strftime("%b %d, %Y %I:%M %p"),
        "route": [{"code": r, "name": FACILITY_NAMES.get(r, r)} for r in pkg.route],
        "scan_count": len(pkg.scan_events),
        "ble_count": len(pkg.ble_events),
    }


# ── SSE Simulation endpoint ─────────────────────────────────────────────────

def _sse_event(event_type: str, data: dict) -> str:
    """Format a Server-Sent Event."""
    return f"event: {event_type}\ndata: {json.dumps(data, default=str)}\n\n"


async def _simulate_stream(tracking_number: str) -> AsyncGenerator[str, None]:
    """Stream package events with time compression for demo."""
    pkg = PACKAGES.get(tracking_number)
    if not pkg:
        yield _sse_event("error", {"message": "Package not found"})
        return

    # Set up injection flag
    inject_flag = asyncio.Event()
    _sim_inject_flags[tracking_number] = inject_flag

    # Send package info first
    yield _sse_event("package_info", {
        "tracking_number": pkg.tracking_number,
        "customer": pkg.customer.model_dump(),
        "origin": pkg.origin,
        "origin_name": FACILITY_NAMES.get(pkg.origin, pkg.origin),
        "destination": pkg.destination,
        "destination_name": FACILITY_NAMES.get(pkg.destination, pkg.destination),
        "edd": pkg.edd.isoformat(),
        "edd_display": pkg.edd.strftime("%b %d, %Y %I:%M %p"),
        "route": [{"code": r, "name": FACILITY_NAMES.get(r, r)} for r in pkg.route],
    })

    await asyncio.sleep(0.5)

    # Build a merged timeline of all events
    timeline = []
    for scan in pkg.scan_events:
        timeline.append(("scan", scan.timestamp, scan))
    for ble in pkg.ble_events:
        timeline.append(("ble", ble.timestamp, ble))
    timeline.sort(key=lambda x: x[1])

    # Track state for incremental milestone detection
    seen_scans = []
    seen_ble = []
    detected_milestones = set()
    ble_buffer = []

    for event_type, ts, event in timeline:
        # Check for delay injection
        if inject_flag.is_set():
            inject_flag.clear()
            async for evt in _handle_delay_injection(pkg, seen_ble, detected_milestones):
                yield evt

        if event_type == "scan":
            seen_scans.append(event)

            # Stream the scan event
            yield _sse_event("scan", {
                "tracking_number": event.tracking_number,
                "location_code": event.location_code,
                "location_name": FACILITY_NAMES.get(event.location_code, event.location_code),
                "timestamp": event.timestamp.isoformat(),
                "timestamp_display": event.timestamp.strftime("%b %d %H:%M"),
                "description": event.description,
            })

            # Run milestone detection on this scan
            mtype = classify_scan(event)
            if mtype and (mtype.value, event.location_code) not in detected_milestones:
                detected_milestones.add((mtype.value, event.location_code))

                from models import Milestone
                milestone = Milestone(
                    tracking_number=event.tracking_number,
                    milestone_type=mtype,
                    timestamp=event.timestamp,
                    location_code=event.location_code,
                    source="scan",
                    detail=event.description,
                )

                # Stream milestone
                yield _sse_event("milestone", {
                    "type": mtype.value,
                    "label": mtype.value.replace("_", " ").title(),
                    "location_code": event.location_code,
                    "location_name": FACILITY_NAMES.get(event.location_code, event.location_code),
                    "timestamp": event.timestamp.isoformat(),
                    "timestamp_display": event.timestamp.strftime("%b %d %H:%M"),
                    "detail": event.description,
                    "source": "scan",
                })

                await asyncio.sleep(0.3)

                # Generate and stream email
                email = generate_email(milestone, pkg)
                if email:
                    yield _sse_event("email", email.model_dump())

                await asyncio.sleep(0.2)

                # Generate and stream ops alert
                ops = generate_ops_alert(milestone, pkg)
                if ops:
                    yield _sse_event("ops_alert", ops.model_dump())

                await asyncio.sleep(0.2)

                # Update EDD risk
                all_milestones_list = [
                    Milestone(tracking_number=pkg.tracking_number, milestone_type=MilestoneType(m[0]),
                              timestamp=ts, location_code=m[1], source="scan", detail="")
                    for m in detected_milestones
                ]
                edd_risk = calculate_edd_risk(all_milestones_list, pkg.edd, event.timestamp)
                yield _sse_event("edd_update", {"risk": edd_risk.value})

            await asyncio.sleep(SIM_EVENT_DELAY_SEC)

        elif event_type == "ble":
            seen_ble.append(event)
            ble_buffer.append(event)

            if len(ble_buffer) >= SIM_BLE_BATCH_SIZE:
                yield _sse_event("ble_batch", {
                    "facility_code": event.facility_code,
                    "facility_name": FACILITY_NAMES.get(event.facility_code, event.facility_code),
                    "count": len(ble_buffer),
                    "from_time": ble_buffer[0].timestamp.isoformat(),
                    "to_time": ble_buffer[-1].timestamp.isoformat(),
                    "from_display": ble_buffer[0].timestamp.strftime("%b %d %H:%M:%S"),
                    "to_display": ble_buffer[-1].timestamp.strftime("%b %d %H:%M:%S"),
                })
                ble_buffer = []
                await asyncio.sleep(0.15)

    # Flush remaining BLE buffer
    if ble_buffer:
        yield _sse_event("ble_batch", {
            "facility_code": ble_buffer[-1].facility_code,
            "facility_name": FACILITY_NAMES.get(ble_buffer[-1].facility_code, ble_buffer[-1].facility_code),
            "count": len(ble_buffer),
            "from_time": ble_buffer[0].timestamp.isoformat(),
            "to_time": ble_buffer[-1].timestamp.isoformat(),
            "from_display": ble_buffer[0].timestamp.strftime("%b %d %H:%M:%S"),
            "to_display": ble_buffer[-1].timestamp.strftime("%b %d %H:%M:%S"),
        })

    yield _sse_event("simulation_complete", {"message": "Simulation finished"})

    # Cleanup
    _sim_inject_flags.pop(tracking_number, None)


async def _handle_delay_injection(pkg, seen_ble, detected_milestones):
    """Handle delay injection — generate delay milestones and alerts."""
    from models import Milestone

    # Find current facility from last BLE
    if not seen_ble:
        return

    current_facility = seen_ble[-1].facility_code
    last_time = seen_ble[-1].timestamp

    # Create delay milestone
    delay_milestone = Milestone(
        tracking_number=pkg.tracking_number,
        milestone_type=MilestoneType.DELAY_DETECTED,
        timestamp=last_time,
        location_code=current_facility,
        source="ble",
        detail=f"INJECTED: Package dwelling at {current_facility} exceeding threshold. "
               f"Extended delay detected at {FACILITY_NAMES.get(current_facility, current_facility)}.",
    )

    detected_milestones.add((MilestoneType.DELAY_DETECTED.value, current_facility))

    yield _sse_event("milestone", {
        "type": MilestoneType.DELAY_DETECTED.value,
        "label": "Delay Detected",
        "location_code": current_facility,
        "location_name": FACILITY_NAMES.get(current_facility, current_facility),
        "timestamp": last_time.isoformat(),
        "timestamp_display": last_time.strftime("%b %d %H:%M"),
        "detail": delay_milestone.detail,
        "source": "ble",
        "injected": True,
    })

    await asyncio.sleep(0.4)

    email = generate_email(delay_milestone, pkg)
    if email:
        yield _sse_event("email", email.model_dump())

    await asyncio.sleep(0.3)

    ops = generate_ops_alert(delay_milestone, pkg)
    if ops:
        yield _sse_event("ops_alert", ops.model_dump())

    await asyncio.sleep(0.3)

    yield _sse_event("edd_update", {"risk": "at_risk"})


@app.get("/api/simulate/{tracking_number}")
async def simulate(tracking_number: str):
    """SSE endpoint — streams package events in time-compressed simulation."""
    if tracking_number not in PACKAGES:
        raise HTTPException(404, "Package not found")
    return StreamingResponse(
        _simulate_stream(tracking_number),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


@app.post("/api/inject-delay/{tracking_number}")
async def inject_delay(tracking_number: str):
    """Inject a delay event into an active simulation."""
    flag = _sim_inject_flags.get(tracking_number)
    if not flag:
        raise HTTPException(400, "No active simulation for this package")
    flag.set()
    return {"status": "delay_injected", "tracking_number": tracking_number}


# ── Run server ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

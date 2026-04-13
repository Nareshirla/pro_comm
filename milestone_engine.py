"""Milestone detection engine — classifies scans, detects delays, generates communications."""

from datetime import datetime, timedelta
from models import (
    ScanEvent, BLEEvent, DwellSession, Milestone, MilestoneType,
    EddRisk, Package, EmailNotification, OpsAlert,
)
from config import FACILITY_NAMES, THRESHOLDS, OPS_ALERT_MILESTONES


# ── Scan-based milestone classification ──────────────────────────────────────

def classify_scan(scan: ScanEvent) -> MilestoneType | None:
    """Classify a scan event into a milestone type using keyword rules."""
    desc = scan.description.lower()

    if "delivery confirmed" in desc or "proof recorded" in desc:
        return MilestoneType.DELIVERED
    if "out-for-delivery" in desc or "loaded onto delivery van" in desc:
        return MilestoneType.OUT_FOR_DELIVERY
    if "pickup completed" in desc or "picked up from sender" in desc:
        return MilestoneType.PICKUP_COMPLETED
    if ("arrival" in desc and "arrived at station" in desc) or "ramp inbound" in desc:
        return MilestoneType.HUB_ARRIVAL
    if "hub departure" in desc or "departing a major hub" in desc:
        return MilestoneType.HUB_DEPARTURE
    if "pickup exception" in desc or "delivery failed" in desc or "failed pickup" in desc:
        return MilestoneType.FAILED_DELIVERY
    if "exception" in desc:
        return MilestoneType.EXCEPTION
    if "clearance" in desc and ("pending" in desc or "held" in desc):
        return MilestoneType.CLEARANCE_ISSUE

    return None


def detect_scan_milestones(scan_events: list[ScanEvent]) -> list[Milestone]:
    """Process scan events and return detected milestones."""
    milestones = []
    for scan in sorted(scan_events, key=lambda s: s.timestamp):
        mtype = classify_scan(scan)
        if mtype:
            milestones.append(Milestone(
                tracking_number=scan.tracking_number,
                milestone_type=mtype,
                timestamp=scan.timestamp,
                location_code=scan.location_code,
                source="scan",
                detail=scan.description,
            ))
    return milestones


# ── BLE sessionization and delay detection ───────────────────────────────────

def sessionize_ble(ble_events: list[BLEEvent]) -> list[DwellSession]:
    """Collapse raw BLE pings into facility dwell sessions."""
    if not ble_events:
        return []

    sorted_events = sorted(ble_events, key=lambda b: b.timestamp)
    sessions = []
    session_start = sorted_events[0].timestamp
    session_facility = sorted_events[0].facility_code
    prev_time = sorted_events[0].timestamp
    tn = sorted_events[0].tracking_number

    gap_threshold = timedelta(minutes=THRESHOLDS["ble_session_gap_minutes"])

    for evt in sorted_events[1:]:
        gap = evt.timestamp - prev_time
        if evt.facility_code != session_facility or gap > gap_threshold:
            dwell = (prev_time - session_start).total_seconds() / 60.0
            sessions.append(DwellSession(
                tracking_number=tn,
                facility_code=session_facility,
                entry_time=session_start,
                exit_time=prev_time,
                dwell_minutes=round(dwell, 1),
            ))
            session_start = evt.timestamp
            session_facility = evt.facility_code
        prev_time = evt.timestamp

    dwell = (prev_time - session_start).total_seconds() / 60.0
    sessions.append(DwellSession(
        tracking_number=tn,
        facility_code=session_facility,
        entry_time=session_start,
        exit_time=prev_time,
        dwell_minutes=round(dwell, 1),
    ))
    return sessions


def detect_ble_delays(sessions: list[DwellSession], origin: str, destination: str) -> list[Milestone]:
    """Detect delays from BLE dwell sessions."""
    milestones = []
    hub_max = THRESHOLDS["hub_dwell_max_minutes"]

    for session in sessions:
        if session.facility_code in (origin, destination):
            continue
        if session.dwell_minutes > hub_max:
            milestones.append(Milestone(
                tracking_number=session.tracking_number,
                milestone_type=MilestoneType.DELAY_DETECTED,
                timestamp=session.entry_time + timedelta(minutes=hub_max),
                location_code=session.facility_code,
                source="ble",
                detail=f"Package dwelling at {session.facility_code} for {session.dwell_minutes:.0f} min "
                       f"(threshold: {hub_max} min)",
            ))
    return milestones


# ── EDD risk calculation ─────────────────────────────────────────────────────

def calculate_edd_risk(milestones: list[Milestone], edd: datetime, now: datetime | None = None) -> EddRisk:
    """Calculate EDD breach risk based on current milestone state."""
    now = now or datetime.now()

    delivered = any(m.milestone_type == MilestoneType.DELIVERED for m in milestones)
    if delivered:
        return EddRisk.ON_TRACK

    has_delay = any(m.milestone_type in (MilestoneType.DELAY_DETECTED, MilestoneType.CLEARANCE_ISSUE)
                    for m in milestones)

    if now > edd:
        return EddRisk.BREACHED
    if has_delay or (edd - now) < timedelta(hours=6):
        return EddRisk.AT_RISK
    return EddRisk.ON_TRACK


# ── Email generation ─────────────────────────────────────────────────────────

MILESTONE_EMAIL_TEMPLATES = {
    MilestoneType.PICKUP_COMPLETED: {
        "subject": "Your package has been picked up!",
        "body": "Great news! Your package {tn} has been picked up from {loc_name} and is now on its way to you. "
                "Estimated delivery: {edd}.",
    },
    MilestoneType.HUB_ARRIVAL: {
        "subject": "Your package arrived at {loc_name}",
        "body": "Your package {tn} has arrived at our {loc_name} facility and is being processed for the next leg "
                "of its journey. Estimated delivery: {edd}.",
    },
    MilestoneType.OUT_FOR_DELIVERY: {
        "subject": "Your package is out for delivery today!",
        "body": "Exciting news! Your package {tn} is on the delivery vehicle and is on its way to you. "
                "Please ensure someone is available to receive it.",
    },
    MilestoneType.DELIVERED: {
        "subject": "Your package has been delivered!",
        "body": "Your package {tn} has been successfully delivered at {loc_name}. "
                "Thank you for choosing our service!",
    },
    MilestoneType.FAILED_DELIVERY: {
        "subject": "Delivery attempt unsuccessful - Action needed",
        "body": "We attempted to deliver your package {tn} but were unable to complete the delivery. "
                "We'll try again on the next business day. You can also schedule a redelivery or pickup.",
    },
    MilestoneType.DELAY_DETECTED: {
        "subject": "Update on your package - Slight delay",
        "body": "Your package {tn} is currently at our {loc_name} facility and is experiencing a slight delay "
                "in processing. We're working to get it moving as quickly as possible. "
                "Your updated estimated delivery may be affected.",
    },
    MilestoneType.CLEARANCE_ISSUE: {
        "subject": "Your package is pending clearance",
        "body": "Your package {tn} is currently held at {loc_name} pending clearance documentation review. "
                "This may cause a brief delay. We'll notify you as soon as it's cleared and moving again.",
    },
    MilestoneType.EXCEPTION: {
        "subject": "Important update about your package",
        "body": "There is an issue with your package {tn} that requires attention. "
                "Our team is investigating and will provide an update shortly.",
    },
}


def generate_email(milestone: Milestone, pkg: Package) -> EmailNotification | None:
    """Generate customer email notification for a milestone."""
    template = MILESTONE_EMAIL_TEMPLATES.get(milestone.milestone_type)
    if not template:
        return None

    loc_name = FACILITY_NAMES.get(milestone.location_code, milestone.location_code)
    edd_str = pkg.edd.strftime("%b %d, %Y %I:%M %p")

    return EmailNotification(
        to_name=pkg.customer.name,
        to_email=pkg.customer.email,
        subject=template["subject"].format(tn=pkg.tracking_number, loc_name=loc_name, edd=edd_str),
        body=template["body"].format(tn=pkg.tracking_number, loc_name=loc_name, edd=edd_str),
        milestone_type=milestone.milestone_type.value,
        timestamp=milestone.timestamp.isoformat(),
    )


# ── Ops alert generation ─────────────────────────────────────────────────────

OPS_ACTIONS = {
    MilestoneType.DELAY_DETECTED: "Investigate hold reason at facility. Check sort schedule and expedite to next outbound.",
    MilestoneType.CLEARANCE_ISSUE: "Contact clearance desk. Verify documentation and escalate if needed.",
    MilestoneType.FAILED_DELIVERY: "Schedule redelivery attempt. Contact customer for delivery preferences.",
    MilestoneType.EXCEPTION: "Investigate exception cause. Determine if package is damaged or misrouted.",
}


def generate_ops_alert(milestone: Milestone, pkg: Package) -> OpsAlert | None:
    """Generate ops team alert for actionable milestones."""
    if milestone.milestone_type.value not in OPS_ALERT_MILESTONES:
        return None

    loc_name = FACILITY_NAMES.get(milestone.location_code, milestone.location_code)
    edd_risk = calculate_edd_risk([milestone], pkg.edd, milestone.timestamp)

    severity = "high"
    if edd_risk == EddRisk.BREACHED:
        severity = "critical"
    elif edd_risk == EddRisk.ON_TRACK:
        severity = "medium"

    return OpsAlert(
        tracking_number=pkg.tracking_number,
        alert_type=milestone.milestone_type.value,
        severity=severity,
        location=milestone.location_code,
        location_name=loc_name,
        detail=milestone.detail,
        recommended_action=OPS_ACTIONS.get(milestone.milestone_type, "Investigate and resolve."),
        edd_risk=edd_risk.value,
        timestamp=milestone.timestamp.isoformat(),
    )

"""Configuration and thresholds for the proactive communication system."""

# Facility code to human-readable name mapping
FACILITY_NAMES = {
    "ROANG": "Roanoke, VA",
    "HSPA": "Houston, TX (Sort Facility)",
    "MEMH": "Memphis, TN (Main Hub)",
    "RDUR": "Durham, NC (Regional)",
    "ISOA": "Indianapolis, IN",
    "ATLGA": "Atlanta, GA",
    "DALFW": "Dallas/Fort Worth, TX",
    "CHCIL": "Chicago, IL",
    "MIAFL": "Miami, FL",
}

# Milestone detection thresholds (in minutes)
THRESHOLDS = {
    "hub_dwell_max_minutes": 360,
    "clearance_dwell_max_minutes": 720,
    "ble_session_gap_minutes": 5,
    "ofd_delivery_window_minutes": 480,
}

# Simulation settings
SIM_EVENT_DELAY_SEC = 0.8
SIM_BLE_BATCH_SIZE = 10

# EDD risk thresholds (hours before EDD)
EDD_RISK_WARNING_HOURS = 6

# Milestone types that trigger ops alerts
OPS_ALERT_MILESTONES = [
    "delay_detected",
    "clearance_issue",
    "failed_delivery",
    "exception",
]

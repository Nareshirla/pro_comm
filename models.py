"""Data models for the proactive communication system."""

from datetime import datetime
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel


class MilestoneType(str, Enum):
    PICKUP_COMPLETED = "pickup_completed"
    HUB_ARRIVAL = "hub_arrival"
    HUB_DEPARTURE = "hub_departure"
    OUT_FOR_DELIVERY = "out_for_delivery"
    DELIVERED = "delivered"
    FAILED_DELIVERY = "failed_delivery"
    DELAY_DETECTED = "delay_detected"
    CLEARANCE_ISSUE = "clearance_issue"
    EXCEPTION = "exception"
    TEMP_APPROACHING_HIGH = "temp_approaching_high"
    TEMP_APPROACHING_LOW = "temp_approaching_low"
    TEMP_BREACHED_HIGH = "temp_breached_high"
    TEMP_BREACHED_LOW = "temp_breached_low"


class EddRisk(str, Enum):
    ON_TRACK = "on_track"
    AT_RISK = "at_risk"
    BREACHED = "breached"


class ScanEvent(BaseModel):
    tracking_number: str
    location_code: str
    timestamp: datetime
    description: str


class BLEEvent(BaseModel):
    tracking_number: str
    timestamp: datetime
    facility_code: str
    temperature: float = 5.0  # °C


class DwellSession(BaseModel):
    tracking_number: str
    facility_code: str
    entry_time: datetime
    exit_time: datetime
    dwell_minutes: float


class Milestone(BaseModel):
    tracking_number: str
    milestone_type: MilestoneType
    timestamp: datetime
    location_code: str
    source: str
    detail: str


class CustomerInfo(BaseModel):
    name: str
    email: str


class EmailNotification(BaseModel):
    to_name: str
    to_email: str
    subject: str
    body: str
    milestone_type: str
    timestamp: str


class OpsAlert(BaseModel):
    tracking_number: str
    alert_type: str
    severity: str
    location: str
    location_name: str
    detail: str
    recommended_action: str
    edd_risk: str
    timestamp: str


class Package(BaseModel):
    tracking_number: str
    customer: CustomerInfo
    origin: str
    destination: str
    edd: datetime
    route: List[str]
    scan_events: List[ScanEvent]
    ble_events: List[BLEEvent]
    temp_min: float = 2.0   # °C — lower limit for this shipment
    temp_max: float = 8.0   # °C — upper limit for this shipment

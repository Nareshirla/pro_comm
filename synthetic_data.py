"""Generate synthetic package data for the POC demo."""

from datetime import datetime, timedelta
import random
from models import Package, ScanEvent, BLEEvent, CustomerInfo


def _ble_pings(tracking_number: str, facility: str, start: datetime, end: datetime) -> list[BLEEvent]:
    """Generate BLE pings every ~6 seconds between start and end."""
    pings = []
    t = start
    while t <= end:
        pings.append(BLEEvent(tracking_number=tracking_number, timestamp=t, facility_code=facility))
        t += timedelta(seconds=random.randint(4, 8))
    return pings


def generate_packages() -> dict[str, Package]:
    """Generate 3 demo packages with different scenarios."""
    packages = {}

    # =========================================================================
    # PACKAGE 1: Happy Path — Full delivery lifecycle
    # =========================================================================
    tn1 = "7922100001"
    scans1 = [
        ScanEvent(tracking_number=tn1, location_code="ROANG", timestamp=datetime(2026, 4, 10, 22, 3),
                  description="Scan for pickup completed, package picked up from sender location."),
        ScanEvent(tracking_number=tn1, location_code="ROANG", timestamp=datetime(2026, 4, 10, 22, 12),
                  description="Scan for free-text comment, comments entered about the shipment."),
        ScanEvent(tracking_number=tn1, location_code="HSPA", timestamp=datetime(2026, 4, 10, 22, 35),
                  description="Scan for consolidation add, package added into a consolidated shipment or pallet."),
        ScanEvent(tracking_number=tn1, location_code="MEMH", timestamp=datetime(2026, 4, 11, 5, 4),
                  description="Scan for consolidation add, package added into a consolidated shipment or pallet."),
        ScanEvent(tracking_number=tn1, location_code="MEMH", timestamp=datetime(2026, 4, 11, 5, 5),
                  description="Scan for free-text comment, comments entered about the shipment."),
        ScanEvent(tracking_number=tn1, location_code="MEMH", timestamp=datetime(2026, 4, 11, 8, 3),
                  description="Scan for arrival, package arrived at station/facility."),
        ScanEvent(tracking_number=tn1, location_code="MEMH", timestamp=datetime(2026, 4, 11, 8, 38),
                  description="Scan for hub departure, package departing a major hub for next transit leg."),
        ScanEvent(tracking_number=tn1, location_code="RDUR", timestamp=datetime(2026, 4, 11, 10, 6),
                  description="Scan for ramp inbound, package arriving on ramp inbound."),
        ScanEvent(tracking_number=tn1, location_code="RDUR", timestamp=datetime(2026, 4, 11, 10, 43),
                  description="Scan for consolidation add, package added into a consolidated shipment or pallet."),
        ScanEvent(tracking_number=tn1, location_code="ISOA", timestamp=datetime(2026, 4, 13, 8, 40),
                  description="Scan for arrival, package arrived at station/facility."),
        ScanEvent(tracking_number=tn1, location_code="ISOA", timestamp=datetime(2026, 4, 13, 10, 9),
                  description="Scan for out-for-delivery load, scanned when loaded onto delivery van for local route."),
        ScanEvent(tracking_number=tn1, location_code="ISOA", timestamp=datetime(2026, 4, 13, 10, 49),
                  description="Scan for delivery confirmation, delivery confirmed and proof recorded."),
    ]

    ble1 = []
    ble1 += _ble_pings(tn1, "ROANG", datetime(2026, 4, 10, 22, 0), datetime(2026, 4, 10, 22, 30))
    ble1 += _ble_pings(tn1, "HSPA", datetime(2026, 4, 10, 22, 33), datetime(2026, 4, 10, 23, 45))
    ble1 += _ble_pings(tn1, "MEMH", datetime(2026, 4, 11, 5, 0), datetime(2026, 4, 11, 8, 40))
    ble1 += _ble_pings(tn1, "RDUR", datetime(2026, 4, 11, 10, 0), datetime(2026, 4, 11, 11, 0))
    ble1 += _ble_pings(tn1, "ISOA", datetime(2026, 4, 13, 8, 35), datetime(2026, 4, 13, 10, 50))

    packages[tn1] = Package(
        tracking_number=tn1,
        customer=CustomerInfo(name="Sarah Johnson", email="sarah.johnson@email.com"),
        origin="ROANG",
        destination="ISOA",
        edd=datetime(2026, 4, 13, 12, 0),
        route=["ROANG", "HSPA", "MEMH", "RDUR", "ISOA"],
        scan_events=sorted(scans1, key=lambda s: s.timestamp),
        ble_events=sorted(ble1, key=lambda b: b.timestamp),
    )

    # =========================================================================
    # PACKAGE 2: Delay at Hub + Clearance Issue
    # =========================================================================
    tn2 = "7922100002"
    scans2 = [
        ScanEvent(tracking_number=tn2, location_code="ATLGA", timestamp=datetime(2026, 4, 10, 14, 0),
                  description="Scan for pickup completed, package picked up from sender location."),
        ScanEvent(tracking_number=tn2, location_code="ATLGA", timestamp=datetime(2026, 4, 10, 14, 30),
                  description="Scan for consolidation add, package added into a consolidated shipment or pallet."),
        ScanEvent(tracking_number=tn2, location_code="MEMH", timestamp=datetime(2026, 4, 11, 2, 0),
                  description="Scan for arrival, package arrived at station/facility."),
        ScanEvent(tracking_number=tn2, location_code="MEMH", timestamp=datetime(2026, 4, 11, 2, 15),
                  description="Scan for consolidation add, package added into a consolidated shipment or pallet."),
        ScanEvent(tracking_number=tn2, location_code="MEMH", timestamp=datetime(2026, 4, 11, 3, 0),
                  description="Scan for free-text comment, package held pending clearance documentation review."),
        ScanEvent(tracking_number=tn2, location_code="MEMH", timestamp=datetime(2026, 4, 11, 14, 0),
                  description="Scan for free-text comment, clearance completed and package released for transit."),
        ScanEvent(tracking_number=tn2, location_code="MEMH", timestamp=datetime(2026, 4, 11, 14, 30),
                  description="Scan for hub departure, package departing a major hub for next transit leg."),
        ScanEvent(tracking_number=tn2, location_code="DALFW", timestamp=datetime(2026, 4, 12, 6, 0),
                  description="Scan for arrival, package arrived at station/facility."),
        ScanEvent(tracking_number=tn2, location_code="DALFW", timestamp=datetime(2026, 4, 12, 9, 0),
                  description="Scan for out-for-delivery load, scanned when loaded onto delivery van for local route."),
        ScanEvent(tracking_number=tn2, location_code="DALFW", timestamp=datetime(2026, 4, 12, 14, 30),
                  description="Scan for delivery confirmation, delivery confirmed and proof recorded."),
    ]

    ble2 = []
    ble2 += _ble_pings(tn2, "ATLGA", datetime(2026, 4, 10, 13, 55), datetime(2026, 4, 10, 14, 45))
    ble2 += _ble_pings(tn2, "MEMH", datetime(2026, 4, 11, 1, 55), datetime(2026, 4, 11, 14, 35))
    ble2 += _ble_pings(tn2, "DALFW", datetime(2026, 4, 12, 5, 55), datetime(2026, 4, 12, 14, 35))

    packages[tn2] = Package(
        tracking_number=tn2,
        customer=CustomerInfo(name="Michael Chen", email="michael.chen@email.com"),
        origin="ATLGA",
        destination="DALFW",
        edd=datetime(2026, 4, 12, 10, 0),
        route=["ATLGA", "MEMH", "DALFW"],
        scan_events=sorted(scans2, key=lambda s: s.timestamp),
        ble_events=sorted(ble2, key=lambda b: b.timestamp),
    )

    # =========================================================================
    # PACKAGE 3: Failed Delivery + Exception
    # =========================================================================
    tn3 = "7922100003"
    scans3 = [
        ScanEvent(tracking_number=tn3, location_code="CHCIL", timestamp=datetime(2026, 4, 10, 16, 0),
                  description="Scan for pickup completed, package picked up from sender location."),
        ScanEvent(tracking_number=tn3, location_code="CHCIL", timestamp=datetime(2026, 4, 10, 16, 30),
                  description="Scan for consolidation add, package added into a consolidated shipment or pallet."),
        ScanEvent(tracking_number=tn3, location_code="MEMH", timestamp=datetime(2026, 4, 11, 4, 0),
                  description="Scan for arrival, package arrived at station/facility."),
        ScanEvent(tracking_number=tn3, location_code="MEMH", timestamp=datetime(2026, 4, 11, 4, 30),
                  description="Scan for hub departure, package departing a major hub for next transit leg."),
        ScanEvent(tracking_number=tn3, location_code="MIAFL", timestamp=datetime(2026, 4, 12, 8, 0),
                  description="Scan for arrival, package arrived at station/facility."),
        ScanEvent(tracking_number=tn3, location_code="MIAFL", timestamp=datetime(2026, 4, 13, 8, 30),
                  description="Scan for out-for-delivery load, scanned when loaded onto delivery van for local route."),
        ScanEvent(tracking_number=tn3, location_code="MIAFL", timestamp=datetime(2026, 4, 13, 14, 0),
                  description="Scan for pickup exception, delivery failed recipient unavailable notice left at door."),
    ]

    ble3 = []
    ble3 += _ble_pings(tn3, "CHCIL", datetime(2026, 4, 10, 15, 55), datetime(2026, 4, 10, 16, 40))
    ble3 += _ble_pings(tn3, "MEMH", datetime(2026, 4, 11, 3, 55), datetime(2026, 4, 11, 4, 35))
    ble3 += _ble_pings(tn3, "MIAFL", datetime(2026, 4, 12, 7, 55), datetime(2026, 4, 13, 14, 5))

    packages[tn3] = Package(
        tracking_number=tn3,
        customer=CustomerInfo(name="Emily Rodriguez", email="emily.rodriguez@email.com"),
        origin="CHCIL",
        destination="MIAFL",
        edd=datetime(2026, 4, 13, 15, 0),
        route=["CHCIL", "MEMH", "MIAFL"],
        scan_events=sorted(scans3, key=lambda s: s.timestamp),
        ble_events=sorted(ble3, key=lambda b: b.timestamp),
    )

    return packages

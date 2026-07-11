"""
Patient registry stub — swap this out for your real data source.

The Twilio microservice writes patient records; this module reads them.
For the hackathon we use a hardcoded dict keyed by E.164 phone number.
"""

from typing import Any

# Swap this with a DB read, an HTTP call to the other microservice, etc.
_PATIENTS: dict[str, dict[str, Any]] = {
    "+15551234567": {
        "name": "Dorothy",
        "medications": ["Lisinopril 10mg", "Metformin 500mg"],
    },
    "+15559876543": {
        "name": "Harold",
        "medications": ["Atorvastatin 20mg"],
    },
}


def get_patient(phone: str) -> dict[str, Any] | None:
    return _PATIENTS.get(phone)


def med_summary(patient: dict[str, Any]) -> str:
    meds = patient.get("medications", [])
    if not meds:
        return "your medication"
    if len(meds) == 1:
        return meds[0]
    return ", ".join(meds[:-1]) + f" and {meds[-1]}"

from .iran_usa_nuclear import SCENARIO as IRAN_USA_NUCLEAR
from .company_acquisition import SCENARIO as COMPANY_ACQUISITION
from .iran_usa_short import SCENARIO as IRAN_USA_SHORT

ALL_SCENARIOS = {
    "USA-Iran Quick Talks (2 issues)": IRAN_USA_SHORT,
    "USA-Iran Nuclear (4 issues)":     IRAN_USA_NUCLEAR,
    "TechCorp Acquisition (4 issues)": COMPANY_ACQUISITION,
}
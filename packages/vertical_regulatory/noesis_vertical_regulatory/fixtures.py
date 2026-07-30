"""A real (small) regulatory fixture — genuine text the corpus is built from.

Honest eval discipline (Rule 5/6): gold quotes must be real substrings of this
text, not synthetic strings copied into a fake block. The staff vs. order values
also exercise authority ordering (an approved order outranks a staff proposal).
"""
from __future__ import annotations

DOCKET = "24-1009-EL-AIR"
JURISDICTION = "OH"

ORDER_TEXT = f"""# In the Matter of the Application of Sample Electric Company, Case No. {DOCKET}

## Staff Report

Staff recommends an authorized return on equity of 9.8 percent for the Company, \
based on a proxy group analysis of comparable utilities.

## Opinion and Order

The Commission approves a return on equity of 9.6 percent, adjusting the Staff \
recommendation to reflect current capital market conditions.
"""

FIXTURE_DOCS = [
    {
        "native_id": "order-1",
        "title": f"Opinion and Order — Sample Electric Company ({DOCKET})",
        "content_type": "text/markdown",
        # Regulatory narrowing facets — denormalized onto every block so filtered
        # search can scope by state/year/utility/filing type/document type.
        "facets": {
            "jurisdiction": JURISDICTION,
            "year": "2024",
            "utility": "sample-electric",
            "filing_type": "rate_case",
            "doc_family": "order",
        },
        "body": ORDER_TEXT.encode("utf-8"),
    },
]

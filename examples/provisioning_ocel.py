"""A subscription-provisioning process as an OCEL: Salesforce -> platform -> Retool.

A worked example of the object model, not real data. One closed-won opportunity
provisions several subscriptions against one organization; the organization
outlives the opportunity and is reused by the next one. That is the shape no
single case id can represent, which is the whole reason to go object-centric.

Run it, then point `pmx ocel inspect` at the file it writes.
"""

from pathlib import Path

import pandas as pd
import pm4py
from pm4py.objects.ocel.obj import OCEL

rel = []


def ev(eid, act, ts, pairs, system):
    for oid, otype in pairs:
        rel.append(
            {
                "ocel:eid": eid,
                "ocel:activity": act,
                "ocel:timestamp": pd.Timestamp(ts),
                "ocel:oid": oid,
                "ocel:type": otype,
                "system": system,
            }
        )


SF, PF, RT = "salesforce", "platform", "retool"

# ── OPP-1: new Japanese reseller. Org must be created first. Two line items.
ev(
    "e1",
    "opportunity closed won",
    "2026-01-05 09:00",
    [("OPP-1", "opportunity"), ("ACC-jp", "account")],
    SF,
)
ev(
    "e2",
    "create organization",
    "2026-01-05 11:00",
    [("OPP-1", "opportunity"), ("ACC-jp", "account"), ("ORG-77", "organization")],
    PF,
)
ev(
    "e3",
    "provision subscription",
    "2026-01-05 12:00",
    [
        ("OPP-1", "opportunity"),
        ("OLI-1", "line_item"),
        ("SUB-1", "subscription"),
        ("ORG-77", "organization"),
    ],
    PF,
)
ev(
    "e4",
    "provision subscription",
    "2026-01-05 12:05",
    [
        ("OPP-1", "opportunity"),
        ("OLI-2", "line_item"),
        ("SUB-2", "subscription"),
        ("ORG-77", "organization"),
    ],
    PF,
)
# one event, two collections, driven by the ACCOUNT's reseller/region fields
ev(
    "e5",
    "enable content collection",
    "2026-01-05 13:00",
    [
        ("SUB-1", "subscription"),
        ("ACC-jp", "account"),
        ("COL-jp-intl", "content_collection"),
        ("COL-base", "content_collection"),
    ],
    PF,
)
ev(
    "e6",
    "enable content collection",
    "2026-01-05 13:05",
    [
        ("SUB-2", "subscription"),
        ("ACC-jp", "account"),
        ("COL-base", "content_collection"),
    ],
    PF,
)
ev(
    "e7",
    "enable feature",
    "2026-01-06 09:00",
    [("SUB-1", "subscription"), ("FEAT-sso", "feature")],
    RT,
)
ev(
    "e8",
    "enable feature",
    "2026-01-06 09:10",
    [("SUB-1", "subscription"), ("FEAT-api", "feature")],
    RT,
)
ev(
    "e9",
    "activate subscription",
    "2026-01-06 10:00",
    [("SUB-1", "subscription"), ("ORG-77", "organization")],
    PF,
)
ev(
    "e10",
    "activate subscription",
    "2026-01-06 10:01",
    [("SUB-2", "subscription"), ("ORG-77", "organization")],
    PF,
)

# ── OPP-2: expansion for the SAME customer. Org already exists -> no create.
ev(
    "e11",
    "opportunity closed won",
    "2026-03-02 09:00",
    [("OPP-2", "opportunity"), ("ACC-jp", "account")],
    SF,
)
ev(
    "e12",
    "provision subscription",
    "2026-03-02 10:00",
    [
        ("OPP-2", "opportunity"),
        ("OLI-3", "line_item"),
        ("SUB-3", "subscription"),
        ("ORG-77", "organization"),
    ],
    PF,
)
ev(
    "e13",
    "enable content collection",
    "2026-03-02 10:30",
    [
        ("SUB-3", "subscription"),
        ("ACC-jp", "account"),
        ("COL-jp-intl", "content_collection"),
    ],
    PF,
)
ev(
    "e14",
    "activate subscription",
    "2026-03-02 11:00",
    [("SUB-3", "subscription"), ("ORG-77", "organization")],
    PF,
)

# ── OPP-3: brand new US customer, single product, feature enabled late
ev(
    "e15",
    "opportunity closed won",
    "2026-04-01 09:00",
    [("OPP-3", "opportunity"), ("ACC-us", "account")],
    SF,
)
ev(
    "e16",
    "create organization",
    "2026-04-01 15:00",
    [("OPP-3", "opportunity"), ("ACC-us", "account"), ("ORG-91", "organization")],
    PF,
)
ev(
    "e17",
    "provision subscription",
    "2026-04-02 09:00",
    [
        ("OPP-3", "opportunity"),
        ("OLI-4", "line_item"),
        ("SUB-4", "subscription"),
        ("ORG-91", "organization"),
    ],
    PF,
)
ev(
    "e18",
    "activate subscription",
    "2026-04-02 09:30",
    [("SUB-4", "subscription"), ("ORG-91", "organization")],
    PF,
)
ev(
    "e19",
    "enable content collection",
    "2026-04-03 11:00",
    [
        ("SUB-4", "subscription"),
        ("ACC-us", "account"),
        ("COL-base", "content_collection"),
    ],
    PF,
)
ev(
    "e20",
    "enable feature",
    "2026-04-05 14:00",
    [("SUB-4", "subscription"), ("FEAT-sso", "feature")],
    RT,
)

relations = pd.DataFrame(rel)
events = relations[["ocel:eid", "ocel:activity", "ocel:timestamp"]].drop_duplicates(
    "ocel:eid"
)
objects = relations[["ocel:oid", "ocel:type"]].drop_duplicates("ocel:oid")
ocel = OCEL(events=events, objects=objects, relations=relations)

print(
    f"{len(ocel.events)} events, {len(ocel.objects)} objects, "
    f"{len(ocel.relations)} event-to-object links"
)
print("object types:", ", ".join(pm4py.ocel_get_object_types(ocel)))

path = Path(__file__).with_name("provisioning.json")
pm4py.write_ocel2_json(ocel, str(path))
print(f"\nwrote {path}\n")
print("Now run, to see what a case id would cost and what the process looks like:")
print(f"  pmx ocel inspect  {path}")
print(f"  pmx ocel discover {path} -i map.svg --bgcolor transparent")

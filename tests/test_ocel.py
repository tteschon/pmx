from __future__ import annotations

import json
from pathlib import Path

import pytest

from pmx.discovery import graphviz_available
from pmx.ocel import Notation, OcelError, discover, flatten, read, render, summarize


def test_reads_an_ocel2_json(prov_ocel: Path) -> None:
    ocel = read(prov_ocel)

    assert len(ocel.events) == 8
    assert len(ocel.objects) == 7


def test_missing_file_is_an_ocel_error(tmp_path: Path) -> None:
    with pytest.raises(OcelError, match="no such file"):
        read(tmp_path / "absent.json")


def test_unknown_suffix_names_the_supported_ones(tmp_path: Path) -> None:
    bad = tmp_path / "log.parquet"
    bad.write_text("not an ocel")

    with pytest.raises(OcelError, match=r"\.json, \.xml, \.sqlite"):
        read(bad)


def test_unparseable_file_reports_what_was_tried(tmp_path: Path) -> None:
    bad = tmp_path / "log.json"
    bad.write_text("{not json")

    with pytest.raises(OcelError, match="could not read"):
        read(bad)


def test_summary_counts(prov_ocel: Path) -> None:
    s = summarize(read(prov_ocel), source=str(prov_ocel))

    assert s.events == 8
    assert s.object_types == {
        "line_item": 2,
        "subscription": 2,
        "opportunity": 1,
        "organization": 1,
        "collection": 1,
    }
    assert "provision" in s.type_activities["subscription"]


def test_convergence_counts_duplicated_events(prov_ocel: Path) -> None:
    s = summarize(read(prov_ocel), source=str(prov_ocel))
    by_type = {c.object_type: c for c in s.convergence}

    # One "enable collection" event touches both subscriptions, so flattening
    # on subscription turns 1 event into 2 rows.
    assert by_type["subscription"].duplicated == 1
    assert by_type["subscription"].inflation > 1.0
    # An opportunity is on every event it appears in exactly once.
    assert by_type["opportunity"].duplicated == 0


def test_divergence_finds_the_one_to_many_pairs(prov_ocel: Path) -> None:
    s = summarize(read(prov_ocel), source=str(prov_ocel))
    pairs = {(d.parent, d.child): d.max_children for d in s.divergence}

    assert pairs[("opportunity", "subscription")] == 2
    assert pairs[("organization", "subscription")] == 2
    # One-to-one pairs are not distortions and are left out.
    assert ("subscription", "collection") not in pairs or pairs[
        ("subscription", "collection")
    ] >= 2


def test_summary_is_json_serialisable(prov_ocel: Path) -> None:
    payload = json.loads(
        json.dumps(summarize(read(prov_ocel), str(prov_ocel)).as_dict())
    )

    assert payload["events"] == 8
    assert payload["convergence"][0]["object_type"] == "subscription"


def test_flatten_rejects_an_unknown_object_type(prov_ocel: Path) -> None:
    with pytest.raises(OcelError, match="no object type 'widget'"):
        flatten(read(prov_ocel), "widget")


def test_flatten_duplicates_on_a_convergent_type(prov_ocel: Path) -> None:
    ocel = read(prov_ocel)
    flat = flatten(ocel, "subscription")

    # More rows than events touching subscriptions: that is convergence made
    # visible, and the reason the CLI warns about it.
    touching = ocel.relations[ocel.relations[ocel.object_type_column] == "subscription"]
    assert len(flat) > touching[ocel.event_id_column].nunique()


def test_ocpn_rejects_an_out_of_range_threshold(prov_ocel: Path) -> None:
    with pytest.raises(OcelError, match=r"noise threshold must be in \[0, 1\]"):
        discover(read(prov_ocel), notation=Notation.OCPN, noise_threshold=1.5)


def test_ocdfg_has_one_flow_per_object_type(prov_ocel: Path) -> None:
    model = discover(read(prov_ocel), notation=Notation.OCDFG)

    assert set(model["edges"]["event_couples"]) <= {
        "opportunity",
        "organization",
        "subscription",
        "line_item",
        "collection",
    }
    assert model["activities"]


def test_ocpn_has_a_net_per_object_type(prov_ocel: Path) -> None:
    model = discover(read(prov_ocel), notation=Notation.OCPN)

    assert set(model["petri_nets"]) == {
        "opportunity",
        "organization",
        "subscription",
        "line_item",
        "collection",
    }


@pytest.mark.skipif(not graphviz_available(), reason="Graphviz 'dot' is not installed")
@pytest.mark.parametrize("notation", [Notation.OCDFG, Notation.OCPN])
def test_render_writes_an_image(
    prov_ocel: Path, tmp_path: Path, notation: Notation
) -> None:
    model = discover(read(prov_ocel), notation=notation)

    target = render(
        model, tmp_path / "nested" / f"{notation.value}.svg", notation=notation
    )

    assert target.stat().st_size > 0

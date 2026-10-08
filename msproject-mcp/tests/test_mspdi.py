import xml.etree.ElementTree as ET

import pytest

from msproject_mcp.common import ProjectError
from msproject_mcp.mspdi import (
    ASSIGNMENT_ORDER,
    PROJECT_ORDER,
    RESOURCE_ORDER,
    TASK_ORDER,
    XmlBackend,
    _local,
    format_duration,
    parse_duration,
    q,
)


@pytest.fixture
def plan():
    b = XmlBackend()
    b.new("Website", "2026-10-05")
    ids = {}
    ids["design"] = b.add_task("Design", 3)["uid"]
    ids["build"] = b.add_task("Build", 0)["uid"]
    ids["code"] = b.add_task("Code", 5, parent_uid=ids["build"], predecessors=[ids["design"]])["uid"]
    ids["docs"] = b.add_task("Docs", 2, parent_uid=ids["build"], predecessors=[ids["design"]])["uid"]
    ids["launch"] = b.add_task("Launch", 0, predecessors=[ids["build"]])["uid"]
    return b, ids


def test_durations():
    assert parse_duration("PT16H0M0S") == 960
    assert parse_duration("PT7H30M0S") == 450
    assert parse_duration("P1DT2H") == 600
    assert format_duration(960) == "PT16H0M0S"
    assert format_duration(450) == "PT7H30M0S"


def test_outline_and_schedule(plan):
    b, ids = plan
    tasks = {t["name"]: t for t in b.list_tasks()}
    assert [t["wbs"] for t in b.list_tasks()] == ["1", "2", "2.1", "2.2", "3"]
    assert tasks["Build"]["summary"] and not tasks["Code"]["summary"]
    assert tasks["Code"]["start"] == "2026-10-08T08:00"
    assert tasks["Code"]["finish"] == "2026-10-14T17:00"  # spans a weekend
    assert tasks["Build"]["duration_days"] == 5
    assert tasks["Launch"]["milestone"] and tasks["Launch"]["start"] == "2026-10-14T17:00"
    assert tasks["Docs"]["total_slack_days"] == 3 and not tasks["Docs"]["critical"]
    assert [t["name"] for t in b.critical_path()] == ["Design", "Code", "Launch"]
    s = b.summary()
    assert (s["finish"], s["duration_days"], s["task_count"], s["milestone_count"]) == ("2026-10-14T17:00", 8, 4, 1)


def test_holiday_pushes_schedule(plan):
    b, ids = plan
    b.add_nonworking_day("2026-10-12")
    assert b.get_task(ids["code"])["finish"] == "2026-10-15T17:00"


def test_update_and_constraints(plan):
    b, ids = plan
    b.update_task(ids["design"], duration_days=4, percent_complete=50, notes="Wireframes")
    t = b.get_task(ids["design"])
    assert (t["duration_days"], t["percent_complete"], t["notes"]) == (4, 50, "Wireframes")
    assert b.get_task(ids["code"])["start"] == "2026-10-09T08:00"
    b.update_task(ids["docs"], constraint_type="SNET", constraint_date="2026-10-20")
    docs = b.get_task(ids["docs"])
    assert docs["start"] == "2026-10-20T08:00" and docs["constraint"] == "SNET"
    with pytest.raises(ProjectError, match="Summary"):
        b.update_task(ids["build"], duration_days=2)
    with pytest.raises(ProjectError, match="constraint_date"):
        b.update_task(ids["docs"], constraint_type="MSO")


def test_link_types_and_unlink(plan):
    b, ids = plan
    extra = b.add_task("Review", 1)["uid"]
    b.link_tasks(ids["design"], extra, "SS", lag_days=1)
    t = b.get_task(extra)
    assert t["start"] == "2026-10-06T08:00"
    assert t["predecessors"] == [{"uid": ids["design"], "type": "SS", "lag_days": 1}]
    b.unlink_tasks(ids["design"], extra)
    assert b.get_task(extra)["predecessors"] == []
    with pytest.raises(ProjectError, match="own subtasks"):
        b.link_tasks(ids["build"], ids["code"])


def test_cycle_rolls_back(plan):
    b, ids = plan
    before = ET.tostring(b.root)
    with pytest.raises(ProjectError, match="cycle"):
        b.link_tasks(ids["launch"], ids["design"])
    assert ET.tostring(b.root) == before


def test_resources_work_and_cost(plan):
    b, ids = plan
    alice = b.add_resource("Alice", standard_rate_per_hour=50, email="a@example.com")["uid"]
    bob = b.add_resource("Bob", max_units=0.5, standard_rate_per_hour=40)["uid"]
    b.assign_resource(ids["code"], alice)
    b.assign_resource(ids["docs"], bob, units=0.5)
    res = {r["name"]: r for r in b.list_resources()}
    assert res["Alice"]["work_hours"] == 40 and res["Alice"]["cost"] == 2000
    assert res["Bob"]["work_hours"] == 8 and res["Bob"]["cost"] == 320
    assert b.summary()["estimated_labor_cost"] == 2320
    assert b.get_task(ids["code"])["resources"] == [{"uid": alice, "name": "Alice", "units": 1.0}]
    b.unassign_resource(ids["code"], alice)
    assert b.get_task(ids["code"])["resources"] == []
    b.delete_resource(bob)
    assert [r["name"] for r in b.list_resources()] == ["Alice"]
    assert b._assignments() == []


def test_delete_summary_cascades(plan):
    b, ids = plan
    b.assign_resource(ids["code"], b.add_resource("Alice")["uid"])
    out = b.delete_task(ids["build"])
    assert out["deleted_task_uids"] == sorted([ids["build"], ids["code"], ids["docs"]])
    assert [t["name"] for t in b.list_tasks()] == ["Design", "Launch"]
    assert b.get_task(ids["launch"])["predecessors"] == []
    assert b._assignments() == []
    assert [t["id"] for t in b.list_tasks()] == [1, 2]


def test_save_and_reopen(plan, tmp_path):
    b, ids = plan
    b.add_resource("Alice")
    path = tmp_path / "site.xml"
    b.save(str(path))
    assert not b.summary()["unsaved_changes"]
    other = XmlBackend()
    other.open(str(path))
    assert other.list_tasks() == b.list_tasks()
    assert other.summary()["title"] == "Website"


def _assert_ordered(el, order):
    ranks = [order.index(_local(c.tag)) for c in el if _local(c.tag) in order]
    assert ranks == sorted(ranks), [_local(c.tag) for c in el]


def test_elements_follow_schema_order(plan):
    b, ids = plan
    b.assign_resource(ids["code"], b.add_resource("Alice", standard_rate_per_hour=10)["uid"])
    b.update_task(ids["docs"], notes="n", constraint_type="SNET", constraint_date="2026-10-20")
    _assert_ordered(b.root, PROJECT_ORDER)
    for t in b.root.iter(q("Task")):
        _assert_ordered(t, TASK_ORDER)
    for r in b.root.iter(q("Resource")):
        _assert_ordered(r, RESOURCE_ORDER)
    for a in b.root.iter(q("Assignment")):
        _assert_ordered(a, ASSIGNMENT_ORDER)


def test_preserves_unknown_elements(tmp_path):
    b = XmlBackend()
    b.new("P", "2026-10-05")
    task = b.add_task("T", 1)
    el = b._task(task["uid"])
    custom = ET.SubElement(el, q("ExtendedAttribute"))
    ET.SubElement(custom, q("FieldID")).text = "188743731"
    path = tmp_path / "p.xml"
    b.save(str(path))
    reopened = XmlBackend()
    reopened.open(str(path))
    reopened.update_task(task["uid"], name="Renamed")
    assert reopened._task(task["uid"]).find(q("ExtendedAttribute")) is not None


def test_errors(tmp_path):
    b = XmlBackend()
    with pytest.raises(ProjectError, match="No project is open"):
        b.list_tasks()
    mpp = tmp_path / "x.mpp"
    mpp.write_bytes(b"\0")
    with pytest.raises(ProjectError, match="Save As"):
        b.open(str(mpp))
    b.new("P", "2026-10-05")
    with pytest.raises(ProjectError, match="No task with UID 99"):
        b.get_task(99)
    with pytest.raises(ProjectError, match="link type"):
        b.link_tasks(b.add_task("A")["uid"], b.add_task("B")["uid"], "XX")
    with pytest.raises(ProjectError, match=".xml"):
        b.save(str(tmp_path / "out.mpp"))

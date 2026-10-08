"""Exercise the COM backend against a minimal fake of Project's object model.

This cannot prove compatibility with real Project 2021 (that needs Windows),
but it catches Python-level mistakes in the backend code paths.
"""

import sys
import types
from datetime import datetime

import pytest

from msproject_mcp.common import ProjectError


class FakeCollection(list):
    def __iter__(self):
        return iter(list(super().__iter__()))


class FakeDep:
    def __init__(self, owner, frm, to, typ, lag):
        self.owner, self.From, self.To, self.Type, self.Lag = owner, frm, to, typ, lag

    def Delete(self):
        self.owner.TaskDependencies.remove(self)


class FakeDeps(FakeCollection):
    def __init__(self, task):
        super().__init__()
        self.task = task

    def Add(self, frm, typ, lag):
        days = float(lag.rstrip("d"))
        self.append(FakeDep(self.task, frm, self.task, typ, days * 480))


class FakeAssignment:
    def __init__(self, task, res, units):
        self.task, self.ResourceUniqueID, self.ResourceName, self.Units = task, res.UniqueID, res.Name, units

    def Delete(self):
        self.task.Assignments.remove(self)


class FakeAssignments(FakeCollection):
    def __init__(self, task, project):
        super().__init__()
        self.task, self.project = task, project

    def Add(self, TaskID, ResourceID, Units):
        res = next(r for r in self.project.Resources if r.ID == ResourceID)
        self.append(FakeAssignment(self.task, res, Units))


class FakeTask:
    def __init__(self, project, uid, name):
        self.project = project
        self.UniqueID, self.ID, self.Name = uid, uid, name
        self.OutlineLevel, self.WBS, self.Summary, self.Milestone, self.Manual = 1, str(uid), False, False, True
        self.Start = self.Finish = datetime(2026, 10, 5, 8)
        self.Duration, self.PercentComplete, self.Critical, self.TotalSlack = 480, 0, True, 0
        self.ConstraintType, self.ConstraintDate, self.Notes = 0, "NA", ""
        self.Cost = 0.0
        self.TaskDependencies = FakeDeps(self)
        self.Assignments = FakeAssignments(self, project)

    def __setattr__(self, key, value):
        if key == "Duration" and isinstance(value, str):
            value = float(value.rstrip("d")) * 480
        super().__setattr__(key, value)

    def Delete(self):
        self.project.Tasks.remove(self)


class FakeTasks(FakeCollection):
    def __init__(self, project):
        super().__init__()
        self.project = project

    def Add(self, name, before=None):
        t = FakeTask(self.project, len(self) + 1, name)
        self.append(t)
        return t

    def UniqueID(self, uid):
        for t in self:
            if t.UniqueID == uid:
                return t
        raise Exception("not found")


class FakeResource:
    def __init__(self, project, uid, name):
        self.project, self.UniqueID, self.ID, self.Name = project, uid, uid, name
        self.Type, self.MaxUnits, self.StandardRate = 1, 1.0, "$0.00/hr"
        self.Initials = self.EMailAddress = self.Group = ""
        self.Work, self.Cost = 0, 0.0

    def Delete(self):
        self.project.Resources.remove(self)


class FakeResources(FakeCollection):
    def __init__(self, project):
        super().__init__()
        self.project = project

    def Add(self, name):
        r = FakeResource(self.project, len(self) + 1, name)
        self.append(r)
        return r

    def UniqueID(self, uid):
        return next(r for r in self if r.UniqueID == uid)


class FakeProject:
    def __init__(self):
        self.Tasks, self.Resources = FakeTasks(self), FakeResources(self)
        self.HoursPerDay, self.FullName, self.Saved, self.Title = 8, "Project1", False, ""
        self.ProjectStart = self.ProjectFinish = datetime(2026, 10, 5, 8)
        self.ProjectSummaryTask = FakeTask(self, 0, "Project1")
        self.exceptions = []
        self.Calendar = types.SimpleNamespace(
            Exceptions=types.SimpleNamespace(Add=lambda **kw: self.exceptions.append(kw))
        )


class FakeApp:
    def __init__(self):
        self.Visible, self.calculated, self.projects = False, 0, []
        self.Projects = types.SimpleNamespace(Count=0)

    @property
    def ActiveProject(self):
        return self.projects[-1]

    def FileNew(self):
        self.projects.append(FakeProject())
        self.Projects.Count = len(self.projects)

    def CalculateProject(self):
        self.calculated += 1


@pytest.fixture
def com(monkeypatch):
    app = FakeApp()
    client = types.ModuleType("win32com.client")
    client.GetActiveObject = lambda name: app
    client.Dispatch = lambda name: app
    win32com = types.ModuleType("win32com")
    win32com.client = client
    pythoncom = types.ModuleType("pythoncom")
    pythoncom.CoInitialize = lambda: None
    monkeypatch.setitem(sys.modules, "win32com", win32com)
    monkeypatch.setitem(sys.modules, "win32com.client", client)
    monkeypatch.setitem(sys.modules, "pythoncom", pythoncom)
    from msproject_mcp.com_backend import ComBackend

    return ComBackend(), app


def test_com_workflow(com):
    b, app = com
    with pytest.raises(ProjectError, match="No project is open"):
        b.list_tasks()
    summary = b.new("Demo", "2026-10-05")
    assert summary["backend"] == "com" and summary["title"] == "Demo"
    a = b.add_task("A", 2)
    child = b.add_task("A.1", 1.5, parent_uid=a["uid"], predecessors=[a["uid"]],
                       constraint_type="SNET", constraint_date="2026-10-07")
    task = app.ActiveProject.Tasks.UniqueID(child["uid"])
    assert task.OutlineLevel == 2 and task.Manual is False and task.ConstraintType == 4
    assert child["duration_days"] == 1.5
    assert child["predecessors"] == [{"uid": a["uid"], "type": "FS", "lag_days": 0}]
    b.link_tasks(a["uid"], child["uid"], "SS", 1)
    b.unlink_tasks(a["uid"], child["uid"])
    assert b.get_task(child["uid"])["predecessors"] == []
    r = b.add_resource("Ann", standard_rate_per_hour=80, email="ann@example.com")
    assert app.ActiveProject.Resources.UniqueID(r["uid"]).StandardRate == "80/h"
    assert b.assign_resource(child["uid"], r["uid"], 0.5)["resources"][0]["units"] == 0.5
    assert b.assign_resource(child["uid"], r["uid"], 1.0)["resources"][0]["units"] == 1.0
    b.unassign_resource(child["uid"], r["uid"])
    b.update_task(a["uid"], name="Renamed", percent_complete=20, notes="n")
    assert b.get_task(a["uid"])["name"] == "Renamed"
    b.add_nonworking_day("2026-12-25", "Christmas")
    assert app.ActiveProject.exceptions[0]["Name"] == "Christmas"
    b.recalculate()
    assert app.calculated == 1
    assert len(b.critical_path()) == 2
    b.delete_task(child["uid"])
    assert [t["name"] for t in b.list_tasks()] == ["Renamed"]
    b.delete_resource(r["uid"])
    assert b.list_resources() == []

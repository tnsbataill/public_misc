"""Backend that drives a running Microsoft Project 2021 instance through COM.

Windows only; requires Project 2021 (or any desktop Project 2010+) and pywin32.
Project itself does the scheduling, so results match exactly what you see in
the Gantt chart, and .mpp files are supported.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from .common import (
    CONSTRAINT_NAMES,
    LINK_NAMES,
    RESOURCE_TYPE_NAMES,
    ProjectError,
    constraint_code,
    iso,
    link_type_code,
    parse_when,
    resource_type_code,
    round_days,
)

PJ_DAILY = 1  # PjExceptionType.pjDaily


def _dt(value: Any) -> datetime | None:
    """Convert a COM date (or Project's 'NA' string) to a naive datetime."""
    if value is None or isinstance(value, str):
        return None
    try:
        return datetime(value.year, value.month, value.day, value.hour, value.minute)
    except (AttributeError, ValueError):
        return None


class ComBackend:
    name = "com"

    def __init__(self) -> None:
        try:
            import pythoncom  # noqa: F401
            import win32com.client  # noqa: F401
        except ImportError as exc:  # pragma: no cover - depends on platform
            raise ProjectError(
                "The com backend needs Windows, Microsoft Project and pywin32 (pip install pywin32)"
            ) from exc
        self._app: Any = None

    # ------------------------------------------------------------------ plumbing

    @property
    def app(self) -> Any:
        if self._app is None:
            import pythoncom
            import win32com.client

            pythoncom.CoInitialize()
            try:
                self._app = win32com.client.GetActiveObject("MSProject.Application")
            except Exception:
                self._app = win32com.client.Dispatch("MSProject.Application")
            self._app.Visible = True
        return self._app

    @property
    def project(self) -> Any:
        if self.app.Projects.Count == 0:
            raise ProjectError("No project is open in Microsoft Project. Call open_project or new_project first.")
        return self.app.ActiveProject

    @property
    def minutes_per_day(self) -> float:
        return float(self.project.HoursPerDay) * 60

    def _tasks(self) -> list[Any]:
        return [t for t in self.project.Tasks if t is not None]

    def _task(self, uid: int) -> Any:
        try:
            return self.project.Tasks.UniqueID(uid)
        except Exception:
            raise ProjectError(f"No task with UID {uid}") from None

    def _resource(self, uid: int) -> Any:
        try:
            return self.project.Resources.UniqueID(uid)
        except Exception:
            raise ProjectError(f"No resource with UID {uid}") from None

    # ------------------------------------------------------------- file actions

    def new(self, title: str, start: str, path: str | None = None) -> dict:
        self.app.FileNew()
        proj = self.project
        proj.ProjectStart = parse_when(start)
        proj.ProjectSummaryTask.Name = title
        proj.Title = title
        if path:
            self.save(path)
        return self.summary()

    def open(self, path: str) -> dict:
        p = Path(path).expanduser().resolve()
        if not p.exists():
            raise ProjectError(f"File not found: {p}")
        if p.suffix.lower() == ".xml":
            self.app.FileOpenEx(Name=str(p), FormatID="MSProject.XML")
        else:
            self.app.FileOpenEx(Name=str(p))
        return self.summary()

    def save(self, path: str | None = None) -> dict:
        proj = self.project
        if path:
            p = Path(path).expanduser().resolve()
            if p.suffix.lower() == ".xml":
                self.app.FileSaveAs(Name=str(p), FormatID="MSProject.XML")
            else:
                self.app.FileSaveAs(Name=str(p))
        else:
            self.app.FileSave()
        return {"saved": str(proj.FullName)}

    def recalculate(self) -> dict:
        self.app.CalculateProject()
        return self.summary()

    # -------------------------------------------------------------- read views

    def _task_dict(self, t: Any) -> dict:
        mpd = self.minutes_per_day
        ctype = int(t.ConstraintType)
        uid = int(t.UniqueID)
        preds = []
        for dep in t.TaskDependencies:
            if int(dep.To.UniqueID) == uid:
                preds.append({
                    "uid": int(dep.From.UniqueID),
                    "type": LINK_NAMES.get(int(dep.Type), str(dep.Type)),
                    "lag_days": round_days(float(dep.Lag), mpd),
                })
        return {
            "uid": uid,
            "id": int(t.ID),
            "name": str(t.Name),
            "wbs": str(t.WBS),
            "outline_level": int(t.OutlineLevel),
            "summary": bool(t.Summary),
            "milestone": bool(t.Milestone),
            "manual": bool(t.Manual),
            "start": iso(_dt(t.Start)),
            "finish": iso(_dt(t.Finish)),
            "duration_days": round_days(float(t.Duration), mpd),
            "percent_complete": int(t.PercentComplete),
            "critical": bool(t.Critical),
            "total_slack_days": round_days(float(t.TotalSlack), mpd),
            "constraint": CONSTRAINT_NAMES.get(ctype, str(ctype)),
            "constraint_date": iso(_dt(t.ConstraintDate)) if ctype not in (0, 1) else None,
            "notes": str(t.Notes) or None,
            "predecessors": preds,
            "resources": [
                {"uid": int(a.ResourceUniqueID), "name": str(a.ResourceName), "units": float(a.Units)}
                for a in t.Assignments
            ],
        }

    def list_tasks(self, include_summary: bool = True, critical_only: bool = False,
                   name_contains: str | None = None) -> list[dict]:
        out = []
        for t in self._tasks():
            if not include_summary and t.Summary:
                continue
            if critical_only and not t.Critical:
                continue
            if name_contains and name_contains.lower() not in str(t.Name).lower():
                continue
            out.append(self._task_dict(t))
        return out

    def get_task(self, uid: int) -> dict:
        return self._task_dict(self._task(uid))

    def critical_path(self) -> list[dict]:
        tasks = self.list_tasks(include_summary=False, critical_only=True)
        return sorted(tasks, key=lambda d: (d["start"] or "", d["id"]))

    def _resource_dict(self, r: Any) -> dict:
        rtype = int(r.Type)
        return {
            "uid": int(r.UniqueID),
            "id": int(r.ID),
            "name": str(r.Name),
            "type": RESOURCE_TYPE_NAMES.get(rtype, str(rtype)),
            "initials": str(r.Initials) or None,
            "email": str(r.EMailAddress) or None,
            "group": str(r.Group) or None,
            "max_units": float(r.MaxUnits) if rtype == 1 else None,
            "standard_rate": str(r.StandardRate),
            "work_hours": round(float(r.Work) / 60, 2),
            "cost": float(r.Cost),
        }

    def list_resources(self) -> list[dict]:
        return [self._resource_dict(r) for r in self.project.Resources if r is not None]

    def summary(self) -> dict:
        proj = self.project
        mpd = self.minutes_per_day
        leaves = [t for t in self._tasks() if not t.Summary]
        st = proj.ProjectSummaryTask
        return {
            "backend": self.name,
            "title": str(st.Name),
            "path": str(proj.FullName),
            "unsaved_changes": not bool(proj.Saved),
            "start": iso(_dt(proj.ProjectStart)),
            "finish": iso(_dt(proj.ProjectFinish)),
            "duration_days": round_days(float(st.Duration), mpd),
            "task_count": len(leaves),
            "milestone_count": sum(1 for t in leaves if t.Milestone),
            "critical_task_count": sum(1 for t in leaves if t.Critical),
            "resource_count": sum(1 for r in proj.Resources if r is not None),
            "percent_complete": float(st.PercentComplete),
            "total_cost": float(st.Cost),
        }

    # ------------------------------------------------------------- task edits

    def _set_constraint(self, t: Any, ctype: str, cdate: str | None) -> None:
        code = constraint_code(ctype)
        t.ConstraintType = code
        if code not in (0, 1):
            if not cdate:
                raise ProjectError(f"Constraint {ctype} needs a constraint_date")
            t.ConstraintDate = parse_when(cdate)

    def add_task(self, name: str, duration_days: float = 1.0, parent_uid: int | None = None,
                 predecessors: list[int] | None = None, constraint_type: str = "ASAP",
                 constraint_date: str | None = None, notes: str | None = None) -> dict:
        tasks = self.project.Tasks
        if parent_uid is not None:
            parent = self._task(parent_uid)
            level = int(parent.OutlineLevel) + 1
            before = None
            for t in self._tasks():
                if int(t.ID) > int(parent.ID) and int(t.OutlineLevel) <= int(parent.OutlineLevel):
                    before = int(t.ID)
                    break
            task = tasks.Add(name, before) if before is not None else tasks.Add(name)
            task.OutlineLevel = level
        else:
            task = tasks.Add(name)
            task.OutlineLevel = 1
        task.Manual = False
        task.Duration = f"{duration_days}d"
        self._set_constraint(task, constraint_type, constraint_date)
        if notes:
            task.Notes = notes
        for pred in predecessors or []:
            task.TaskDependencies.Add(self._task(pred), link_type_code("FS"), "0d")
        return self._task_dict(task)

    def update_task(self, uid: int, name: str | None = None, duration_days: float | None = None,
                    percent_complete: int | None = None, notes: str | None = None,
                    constraint_type: str | None = None, constraint_date: str | None = None) -> dict:
        t = self._task(uid)
        if name is not None:
            t.Name = name
        if duration_days is not None:
            if t.Summary:
                raise ProjectError("Summary task durations are calculated from their subtasks")
            t.Duration = f"{duration_days}d"
        if percent_complete is not None:
            if not 0 <= percent_complete <= 100:
                raise ProjectError("percent_complete must be between 0 and 100")
            t.PercentComplete = percent_complete
        if notes is not None:
            t.Notes = notes
        if constraint_type is not None:
            self._set_constraint(t, constraint_type, constraint_date)
        return self._task_dict(t)

    def delete_task(self, uid: int) -> dict:
        t = self._task(uid)
        gone = [uid]
        if t.Summary:
            for sub in self._tasks():
                if int(sub.ID) > int(t.ID):
                    if int(sub.OutlineLevel) <= int(t.OutlineLevel):
                        break
                    gone.append(int(sub.UniqueID))
        t.Delete()
        return {"deleted_task_uids": sorted(gone)}

    def link_tasks(self, predecessor_uid: int, successor_uid: int, link_type: str = "FS",
                   lag_days: float = 0.0) -> dict:
        code = link_type_code(link_type)
        if predecessor_uid == successor_uid:
            raise ProjectError("A task cannot be linked to itself")
        pred, succ = self._task(predecessor_uid), self._task(successor_uid)
        succ.TaskDependencies.Add(pred, code, f"{lag_days}d")
        return self._task_dict(succ)

    def unlink_tasks(self, predecessor_uid: int, successor_uid: int) -> dict:
        succ = self._task(successor_uid)
        found = False
        for dep in list(succ.TaskDependencies):
            if int(dep.From.UniqueID) == predecessor_uid and int(dep.To.UniqueID) == successor_uid:
                dep.Delete()
                found = True
        if not found:
            raise ProjectError(f"Task {successor_uid} has no link from task {predecessor_uid}")
        return self._task_dict(succ)

    # --------------------------------------------------------- resource edits

    def add_resource(self, name: str, resource_type: str = "work", max_units: float = 1.0,
                     standard_rate_per_hour: float = 0.0, initials: str | None = None,
                     email: str | None = None, group: str | None = None) -> dict:
        code = resource_type_code(resource_type)
        r = self.project.Resources.Add(name)
        r.Type = code
        if code == 1:
            r.MaxUnits = max_units
            r.StandardRate = f"{standard_rate_per_hour}/h"
        elif code == 0:
            r.StandardRate = standard_rate_per_hour
        if initials:
            r.Initials = initials
        if email:
            r.EMailAddress = email
        if group:
            r.Group = group
        return self._resource_dict(r)

    def delete_resource(self, uid: int) -> dict:
        self._resource(uid).Delete()
        return {"deleted_resource_uid": uid}

    def assign_resource(self, task_uid: int, resource_uid: int, units: float = 1.0) -> dict:
        if units <= 0:
            raise ProjectError("units must be > 0 (1.0 = 100%)")
        t, r = self._task(task_uid), self._resource(resource_uid)
        for a in t.Assignments:
            if int(a.ResourceUniqueID) == resource_uid:
                a.Units = units
                break
        else:
            t.Assignments.Add(TaskID=t.ID, ResourceID=r.ID, Units=units)
        return self._task_dict(t)

    def unassign_resource(self, task_uid: int, resource_uid: int) -> dict:
        t = self._task(task_uid)
        matches = [a for a in t.Assignments if int(a.ResourceUniqueID) == resource_uid]
        if not matches:
            raise ProjectError(f"Resource {resource_uid} is not assigned to task {task_uid}")
        for a in matches:
            a.Delete()
        return self._task_dict(t)

    # --------------------------------------------------------------- calendar

    def add_nonworking_day(self, day: str, name: str = "Holiday") -> dict:
        d = parse_when(day).date()
        when = datetime(d.year, d.month, d.day)
        self.project.Calendar.Exceptions.Add(Type=PJ_DAILY, Start=when, Finish=when, Name=name)
        return {"nonworking_day": d.isoformat(), "name": name, "project": self.summary()}

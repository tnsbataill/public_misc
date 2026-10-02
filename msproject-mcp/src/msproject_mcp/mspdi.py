"""Backend that edits Microsoft Project XML (MSPDI) files directly.

MSPDI is the XML format Microsoft Project 2021 opens and saves natively
(File > Save As > "XML Format (*.xml)"). The document tree is edited in place,
so elements this server does not understand are preserved on save.
"""

from __future__ import annotations

import copy
import re
import xml.etree.ElementTree as ET
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Iterator

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
from .scheduler import FS, MINUTES_PER_DAY, ScheduleError, STask, WorkCalendar, schedule

NS = "http://schemas.microsoft.com/project"
ET.register_namespace("", NS)


def q(tag: str) -> str:
    return f"{{{NS}}}{tag}"


# Child element order required by the MSPDI schema (subset that we may write).
PROJECT_ORDER = """SaveVersion UID Name GUID Title Subject Category Company Manager Author CreationDate
Revision LastSaved ScheduleFromStart StartDate FinishDate FYStartDate CriticalSlackLimit
CurrencyDigits CurrencySymbol CurrencyCode CurrencySymbolPosition CalendarUID DefaultStartTime
DefaultFinishTime MinutesPerDay MinutesPerWeek DaysPerMonth DefaultTaskType DefaultFixedCostAccrual
DefaultStandardRate DefaultOvertimeRate DurationFormat WorkFormat EditableActualCosts HonorConstraints
EarnedValueMethod InsertedProjectsLikeSummary MultipleCriticalPaths NewTasksEffortDriven
NewTasksEstimated SplitsInProgressTasks SpreadActualCost SpreadPercentComplete TaskUpdatesResource
FiscalYearStart WeekStartDay MoveCompletedEndsBack MoveRemainingStartsBack MoveRemainingStartsForward
MoveCompletedEndsForward BaselineForEarnedValue AutoAddNewResourcesAndTasks StatusDate CurrentDate
MicrosoftProjectServerURL Autolink NewTaskStartDate NewTasksAreManual DefaultTaskEVMethod
ProjectExternallyEdited ExtendedCreationDate ActualsInSync RemoveFileProperties AdminProject
UpdateManuallyScheduledTasksWhenEditingLinks KeepTaskOnNearestWorkingTimeWhenMadeAutoScheduled
OutlineCodes WBSMasks ExtendedAttributes Calendars Tasks Resources Assignments""".split()

TASK_ORDER = """UID GUID ID Name Active Manual Type IsNull CreateDate Contact WBS WBSLevel OutlineNumber
OutlineLevel Priority Start Finish Duration ManualStart ManualFinish ManualDuration DurationFormat Work
Stop Resume ResumeValid EffortDriven Recurring OverAllocated Estimated Milestone Summary
DisplayAsSummary Critical IsSubproject IsSubprojectReadOnly SubprojectName ExternalTask
ExternalTaskProject EarlyStart EarlyFinish LateStart LateFinish StartVariance FinishVariance
WorkVariance FreeSlack TotalSlack StartSlack FinishSlack FixedCost FixedCostAccrual PercentComplete
PercentWorkComplete Cost OvertimeCost OvertimeWork ActualStart ActualFinish ActualDuration ActualCost
ActualOvertimeCost ActualWork ActualOvertimeWork RegularWork RemainingDuration RemainingCost
RemainingWork RemainingOvertimeCost RemainingOvertimeWork ACWP CV ConstraintType CalendarUID
ConstraintDate Deadline LevelAssignments LevelingCanSplit LevelingDelay LevelingDelayFormat
PreLeveledStart PreLeveledFinish Hyperlink HyperlinkAddress HyperlinkSubAddress IgnoreResourceCalendar
Notes HideBar Rollup BCWS BCWP PhysicalPercentComplete EarnedValueMethod PredecessorLink
ActualWorkProtected ActualOvertimeWorkProtected ExtendedAttribute Baseline OutlineCode IsPublished
StatusManager CommitmentStart CommitmentFinish CommitmentType TimephasedData""".split()

LINK_ORDER = "PredecessorUID Type CrossProject CrossProjectName LinkLag LagFormat".split()

RESOURCE_ORDER = """UID GUID ID Name Type IsNull Initials Phonetics NTAccount MaterialLabel Code Group
WorkGroup EmailAddress Hyperlink HyperlinkAddress HyperlinkSubAddress MaxUnits PeakUnits OverAllocated
AvailableFrom AvailableTo Start Finish CanLevel AccrueAt Work RegularWork OvertimeWork ActualWork
RemainingWork ActualOvertimeWork RemainingOvertimeWork PercentWorkComplete StandardRate
StandardRateFormat Cost OvertimeRate OvertimeRateFormat OvertimeCost CostPerUse ActualCost
ActualOvertimeCost RemainingCost RemainingOvertimeCost WorkVariance CostVariance SV CV ACWP
CalendarUID Notes""".split()

ASSIGNMENT_ORDER = """UID GUID TaskUID ResourceUID PercentWorkComplete ActualCost ActualFinish
ActualOvertimeCost ActualOvertimeWork ActualStart ActualWork ACWP Confirmed Cost CostRateTable
CostVariance CV Delay Finish FinishVariance Hyperlink HyperlinkAddress HyperlinkSubAddress
WorkVariance HasFixedRateUnits FixedMaterial LevelingDelay LevelingDelayFormat LinkedFields Milestone
Notes Overallocated OvertimeCost OvertimeWork PeakUnits RegularWork RemainingCost
RemainingOvertimeCost RemainingOvertimeWork RemainingWork ResponsePending Start Stop Resume
StartVariance Units UpdateNeeded VAC Work WorkContour""".split()

CALENDAR_ORDER = "UID GUID Name IsBaseCalendar IsBaselineCalendar BaseCalendarUID WeekDays Exceptions WorkWeeks".split()
EXCEPTION_ORDER = "EnteredByOccurrences TimePeriod Occurrences Name Type DayWorking".split()


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _fmt(value: Any) -> str:
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, datetime):
        return value.isoformat(timespec="seconds")
    if isinstance(value, float):
        return f"{value:.6f}".rstrip("0").rstrip(".") or "0"
    return str(value)


def _insert_ordered(parent: ET.Element, child: ET.Element, order: list[str]) -> None:
    name = _local(child.tag)
    if name in order:
        rank = order.index(name)
        for i, existing in enumerate(parent):
            other = _local(existing.tag)
            if other in order and order.index(other) > rank:
                parent.insert(i, child)
                return
    parent.append(child)


def set_child(parent: ET.Element, tag: str, value: Any, order: list[str]) -> ET.Element:
    child = parent.find(q(tag))
    if child is None:
        child = ET.Element(q(tag))
        _insert_ordered(parent, child, order)
    child.text = _fmt(value)
    return child


def add_child(parent: ET.Element, tag: str, order: list[str]) -> ET.Element:
    child = ET.Element(q(tag))
    _insert_ordered(parent, child, order)
    return child


def remove_child(parent: ET.Element, tag: str) -> None:
    for child in parent.findall(q(tag)):
        parent.remove(child)


def text(el: ET.Element, tag: str, default: str | None = None) -> str | None:
    child = el.find(q(tag))
    if child is None or child.text is None:
        return default
    return child.text.strip()


def int_of(el: ET.Element, tag: str, default: int = 0) -> int:
    value = text(el, tag)
    try:
        return int(float(value)) if value is not None else default
    except ValueError:
        return default


def float_of(el: ET.Element, tag: str, default: float = 0.0) -> float:
    value = text(el, tag)
    try:
        return float(value) if value is not None else default
    except ValueError:
        return default


def dt_of(el: ET.Element, tag: str) -> datetime | None:
    value = text(el, tag)
    if not value:
        return None
    try:
        return datetime.fromisoformat(value).replace(tzinfo=None)
    except ValueError:
        return None


_DURATION = re.compile(
    r"^(-)?P(?:(\d+(?:\.\d+)?)Y)?(?:(\d+(?:\.\d+)?)M)?(?:(\d+(?:\.\d+)?)D)?"
    r"(?:T(?:(\d+(?:\.\d+)?)H)?(?:(\d+(?:\.\d+)?)M)?(?:(\d+(?:\.\d+)?)S)?)?$"
)


def parse_duration(value: str | None, minutes_per_day: float = MINUTES_PER_DAY) -> float:
    """ISO-8601 duration (as written by Project, e.g. 'PT16H0M0S') to working minutes."""
    if not value:
        return 0.0
    m = _DURATION.match(value.strip())
    if not m:
        return 0.0
    sign, years, months, days, hours, mins, secs = m.groups()
    total = (
        float(years or 0) * 12 * 20 * minutes_per_day
        + float(months or 0) * 20 * minutes_per_day
        + float(days or 0) * minutes_per_day
        + float(hours or 0) * 60
        + float(mins or 0)
        + float(secs or 0) / 60
    )
    return -total if sign else total


def format_duration(minutes: float) -> str:
    seconds = int(round(abs(minutes) * 60))
    h, rest = divmod(seconds, 3600)
    m, s = divmod(rest, 60)
    return f"{'-' if minutes < 0 else ''}PT{h}H{m}M{s}S"


def _sub(parent: ET.Element, tag: str, value: Any = None) -> ET.Element:
    el = ET.SubElement(parent, q(tag))
    if value is not None:
        el.text = _fmt(value)
    return el


def _standard_calendar(parent: ET.Element) -> None:
    cal = _sub(parent, "Calendar")
    _sub(cal, "UID", 1)
    _sub(cal, "Name", "Standard")
    _sub(cal, "IsBaseCalendar", 1)
    _sub(cal, "IsBaselineCalendar", 0)
    _sub(cal, "BaseCalendarUID", -1)
    weekdays = _sub(cal, "WeekDays")
    for day_type in range(1, 8):  # 1 = Sunday .. 7 = Saturday
        wd = _sub(weekdays, "WeekDay")
        _sub(wd, "DayType", day_type)
        working = day_type not in (1, 7)
        _sub(wd, "DayWorking", int(working))
        if working:
            times = _sub(wd, "WorkingTimes")
            for start, finish in (("08:00:00", "12:00:00"), ("13:00:00", "17:00:00")):
                wt = _sub(times, "WorkingTime")
                _sub(wt, "FromTime", start)
                _sub(wt, "ToTime", finish)


def new_document(title: str, start: datetime) -> ET.ElementTree:
    root = ET.Element(q("Project"))
    _sub(root, "SaveVersion", 14)
    _sub(root, "Name", f"{title}.xml")
    _sub(root, "Title", title)
    _sub(root, "CreationDate", datetime.now().replace(microsecond=0))
    _sub(root, "ScheduleFromStart", 1)
    _sub(root, "StartDate", start)
    _sub(root, "FinishDate", start)
    _sub(root, "CalendarUID", 1)
    _sub(root, "DefaultStartTime", "08:00:00")
    _sub(root, "DefaultFinishTime", "17:00:00")
    _sub(root, "MinutesPerDay", 480)
    _sub(root, "MinutesPerWeek", 2400)
    _sub(root, "DaysPerMonth", 20)
    _sub(root, "DurationFormat", 7)
    _sub(root, "WorkFormat", 2)
    _sub(root, "NewTasksAreManual", 0)
    _standard_calendar(_sub(root, "Calendars"))
    tasks = _sub(root, "Tasks")
    summary = _sub(tasks, "Task")
    for tag, value in (
        ("UID", 0), ("ID", 0), ("Name", title), ("Manual", 0), ("Type", 1), ("IsNull", 0),
        ("WBS", 0), ("OutlineNumber", 0), ("OutlineLevel", 0), ("Start", start), ("Finish", start),
        ("Duration", "PT0H0M0S"), ("DurationFormat", 7), ("Summary", 1),
    ):
        _sub(summary, tag, value)
    _sub(root, "Resources")
    _sub(root, "Assignments")
    return ET.ElementTree(root)


class XmlBackend:
    """Edits an MSPDI document held in memory; ``save`` writes it to disk."""

    name = "xml"

    def __init__(self) -> None:
        self.tree: ET.ElementTree | None = None
        self.path: Path | None = None
        self.dirty = False

    # ------------------------------------------------------------------ plumbing

    @property
    def root(self) -> ET.Element:
        if self.tree is None:
            raise ProjectError("No project is open. Call open_project or new_project first.")
        return self.tree.getroot()

    def _section(self, tag: str) -> ET.Element:
        el = self.root.find(q(tag))
        if el is None:
            el = add_child(self.root, tag, PROJECT_ORDER)
        return el

    @property
    def minutes_per_day(self) -> float:
        return float_of(self.root, "MinutesPerDay", MINUTES_PER_DAY) or MINUTES_PER_DAY

    def _tasks(self) -> list[ET.Element]:
        return self._section("Tasks").findall(q("Task"))

    def _resources(self) -> list[ET.Element]:
        return [r for r in self._section("Resources").findall(q("Resource")) if int_of(r, "UID") != 0]

    def _assignments(self) -> list[ET.Element]:
        return self._section("Assignments").findall(q("Assignment"))

    def _task(self, uid: int) -> ET.Element:
        for t in self._tasks():
            if int_of(t, "UID", -1) == uid:
                return t
        raise ProjectError(f"No task with UID {uid}")

    def _resource(self, uid: int) -> ET.Element:
        for r in self._resources():
            if int_of(r, "UID", -1) == uid:
                return r
        raise ProjectError(f"No resource with UID {uid}")

    @staticmethod
    def _is_project_summary(t: ET.Element) -> bool:
        return int_of(t, "OutlineLevel", 1) == 0

    def _descendants(self, uid: int) -> list[ET.Element]:
        tasks = self._tasks()
        idx = next(i for i, t in enumerate(tasks) if int_of(t, "UID", -1) == uid)
        level = int_of(tasks[idx], "OutlineLevel", 1)
        out = []
        for t in tasks[idx + 1:]:
            if int_of(t, "OutlineLevel", 1) <= level:
                break
            out.append(t)
        return out

    @contextmanager
    def _mutation(self) -> Iterator[None]:
        """Apply a change and reschedule; restore the previous document on failure."""
        backup = copy.deepcopy(self.root)
        try:
            yield
            self._renumber()
            self._reschedule()
        except Exception:
            self.tree = ET.ElementTree(backup)
            raise
        self.dirty = True

    # ------------------------------------------------------------- file actions

    def new(self, title: str, start: str, path: str | None = None) -> dict:
        self.tree = new_document(title, parse_when(start))
        self.path = Path(path).expanduser().resolve() if path else None
        self._reschedule()
        self.dirty = True
        if self.path:
            self.save()
        return self.summary()

    def open(self, path: str) -> dict:
        p = Path(path).expanduser().resolve()
        if p.suffix.lower() == ".mpp":
            raise ProjectError(
                "The xml backend cannot read binary .mpp files. In Project 2021 use "
                "File > Save As > 'XML Format (*.xml)', or run this server with MSPROJECT_BACKEND=com on Windows."
            )
        if not p.exists():
            raise ProjectError(f"File not found: {p}")
        try:
            tree = ET.parse(p)
        except ET.ParseError as exc:
            raise ProjectError(f"Not a valid XML file: {exc}") from None
        if tree.getroot().tag != q("Project"):
            raise ProjectError("Not a Microsoft Project XML (MSPDI) file: root element must be <Project>")
        self.tree, self.path, self.dirty = tree, p, False
        return self.summary()

    def save(self, path: str | None = None) -> dict:
        root = self.root
        if path:
            self.path = Path(path).expanduser().resolve()
        if self.path is None:
            raise ProjectError("No file path set; pass a path ending in .xml")
        if self.path.suffix.lower() != ".xml":
            raise ProjectError("The xml backend saves MSPDI XML only; use a path ending in .xml")
        set_child(root, "Name", self.path.name, PROJECT_ORDER)
        set_child(root, "LastSaved", datetime.now().replace(microsecond=0), PROJECT_ORDER)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        ET.indent(self.tree, space="  ")
        self.tree.write(self.path, encoding="UTF-8", xml_declaration=True)
        self.dirty = False
        return {"saved": str(self.path)}

    # ---------------------------------------------------------------- scheduling

    def _calendar(self, start: date) -> WorkCalendar:
        cal_uid = int_of(self.root, "CalendarUID", 1)
        cal = None
        for c in self._section("Calendars").findall(q("Calendar")):
            if int_of(c, "UID", -1) == cal_uid:
                cal = c
                break
        if cal is None:
            return WorkCalendar(start)
        weekdays: set[int] = set()
        holidays: set[date] = set()
        found_weekday = False

        def add_range(period: ET.Element | None) -> None:
            if period is None:
                return
            first, last = dt_of(period, "FromDate"), dt_of(period, "ToDate")
            if first and last:
                d = first.date()
                while d <= last.date() and (d - first.date()).days < 3700:
                    holidays.add(d)
                    d += timedelta(days=1)

        for wd in cal.iter(q("WeekDay")):
            day_type = int_of(wd, "DayType", -1)
            working = int_of(wd, "DayWorking") == 1
            if 1 <= day_type <= 7:
                found_weekday = True
                if working:
                    weekdays.add((day_type + 5) % 7)  # 1=Sunday -> 6, 2=Monday -> 0
            elif day_type == 0 and not working:
                add_range(wd.find(q("TimePeriod")))
        for exc in cal.iter(q("Exception")):
            if int_of(exc, "DayWorking") == 0:
                add_range(exc.find(q("TimePeriod")))
        return WorkCalendar(start, weekdays if found_weekday else None, holidays)

    def _project_start(self) -> datetime:
        start = dt_of(self.root, "StartDate")
        if start is None:
            starts = [dt_of(t, "Start") for t in self._tasks()]
            start = min((s for s in starts if s), default=datetime.now().replace(hour=8, minute=0, second=0, microsecond=0))
        return start

    def _renumber(self) -> None:
        counters: list[int] = []
        next_id = 1
        for t in self._tasks():
            level = int_of(t, "OutlineLevel", 1)
            if level == 0:
                set_child(t, "ID", 0, TASK_ORDER)
                continue
            set_child(t, "ID", next_id, TASK_ORDER)
            next_id += 1
            del counters[level:]
            while len(counters) < level:
                counters.append(0)
            counters[level - 1] += 1
            number = ".".join(str(c) for c in counters)
            old = text(t, "OutlineNumber")
            if text(t, "WBS") in (None, old):
                set_child(t, "WBS", number, TASK_ORDER)
            set_child(t, "OutlineNumber", number, TASK_ORDER)

    def _reschedule(self) -> None:
        start = self._project_start()
        cal = self._calendar(start.date())
        mpd = self.minutes_per_day
        scale = MINUTES_PER_DAY / mpd  # the scheduler always works in 480-minute days

        elements: dict[int, ET.Element] = {}
        stasks: list[STask] = []
        for t in self._tasks():
            if self._is_project_summary(t) or int_of(t, "IsNull") == 1:
                continue
            uid = int_of(t, "UID")
            elements[uid] = t
            st = STask(uid=uid, level=max(int_of(t, "OutlineLevel", 1), 1))
            st.duration = int(round(parse_duration(text(t, "Duration"), mpd) * scale))
            for link in t.findall(q("PredecessorLink")):
                lag = float_of(link, "LinkLag") / 10 * scale
                st.links.append((int_of(link, "PredecessorUID", -1), int_of(link, "Type", FS), int(round(lag))))
            ctype = int_of(t, "ConstraintType")
            cdate = dt_of(t, "ConstraintDate")
            actual = dt_of(t, "ActualStart")
            if actual is not None:
                st.fixed_start = cal.to_offset(actual)
            elif int_of(t, "Manual") == 1 and dt_of(t, "Start") is not None:
                st.fixed_start = cal.to_offset(dt_of(t, "Start"))
            elif cdate is not None and ctype == 2:  # Must Start On
                st.fixed_start = cal.to_offset(cdate)
            elif cdate is not None and ctype == 4:  # Start No Earlier Than
                st.snet = cal.to_offset(cdate)
            elif cdate is not None and ctype == 6:  # Finish No Earlier Than
                st.fnet = cal.to_offset(cdate)
            stasks.append(st)

        try:
            finish = schedule(stasks)
        except ScheduleError as exc:
            raise ProjectError(str(exc)) from None

        by_uid = {s.uid: s for s in stasks}
        for st in stasks:
            t = elements[st.uid]
            if st.duration == 0 and not st.summary:
                t_start = t_finish = cal.finish_dt(st.es)
            else:
                t_start, t_finish = cal.start_dt(st.es), cal.finish_dt(st.ef)
            set_child(t, "Start", t_start, TASK_ORDER)
            set_child(t, "Finish", t_finish, TASK_ORDER)
            if st.summary:
                set_child(t, "Duration", format_duration(st.duration / scale), TASK_ORDER)
            set_child(t, "Milestone", st.duration == 0 and not st.summary, TASK_ORDER)
            set_child(t, "Summary", st.summary, TASK_ORDER)
            set_child(t, "EarlyStart", cal.start_dt(st.es), TASK_ORDER)
            set_child(t, "EarlyFinish", cal.finish_dt(st.ef), TASK_ORDER)
            set_child(t, "LateStart", cal.start_dt(st.ls), TASK_ORDER)
            set_child(t, "LateFinish", cal.finish_dt(st.lf), TASK_ORDER)
            slack = st.total_slack if not st.summary else min(
                by_uid[c].total_slack for c in st.children
            )
            set_child(t, "TotalSlack", int(round(slack / scale * 10)), TASK_ORDER)
            set_child(t, "Critical", slack <= 0, TASK_ORDER)

        project_start = cal.start_dt(min((s.es for s in stasks), default=0))
        project_finish = cal.finish_dt(finish)
        for t in self._tasks():
            if self._is_project_summary(t):
                set_child(t, "Start", project_start, TASK_ORDER)
                set_child(t, "Finish", project_finish, TASK_ORDER)
                set_child(t, "Duration", format_duration(finish / scale), TASK_ORDER)
                set_child(t, "Summary", True, TASK_ORDER)
        set_child(self.root, "FinishDate", project_finish, PROJECT_ORDER)

        # Keep assignment dates and work consistent with their tasks.
        resource_work: dict[int, float] = {}
        task_work: dict[int, float] = {}
        for a in self._assignments():
            st = by_uid.get(int_of(a, "TaskUID", -1))
            if st is None:
                continue
            t = elements[st.uid]
            work = st.duration / scale * float_of(a, "Units", 1.0)
            set_child(a, "Start", dt_of(t, "Start"), ASSIGNMENT_ORDER)
            set_child(a, "Finish", dt_of(t, "Finish"), ASSIGNMENT_ORDER)
            set_child(a, "Work", format_duration(work), ASSIGNMENT_ORDER)
            r_uid = int_of(a, "ResourceUID", -1)
            resource_work[r_uid] = resource_work.get(r_uid, 0.0) + work
            task_work[st.uid] = task_work.get(st.uid, 0.0) + work
        for uid, work in task_work.items():
            set_child(elements[uid], "Work", format_duration(work), TASK_ORDER)
        for r in self._resources():
            set_child(r, "Work", format_duration(resource_work.get(int_of(r, "UID"), 0.0)), RESOURCE_ORDER)

    def recalculate(self) -> dict:
        with self._mutation():
            pass
        return self.summary()

    # -------------------------------------------------------------- read views

    def _resource_rate(self, r: ET.Element) -> float:
        return float_of(r, "StandardRate")

    def _task_dict(self, t: ET.Element, names: dict[int, str] | None = None) -> dict:
        mpd = self.minutes_per_day
        uid = int_of(t, "UID")
        if names is None:
            names = {int_of(r, "UID"): text(r, "Name", "") for r in self._resources()}
        ctype = int_of(t, "ConstraintType")
        return {
            "uid": uid,
            "id": int_of(t, "ID"),
            "name": text(t, "Name", ""),
            "wbs": text(t, "WBS"),
            "outline_level": int_of(t, "OutlineLevel", 1),
            "summary": int_of(t, "Summary") == 1,
            "milestone": int_of(t, "Milestone") == 1,
            "manual": int_of(t, "Manual") == 1,
            "start": iso(dt_of(t, "Start")),
            "finish": iso(dt_of(t, "Finish")),
            "duration_days": round_days(parse_duration(text(t, "Duration"), mpd), mpd),
            "percent_complete": int_of(t, "PercentComplete"),
            "critical": int_of(t, "Critical") == 1,
            "total_slack_days": round_days(float_of(t, "TotalSlack") / 10, mpd),
            "constraint": CONSTRAINT_NAMES.get(ctype, str(ctype)),
            "constraint_date": iso(dt_of(t, "ConstraintDate")) if ctype not in (0, 1) else None,
            "notes": text(t, "Notes"),
            "predecessors": [
                {
                    "uid": int_of(link, "PredecessorUID"),
                    "type": LINK_NAMES.get(int_of(link, "Type", FS), "FS"),
                    "lag_days": round_days(float_of(link, "LinkLag") / 10, mpd),
                }
                for link in t.findall(q("PredecessorLink"))
            ],
            "resources": [
                {"uid": int_of(a, "ResourceUID"), "name": names.get(int_of(a, "ResourceUID"), "?"),
                 "units": float_of(a, "Units", 1.0)}
                for a in self._assignments()
                if int_of(a, "TaskUID", -1) == uid
            ],
        }

    def list_tasks(self, include_summary: bool = True, critical_only: bool = False,
                   name_contains: str | None = None) -> list[dict]:
        names = {int_of(r, "UID"): text(r, "Name", "") for r in self._resources()}
        out = []
        for t in self._tasks():
            if self._is_project_summary(t) or int_of(t, "IsNull") == 1:
                continue
            d = self._task_dict(t, names)
            if not include_summary and d["summary"]:
                continue
            if critical_only and not d["critical"]:
                continue
            if name_contains and name_contains.lower() not in d["name"].lower():
                continue
            out.append(d)
        return out

    def get_task(self, uid: int) -> dict:
        return self._task_dict(self._task(uid))

    def critical_path(self) -> list[dict]:
        tasks = self.list_tasks(include_summary=False, critical_only=True)
        return sorted(tasks, key=lambda d: (d["start"] or "", d["id"]))

    def _resource_dict(self, r: ET.Element) -> dict:
        mpd = self.minutes_per_day
        rtype = int_of(r, "Type", 1)
        work_hours = round(parse_duration(text(r, "Work"), mpd) / 60, 2)
        rate = self._resource_rate(r)
        return {
            "uid": int_of(r, "UID"),
            "id": int_of(r, "ID"),
            "name": text(r, "Name", ""),
            "type": RESOURCE_TYPE_NAMES.get(rtype, str(rtype)),
            "initials": text(r, "Initials"),
            "email": text(r, "EmailAddress"),
            "group": text(r, "Group"),
            "max_units": float_of(r, "MaxUnits", 1.0),
            "standard_rate_per_hour": rate,
            "work_hours": work_hours,
            "cost": round(work_hours * rate, 2) if rtype == 1 else None,
        }

    def list_resources(self) -> list[dict]:
        return [self._resource_dict(r) for r in self._resources()]

    def summary(self) -> dict:
        root = self.root
        mpd = self.minutes_per_day
        leaves = self.list_tasks(include_summary=False)
        total = sum(t["duration_days"] for t in leaves)
        done = sum(t["duration_days"] * t["percent_complete"] / 100 for t in leaves)
        resources = self.list_resources()
        start, finish = dt_of(root, "StartDate"), dt_of(root, "FinishDate")
        project_summary = next((t for t in self._tasks() if self._is_project_summary(t)), None)
        return {
            "backend": self.name,
            "title": text(root, "Title") or text(root, "Name"),
            "path": str(self.path) if self.path else None,
            "unsaved_changes": self.dirty,
            "start": iso(start),
            "finish": iso(finish),
            "duration_days": round_days(parse_duration(text(project_summary, "Duration"), mpd), mpd)
            if project_summary is not None else None,
            "task_count": len(leaves),
            "milestone_count": sum(1 for t in leaves if t["milestone"]),
            "critical_task_count": sum(1 for t in leaves if t["critical"]),
            "resource_count": len(resources),
            "percent_complete": round(100 * done / total, 1) if total else 0.0,
            "estimated_labor_cost": round(sum(r["cost"] or 0 for r in resources), 2),
        }

    # ------------------------------------------------------------- task edits

    def _set_constraint(self, t: ET.Element, ctype: str, cdate: str | None) -> None:
        code = constraint_code(ctype)
        set_child(t, "ConstraintType", code, TASK_ORDER)
        if code in (0, 1):
            remove_child(t, "ConstraintDate")
        else:
            if not cdate:
                raise ProjectError(f"Constraint {ctype} needs a constraint_date")
            set_child(t, "ConstraintDate", parse_when(cdate), TASK_ORDER)

    def _set_duration(self, t: ET.Element, days: float) -> None:
        if days < 0:
            raise ProjectError("duration_days must be >= 0")
        set_child(t, "Duration", format_duration(days * self.minutes_per_day), TASK_ORDER)
        set_child(t, "DurationFormat", 7, TASK_ORDER)

    def add_task(self, name: str, duration_days: float = 1.0, parent_uid: int | None = None,
                 predecessors: list[int] | None = None, constraint_type: str = "ASAP",
                 constraint_date: str | None = None, notes: str | None = None) -> dict:
        with self._mutation():
            tasks_el = self._section("Tasks")
            tasks = self._tasks()
            uid = max((int_of(t, "UID") for t in tasks), default=0) + 1
            if parent_uid is not None:
                parent = self._task(parent_uid)
                level = int_of(parent, "OutlineLevel", 1) + 1
                after = (self._descendants(parent_uid) or [parent])[-1]
                index = list(tasks_el).index(after) + 1
            else:
                level, index = 1, len(tasks_el)
            t = ET.Element(q("Task"))
            for tag, value in (
                ("UID", uid), ("ID", uid), ("Name", name), ("Manual", 0), ("Type", 0), ("IsNull", 0),
                ("CreateDate", datetime.now().replace(microsecond=0)), ("OutlineLevel", level),
                ("Priority", 500), ("PercentComplete", 0), ("CalendarUID", -1),
            ):
                set_child(t, tag, value, TASK_ORDER)
            self._set_duration(t, duration_days)
            self._set_constraint(t, constraint_type, constraint_date)
            if notes:
                set_child(t, "Notes", notes, TASK_ORDER)
            tasks_el.insert(index, t)
            for pred in predecessors or []:
                self._add_link(pred, uid, "FS", 0.0)
        return self.get_task(uid)

    def update_task(self, uid: int, name: str | None = None, duration_days: float | None = None,
                    percent_complete: int | None = None, notes: str | None = None,
                    constraint_type: str | None = None, constraint_date: str | None = None) -> dict:
        with self._mutation():
            t = self._task(uid)
            if name is not None:
                set_child(t, "Name", name, TASK_ORDER)
            if duration_days is not None:
                if self._descendants(uid):
                    raise ProjectError("Summary task durations are calculated from their subtasks")
                self._set_duration(t, duration_days)
            if percent_complete is not None:
                if not 0 <= percent_complete <= 100:
                    raise ProjectError("percent_complete must be between 0 and 100")
                set_child(t, "PercentComplete", percent_complete, TASK_ORDER)
            if notes is not None:
                set_child(t, "Notes", notes, TASK_ORDER)
            if constraint_type is not None:
                self._set_constraint(t, constraint_type, constraint_date)
        return self.get_task(uid)

    def delete_task(self, uid: int) -> dict:
        with self._mutation():
            t = self._task(uid)
            if self._is_project_summary(t):
                raise ProjectError("The project summary task cannot be deleted")
            doomed = [t, *self._descendants(uid)]
            gone = {int_of(x, "UID") for x in doomed}
            tasks_el = self._section("Tasks")
            for x in doomed:
                tasks_el.remove(x)
            for other in self._tasks():
                for link in other.findall(q("PredecessorLink")):
                    if int_of(link, "PredecessorUID", -1) in gone:
                        other.remove(link)
            assignments_el = self._section("Assignments")
            for a in self._assignments():
                if int_of(a, "TaskUID", -1) in gone:
                    assignments_el.remove(a)
        return {"deleted_task_uids": sorted(gone)}

    def _add_link(self, pred_uid: int, succ_uid: int, link_type: str, lag_days: float) -> None:
        code = link_type_code(link_type)
        if pred_uid == succ_uid:
            raise ProjectError("A task cannot be linked to itself")
        pred, succ = self._task(pred_uid), self._task(succ_uid)
        if self._is_project_summary(pred) or self._is_project_summary(succ):
            raise ProjectError("The project summary task cannot be linked")
        if succ in self._descendants(pred_uid) or pred in self._descendants(succ_uid):
            raise ProjectError("A summary task cannot be linked to its own subtasks")
        link = next((x for x in succ.findall(q("PredecessorLink"))
                     if int_of(x, "PredecessorUID", -1) == pred_uid), None)
        if link is None:
            link = add_child(succ, "PredecessorLink", TASK_ORDER)
        set_child(link, "PredecessorUID", pred_uid, LINK_ORDER)
        set_child(link, "Type", code, LINK_ORDER)
        set_child(link, "CrossProject", 0, LINK_ORDER)
        set_child(link, "LinkLag", int(round(lag_days * self.minutes_per_day * 10)), LINK_ORDER)
        set_child(link, "LagFormat", 7, LINK_ORDER)

    def link_tasks(self, predecessor_uid: int, successor_uid: int, link_type: str = "FS",
                   lag_days: float = 0.0) -> dict:
        with self._mutation():
            self._add_link(predecessor_uid, successor_uid, link_type, lag_days)
        return self.get_task(successor_uid)

    def unlink_tasks(self, predecessor_uid: int, successor_uid: int) -> dict:
        with self._mutation():
            succ = self._task(successor_uid)
            links = [x for x in succ.findall(q("PredecessorLink"))
                     if int_of(x, "PredecessorUID", -1) == predecessor_uid]
            if not links:
                raise ProjectError(f"Task {successor_uid} has no link from task {predecessor_uid}")
            for x in links:
                succ.remove(x)
        return self.get_task(successor_uid)

    # --------------------------------------------------------- resource edits

    def add_resource(self, name: str, resource_type: str = "work", max_units: float = 1.0,
                     standard_rate_per_hour: float = 0.0, initials: str | None = None,
                     email: str | None = None, group: str | None = None) -> dict:
        code = resource_type_code(resource_type)
        with self._mutation():
            res_el = self._section("Resources")
            uids = [int_of(r, "UID") for r in res_el.findall(q("Resource"))]
            uid = max(uids, default=0) + 1
            r = ET.Element(q("Resource"))
            values: list[tuple[str, Any]] = [
                ("UID", uid), ("ID", len(self._resources()) + 1), ("Name", name), ("Type", code),
                ("IsNull", 0), ("Initials", initials or name[:1].upper()),
                ("MaxUnits", max_units if code == 1 else 1.0),
                ("StandardRate", standard_rate_per_hour), ("StandardRateFormat", 2),
            ]
            if email:
                values.append(("EmailAddress", email))
            if group:
                values.append(("Group", group))
            for tag, value in values:
                set_child(r, tag, value, RESOURCE_ORDER)
            res_el.append(r)
        return self._resource_dict(self._resource(uid))

    def delete_resource(self, uid: int) -> dict:
        with self._mutation():
            self._section("Resources").remove(self._resource(uid))
            assignments_el = self._section("Assignments")
            for a in self._assignments():
                if int_of(a, "ResourceUID", -1) == uid:
                    assignments_el.remove(a)
            for i, r in enumerate(self._resources(), start=1):
                set_child(r, "ID", i, RESOURCE_ORDER)
        return {"deleted_resource_uid": uid}

    def assign_resource(self, task_uid: int, resource_uid: int, units: float = 1.0) -> dict:
        if units <= 0:
            raise ProjectError("units must be > 0 (1.0 = 100%)")
        with self._mutation():
            t = self._task(task_uid)
            self._resource(resource_uid)
            if self._is_project_summary(t):
                raise ProjectError("Resources cannot be assigned to the project summary task")
            existing = next((a for a in self._assignments()
                             if int_of(a, "TaskUID", -1) == task_uid
                             and int_of(a, "ResourceUID", -1) == resource_uid), None)
            if existing is None:
                uid = max((int_of(a, "UID") for a in self._assignments()), default=0) + 1
                existing = ET.Element(q("Assignment"))
                set_child(existing, "UID", uid, ASSIGNMENT_ORDER)
                set_child(existing, "TaskUID", task_uid, ASSIGNMENT_ORDER)
                set_child(existing, "ResourceUID", resource_uid, ASSIGNMENT_ORDER)
                self._section("Assignments").append(existing)
            set_child(existing, "Units", float(units), ASSIGNMENT_ORDER)
        return self.get_task(task_uid)

    def unassign_resource(self, task_uid: int, resource_uid: int) -> dict:
        with self._mutation():
            matches = [a for a in self._assignments()
                       if int_of(a, "TaskUID", -1) == task_uid and int_of(a, "ResourceUID", -1) == resource_uid]
            if not matches:
                raise ProjectError(f"Resource {resource_uid} is not assigned to task {task_uid}")
            for a in matches:
                self._section("Assignments").remove(a)
        return self.get_task(task_uid)

    # --------------------------------------------------------------- calendar

    def add_nonworking_day(self, day: str, name: str = "Holiday") -> dict:
        d = parse_when(day).date()
        with self._mutation():
            cal_uid = int_of(self.root, "CalendarUID", 1)
            calendars = self._section("Calendars")
            cal = next((c for c in calendars.findall(q("Calendar")) if int_of(c, "UID", -1) == cal_uid), None)
            if cal is None:
                raise ProjectError(f"Project calendar UID {cal_uid} not found")
            exceptions = cal.find(q("Exceptions"))
            if exceptions is None:
                exceptions = add_child(cal, "Exceptions", CALENDAR_ORDER)
            exc = ET.SubElement(exceptions, q("Exception"))
            set_child(exc, "EnteredByOccurrences", 0, EXCEPTION_ORDER)
            period = add_child(exc, "TimePeriod", EXCEPTION_ORDER)
            _sub(period, "FromDate", datetime(d.year, d.month, d.day))
            _sub(period, "ToDate", datetime(d.year, d.month, d.day, 23, 59))
            set_child(exc, "Occurrences", 1, EXCEPTION_ORDER)
            set_child(exc, "Name", name, EXCEPTION_ORDER)
            set_child(exc, "Type", 1, EXCEPTION_ORDER)
            set_child(exc, "DayWorking", 0, EXCEPTION_ORDER)
        return {"nonworking_day": d.isoformat(), "name": name, "project": self.summary()}

"""MCP server exposing Microsoft Project 2021 schedules as tools.

Backends (choose with the MSPROJECT_BACKEND environment variable):
  xml  (default) edit Project XML (MSPDI) files directly; works on any OS.
  com  drive a running Microsoft Project 2021 on Windows via COM automation.
"""

from __future__ import annotations

import os
from typing import Annotated, Any, Literal

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from .common import ProjectError

LinkType = Literal["FS", "SS", "FF", "SF"]
ConstraintType = Literal["ASAP", "ALAP", "SNET", "SNLT", "FNET", "FNLT", "MSO", "MFO"]
ResourceType = Literal["work", "material", "cost"]

INSTRUCTIONS = """\
Tools for building and editing Microsoft Project 2021 schedules.
Workflow: open_project (or new_project) -> inspect with get_project_summary/list_tasks ->
edit with add_task/link_tasks/assign_resource/... -> save_project.
Tasks and resources are identified by their UID (stable), not their row ID.
Durations and lags are in working days (8h). Dates are 'YYYY-MM-DD' or 'YYYY-MM-DDTHH:MM'.
Changes are only written to disk by save_project."""

mcp = FastMCP("msproject", instructions=INSTRUCTIONS)

_backend: Any = None


def make_backend(kind: str | None = None) -> Any:
    kind = (kind or os.environ.get("MSPROJECT_BACKEND", "xml")).lower()
    if kind == "xml":
        from .mspdi import XmlBackend

        return XmlBackend()
    if kind == "com":
        from .com_backend import ComBackend

        return ComBackend()
    raise ProjectError(f"Unknown MSPROJECT_BACKEND {kind!r}; use 'xml' or 'com'")


def backend() -> Any:
    global _backend
    if _backend is None:
        _backend = make_backend()
    return _backend


def set_backend(value: Any) -> None:
    """Replace the active backend (used by tests)."""
    global _backend
    _backend = value


Uid = Annotated[int, Field(description="Task UID (from list_tasks)")]
Days = Annotated[float, Field(description="Working days; 0 makes a milestone", ge=0)]


# --------------------------------------------------------------------- project


@mcp.tool()
def new_project(
    title: str,
    start_date: Annotated[str, Field(description="Project start, YYYY-MM-DD")],
    path: Annotated[str | None, Field(description="Optional file to save to (.xml; .mpp with the com backend)")] = None,
) -> dict:
    """Create a new, empty project with a standard Mon-Fri 8h calendar."""
    return backend().new(title, start_date, path)


@mcp.tool()
def open_project(path: Annotated[str, Field(description="Path to a Project XML file (or .mpp with the com backend)")]) -> dict:
    """Open an existing project file and return its summary."""
    return backend().open(path)


@mcp.tool()
def save_project(path: Annotated[str | None, Field(description="Save-as path; omit to save in place")] = None) -> dict:
    """Write the open project to disk."""
    return backend().save(path)


@mcp.tool()
def get_project_summary() -> dict:
    """Project title, start/finish, duration, task/resource counts, progress and cost."""
    return backend().summary()


@mcp.tool()
def recalculate_schedule() -> dict:
    """Recalculate dates, slack and the critical path."""
    return backend().recalculate()


# ----------------------------------------------------------------------- tasks


@mcp.tool()
def list_tasks(
    include_summary: bool = True,
    critical_only: bool = False,
    name_contains: str | None = None,
) -> list[dict]:
    """List tasks in outline order with dates, duration, progress, links and resources."""
    return backend().list_tasks(include_summary, critical_only, name_contains)


@mcp.tool()
def get_task(uid: Uid) -> dict:
    """Full details for one task."""
    return backend().get_task(uid)


@mcp.tool()
def get_critical_path() -> list[dict]:
    """Critical (zero-slack) work tasks in start order: the chain that drives the finish date."""
    return backend().critical_path()


@mcp.tool()
def add_task(
    name: str,
    duration_days: Days = 1.0,
    parent_uid: Annotated[int | None, Field(description="Make this a subtask of the given task (which becomes a summary)")] = None,
    predecessors: Annotated[list[int] | None, Field(description="UIDs of finish-to-start predecessors")] = None,
    constraint_type: ConstraintType = "ASAP",
    constraint_date: Annotated[str | None, Field(description="Required for constraints other than ASAP/ALAP")] = None,
    notes: str | None = None,
) -> dict:
    """Add an auto-scheduled task (at the end, or as the last subtask of parent_uid)."""
    return backend().add_task(name, duration_days, parent_uid, predecessors, constraint_type, constraint_date, notes)


@mcp.tool()
def update_task(
    uid: Uid,
    name: str | None = None,
    duration_days: Annotated[float | None, Field(ge=0)] = None,
    percent_complete: Annotated[int | None, Field(ge=0, le=100)] = None,
    notes: str | None = None,
    constraint_type: ConstraintType | None = None,
    constraint_date: str | None = None,
) -> dict:
    """Change fields of a task; omitted fields are left unchanged."""
    return backend().update_task(uid, name, duration_days, percent_complete, notes, constraint_type, constraint_date)


@mcp.tool()
def delete_task(uid: Uid) -> dict:
    """Delete a task (and its subtasks), along with its links and assignments."""
    return backend().delete_task(uid)


@mcp.tool()
def link_tasks(
    predecessor_uid: int,
    successor_uid: int,
    link_type: LinkType = "FS",
    lag_days: Annotated[float, Field(description="Lag in working days; negative for lead time")] = 0.0,
) -> dict:
    """Create (or update) a dependency. FS=finish-to-start, SS=start-to-start, FF, SF."""
    return backend().link_tasks(predecessor_uid, successor_uid, link_type, lag_days)


@mcp.tool()
def unlink_tasks(predecessor_uid: int, successor_uid: int) -> dict:
    """Remove the dependency between two tasks."""
    return backend().unlink_tasks(predecessor_uid, successor_uid)


# ------------------------------------------------------------------- resources


@mcp.tool()
def list_resources() -> list[dict]:
    """List resources with type, availability, rate, assigned work and cost."""
    return backend().list_resources()


@mcp.tool()
def add_resource(
    name: str,
    resource_type: ResourceType = "work",
    max_units: Annotated[float, Field(description="Availability; 1.0 = 100% (one full-time person)", gt=0)] = 1.0,
    standard_rate_per_hour: Annotated[float, Field(ge=0)] = 0.0,
    initials: str | None = None,
    email: str | None = None,
    group: str | None = None,
) -> dict:
    """Add a resource to the project's resource sheet."""
    return backend().add_resource(name, resource_type, max_units, standard_rate_per_hour, initials, email, group)


@mcp.tool()
def delete_resource(uid: Annotated[int, Field(description="Resource UID")]) -> dict:
    """Delete a resource and all of its assignments."""
    return backend().delete_resource(uid)


@mcp.tool()
def assign_resource(
    task_uid: int,
    resource_uid: int,
    units: Annotated[float, Field(description="1.0 = 100% of the resource's time", gt=0)] = 1.0,
) -> dict:
    """Assign a resource to a task (or change the units of an existing assignment)."""
    return backend().assign_resource(task_uid, resource_uid, units)


@mcp.tool()
def unassign_resource(task_uid: int, resource_uid: int) -> dict:
    """Remove a resource assignment from a task."""
    return backend().unassign_resource(task_uid, resource_uid)


# -------------------------------------------------------------------- calendar


@mcp.tool()
def add_nonworking_day(
    day: Annotated[str, Field(description="YYYY-MM-DD")],
    name: str = "Holiday",
) -> dict:
    """Mark a date as non-working on the project calendar (holiday, shutdown...)."""
    return backend().add_nonworking_day(day, name)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()

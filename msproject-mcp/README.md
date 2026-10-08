# msproject-mcp

An [MCP](https://modelcontextprotocol.io) server for **Microsoft Project 2021**. Claude (or any MCP client) can use it to create, inspect and edit project schedules: tasks, outlines, dependencies, resources, assignments, calendars and the critical path.

## Two backends

| | `xml` (default) | `com` |
|---|---|---|
| Works on | Windows, macOS, Linux | Windows only |
| Needs Project installed | No | Yes (Project 2021, or any desktop Project 2010+) |
| File formats | Project XML (`.xml`, MSPDI) | `.mpp` and `.xml` |
| Who schedules | Built-in critical-path engine | Microsoft Project itself |

Choose one with the `MSPROJECT_BACKEND` environment variable.

**xml**: Project 2021 opens and saves this format natively. To save: *File → Save As → "XML Format (\*.xml)"*. To load: *File → Open*, pick the `.xml` file, then choose *"As a new project"*. The server edits the XML tree in place, so fields it doesn't manage (custom fields, baselines, extended attributes) are kept as they are.

**com**: attaches to a running Project 2021 instance, or starts one, and makes every change live in the open Gantt chart. You can watch the edits happen.

## Install

```bash
cd msproject-mcp
pip install .            # xml backend
pip install ".[com]"     # adds pywin32 for the com backend (Windows)
```

## Configure your MCP client

Claude Desktop (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "msproject": {
      "command": "msproject-mcp",
      "env": { "MSPROJECT_BACKEND": "com" }
    }
  }
}
```

Claude Code:

```bash
claude mcp add msproject -e MSPROJECT_BACKEND=xml -- msproject-mcp
```

To run without installing, use `python -m msproject_mcp` with `PYTHONPATH=src`.

## Tools

| Area | Tools |
|---|---|
| Project | `new_project`, `open_project`, `save_project`, `get_project_summary`, `recalculate_schedule` |
| Tasks | `list_tasks`, `get_task`, `add_task`, `update_task`, `delete_task`, `get_critical_path` |
| Dependencies | `link_tasks` (FS/SS/FF/SF, lag or lead), `unlink_tasks` |
| Resources | `list_resources`, `add_resource`, `delete_resource`, `assign_resource`, `unassign_resource` |
| Calendar | `add_nonworking_day` |

Conventions:
- Tasks and resources are identified by **UID**, which stays stable when rows move. Row IDs do not.
- Durations and lags are in **working days** (8 hours). A duration of `0` makes a milestone.
- Dates are `YYYY-MM-DD` or `YYYY-MM-DDTHH:MM`.
- Nothing is written to disk until `save_project` is called.

Example prompt: *"Open C:\plans\website.xml, add a 'QA' phase with 'Test plan' (2d) and 'Regression' (4d) after 'Build', assign Alice to Regression at 50%, mark Dec 25 as a holiday, show me the critical path, then save."*

## Scheduling in the xml backend

After each edit the built-in engine recalculates the schedule:
- It does forward and backward passes over all four link types, with lags and leads. Links on summary tasks apply to their subtasks.
- It calculates total slack and the critical flag, rolls dates up to summary tasks and the project summary, and keeps assignment work up to date (work = duration × units).
- It honours these constraints: ASAP, SNET, FNET and MSO. Tasks with an actual start, and manually scheduled tasks, keep their start dates.
- It uses the project calendar's working weekdays and non-working exceptions, with standard working hours: 08:00–12:00 and 13:00–17:00.

These are simplifications. Project 2021 recalculates everything on its own when it opens the file, using its full engine: resource calendars, leveling, ALAP, deadlines and so on. If a change leads to a dependency cycle, the edit is rejected and the document is left unchanged.

## Development

```bash
pip install -e ".[dev]"
pytest
```

Tests cover the scheduler, the MSPDI backend (round-trip, schema element order, preservation of unknown elements, rollback) and the server over a real MCP client session. The COM backend is tested against a fake Project object model, so it still needs checking on Windows against a real Project 2021 install.

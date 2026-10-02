"""Drive the server through a real MCP client session (in-memory transport)."""

import json

import anyio
import pytest
from mcp.shared.memory import create_connected_server_and_client_session

from msproject_mcp import server
from msproject_mcp.mspdi import XmlBackend


@pytest.fixture(autouse=True)
def fresh_backend():
    server.set_backend(XmlBackend())
    yield
    server.set_backend(None)


async def _session_calls(tmp_path):
    async with create_connected_server_and_client_session(server.mcp._mcp_server) as client:
        tools = {t.name for t in (await client.list_tools()).tools}

        async def call(tool, **args):
            result = await client.call_tool(tool, args)
            assert not result.isError, result.content
            return json.loads(result.content[0].text)

        await call("new_project", title="Demo", start_date="2026-10-05")
        a = (await call("add_task", name="A", duration_days=2))["uid"]
        b = (await call("add_task", name="B", duration_days=3, predecessors=[a]))["uid"]
        r = (await call("add_resource", name="Ann", standard_rate_per_hour=100))["uid"]
        await call("assign_resource", task_uid=b, resource_uid=r)
        summary = await call("get_project_summary")
        saved = await call("save_project", path=str(tmp_path / "demo.xml"))

        bad = await client.call_tool("get_task", {"uid": 42})
        return tools, summary, saved, bad


def test_tools_over_mcp(tmp_path):
    tools, summary, saved, bad = anyio.run(_session_calls, tmp_path)
    assert {"open_project", "add_task", "link_tasks", "get_critical_path", "save_project"} <= tools
    assert summary["finish"] == "2026-10-09T17:00"
    assert summary["estimated_labor_cost"] == 2400
    assert saved["saved"].endswith("demo.xml")
    assert bad.isError and "No task with UID 42" in bad.content[0].text

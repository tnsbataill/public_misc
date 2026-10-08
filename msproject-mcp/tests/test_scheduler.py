from datetime import date, datetime

import pytest

from msproject_mcp.scheduler import FF, FS, SF, SS, ScheduleError, STask, WorkCalendar, schedule

DAY = 480


def run(*tasks):
    finish = schedule(list(tasks))
    return finish, {t.uid: t for t in tasks}


def test_calendar_skips_weekends_and_holidays():
    cal = WorkCalendar(date(2026, 10, 2), holidays={date(2026, 10, 6)})  # Friday start
    assert cal.day(0) == date(2026, 10, 2)
    assert cal.day(1) == date(2026, 10, 5)  # Monday
    assert cal.day(2) == date(2026, 10, 7)  # Tuesday is a holiday
    assert cal.index_of(date(2026, 10, 3)) == 1  # Saturday -> next working day


def test_calendar_offset_round_trip():
    cal = WorkCalendar(date(2026, 10, 5))
    assert cal.start_dt(0) == datetime(2026, 10, 5, 8)
    assert cal.finish_dt(DAY) == datetime(2026, 10, 5, 17)
    assert cal.start_dt(DAY) == datetime(2026, 10, 6, 8)
    assert cal.finish_dt(240) == datetime(2026, 10, 5, 12)
    assert cal.start_dt(240) == datetime(2026, 10, 5, 13)
    for dt in (datetime(2026, 10, 6, 10, 30), datetime(2026, 10, 6, 15)):
        assert cal.start_dt(cal.to_offset(dt)) == dt


def test_finish_to_start_chain_and_slack():
    _, t = run(
        STask(1, 1, 2 * DAY),
        STask(2, 1, 3 * DAY, links=[(1, FS, 0)]),
        STask(3, 1, 1 * DAY, links=[(1, FS, 0)]),
    )
    assert (t[2].es, t[2].ef) == (2 * DAY, 5 * DAY)
    assert t[1].total_slack == 0 and t[2].total_slack == 0
    assert t[3].total_slack == 2 * DAY


@pytest.mark.parametrize(
    "typ,lag,expected_es",
    [(FS, 0, 4 * DAY), (FS, DAY, 5 * DAY), (FS, -DAY, 3 * DAY), (SS, DAY, DAY), (FF, 0, 2 * DAY), (SF, 3 * DAY, DAY)],
)
def test_link_types(typ, lag, expected_es):
    _, t = run(STask(1, 1, 4 * DAY), STask(2, 1, 2 * DAY, links=[(1, typ, lag)]))
    assert t[2].es == expected_es


def test_links_on_summary_tasks_apply_to_subtasks():
    _, t = run(
        STask(1, 1, 2 * DAY),
        STask(2, 1, links=[(1, FS, 0)]),  # summary
        STask(3, 2, 3 * DAY),
        STask(4, 2, 1 * DAY),
        STask(5, 1, 0, links=[(2, FS, 0)]),  # milestone after the summary
    )
    assert t[2].summary and t[3].parent == 2
    assert t[3].es == t[4].es == 2 * DAY
    assert (t[2].es, t[2].ef, t[2].duration) == (2 * DAY, 5 * DAY, 3 * DAY)
    assert t[5].es == 5 * DAY


def test_constraints():
    _, t = run(STask(1, 1, DAY, snet=3 * DAY), STask(2, 1, DAY, fixed_start=DAY, links=[(1, FS, 0)]))
    assert t[1].es == 3 * DAY
    assert t[2].es == DAY  # fixed start ignores predecessors


def test_cycle_is_reported():
    with pytest.raises(ScheduleError, match="cycle"):
        run(STask(1, 1, DAY, links=[(2, FS, 0)]), STask(2, 1, DAY, links=[(1, FS, 0)]))

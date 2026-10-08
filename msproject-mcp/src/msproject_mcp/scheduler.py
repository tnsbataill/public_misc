"""A small critical-path (CPM) scheduler working in working-time minutes.

Time is modelled as an offset in working minutes from the start of the first
working day of the project. Each working day has 480 minutes, laid out as
08:00-12:00 and 13:00-17:00 (Microsoft Project's default "Standard" calendar).
"""

from __future__ import annotations

import bisect
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta

MINUTES_PER_DAY = 480
_MORNING = 240  # 08:00-12:00

# MSPDI / VBA link type codes.
FF, FS, SF, SS = 0, 1, 2, 3


class ScheduleError(Exception):
    pass


class WorkCalendar:
    def __init__(
        self,
        start: date,
        working_weekdays: set[int] | None = None,
        holidays: set[date] | None = None,
    ) -> None:
        # Python weekday numbers: Monday=0 .. Sunday=6.
        self.working_weekdays = working_weekdays if working_weekdays is not None else {0, 1, 2, 3, 4}
        if not self.working_weekdays:
            raise ScheduleError("Calendar has no working weekdays")
        self.holidays = holidays or set()
        self._days: list[date] = []
        self._cursor = start

    def is_working(self, d: date) -> bool:
        return d.weekday() in self.working_weekdays and d not in self.holidays

    def _extend_to(self, n: int) -> None:
        while len(self._days) <= n:
            if self.is_working(self._cursor):
                self._days.append(self._cursor)
            self._cursor += timedelta(days=1)

    def day(self, n: int) -> date:
        self._extend_to(max(n, 0))
        return self._days[max(n, 0)]

    @property
    def first_day(self) -> date:
        return self.day(0)

    def index_of(self, d: date) -> int:
        """Index of the first working day on or after ``d``."""
        if d <= self.first_day:
            return 0
        while self._days[-1] < d:
            self._extend_to(len(self._days))
        return bisect.bisect_left(self._days, d)

    def to_offset(self, dt: datetime) -> int:
        d = dt.date()
        idx = self.index_of(d)
        if self.day(idx) != d:
            return idx * MINUTES_PER_DAY
        t = dt.hour * 60 + dt.minute
        if t <= 8 * 60:
            m = 0
        elif t <= 12 * 60:
            m = t - 8 * 60
        elif t <= 13 * 60:
            m = _MORNING
        elif t <= 17 * 60:
            m = _MORNING + t - 13 * 60
        else:
            m = MINUTES_PER_DAY
        return idx * MINUTES_PER_DAY + m

    @staticmethod
    def _clock(m: int, finish: bool) -> time:
        if m < _MORNING or (finish and m == _MORNING):
            total = 8 * 60 + m
        else:
            total = 13 * 60 + (m - _MORNING)
        return time(total // 60, total % 60)

    def start_dt(self, off: int) -> datetime:
        off = max(off, 0)
        d, m = divmod(off, MINUTES_PER_DAY)
        return datetime.combine(self.day(d), self._clock(m, finish=False))

    def finish_dt(self, off: int) -> datetime:
        off = max(off, 0)
        if off == 0:
            return datetime.combine(self.day(0), time(8, 0))
        d, m = divmod(off, MINUTES_PER_DAY)
        if m == 0:
            return datetime.combine(self.day(d - 1), time(17, 0))
        return datetime.combine(self.day(d), self._clock(m, finish=True))


@dataclass
class STask:
    uid: int
    level: int
    duration: int = 0  # working minutes (leaf tasks only)
    links: list[tuple[int, int, int]] = field(default_factory=list)  # (pred_uid, type, lag_minutes)
    fixed_start: int | None = None  # Must Start On / manually scheduled
    snet: int | None = None  # Start No Earlier Than
    fnet: int | None = None  # Finish No Earlier Than
    # Filled in by schedule():
    summary: bool = False
    parent: int | None = None
    children: list[int] = field(default_factory=list)
    es: int = 0
    ef: int = 0
    ls: int = 0
    lf: int = 0

    @property
    def total_slack(self) -> int:
        return self.ls - self.es


def schedule(tasks: list[STask]) -> int:
    """Schedule ``tasks`` (in outline order) in place; return the project finish offset."""
    by_uid = {t.uid: t for t in tasks}

    # Outline structure.
    stack: list[STask] = []
    for t in tasks:
        t.summary, t.children, t.parent = False, [], None
        while stack and stack[-1].level >= t.level:
            stack.pop()
        if stack:
            t.parent = stack[-1].uid
            stack[-1].summary = True
            stack[-1].children.append(t.uid)
        stack.append(t)

    leaf_cache: dict[int, list[int]] = {}

    def leaves(uid: int) -> list[int]:
        if uid not in leaf_cache:
            t = by_uid[uid]
            leaf_cache[uid] = [uid] if not t.summary else [x for c in t.children for x in leaves(c)]
        return leaf_cache[uid]

    def lineage(uid: int) -> list[int]:
        out = []
        cur: int | None = uid
        while cur is not None:
            out.append(cur)
            cur = by_uid[cur].parent
        return out

    leaf_tasks = [t for t in tasks if not t.summary]

    # Links that constrain each leaf: its own plus those on its summary ancestors.
    incoming: dict[int, list[tuple[int, int, int]]] = defaultdict(list)  # leaf -> (pred_node, type, lag)
    outgoing: dict[int, list[tuple[int, int, int]]] = defaultdict(list)  # pred leaf -> (succ leaf, type, lag)
    succs: dict[int, set[int]] = defaultdict(set)
    indeg = {t.uid: 0 for t in leaf_tasks}
    for leaf in leaf_tasks:
        line = lineage(leaf.uid)
        for owner in line:
            for pred, typ, lag in by_uid[owner].links:
                if pred not in by_uid or pred in line:
                    continue
                pred_leaves = [p for p in leaves(pred) if owner not in lineage(p)]
                if not pred_leaves:
                    continue
                incoming[leaf.uid].append((pred, typ, lag))
                for p in pred_leaves:
                    outgoing[p].append((leaf.uid, typ, lag))
                    if leaf.uid not in succs[p]:
                        succs[p].add(leaf.uid)
                        indeg[leaf.uid] += 1

    # Topological order (Kahn), preserving outline order among ready tasks.
    position = {t.uid: i for i, t in enumerate(tasks)}
    ready = deque(sorted((u for u, d in indeg.items() if d == 0), key=position.__getitem__))
    order: list[int] = []
    while ready:
        u = ready.popleft()
        order.append(u)
        for s in sorted(succs[u], key=position.__getitem__):
            indeg[s] -= 1
            if indeg[s] == 0:
                ready.append(s)
    if len(order) != len(leaf_tasks):
        stuck = sorted(u for u, d in indeg.items() if d > 0)
        raise ScheduleError(f"Dependency cycle detected among task UIDs {stuck}")

    def node_es(uid: int) -> int:
        return min(by_uid[x].es for x in leaves(uid))

    def node_ef(uid: int) -> int:
        return max(by_uid[x].ef for x in leaves(uid))

    # Forward pass.
    for uid in order:
        t = by_uid[uid]
        d = t.duration
        if t.fixed_start is not None:
            es = t.fixed_start
        else:
            es = 0
            for pred, typ, lag in incoming[uid]:
                if typ == FS:
                    es = max(es, node_ef(pred) + lag)
                elif typ == SS:
                    es = max(es, node_es(pred) + lag)
                elif typ == FF:
                    es = max(es, node_ef(pred) + lag - d)
                elif typ == SF:
                    es = max(es, node_es(pred) + lag - d)
            if t.snet is not None:
                es = max(es, t.snet)
            if t.fnet is not None:
                es = max(es, t.fnet - d)
            es = max(es, 0)
        t.es, t.ef = es, es + d

    finish = max((t.ef for t in leaf_tasks), default=0)

    # Backward pass.
    for uid in reversed(order):
        t = by_uid[uid]
        d = t.duration
        lf = finish
        for s_uid, typ, lag in outgoing[uid]:
            s = by_uid[s_uid]
            if typ == FS:
                lf = min(lf, s.ls - lag)
            elif typ == SS:
                lf = min(lf, s.ls - lag + d)
            elif typ == FF:
                lf = min(lf, s.lf - lag)
            elif typ == SF:
                lf = min(lf, s.lf - lag + d)
        t.lf, t.ls = lf, lf - d

    # Roll up summaries (children come after parents in outline order).
    for t in reversed(tasks):
        if t.summary:
            kids = [by_uid[c] for c in t.children]
            t.es = min(k.es for k in kids)
            t.ef = max(k.ef for k in kids)
            t.ls = min(k.ls for k in kids)
            t.lf = max(k.lf for k in kids)
            t.duration = t.ef - t.es

    return finish

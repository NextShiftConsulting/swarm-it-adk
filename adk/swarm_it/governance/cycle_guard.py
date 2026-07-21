"""CycleGuard — enforces morph-repair XOR handoff mutual exclusion (Claim 9).

A thread of execution must never be inside a "repair" cycle and a
"handoff" cycle at the same time: repair mutates state in place to
converge back toward validity, handoff hands the (unmutated) state to
another agent under its own authority. Mixing the two lets a repair
silently smuggle a mutation across a handoff boundary, or a handoff
observe state mid-repair. Re-entering the SAME mode (nesting a repair
inside a repair, or a handoff inside a handoff) is fine and expected.
"""

import contextlib
import contextvars
from typing import Literal, Optional

Mode = Literal["repair", "handoff"]

# contextvars.ContextVar, not threading.local: this guard must stay correctly
# scoped across `await` points. A thread.local would leak/lose state across
# suspensions of a coroutine on the same OS thread (asyncio can interleave
# multiple logical tasks on one thread), which would let a repair and a
# handoff coroutine appear to share (or clobber) the same guard state.
# Token-based reset() restores the exact prior value on exit, so nesting
# (same mode inside itself) "just works" without a separate depth counter.
_mode: contextvars.ContextVar[Optional[Mode]] = contextvars.ContextVar("cycle_guard_mode", default=None)


class CycleGuard:
    """Guards mutual exclusion between morph-repair and handoff cycles."""

    @staticmethod
    @contextlib.contextmanager
    def enter(mode: Mode):
        current = _mode.get()
        if current is not None and current != mode:
            raise RuntimeError(
                f"CycleGuard violation: cannot enter '{mode}' while inside '{current}' "
                "(morph-repair and handoff are mutually exclusive)"
            )

        token = _mode.set(mode)
        try:
            yield
        finally:
            _mode.reset(token)

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
import threading
from typing import Literal

Mode = Literal["repair", "handoff"]

_state = threading.local()


class CycleGuard:
    """Guards mutual exclusion between morph-repair and handoff cycles."""

    @staticmethod
    @contextlib.contextmanager
    def enter(mode: Mode):
        current = getattr(_state, "mode", None)
        if current is not None and current != mode:
            raise RuntimeError(
                f"CycleGuard violation: cannot enter '{mode}' while inside '{current}' "
                "(morph-repair and handoff are mutually exclusive)"
            )

        depth = getattr(_state, "depth", 0)
        _state.mode = mode
        _state.depth = depth + 1
        try:
            yield
        finally:
            _state.depth -= 1
            if _state.depth == 0:
                _state.mode = None

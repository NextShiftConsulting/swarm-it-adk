"""
Session Bootstrap - Context loading enforcement for agent sessions.

Ensures agents always load context (tasks, skills, recent files) before
acting or asking questions.

Part of swarm-it-adk harness for context-aware agent execution.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Optional, Any
from datetime import datetime


@dataclass
class SessionContext:
    """Loaded session context."""
    open_tasks: List[Dict[str, Any]]
    available_skills: List[str]
    recent_files: List[str]
    last_progress: Optional[str]
    workspace_root: Path
    timestamp: str


class SessionBootstrap:
    """
    Enforces context-loading pattern for agent sessions.

    This is the harness component that guarantees agents read artifacts
    before asking questions or taking actions.

    Usage:
        bootstrap = SessionBootstrap(workspace_root="~/github/yrsn")
        context = bootstrap.load_context()

        # Now agent has context loaded - can proceed
        summary = bootstrap.generate_summary(context)

    Enforcement:
        Use @enforce_bootstrap decorator on methods that require context.
        Methods will fail if bootstrap hasn't been called.
    """

    def __init__(self, workspace_root: str):
        """
        Initialize bootstrap for a workspace.

        Args:
            workspace_root: Path to workspace (repo root)
        """
        self.workspace = Path(workspace_root).expanduser().resolve()
        self.context_loaded = False
        self.context: Optional[SessionContext] = None

    def load_context(self) -> SessionContext:
        """
        Load all context artifacts (required first step).

        This method:
        1. Reads TASKS.md (or calls TaskList)
        2. Scans skills directory
        3. Finds recent .md files
        4. Reads PROGRESS_LOG.md

        Returns:
            SessionContext with all loaded artifacts
        """
        tasks = self._read_tasks()
        skills = self._read_skills()
        recent = self._read_recent_files(limit=5)
        progress = self._read_progress_log()

        self.context = SessionContext(
            open_tasks=tasks,
            available_skills=skills,
            recent_files=recent,
            last_progress=progress,
            workspace_root=self.workspace,
            timestamp=datetime.now().isoformat()
        )

        self.context_loaded = True
        return self.context

    def generate_summary(self, context: Optional[SessionContext] = None) -> str:
        """
        Generate human-readable context summary for agent.

        This is what the agent should output instead of asking
        "what were we working on?"

        Args:
            context: SessionContext to summarize (uses self.context if None)

        Returns:
            Formatted summary string
        """
        ctx = context or self.context
        if not ctx:
            raise RuntimeError("No context loaded - call load_context() first")

        summary = ["**Session Bootstrap Complete**", ""]

        # Open tasks
        summary.append("**Open Tasks:**")
        if ctx.open_tasks:
            for task in ctx.open_tasks:
                status = "PENDING" if not task.get("completed") else "COMPLETED"
                summary.append(f"- #{task['id']}: {task['title']} [{status}]")
        else:
            summary.append("- No open tasks")
        summary.append("")

        # Available skills
        summary.append("**Available Skills:**")
        if ctx.available_skills:
            summary.append(", ".join(ctx.available_skills))
        else:
            summary.append("- No skills found")
        summary.append("")

        # Recent files
        summary.append("**Recent Files:**")
        if ctx.recent_files:
            for f in ctx.recent_files:
                summary.append(f"- {f}")
        else:
            summary.append("- No recent files")
        summary.append("")

        # Last progress
        if ctx.last_progress:
            summary.append("**Last Session:**")
            summary.append(ctx.last_progress)
            summary.append("")

        # Recommended action
        if ctx.open_tasks:
            next_task = ctx.open_tasks[0]
            summary.append("**Recommended Next Action:**")
            summary.append(f"Task #{next_task['id']}: {next_task['title']}")
            summary.append("")

        summary.append(f"**Context loaded at:** {ctx.timestamp}")

        return "\n".join(summary)

    def append_progress(self, entry: str):
        """
        Append entry to PROGRESS_LOG.md.

        All skills should call this when completing work.

        Args:
            entry: Progress entry (markdown format)
        """
        progress_log = self.workspace / "PROGRESS_LOG.md"

        with open(progress_log, "a") as f:
            f.write(f"\n## {datetime.now().strftime('%Y-%m-%d %H:%M')} - {entry}\n")

    def _read_tasks(self) -> List[Dict[str, Any]]:
        """
        Read TASKS.md or equivalent.

        Parses checkbox format:
        - [ ] #1: Task title
        - [x] #2: Completed task

        Returns:
            List of task dictionaries
        """
        tasks_file = self.workspace / "TASKS.md"
        if not tasks_file.exists():
            return []

        tasks = []
        with open(tasks_file) as f:
            for line in f:
                line = line.strip()
                if line.startswith("- ["):
                    completed = "x" in line[:5]
                    # Extract ID and title
                    rest = line[5:].strip()
                    if rest.startswith("#"):
                        # Format: #1: Title
                        parts = rest.split(":", 1)
                        if len(parts) == 2:
                            task_id = parts[0].strip("#").strip()
                            title = parts[1].strip()
                            tasks.append({
                                "id": task_id,
                                "title": title,
                                "completed": completed
                            })

        return tasks

    def _read_skills(self) -> List[str]:
        """
        Read skills directory.

        Looks in:
        - ~/.claude/skills/
        - workspace/skills/

        Returns:
            List of skill names
        """
        skills = []

        # Check user skills
        user_skills = Path.home() / ".claude" / "skills"
        if user_skills.exists():
            for skill_dir in user_skills.iterdir():
                if skill_dir.is_dir() and not skill_dir.name.startswith("."):
                    skills.append(skill_dir.name)

        # Check workspace skills
        workspace_skills = self.workspace / "skills"
        if workspace_skills.exists():
            for skill_dir in workspace_skills.iterdir():
                if skill_dir.is_dir() and not skill_dir.name.startswith("."):
                    if skill_dir.name not in skills:
                        skills.append(skill_dir.name)

        return sorted(skills)

    def _read_recent_files(self, limit: int) -> List[str]:
        """
        Get recently modified .md files.

        Args:
            limit: Max number of files to return

        Returns:
            List of file paths (relative to workspace)
        """
        md_files = []

        for md_file in self.workspace.rglob("*.md"):
            # Skip hidden and vendor directories
            if any(part.startswith(".") for part in md_file.parts):
                continue
            if "node_modules" in md_file.parts or "venv" in md_file.parts:
                continue

            md_files.append((md_file, md_file.stat().st_mtime))

        # Sort by modification time, most recent first
        md_files.sort(key=lambda x: x[1], reverse=True)

        # Return relative paths
        return [str(f.relative_to(self.workspace)) for f, _ in md_files[:limit]]

    def _read_progress_log(self) -> Optional[str]:
        """
        Read PROGRESS_LOG.md.

        Returns last entry (last session's work).

        Returns:
            Last progress entry or None
        """
        progress_log = self.workspace / "PROGRESS_LOG.md"
        if not progress_log.exists():
            return None

        with open(progress_log) as f:
            content = f.read()

        # Get last section (starts with ##)
        sections = content.split("\n## ")
        if len(sections) > 1:
            return sections[-1].strip()

        return None


def enforce_bootstrap(func):
    """
    Decorator to enforce bootstrap before method execution.

    Usage:
        class Agent:
            def __init__(self):
                self.context_loaded = False

            @enforce_bootstrap
            def execute_task(self, ...):
                # This will fail if bootstrap() wasn't called
                pass

    The decorated method's class must have a `context_loaded` attribute.
    """
    def wrapper(self, *args, **kwargs):
        if not getattr(self, 'context_loaded', False):
            raise RuntimeError(
                "Bootstrap required: Must call load_context() before "
                "executing tasks. Agent has not loaded workspace context.\n\n"
                "Use SessionBootstrap to load context first:\n"
                "  bootstrap = SessionBootstrap(workspace_root)\n"
                "  context = bootstrap.load_context()\n"
                "  self.context_loaded = True"
            )
        return func(self, *args, **kwargs)
    return wrapper


class BootstrapError(Exception):
    """Raised when bootstrap requirements are violated."""
    pass

"""
Example: Session Bootstrap

Shows how to use SessionBootstrap to enforce context loading
before agent actions.

This guarantees agents never ask "what were we working on?" -
they read artifacts first.
"""

from swarm_it.session import SessionBootstrap, enforce_bootstrap


def example_basic_bootstrap():
    """Basic bootstrap example."""
    print("=== Basic Session Bootstrap ===\n")

    # Initialize bootstrap for workspace
    bootstrap = SessionBootstrap(workspace_root="~/github/yrsn")

    # Load context (required first step)
    context = bootstrap.load_context()

    # Generate summary
    summary = bootstrap.generate_summary(context)
    print(summary)

    # Append progress for next session
    bootstrap.append_progress("Session Bootstrap Example - Completed basic demo")


def example_enforced_bootstrap():
    """Example with @enforce_bootstrap decorator."""
    print("\n=== Enforced Bootstrap ===\n")

    class Agent:
        def __init__(self, workspace_root: str):
            self.workspace = workspace_root
            self.context_loaded = False

        def load_context(self):
            """Load workspace context."""
            bootstrap = SessionBootstrap(self.workspace)
            context = bootstrap.load_context()
            self.context_loaded = True
            return context

        @enforce_bootstrap
        def execute_task(self, task_id: str):
            """
            Execute a task (requires bootstrap).

            This method will fail if load_context() wasn't called first.
            """
            print(f"Executing task #{task_id}")
            print("✓ Context was loaded, proceeding with execution")

    # Create agent
    agent = Agent("~/github/yrsn")

    # Try to execute without loading context - will fail
    try:
        agent.execute_task("8")
        print("❌ Should have failed!")
    except RuntimeError as e:
        print(f"✓ Correctly blocked: {e}\n")

    # Load context, then execute - will succeed
    agent.load_context()
    agent.execute_task("8")


def example_skill_with_bootstrap():
    """Example: Skill using SessionBootstrap."""
    print("\n=== Skill with Bootstrap ===\n")

    class ExperimentSkill:
        """Example skill that requires context loading."""

        def __init__(self, workspace_root: str):
            self.workspace = workspace_root
            self.context_loaded = False
            self.bootstrap = SessionBootstrap(workspace_root)

        def run(self, exp_id: str):
            """
            Run experiment.

            Automatically loads context if not already loaded.
            """
            if not self.context_loaded:
                print("Loading context before running experiment...")
                context = self.bootstrap.load_context()
                summary = self.bootstrap.generate_summary(context)
                print(summary)
                self.context_loaded = True

            # Now execute experiment
            self._execute_experiment(exp_id)

        @enforce_bootstrap
        def _execute_experiment(self, exp_id: str):
            """Execute experiment (requires context)."""
            print(f"\n✓ Running experiment {exp_id}")
            print("✓ Context was loaded, experiment proceeding")

            # Append progress
            self.bootstrap.append_progress(
                f"Experiment {exp_id} - Completed successfully"
            )

    # Run skill
    skill = ExperimentSkill("~/github/yrsn")
    skill.run("DIM-03")


if __name__ == "__main__":
    # Run examples
    example_basic_bootstrap()
    example_enforced_bootstrap()
    example_skill_with_bootstrap()

    print("\n=== Summary ===")
    print("✓ Session bootstrap ensures agents load context before acting")
    print("✓ Use @enforce_bootstrap to guard methods that require context")
    print("✓ Skills should use SessionBootstrap to prevent 'what were we doing?' questions")

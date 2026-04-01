"""Agent base class module.

Provides the abstract interface that all Agents must implement.
Other responsibilities have been moved to specialized modules:

- Context building and memory: core/context.py, core/memory.py
- Session management: core/session.py
- LLM invocation: core/llm.py

Attributes:
    NAME: Agent identifier (must be set by subclass).
    SYSTEM_PROMPT: System prompt that defines agent behavior (loaded from Skill).
"""

from abc import ABC, abstractmethod


class BaseAgent(ABC):
    """Abstract base class for all Agents.

    All concrete Agent classes must inherit from this class
    and implement the process() method.

    Attributes:
        NAME: Agent identifier, corresponds to Skill directory name.
        SYSTEM_PROMPT: System prompt loaded from Skill's SKILL.md.

    Example:
        class MyAgent(BaseAgent):
            NAME = "my_agent"

            def process(self, task: str) -> str:
                return f"Processed: {task}"
    """

    NAME: str = ""
    SYSTEM_PROMPT: str = ""

    @abstractmethod
    def process(self, task: str) -> str:
        """Process a task and return the result.

        Each concrete Agent must implement this method.

        Args:
            task: The task description or user input.

        Returns:
            Processing result as a string.
        """
        pass

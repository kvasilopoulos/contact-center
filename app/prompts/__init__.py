"""Prompt management system for LLM interactions.

This module provides a file-based prompt management system with:
- Version control for prompts (stored as YAML files)
- A/B testing support
- Template rendering with Jinja2
- Runtime prompt registry
"""

from app.prompts.loader import load_prompts
from app.prompts.registry import get_registry
from app.prompts.template import PromptTemplate

# Global registry instance
registry = get_registry()

__all__ = ["PromptTemplate", "load_prompts", "registry"]

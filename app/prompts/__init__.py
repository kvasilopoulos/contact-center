"""Prompt management: YAML-based templates with versioning."""

from app.prompts.loader import load_prompts
from app.prompts.registry import get_registry
from app.prompts.template import PromptTemplate

registry = get_registry()

__all__ = ["PromptTemplate", "load_prompts", "registry"]

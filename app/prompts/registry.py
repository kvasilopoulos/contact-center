"""Prompt registry for managing and retrieving prompt templates."""

from dataclasses import dataclass, field
import random
from typing import Any

import structlog

from app.prompts.template import PromptTemplate

logger = structlog.get_logger(__name__)


@dataclass
class ExperimentVariant:
    """A variant in an A/B test experiment."""

    name: str
    version: str
    traffic: float  # Percentage of traffic (0.0 to 1.0)


@dataclass
class ExperimentConfig:
    """Configuration for an A/B test experiment."""

    id: str
    name: str
    active: bool
    variants: list[ExperimentVariant]
    metrics: list[str] = field(default_factory=list)
    start_date: str = ""
    end_date: str = ""

    def select_variant(self) -> ExperimentVariant:
        """Select a variant based on traffic split.

        Returns:
            Selected variant based on weighted random selection
        """
        if not self.variants:
            raise ValueError(f"Experiment {self.id} has no variants")

        # Normalize traffic percentages
        total_traffic = sum(v.traffic for v in self.variants)
        if total_traffic == 0:
            raise ValueError(f"Experiment {self.id} has total traffic of 0")

        # Weighted random selection
        rand = random.random() * total_traffic
        cumulative = 0.0
        for variant in self.variants:
            cumulative += variant.traffic
            if rand <= cumulative:
                return variant

        # Fallback to last variant
        return self.variants[-1]


class PromptRegistry:
    """Registry for managing prompt templates with versioning and A/B testing.

    The registry maintains:
    - All loaded prompt templates by ID and version
    - Active version for each prompt ID
    - A/B test experiment configurations
    """

    def __init__(self) -> None:
        """Initialize an empty prompt registry."""
        # Store templates by "id:version" key
        self._templates: dict[str, PromptTemplate] = {}
        # Store active version for each prompt ID
        self._active_versions: dict[str, str] = {}
        # Store experiments by experiment ID
        self._experiments: dict[str, ExperimentConfig] = {}

    def register(self, template: PromptTemplate) -> None:
        """Register a prompt template.

        Args:
            template: The prompt template to register

        Raises:
            ValueError: If a template with the same ID and version already exists
        """
        key = template.get_full_key()
        if key in self._templates:
            logger.warning(
                "Overwriting existing prompt template",
                prompt_id=template.id,
                version=template.version,
            )

        self._templates[key] = template
        logger.debug(
            "Registered prompt template",
            prompt_id=template.id,
            version=template.version,
            key=key,
        )

        # Set as active if it's the first version for this ID
        if template.id not in self._active_versions:
            self._active_versions[template.id] = template.version
            logger.info(
                "Set as active prompt version (first registered)",
                prompt_id=template.id,
                version=template.version,
            )

    def get(self, prompt_id: str, version: str | None = None) -> PromptTemplate:
        """Get a prompt template by ID and optional version.

        Args:
            prompt_id: The prompt ID
            version: Optional specific version. If None, returns active version.

        Returns:
            The requested prompt template

        Raises:
            KeyError: If the prompt ID or version is not found
        """
        if version is None:
            version = self.get_active_version(prompt_id)

        key = f"{prompt_id}:{version}"
        if key not in self._templates:
            available = self.list_versions(prompt_id)
            raise KeyError(
                f"Prompt template '{prompt_id}' version '{version}' not found. "
                f"Available versions: {available}"
            )

        return self._templates[key]

    def get_active(self, prompt_id: str) -> PromptTemplate:
        """Get the active version of a prompt.

        Args:
            prompt_id: The prompt ID

        Returns:
            The active prompt template

        Raises:
            KeyError: If the prompt ID is not found
        """
        return self.get(prompt_id, version=None)

    def get_active_version(self, prompt_id: str) -> str:
        """Get the active version string for a prompt ID.

        Args:
            prompt_id: The prompt ID

        Returns:
            The active version string

        Raises:
            KeyError: If the prompt ID is not found
        """
        if prompt_id not in self._active_versions:
            raise KeyError(f"Prompt ID '{prompt_id}' not found in registry")
        return self._active_versions[prompt_id]

    def set_active(self, prompt_id: str, version: str) -> None:
        """Set the active version for a prompt ID.

        Args:
            prompt_id: The prompt ID
            version: The version to set as active

        Raises:
            KeyError: If the prompt ID or version is not found
        """
        key = f"{prompt_id}:{version}"
        if key not in self._templates:
            available = self.list_versions(prompt_id)
            raise KeyError(
                f"Cannot set active version: '{prompt_id}' version '{version}' not found. "
                f"Available versions: {available}"
            )

        self._active_versions[prompt_id] = version
        logger.info(
            "Set active prompt version",
            prompt_id=prompt_id,
            version=version,
        )

    def list_versions(self, prompt_id: str) -> list[str]:
        """List all available versions for a prompt ID.

        Args:
            prompt_id: The prompt ID

        Returns:
            List of version strings
        """
        versions = []
        for key in self._templates:
            pid, version = key.split(":", 1)
            if pid == prompt_id:
                versions.append(version)
        return sorted(versions)

    def list_prompts(self) -> list[str]:
        """List all registered prompt IDs.

        Returns:
            List of prompt IDs
        """
        return sorted(set(self._active_versions.keys()))

    def add_experiment(self, experiment: ExperimentConfig) -> None:
        """Add an A/B test experiment configuration.

        Args:
            experiment: The experiment configuration
        """
        self._experiments[experiment.id] = experiment
        logger.info(
            "Added experiment",
            experiment_id=experiment.id,
            name=experiment.name,
            active=experiment.active,
            variants=[v.name for v in experiment.variants],
        )

    def get_experiment(self, experiment_id: str) -> ExperimentConfig | None:
        """Get an experiment configuration by ID.

        Args:
            experiment_id: The experiment ID

        Returns:
            The experiment configuration or None if not found
        """
        return self._experiments.get(experiment_id)

    def get_for_experiment(
        self, prompt_id: str, experiment_id: str | None = None
    ) -> tuple[PromptTemplate, dict[str, Any]]:
        """Get a prompt template, optionally using A/B testing.

        Args:
            prompt_id: The prompt ID
            experiment_id: Optional experiment ID for A/B testing

        Returns:
            Tuple of (prompt_template, metadata) where metadata contains
            version and variant information

        Raises:
            KeyError: If the prompt ID is not found
            ValueError: If the experiment is invalid or inactive
        """
        metadata: dict[str, Any] = {"prompt_id": prompt_id}

        if experiment_id:
            experiment = self.get_experiment(experiment_id)
            if not experiment:
                logger.warning(
                    "Experiment not found, using active version",
                    experiment_id=experiment_id,
                    prompt_id=prompt_id,
                )
                template = self.get_active(prompt_id)
                metadata["version"] = template.version
                metadata["variant"] = "active"
                return template, metadata

            if not experiment.active:
                logger.info(
                    "Experiment is inactive, using active version",
                    experiment_id=experiment_id,
                    prompt_id=prompt_id,
                )
                template = self.get_active(prompt_id)
                metadata["version"] = template.version
                metadata["variant"] = "active"
                return template, metadata

            # Select variant based on traffic split
            variant = experiment.select_variant()
            template = self.get(prompt_id, version=variant.version)
            metadata["version"] = variant.version
            metadata["variant"] = variant.name
            metadata["experiment_id"] = experiment_id

            logger.debug(
                "Selected experiment variant",
                experiment_id=experiment_id,
                variant=variant.name,
                version=variant.version,
            )
            return template, metadata

        # No experiment, use active version
        template = self.get_active(prompt_id)
        metadata["version"] = template.version
        metadata["variant"] = "active"
        return template, metadata

    def get_stats(self) -> dict[str, Any]:
        """Get statistics about the registry.

        Returns:
            Dictionary with registry statistics
        """
        return {
            "total_templates": len(self._templates),
            "prompt_ids": len(self._active_versions),
            "experiments": len(self._experiments),
            "active_experiments": sum(1 for e in self._experiments.values() if e.active),
        }


# Global registry instance
_registry: PromptRegistry | None = None


def get_registry() -> PromptRegistry:
    """Get the global prompt registry instance.

    Returns:
        The global PromptRegistry instance
    """
    global _registry  # noqa: PLW0603
    if _registry is None:
        _registry = PromptRegistry()
    return _registry

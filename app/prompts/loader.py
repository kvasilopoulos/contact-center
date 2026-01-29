"""YAML prompt loader for loading prompts from files."""

from pathlib import Path
from typing import Any

import structlog
import yaml

from app.prompts.registry import ExperimentConfig, ExperimentVariant, get_registry
from app.prompts.template import LLMConfig, PromptMetadata, PromptParameter, PromptTemplate

logger = structlog.get_logger(__name__)


def get_prompts_directory() -> Path:
    """Get the prompts directory at project root.

    Returns:
        Path to the prompts directory

    Raises:
        FileNotFoundError: If the prompts directory doesn't exist
    """
    # Get project root (parent of app/)
    project_root = Path(__file__).parent.parent.parent
    prompts_dir = project_root / "prompts"

    if not prompts_dir.exists():
        raise FileNotFoundError(
            f"Prompts directory not found at {prompts_dir}. Please create it at the project root."
        )

    return prompts_dir


def parse_prompt_template(data: dict[str, Any], file_path: Path) -> PromptTemplate:
    """Parse a prompt template from YAML data.

    Args:
        data: Dictionary loaded from YAML file
        file_path: Path to the YAML file (for error messages)

    Returns:
        Parsed PromptTemplate instance

    Raises:
        ValueError: If required fields are missing or invalid
    """
    try:
        # Required fields
        prompt_id = data.get("id")
        version = data.get("version")
        system_prompt = data.get("system_prompt")
        user_prompt_template = data.get("user_prompt_template")

        if not all([prompt_id, version, system_prompt, user_prompt_template]):
            missing = []
            if not prompt_id:
                missing.append("id")
            if not version:
                missing.append("version")
            if not system_prompt:
                missing.append("system_prompt")
            if not user_prompt_template:
                missing.append("user_prompt_template")
            raise ValueError(f"Missing required fields: {missing}")

        # Parse parameters
        parameters = []
        for param_data in data.get("parameters", []):
            parameters.append(
                PromptParameter(
                    name=param_data.get("name", ""),
                    type=param_data.get("type", "string"),
                    description=param_data.get("description", ""),
                )
            )

        # Parse LLM config
        llm_config_data = data.get("llm_config", {})
        llm_config = LLMConfig(
            temperature=float(llm_config_data.get("temperature", 0.0)),
            max_tokens=int(llm_config_data.get("max_tokens", 500)),
            response_format=llm_config_data.get("response_format", "json_object"),
            model=llm_config_data.get("model", ""),
        )

        # Parse metadata
        metadata_data = data.get("metadata", {})
        metadata = PromptMetadata(
            author=metadata_data.get("author", ""),
            created=metadata_data.get("created", ""),
            description=metadata_data.get("description", ""),
            tags=metadata_data.get("tags", []),
            changes=metadata_data.get("changes", ""),
        )

        return PromptTemplate(
            id=str(prompt_id),
            version=str(version),
            system_prompt=str(system_prompt),
            user_prompt_template=str(user_prompt_template),
            parameters=parameters,
            llm_config=llm_config,
            metadata=metadata,
        )

    except Exception as e:
        raise ValueError(f"Failed to parse prompt template from {file_path}: {e}") from e


def parse_experiments(data: dict[str, Any], file_path: Path) -> list[ExperimentConfig]:
    """Parse experiment configurations from YAML data.

    Args:
        data: Dictionary loaded from YAML file
        file_path: Path to the YAML file (for error messages)

    Returns:
        List of parsed ExperimentConfig instances
    """
    experiments = []

    for exp_data in data.get("experiments", []):
        try:
            variants = []
            for var_data in exp_data.get("variants", []):
                variants.append(
                    ExperimentVariant(
                        name=var_data.get("name", ""),
                        version=str(var_data.get("version", "")),
                        traffic=float(var_data.get("traffic", 0.0)),
                        model=var_data.get("model", ""),
                    )
                )

            experiment = ExperimentConfig(
                id=exp_data.get("id", ""),
                name=exp_data.get("name", ""),
                active=bool(exp_data.get("active", False)),
                variants=variants,
                metrics=exp_data.get("metrics", []),
                start_date=exp_data.get("start_date", ""),
                end_date=exp_data.get("end_date", ""),
            )
            experiments.append(experiment)

        except Exception as e:
            logger.error(
                "Failed to parse experiment",
                file_path=str(file_path),
                experiment_id=exp_data.get("id", "unknown"),
                error=str(e),
            )
            continue

    return experiments


def load_prompt_file(file_path: Path) -> PromptTemplate | None:
    """Load a single prompt template from a YAML file.

    Args:
        file_path: Path to the YAML file

    Returns:
        Loaded PromptTemplate or None if loading fails
    """
    try:
        with file_path.open(encoding="utf-8") as f:
            data = yaml.safe_load(f)

        if not data:
            logger.warning("Empty YAML file", file_path=str(file_path))
            return None

        template = parse_prompt_template(data, file_path)
        logger.debug(
            "Loaded prompt template",
            file_path=str(file_path),
            prompt_id=template.id,
            version=template.version,
        )
        return template

    except Exception as e:
        logger.error(
            "Failed to load prompt file",
            file_path=str(file_path),
            error=str(e),
        )
        return None


def load_experiments_file(file_path: Path) -> list[ExperimentConfig]:
    """Load experiment configurations from a YAML file.

    Args:
        file_path: Path to the experiments YAML file

    Returns:
        List of loaded ExperimentConfig instances
    """
    try:
        with file_path.open(encoding="utf-8") as f:
            data = yaml.safe_load(f)

        if not data:
            logger.warning("Empty experiments file", file_path=str(file_path))
            return []

        experiments = parse_experiments(data, file_path)
        logger.info(
            "Loaded experiments",
            file_path=str(file_path),
            count=len(experiments),
        )
        return experiments

    except Exception as e:
        logger.error(
            "Failed to load experiments file",
            file_path=str(file_path),
            error=str(e),
        )
        return []


def load_prompts(prompts_dir: Path | None = None) -> None:
    """Load all prompt templates and experiments from the prompts directory.

    This function:
    1. Scans the prompts directory for YAML files
    2. Loads prompt templates (excluding experiments.yaml files)
    3. Loads experiment configurations from experiments.yaml files
    4. Registers everything in the global registry

    Args:
        prompts_dir: Optional path to prompts directory. If None, uses default
                     location at project root.

    Raises:
        FileNotFoundError: If the prompts directory doesn't exist
    """
    prompts_dir = get_prompts_directory() if prompts_dir is None else Path(prompts_dir)

    if not prompts_dir.exists():
        raise FileNotFoundError(f"Prompts directory not found: {prompts_dir}")

    registry = get_registry()
    templates_loaded = 0
    experiments_loaded = 0

    logger.info("Loading prompts from directory", prompts_dir=str(prompts_dir))

    # Walk through all subdirectories
    for yaml_file in prompts_dir.rglob("*.yaml"):
        # Skip experiments files for now
        if yaml_file.name == "experiments.yaml":
            continue

        # Load and register prompt template
        template = load_prompt_file(yaml_file)
        if template:
            registry.register(template)
            templates_loaded += 1

    # Load all experiments files
    for experiments_file in prompts_dir.rglob("experiments.yaml"):
        experiments = load_experiments_file(experiments_file)
        for experiment in experiments:
            registry.add_experiment(experiment)
            experiments_loaded += 1

    logger.info(
        "Finished loading prompts",
        templates_loaded=templates_loaded,
        experiments_loaded=experiments_loaded,
        registry_stats=registry.get_stats(),
    )

    if templates_loaded == 0:
        logger.warning(
            "No prompt templates found",
            prompts_dir=str(prompts_dir),
            hint="Create YAML files in subdirectories like prompts/classification/v1.0.0.yaml",
        )

# Prompts Directory

This directory contains versioned prompt templates for LLM interactions, stored as YAML files for better version control and modularity.

## Structure

```
prompts/
├── classification/           # Classification prompts
│   ├── v1.0.0.yaml          # Version 1.0.0
│   ├── v1.1.0.yaml          # Version 1.1.0 (future)
│   └── experiments.yaml     # A/B test configurations
└── workflows/               # Future: workflow-specific prompts
    └── safety/
        └── v1.0.0.yaml
```

## YAML Schema

Each prompt file follows this structure:

```yaml
id: <prompt_identifier>      # Unique ID (e.g., "classification")
version: <semantic_version>  # Version string (e.g., "1.0.0")

metadata:
  author: <author_name>
  created: <date>
  description: <description>
  tags: [tag1, tag2]
  changes: <what changed from previous version>

system_prompt: |
  The system prompt text goes here.
  Use YAML's pipe notation for multi-line strings.

user_prompt_template: |
  User prompt with Jinja2 variables: {{variable_name}}
  CHANNEL: {{channel}}
  MESSAGE: {{message}}

parameters:
  - name: variable_name
    type: string
    description: Description of what this variable is

llm_config:
  temperature: 0.0
  max_tokens: 500
  response_format: json_object
```

## Creating a New Prompt Version

1. **Copy the current version**:
   ```bash
   cp prompts/classification/v1.0.0.yaml prompts/classification/v1.1.0.yaml
   ```

2. **Edit the new version**:
   - Update the `version` field
   - Update `metadata.created` and `metadata.changes`
   - Make your prompt changes

3. **Test the new version**:
   ```python
   from app.prompts import registry
   registry.set_active("classification", "1.1.0")
   ```

4. **Commit the change**:
   ```bash
   git add prompts/classification/v1.1.0.yaml
   git commit -m "Add classification prompt v1.1.0 - shorter, more focused"
   ```

## A/B Testing

Create an `experiments.yaml` file in the prompt directory:

```yaml
# prompts/classification/experiments.yaml
experiments:
  - id: classification_exp_1
    name: "Test shorter prompt"
    active: true
    variants:
      - name: control
        version: 1.0.0
        traffic: 0.5
      - name: variant_a
        version: 1.1.0
        traffic: 0.5
    metrics:
      - accuracy
      - latency
      - confidence_score
    start_date: 2024-01-20
    end_date: 2024-02-20
```

## Usage in Code

```python
# Load prompts at startup (in app/main.py)
from app.prompts import load_prompts, registry

load_prompts()
registry.set_active("classification", "1.0.0")

# Use in services
result = await llm_client.complete_with_template(
    template_id="classification",
    variables={"channel": "chat", "message": "What's your refund policy?"}
)
```

## Best Practices

1. **Semantic Versioning**: Use MAJOR.MINOR.PATCH
   - MAJOR: Breaking changes (different output format)
   - MINOR: Backwards-compatible improvements
   - PATCH: Bug fixes, typos

2. **Git Workflow**:
   - Each version is a separate file for clean git history
   - Use descriptive commit messages
   - Review prompt changes in PRs like code changes

3. **Testing**:
   - Test new prompts with representative examples
   - Compare outputs between versions
   - Monitor metrics after deploying new versions

4. **Documentation**:
   - Use `metadata.description` to explain the prompt's purpose
   - Use `metadata.changes` to document what changed from the previous version
   - Add comments in YAML for complex logic

## Validation

Prompts are automatically validated at load time:
- Required fields must be present
- Jinja2 template syntax must be valid
- Parameter definitions must match template variables

If validation fails, the application will log an error and may refuse to start.

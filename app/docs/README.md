# Documentation Rendering System

This module provides a documentation rendering system that displays markdown files from the `/docs` directory with a sidebar navigation and table of contents.

## Features

- **Sidebar Navigation**: Left sidebar with configurable sections and pages
- **Table of Contents**: Right sidebar showing headers (h1, h2, h3) from the current page
- **Markdown Rendering**: Full markdown support with syntax highlighting, tables, and more
- **Responsive Design**: Works on desktop and mobile devices

## Configuration

### Sidebar Configuration

Edit `app/docs/sidebar.yaml` to configure the sidebar navigation:

```yaml
sections:
  - title: "Section Name"
    items:
      - title: "Page Title"
        path: "relative/path/to/file"  # without .md extension
```

The `path` should be relative to the `/docs` directory. For example:
- `"README"` → `/docs/README.md`
- `"architecture"` → `/docs/architecture.md`
- `"plan/IMPLEMENTATION_PLAN"` → `/docs/plan/IMPLEMENTATION_PLAN.md`

### Adding New Documentation

1. Create your markdown file in the `/docs` directory
2. Add an entry to `sidebar.yaml` to make it accessible
3. The page will automatically render when accessed

## URLs

- Home page: `http://localhost:8000/`
- Specific page: `http://localhost:8000/{path}`

Example:
- `http://localhost:8000/` - Loads first page from sidebar
- `http://localhost:8000/architecture` - Loads `/docs/architecture.md`
- `http://localhost:8000/plan/IMPLEMENTATION_PLAN` - Loads `/docs/plan/IMPLEMENTATION_PLAN.md`

## Markdown Support

The system supports:
- Headers (h1-h6)
- Bold, italic, strikethrough
- Links and images
- Code blocks with syntax highlighting
- Tables
- Lists (ordered and unordered)
- Blockquotes
- Horizontal rules

## Development

### File Structure

```
app/
├── docs/
│   ├── __init__.py
│   ├── router.py       # FastAPI routes
│   ├── sidebar.yaml    # Sidebar configuration
│   └── README.md       # This file
└── templates/
    └── docs.html       # Main template (minimalist shadcn/ui inspired design)
```

### Customization

#### Styling

The UI uses a minimalist design inspired by shadcn/ui with:
- CSS variables for theming (easily customizable)
- Clean typography with proper hierarchy
- Subtle borders and hover states
- Smooth transitions
- Responsive design

Edit the `<style>` section in `app/templates/docs.html` to customize the appearance.

#### Template

The template uses Jinja2. Variables available:
- `title` - Page title
- `content` - Rendered HTML content
- `toc` - Table of contents (list of headers)
- `sidebar` - Sidebar configuration
- `current_page` - Current page path for highlighting

## Security

- Path traversal protection is built-in
- Only files within `/docs` directory can be accessed
- Paths are sanitized before file system access

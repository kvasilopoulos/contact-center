# Documentation Rendering System

This module provides a documentation rendering system that displays markdown files from the project `docs/` directory with a sidebar navigation and table of contents. It lives under `app/frontend/docs/` and is mounted at prefix `/docs`. Templates are in `app/frontend/templates/`.

## Features

- **Sidebar Navigation**: Left sidebar with configurable sections and pages
- **Table of Contents**: Right sidebar showing headers (h1, h2, h3) from the current page
- **Markdown Rendering**: Full markdown support with syntax highlighting, tables, and more
- **Responsive Design**: Works on desktop and mobile devices

## Configuration

Edit `app/frontend/docs/sidebar.yaml` to configure the sidebar navigation.

## File Structure

```
app/
├── frontend/
│   ├── docs/
│   │   ├── __init__.py
│   │   ├── router.py
│   │   ├── sidebar.yaml
│   │   └── README.md
│   ├── qa/
│   │   └── ...
│   └── templates/
│       ├── docs.html
│       ├── landing.html
│       └── qa_interface.html
```

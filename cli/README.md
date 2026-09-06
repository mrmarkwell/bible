# Command Line Interface (`cli/`)

This directory houses the command-line interface implementation for the Bible Engine.

## Intended CLI Commands
- `bible get <reference> [--version=<ver>]`: Fetch and display verses or passage spans.
- `bible search <query> [--version=<ver>]`: Full-text search across scripture.
- `bible tag add <reference> <tag>`: Associate a semantic tag with a verse or passage span.
- `bible tag list <reference>`: Display all semantic tags for a given scripture reference.
- `bible serve [--port=<port>]`: Launch the local Web UI dashboard.
- `bible render <reference> [--output=<file>]`: Render scripture to visual cards (via Typst).

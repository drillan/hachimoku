project = "hachimoku"
copyright = "2026, driller"
author = "driller"
release = "0.0.1"
language = "ja"

extensions = [
    "myst_parser",
    "sphinxcontrib.mermaid",
]

myst_enable_extensions = [
    "colon_fence",
    "substitution",
    "tasklist",
    "attrs_inline",
    "deflist",
]

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

html_theme = "shibuya"
html_static_path = ["_static"]

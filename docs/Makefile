# Makefile for Sphinx documentation (i18n structure)

SPHINXOPTS    ?=
SPHINXBUILD   ?= uv run --group docs sphinx-build

# Language-specific targets
html-ja:
	@$(SPHINXBUILD) -M html "ja" "ja/_build" $(SPHINXOPTS) $(O)

# html is alias for html-ja (default language)
html: html-ja

# Clean targets
clean-ja:
	@$(SPHINXBUILD) -M clean "ja" "ja/_build" $(SPHINXOPTS) $(O)

clean: clean-ja

help:
	@echo "Available targets:"
	@echo "  html       Build HTML docs (alias for html-ja)"
	@echo "  html-ja    Build Japanese HTML docs"
	@echo "  clean      Clean build artifacts"
	@echo "  clean-ja   Clean Japanese build artifacts"

.PHONY: help html html-ja clean clean-ja

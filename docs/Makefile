# Makefile for Sphinx documentation (i18n structure)

SPHINXOPTS    ?=
SPHINXBUILD   ?= uv run --group docs sphinx-build

# Language-specific targets
html-ja:
	@$(SPHINXBUILD) -M html "ja" "ja/_build" $(SPHINXOPTS) $(O)

html-en:
	@$(SPHINXBUILD) -M html "en" "en/_build" $(SPHINXOPTS) $(O)

# html builds all languages
html: html-ja html-en

# Clean targets
clean-ja:
	@$(SPHINXBUILD) -M clean "ja" "ja/_build" $(SPHINXOPTS) $(O)

clean-en:
	@$(SPHINXBUILD) -M clean "en" "en/_build" $(SPHINXOPTS) $(O)

clean: clean-ja clean-en

help:
	@echo "Available targets:"
	@echo "  html       Build HTML docs (all languages)"
	@echo "  html-ja    Build Japanese HTML docs"
	@echo "  html-en    Build English HTML docs"
	@echo "  clean      Clean all build artifacts"
	@echo "  clean-ja   Clean Japanese build artifacts"
	@echo "  clean-en   Clean English build artifacts"

.PHONY: help html html-ja html-en clean clean-ja clean-en

PYTHON ?= python3

.PHONY: setup init-config env-check test

setup:
	bash scripts/bootstrap.sh

init-config:
	$(PYTHON) -m goofish_rent init-config

env-check:
	$(PYTHON) -m goofish_rent env-check

test:
	$(PYTHON) -m unittest discover -s tests -p 'test*.py' -q

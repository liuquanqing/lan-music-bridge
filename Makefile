.PHONY: check release-audit clean

check:
	PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -W error::ResourceWarning -m unittest discover -s tests -t . -v
	PYTHONPATH=src python3 -m compileall -q src tests
	python3 scripts/check_stdlib.py
	$(MAKE) clean

release-audit:
	./scripts/release-audit.sh
	./scripts/test-release-audit-dotfiles.sh

clean:
	find src tests -type f \( -name '*.pyc' -o -name '*.pyo' \) -delete
	find src tests -type d -name __pycache__ -empty -delete

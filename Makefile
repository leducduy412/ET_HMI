SHELL := /bin/bash

.PHONY: install lint fmt clean

install:
	pip install --editable .
	pip install -r requirements.txt

clean:
	rm -rf ./dist ./build *.egg-info

lint:
	flake8 .
	mypy ./et_label_app || exit 1 # Return error if mypy failed
	# Check if something has changed after generation
	git \
		--no-pager diff \
		--exit-code \
		.

fmt:
	black . \
		--exclude "/(\.tox.*|venv.*)/"

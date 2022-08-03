.DEFAULT_GOAL := install

install:
	pip3 install -r requirements.txt

test:
	python3 test.py

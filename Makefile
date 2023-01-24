build:
	py -m build

pypi:
	py -m twine upload --repository pypi dist/*

test:
	pytest
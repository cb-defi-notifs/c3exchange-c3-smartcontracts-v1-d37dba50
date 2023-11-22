
# Allow to run multiple lines in a recipe in the same shell.
.ONESHELL:

SRCDIR=contracts_unified/

TARGETDIRS=$(SRCDIR)

autoflake:
	poetry run autoflake -r --in-place --remove-unused-variables --remove-all-unused-imports $(TARGETDIRS)

isort:
	poetry run isort $(TARGETDIRS)

mypy:
	poetry run mypy $(TARGETDIRS)

pylint:
	poetry run pylint --disable=fixme,too-few-public-methods,too-many-public-methods,too-many-arguments,too-many-locals,too-many-statements,missing-kwoa,line-too-long,duplicate-code $(TARGETDIRS)

consistent-format: autoflake isort

correct-format: consistent-format mypy pylint

coverage-report:
	poetry run coverage report -m --sort=Cover > coverage-report.txt
	cat coverage-report.txt

# .PHONY indicates which targets are not connected to the generation of one or more files.
.PHONY: autoflake isort mypy pylint consistent-format correct-format tests coverage-report

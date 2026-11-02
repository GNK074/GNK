# Unit tests

`test_service_script.py` checks the Bash manager using isolated Docker and curl test doubles on Ubuntu. Tests cover start readiness, stop volume preservation, build/deploy sequencing, failed builds, service status, failed container/HTTP health, production URLs, log filters, input validation, and safe dotenv handling. No real containers are started.

Run `python -m unittest discover -s tests/unit -p test_service_script.py -v`. These tests skip on hosts without a functioning Linux Bash. CI runs Bash syntax validation and all command tests on Ubuntu.

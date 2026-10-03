import json
from hypothesis import HealthCheck, settings

settings.register_profile("pipeline", max_examples=200, deadline=None,
                          database=None, suppress_health_check=[HealthCheck.too_slow])
settings.load_profile("pipeline")
_results = []

def pytest_collectreport(report):
    if report.failed:
        _results.append({"test": "<collection>", "outcome": "error",
                          "detail": report.longreprtext[-4000:]})

def pytest_runtest_logreport(report):
    if report.when == "call" or report.failed:
        _results.append({"test": report.nodeid.split("::")[-1], "outcome": report.outcome,
                          "detail": report.longreprtext[-4000:] if report.failed else ""})

def pytest_sessionfinish(session, exitstatus):
    with open("results.json", "w") as f:
        json.dump({"exitstatus": int(exitstatus), "tests": _results}, f, indent=2)

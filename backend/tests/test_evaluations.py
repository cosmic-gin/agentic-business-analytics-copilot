from backend.app.agent.graph import AnalyticsAgent
from backend.app.agent.planning import DeterministicPlanner
from backend.app.services.analytics import AnalyticsTools
from evals.run import run_benchmark


def test_versioned_benchmark(database):
    report = run_benchmark(AnalyticsAgent(AnalyticsTools(database), DeterministicPlanner()))
    failures = [(case.id, case.failure_reasons) for case in report.cases if not case.passed]
    assert not failures
    assert report.overall.passed == report.overall.total == 50
    assert report.numeric_accuracy.total == 36
    assert report.unsafe_rejection.passed == 6
    assert report.cost_status == "not_applicable"
    assert len({case.id for case in report.cases}) == 50

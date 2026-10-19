"""Evaluation (milestone 7): my cases with expected result and trajectory.

The expected outcome is not changed to make it pass. The 5 failures found by the
first pass (milestone 7) were fixed in milestone 7b; see the worklog.
"""

import pytest

from office_support.evaluation import CASES, evaluate, main
from office_support.model import SimulatedModel

BY_NUMBER = {c.n: c for c in CASES}


def _ids(cases) -> list[str]:
    return [f"{c.n}-{c.name}" for c in cases]


@pytest.mark.parametrize("case", CASES, ids=_ids(CASES))
def test_case_with_script(case):
    evaluation = evaluate(case)
    assert evaluation.obtained() == case.expected


SIMULABLE = [c for c in CASES if c.simulated]


@pytest.mark.parametrize("case", SIMULABLE, ids=_ids(SIMULABLE))
def test_case_with_simulated_model(case):
    evaluation = evaluate(case, SimulatedModel())
    assert evaluation.obtained() == case.expected


def _executed_tools(evaluation, name: str) -> list:
    return [s for s in evaluation.result.trace if s.tool == name]


def test_case_1_restarts_the_vpn():
    evaluation = evaluate(BY_NUMBER[1])
    assert evaluation.network.services["MAD-01"]["vpn"] == "ok"
    assert len(evaluation.questions) == 1


def test_case_2_rejection_does_not_restart_r1():
    evaluation = evaluate(BY_NUMBER[2])
    assert evaluation.network.services["MAD-01"]["vpn"] == "down"
    assert _executed_tools(evaluation, "restart_service") == []
    assert evaluation.result.escalation is not None


def test_case_8_does_not_call_the_model():
    assert evaluate(BY_NUMBER[8]).model_calls == 0


def test_case_9_made_up_citation_removed_r5():
    result = evaluate(BY_NUMBER[9]).result
    assert "docs/kb-network-07.md#Steps" not in result.citations
    assert "kb-network-07" not in result.answer


def test_case_10_guardrail_blocks_without_asking_r2():
    evaluation = evaluate(BY_NUMBER[10])
    assert evaluation.questions == []
    assert evaluation.network.services["MAD-01"]["erp"] == "ok"
    assert _executed_tools(evaluation, "restart_service") == []


def test_table_for_the_report(capsys):
    assert main(["--model", "script"]) == 0
    output = capsys.readouterr().out
    assert "| 1 | internet MAD-01, confirms |" in output
    assert "**Hits**" in output

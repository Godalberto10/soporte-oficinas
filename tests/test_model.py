"""Tests of the scripted model."""

import pytest

from office_support.model import Model, ScriptedModel


def test_returns_responses_in_order():
    model = ScriptedModel(['{"a": 1}', '{"b": 2}'])
    assert model.generate("s", []) == '{"a": 1}'
    assert model.generate("s", []) == '{"b": 2}'


def test_exhausted_raises_runtime_error():
    model = ScriptedModel(["one"])
    model.generate("s", [])
    with pytest.raises(RuntimeError):
        model.generate("s", [])


def test_records_the_calls():
    model = ScriptedModel(["r"])
    messages = [{"role": "user", "content": "I have no internet"}]
    model.generate("you are the classifier", messages)
    messages.append({"role": "assistant", "content": "later change"})
    assert model.calls == [{
        "system": "you are the classifier",
        "messages": [{"role": "user", "content": "I have no internet"}],
    }]


def test_does_not_modify_the_original_list():
    responses = ["a", "b"]
    ScriptedModel(responses).generate("s", [])
    assert responses == ["a", "b"]


def test_satisfies_the_protocol():
    def use(model: Model) -> str:
        return model.generate("s", [])

    assert use(ScriptedModel(["ok"])) == "ok"

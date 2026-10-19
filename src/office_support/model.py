"""Language model contract, scripted model, simulated model and Hugging Face."""

import json
import os
import re
from typing import Any, Protocol

from dotenv import load_dotenv
from huggingface_hub import InferenceClient

from office_support.retrieval import tokenize

DEFAULT_MODEL = "Qwen/Qwen2.5-72B-Instruct"
OLLAMA_DEFAULT_MODEL = "qwen2.5:7b"
OLLAMA_DEFAULT_URL = "http://localhost:11434/v1"
ATTEMPTS = 2


class Model(Protocol):
    """Any model that, given a system prompt and messages, returns text."""

    def generate(self, system: str, messages: list[dict]) -> str: ...


class ScriptedModel:
    """Returns responses fixed in advance, in order. For tests only."""

    def __init__(self, responses: list[str]) -> None:
        self._responses = list(responses)
        self.calls: list[dict] = []

    def generate(self, system: str, messages: list[dict]) -> str:
        """Records the call and returns the next response of the script."""
        self.calls.append({"system": system, "messages": list(messages)})
        if not self._responses:
            raise RuntimeError("ScriptedModel: no responses left in the script")
        return self._responses.pop(0)


# --- Hugging Face ----------------------------------------------------------

class HFModel:
    """Real model through huggingface_hub.InferenceClient (token in HF_TOKEN)."""

    def __init__(self, model: str | None = None, client: Any = None) -> None:
        load_dotenv()
        self.model = model or os.environ.get("HF_MODEL") or DEFAULT_MODEL
        self._token = os.environ.get("HF_TOKEN")
        if client is None:
            if not self._token:
                raise RuntimeError("HF_TOKEN is missing: add it to the .env file "
                                   "(HF_TOKEN=...) or use --model simulated")
            client = InferenceClient(model=self.model, token=self._token)
        self._client = client
        self._extra: dict[str, str] = {}

    def _without_token(self, text: str) -> str:
        return text.replace(self._token, "***") if self._token else text

    def generate(self, system: str, messages: list[dict]) -> str:
        """One response with temperature=0; retries once if the failure is transient."""
        full = [{"role": "system", "content": system}, *messages]
        for attempt in range(1, ATTEMPTS + 1):
            try:
                response = self._client.chat_completion(
                    messages=full, temperature=0, max_tokens=512, **self._extra)
                return response.choices[0].message.content or ""
            except Exception as error:  # network or provider
                if attempt == ATTEMPTS or not is_transient(error):
                    reason = self._without_token(f"{type(error).__name__}: {error}")
                    raise RuntimeError(f"model {self.model} did not respond after "
                                       f"{attempt} attempt(s) ({reason})") from None
        raise AssertionError("unreachable")


class OllamaModel(HFModel):
    """Real local model with Ollama: same protocol as HF, no token or credits."""

    def __init__(self, model: str | None = None, client: Any = None) -> None:
        load_dotenv()
        self.model = model or os.environ.get("OLLAMA_MODEL") or OLLAMA_DEFAULT_MODEL
        self._token = None
        url = os.environ.get("OLLAMA_URL") or OLLAMA_DEFAULT_URL
        self._client = client or InferenceClient(base_url=url)
        self._extra = {"model": self.model}  # Ollama needs the model in every call


def is_transient(error: Exception) -> bool:
    """Network failure, 429 or 5xx: worth retrying. 401/402/404… are not fixed by retrying."""
    status = getattr(getattr(error, "response", None), "status_code", None)
    return status is None or status == 429 or status >= 500


# --- Simulated ---------------------------------------------------------------

TYPE_WORDS = [  # order matters: "I can't log in to the ERP" is not network
    ("printer", ("print", "toner", "jam")),
    ("app_access", ("erp", "password", "access", "app", "login", "log")),
    ("email", ("email", "mail", "outlook", "inbox")),
    ("hardware", ("laptop", "monitor", "power", "screen", "keyboard", "computer", "pc",
                  "device", "turn", "slow", "mouse", "freez", "hang", "crash")),
    ("network", ("internet", "vpn", "connect", "network", "wifi", "brows", "online")),
]
SUPPORT_WORDS = ("work", "error", "fail", "problem", "cant", "cannot", "unable", "program",
                 "install", "updat", "office", "broken", "issue")
DAMAGE_WORDS = ("explod", "smok", "burn", "spark", "melt", "flame", "flood")  # physical repair
TYPE_PRIORITY = {"printer": "P4"}  # there is usually another printer available
ANNOYANCE_WORDS = ("slow", "delay", "long", "late", "freez", "hang")  # can work, though worse → P4
TYPE_SERVICE = {"network": "vpn", "printer": "printing",
                "app_access": "erp", "email": "email"}


def _has(tokens: list[str], prefixes: tuple[str, ...]) -> bool:
    return any(t.startswith(p) for t in tokens for p in prefixes)


def _type_from_words(text: str) -> str:
    """Type from keywords; with none of them, `other` if it sounds like support."""
    tokens = tokenize(text)
    for type_, prefixes in TYPE_WORDS:
        if _has(tokens, prefixes):
            return type_
    return "other" if _has(tokens, SUPPORT_WORDS) else "out_of_scope"


def _of_its_type(fragments: list[dict], type_: str) -> list[dict]:
    """Only kb-<type>-NN.md articles: an article of another type is not cited."""
    return [f for f in fragments if f["doc"].startswith(f"docs/kb-{type_}-")]


def _last_observation(messages: list[dict]) -> Any:
    content = messages[-1]["content"].removeprefix("Observation: ")
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return {"error": content}


class SimulatedModel:
    """Deterministic rule-based model to use the system without a token.

    It applies no safety rule: the orchestrator always does that.
    """

    def generate(self, system: str, messages: list[dict]) -> str:
        agent = re.search(r'the "(\w+)" agent', system)
        context = json.loads(messages[0]["content"])
        turn = sum(1 for m in messages if m["role"] == "assistant")
        respond = getattr(self, f"_{agent.group(1) if agent else 'unknown'}", self._unknown)
        return json.dumps(respond(context, turn, messages), ensure_ascii=False)

    def _classifier(self, ctx: dict, turn: int, messages: list[dict]) -> dict:
        type_ = _type_from_words(ctx["incident"])
        annoyance = _has(tokenize(ctx["incident"]), ANNOYANCE_WORDS)
        priority = "P4" if annoyance else TYPE_PRIORITY.get(type_, "P3")
        return {"type": type_, "priority": priority,
                "reason": f"keywords of the incident: {type_}"}

    def _diagnosis(self, ctx: dict, turn: int, messages: list[dict]) -> dict:
        tokens = tokenize(ctx["incident"])
        if _has(tokens, DAMAGE_WORDS) or {"fire", "fires"} & set(tokens):
            return {"cause": "physical damage to the device: it needs an on-site repair, "
                             "which first level does not do", "service": None,
                    "evidence": ["the incident describes physical damage"]}
        service = TYPE_SERVICE.get(ctx["known"].get("type", ""))
        if service is None:
            return {"cause": "possible failure of the employee's device", "service": None,
                    "evidence": ["the incident type does not depend on a service"]}
        if turn == 0:
            return {"tool": "check_service",
                    "arguments": {"service": service, "office": ctx["office"]}}
        status = _last_observation(messages).get("status", "unknown")
        if status == "ok":
            return {"cause": f"{service} ok in {ctx['office']}: possible device failure",
                    "service": None, "evidence": [f"{service} = ok"]}
        return {"cause": f"{service} {status} in {ctx['office']}", "service": service,
                "evidence": [f"check_service({service}, {ctx['office']}) = {status}"]}

    def _knowledge(self, ctx: dict, turn: int, messages: list[dict]) -> dict:
        known = ctx["known"]
        if turn == 0:
            query = f"{ctx['incident']} {known.get('cause', '')}"
            return {"tool": "search_docs", "arguments": {"query": query, "k": 5}}
        fragments = _of_its_type(_last_observation(messages).get("fragments", []),
                                 known.get("type", ""))
        steps = [f for f in fragments if f["section"] == "Steps"]  # only «Steps» is a procedure
        if not steps or "physical damage" in known.get("cause", ""):  # no first-level procedure
            return {"procedure": None, "citations": [], "action": None}
        chosen = steps[0]
        service, cause = known.get("service"), known.get("cause", "")
        action = None
        if service and ("down" in cause or "degraded" in cause):
            action = {"tool": "restart_service",
                      "arguments": {"service": service, "office": ctx["office"]}}
        return {"procedure": chosen["text"],
                "citations": [f"{chosen['doc']}#{chosen['section']}"], "action": action}

    def _escalation(self, ctx: dict, turn: int, messages: list[dict]) -> dict:
        known = ctx["known"]
        return {"summary": f"{ctx['incident']} ({ctx['office']}). "
                           f"Cause: {known.get('cause', 'not diagnosed')}.",
                "tried": [str(n) for n in ctx.get("orchestrator_notes", [])],
                "priority": known.get("priority", "P3")}

    def _unknown(self, ctx: dict, turn: int, messages: list[dict]) -> dict:
        return {"error": "unknown agent"}

"""LLM provider adapters.

Each adapter exposes ``complete(system, messages, schema=None, max_tokens=...)`` and
returns an ``LLMResult``. Adapters are plain Python (no ORM access) so they can be
unit-tested and swapped by configuration only (FRD §8 "Provider abstraction").
"""
import json
import logging
import time
from dataclasses import dataclass, field

import requests

_logger = logging.getLogger(__name__)

# Models that accept the server-side refusal fallback (Claude API only).
ANTHROPIC_FALLBACK_MODELS = {"claude-fable-5-1", "claude-opus-5-5", "claude-opus-5", "claude-sonnet-5-5"}


class LLMError(Exception):
    """Raised when a provider call fails after retries (caller may queue a retry)."""

    def __init__(self, message, retryable=True):
        super().__init__(message)
        self.retryable = retryable


@dataclass
class LLMResult:
    text: str
    data: object = None  # parsed JSON when a schema was requested
    input_tokens: int = 0
    output_tokens: int = 0
    model: str = ""
    latency_ms: int = 0
    raw: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# JSON helpers
# ---------------------------------------------------------------------------

def extract_json(text):
    """Parse JSON from a model reply, tolerating ```json fences or leading prose."""
    text = (text or "").strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if text.rstrip().endswith("```"):
            text = text.rstrip()[:-3]
    try:
        return json.loads(text)
    except ValueError:
        pass
    for open_c, close_c in (("{", "}"), ("[", "]")):
        start, end = text.find(open_c), text.rfind(close_c)
        if start != -1 and end > start:
            try:
                return json.loads(text[start:end + 1])
            except ValueError:
                continue
    raise ValueError("No valid JSON found in model output")


_TYPE_MAP = {
    "object": dict, "array": list, "string": str, "integer": int,
    "number": (int, float), "boolean": bool, "null": type(None),
}


def validate_schema(data, schema, path="$"):
    """Minimal JSON-schema validator (type/required/properties/items/enum/min/max).

    Returns a list of error strings; empty means valid. Kept dependency-free on purpose.
    """
    errors = []
    expected = schema.get("type")
    if expected:
        types = expected if isinstance(expected, list) else [expected]
        py_types = tuple(t for name in types for t in (
            _TYPE_MAP[name] if isinstance(_TYPE_MAP[name], tuple) else (_TYPE_MAP[name],)))
        if not isinstance(data, py_types) or (isinstance(data, bool) and "boolean" not in types):
            return [f"{path}: expected {expected}, got {type(data).__name__}"]
    if "enum" in schema and data not in schema["enum"]:
        errors.append(f"{path}: {data!r} not in {schema['enum']}")
    if isinstance(data, (int, float)) and not isinstance(data, bool):
        if "minimum" in schema and data < schema["minimum"]:
            errors.append(f"{path}: {data} < {schema['minimum']}")
        if "maximum" in schema and data > schema["maximum"]:
            errors.append(f"{path}: {data} > {schema['maximum']}")
    if isinstance(data, dict):
        for key in schema.get("required", []):
            if key not in data:
                errors.append(f"{path}: missing '{key}'")
        for key, sub in schema.get("properties", {}).items():
            if key in data:
                errors.extend(validate_schema(data[key], sub, f"{path}.{key}"))
    if isinstance(data, list):
        if "minItems" in schema and len(data) < schema["minItems"]:
            errors.append(f"{path}: fewer than {schema['minItems']} items")
        if "maxItems" in schema and len(data) > schema["maxItems"]:
            errors.append(f"{path}: more than {schema['maxItems']} items")
        if "items" in schema:
            for i, item in enumerate(data):
                errors.extend(validate_schema(item, schema["items"], f"{path}[{i}]"))
    return errors


def _strict_schema(schema):
    """Copy of a schema with additionalProperties: false on every object (structured outputs)."""
    if isinstance(schema, dict):
        out = {k: _strict_schema(v) for k, v in schema.items()
               if k not in ("minimum", "maximum", "minItems", "maxItems")}
        if out.get("type") == "object":
            out.setdefault("additionalProperties", False)
        return out
    if isinstance(schema, list):
        return [_strict_schema(s) for s in schema]
    return schema


# ---------------------------------------------------------------------------
# Adapters
# ---------------------------------------------------------------------------

class BaseLLM:
    def __init__(self, config):
        """config: dict with keys kind, base_url, api_key, model, timeout, effort, refusal_fallback."""
        self.config = config
        self.model = config.get("model") or ""
        self.timeout = config.get("timeout") or 60

    def _call(self, system, messages, schema, max_tokens):
        raise NotImplementedError

    def complete(self, system, messages, schema=None, max_tokens=4000, retries=2):
        """Call the model; when ``schema`` is given, parse + validate JSON and retry on mismatch."""
        last_error = None
        convo = list(messages)
        for attempt in range(retries + 1):
            started = time.time()
            result = self._call(system, convo, schema, max_tokens)
            result.latency_ms = int((time.time() - started) * 1000)
            if not schema:
                return result
            try:
                data = extract_json(result.text)
                errors = validate_schema(data, schema)
            except ValueError as exc:
                errors = [str(exc)]
            if not errors:
                result.data = data
                return result
            last_error = "; ".join(errors[:5])
            _logger.info("LLM JSON validation failed (attempt %s): %s", attempt + 1, last_error)
            convo = list(messages) + [
                {"role": "assistant", "content": result.text or "(empty)"},
                {"role": "user", "content": "Your reply did not match the required JSON schema: "
                                            f"{last_error}. Reply again with only valid JSON."},
            ]
        raise LLMError(f"Model output failed schema validation: {last_error}", retryable=True)


class AnthropicLLM(BaseLLM):
    """Claude via the official ``anthropic`` SDK."""

    def _client(self):
        try:
            import anthropic
        except ImportError as exc:
            raise LLMError("The 'anthropic' Python package is not installed "
                           "(pip install anthropic)", retryable=False) from exc
        kwargs = {"api_key": self.config.get("api_key") or None,
                  "timeout": float(self.timeout), "max_retries": 2}
        if self.config.get("base_url"):
            kwargs["base_url"] = self.config["base_url"]
        if self.config.get("workspace_id"):
            # Needed for keys that are not scoped to a workspace (e.g. user-level sk-ant-usr… keys).
            kwargs["default_headers"] = {"anthropic-workspace-id": self.config["workspace_id"]}
        return anthropic, anthropic.Anthropic(**kwargs)

    def _call(self, system, messages, schema, max_tokens):
        anthropic, client = self._client()
        params = {"model": self.model, "max_tokens": max_tokens, "messages": messages}
        if system:
            params["system"] = system
        output_config = {}
        if self.config.get("effort"):
            output_config["effort"] = self.config["effort"]
        if schema and self.config.get("structured_output", True):
            output_config["format"] = {"type": "json_schema", "schema": _strict_schema(schema)}
        if output_config:
            params["output_config"] = output_config
        use_fallback = self.config.get("refusal_fallback") and self.model in ANTHROPIC_FALLBACK_MODELS
        try:
            if use_fallback:
                response = client.beta.messages.create(
                    betas=["server-side-fallback-2026-07-01"],
                    extra_body={"fallbacks": "default"}, **params)
            else:
                response = client.messages.create(**params)
        except anthropic.BadRequestError as exc:
            # Some models reject structured outputs/effort: retry once with plain prompting.
            if "output_config" in params:
                _logger.info("Retrying without output_config: %s", exc)
                params.pop("output_config")
                self.config = dict(self.config, structured_output=False)
                response = client.messages.create(**params)
            else:
                raise LLMError(f"Anthropic request rejected: {exc}", retryable=False) from exc
        except (anthropic.AuthenticationError, anthropic.PermissionDeniedError, anthropic.NotFoundError) as exc:
            raise LLMError(f"Anthropic configuration error: {exc}", retryable=False) from exc
        except (anthropic.RateLimitError, anthropic.APIStatusError, anthropic.APIConnectionError) as exc:
            raise LLMError(f"Anthropic call failed: {exc}", retryable=True) from exc
        if response.stop_reason == "refusal":
            raise LLMError("Model declined the request (refusal)", retryable=False)
        text = "".join(b.text for b in response.content if getattr(b, "type", "") == "text")
        usage = response.usage
        return LLMResult(text=text, input_tokens=usage.input_tokens or 0,
                         output_tokens=usage.output_tokens or 0, model=response.model)


class OpenAICompatLLM(BaseLLM):
    """Any OpenAI-compatible /chat/completions endpoint (OpenAI, Azure, OpenRouter, vLLM, Ollama)."""

    def _call(self, system, messages, schema, max_tokens):
        base = (self.config.get("base_url") or "https://api.openai.com/v1").rstrip("/")
        headers = {"Content-Type": "application/json"}
        if self.config.get("api_key"):
            headers["Authorization"] = f"Bearer {self.config['api_key']}"
            headers["api-key"] = self.config["api_key"]  # Azure OpenAI
        payload = {"model": self.model, "max_tokens": max_tokens,
                   "messages": ([{"role": "system", "content": system}] if system else []) + messages}
        if schema and self.config.get("structured_output", True):
            payload["response_format"] = {"type": "json_object"}
        try:
            resp = requests.post(f"{base}/chat/completions", json=payload, headers=headers, timeout=self.timeout)
            if resp.status_code == 400 and "response_format" in payload:
                payload.pop("response_format")
                resp = requests.post(f"{base}/chat/completions", json=payload, headers=headers, timeout=self.timeout)
        except requests.RequestException as exc:
            raise LLMError(f"LLM endpoint unreachable: {exc}") from exc
        if resp.status_code in (401, 403, 404):
            raise LLMError(f"LLM configuration error {resp.status_code}: {resp.text[:300]}", retryable=False)
        if resp.status_code >= 400:
            raise LLMError(f"LLM error {resp.status_code}: {resp.text[:300]}", retryable=resp.status_code >= 429)
        body = resp.json()
        usage = body.get("usage") or {}
        return LLMResult(text=body["choices"][0]["message"].get("content") or "",
                         input_tokens=usage.get("prompt_tokens", 0),
                         output_tokens=usage.get("completion_tokens", 0),
                         model=body.get("model", self.model), raw={"id": body.get("id")})


class MockLLM(BaseLLM):
    """Deterministic offline LLM used for development, demos and tests.

    It recognises the ``task`` marker the prompt builders put in the system prompt and
    returns a plausible, schema-valid answer.
    """

    def _call(self, system, messages, schema, max_tokens):
        from . import mock_responses
        last = messages[-1]["content"] if messages else ""
        text = mock_responses.respond(system or "", last if isinstance(last, str) else json.dumps(last), schema)
        return LLMResult(text=text, input_tokens=len((system or "") + str(last)) // 4,
                         output_tokens=len(text) // 4, model="mock")


ADAPTERS = {"anthropic": AnthropicLLM, "openai": OpenAICompatLLM, "mock": MockLLM}


def get_llm(config):
    kind = config.get("kind") or "mock"
    if kind not in ADAPTERS:
        raise LLMError(f"Unknown LLM provider kind '{kind}'", retryable=False)
    return ADAPTERS[kind](config)

from types import SimpleNamespace
from unittest.mock import patch

from odoo.tests import BaseCase, tagged

from ..services import prompts
from ..services.llm import AnthropicLLM, OpenAICompatLLM


class FakeMessages:
    def __init__(self, sink, reply):
        self.sink, self.reply = sink, reply

    def create(self, **params):
        self.sink.append(params)
        return SimpleNamespace(
            stop_reason="end_turn", model=params["model"],
            content=[SimpleNamespace(type="text", text=self.reply)],
            usage=SimpleNamespace(input_tokens=11, output_tokens=7))


class FakeClient:
    sink = []
    init_kwargs = []
    reply = '{"answer": "ok", "out_of_scope": false}'

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.init_kwargs.append(kwargs)
        self.messages = FakeMessages(self.sink, self.reply)
        self.beta = SimpleNamespace(messages=FakeMessages(self.sink, self.reply))


@tagged("post_install", "-at_install", "linda")
class TestLLMAdapters(BaseCase):

    def setUp(self):
        super().setUp()
        FakeClient.sink.clear()
        FakeClient.init_kwargs.clear()

    def test_anthropic_request_shape(self):
        import anthropic
        with patch.object(anthropic, "Anthropic", FakeClient):
            llm = AnthropicLLM({"kind": "anthropic", "model": "claude-sonnet-5-5", "api_key": "k",
                                "refusal_fallback": True, "effort": "medium"})
            res = llm.complete(*prompts.ask_doc("doc", "q"), schema=prompts.ANSWER_SCHEMA)
        params = FakeClient.sink[0]
        self.assertEqual(res.data["answer"], "ok")
        self.assertEqual((res.input_tokens, res.output_tokens), (11, 7))
        self.assertEqual(params["model"], "claude-sonnet-5-5")
        self.assertNotIn("temperature", params)
        self.assertEqual(params["output_config"]["format"]["type"], "json_schema")
        self.assertFalse(params["output_config"]["format"]["schema"]["additionalProperties"])
        self.assertEqual(params["output_config"]["effort"], "medium")
        self.assertEqual(params["betas"], ["server-side-fallback-2026-07-01"])
        self.assertEqual(params["extra_body"], {"fallbacks": "default"})

    def test_anthropic_custom_model_no_fallback(self):
        import anthropic
        with patch.object(anthropic, "Anthropic", FakeClient):
            llm = AnthropicLLM({"kind": "anthropic", "model": "claude-haiku-4-5", "refusal_fallback": True})
            llm.complete("TASK: x", [{"role": "user", "content": "hi"}])
        params = FakeClient.sink[0]
        self.assertEqual(params["model"], "claude-haiku-4-5")
        self.assertNotIn("betas", params)
        self.assertNotIn("output_config", params)

    def test_anthropic_workspace_header(self):
        import anthropic
        with patch.object(anthropic, "Anthropic", FakeClient):
            AnthropicLLM({"kind": "anthropic", "model": "claude-haiku-4-5", "api_key": "k",
                          "workspace_id": "wrkspc_123"}).complete("TASK: x", [{"role": "user", "content": "hi"}])
            AnthropicLLM({"kind": "anthropic", "model": "claude-haiku-4-5", "api_key": "k"}).complete(
                "TASK: x", [{"role": "user", "content": "hi"}])
        self.assertEqual(FakeClient.init_kwargs[0]["default_headers"], {"anthropic-workspace-id": "wrkspc_123"})
        self.assertNotIn("default_headers", FakeClient.init_kwargs[1])

    def test_openai_compatible(self):
        captured = {}

        def fake_post(url, json=None, headers=None, timeout=None):
            captured.update(url=url, json=json, headers=headers)
            return SimpleNamespace(status_code=200, text="", json=lambda: {
                "model": json["model"], "choices": [{"message": {"content": '{"answer": "hi", "out_of_scope": false}'}}],
                "usage": {"prompt_tokens": 5, "completion_tokens": 3}})

        with patch("requests.post", fake_post):
            llm = OpenAICompatLLM({"kind": "openai", "base_url": "http://localhost:11434/v1", "model": "llama3.1:8b"})
            res = llm.complete(*prompts.ask_doc("doc", "q"), schema=prompts.ANSWER_SCHEMA)
        self.assertEqual(captured["url"], "http://localhost:11434/v1/chat/completions")
        self.assertEqual(captured["json"]["model"], "llama3.1:8b")
        self.assertEqual(captured["json"]["messages"][0]["role"], "system")
        self.assertEqual(res.data["answer"], "hi")

import unittest
from unittest.mock import patch

from backend.app.services.openai_service import OpenAIChatService


class FakeResponse:
    status_code = 200

    def json(self):
        return {
            "choices": [
                {
                    "message": {
                        "tool_calls": [
                            {
                                "function": {
                                    "name": "create_training_plan",
                                    "arguments": '{"title":"Treino"}',
                                }
                            }
                        ]
                    }
                }
            ]
        }


class FakeAsyncClient:
    def __init__(self, *args, **kwargs):
        self.payload = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return False

    async def post(self, url, *, headers, json):
        self.payload = json
        return FakeResponse()


class OpenAIServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_gpt_5_6_tool_payload_is_compatible_and_forced(self):
        service = object.__new__(OpenAIChatService)
        service.api_key = "test-key"
        service.base_url = "https://example.invalid/v1/chat/completions"
        service.model = "gpt-5.6-terra"
        client = FakeAsyncClient()

        with patch(
            "backend.app.services.openai_service.httpx.AsyncClient",
            return_value=client,
        ):
            result = await service.complete_with_tools(
                system_prompt="Use tools.",
                history=[],
                reasoning_level="medium",
                tools=[
                    {
                        "type": "function",
                        "function": {
                            "name": "create_training_plan",
                            "description": "Create a plan",
                            "parameters": {"type": "object"},
                        },
                    }
                ],
                user_message="Crie um treino",
                forced_tool="create_training_plan",
                max_completion_tokens=2400,
            )

        self.assertTrue(result["tool_calls"])
        self.assertEqual(client.payload["reasoning_effort"], "none")
        self.assertNotIn("temperature", client.payload)
        self.assertEqual(client.payload["max_completion_tokens"], 2400)
        self.assertEqual(
            client.payload["tool_choice"],
            {"type": "function", "function": {"name": "create_training_plan"}},
        )


if __name__ == "__main__":
    unittest.main()

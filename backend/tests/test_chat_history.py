import unittest
from unittest.mock import patch

from backend.app.api.routes.chat import list_nutritionist_chat_messages
from backend.app.services.supabase_workspace_service import SupabaseWorkspaceService


class RecordingHistoryWorkspace(SupabaseWorkspaceService):
    def __init__(self):
        self.request = None

    async def _request(self, method, path, **kwargs):
        self.request = {"method": method, "path": path, **kwargs}
        return [
            {"id": "newest", "created_at": "2026-08-22T12:02:00Z"},
            {"id": "middle", "created_at": "2026-08-22T12:01:00Z"},
            {"id": "oldest", "created_at": "2026-08-22T12:00:00Z"},
        ]


class ChatHistoryTests(unittest.IsolatedAsyncioTestCase):
    async def test_history_selects_latest_page_and_returns_chronological_order(self):
        workspace = RecordingHistoryWorkspace()

        rows = await workspace._list_chat_messages(
            "nutritionist_messages",
            "conversation-a",
            limit=80,
            offset=0,
        )

        self.assertEqual([row["id"] for row in rows], ["oldest", "middle", "newest"])
        self.assertEqual(workspace.request["params"]["order"], "created_at.desc,id.desc")
        self.assertEqual(workspace.request["params"]["limit"], "80")
        self.assertEqual(workspace.request["params"]["offset"], "0")

    async def test_canonical_history_endpoint_forwards_limit_80_without_404(self):
        calls = []

        class AuthorizedWorkspace:
            async def list_authorized_nutritionist_messages(
                self,
                token,
                session_id,
                limit,
                offset,
            ):
                calls.append((token, session_id, limit, offset))
                return [{"id": "message-a"}]

        with patch(
            "backend.app.api.routes.chat.SupabaseWorkspaceService",
            AuthorizedWorkspace,
        ):
            rows = await list_nutritionist_chat_messages(
                session_id="conversation-a",
                limit=80,
                offset=0,
                token="owner-token",
            )

        self.assertEqual(rows, [{"id": "message-a"}])
        self.assertEqual(calls, [("owner-token", "conversation-a", 80, 0)])


if __name__ == "__main__":
    unittest.main()

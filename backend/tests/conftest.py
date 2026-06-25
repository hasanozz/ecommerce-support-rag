from __future__ import annotations

import os
import tempfile
from pathlib import Path


_TEST_SECRETS = Path(tempfile.gettempdir()) / "destekai_test_secrets.env.local"
_TEST_SECRETS.write_text(
    "\n".join(
        [
            "GOOGLE_CLIENT_ID=test-client-id",
            "GOOGLE_CLIENT_SECRET=test-client-secret",
            "GOOGLE_REDIRECT_URI=http://localhost:8000/auth/google/callback",
            "GEMINI_API_KEY=test-gemini-api-key",
            "GEMINI_MODEL=gemini-test-model",
            "GEMINI_MODEL_DEV=gemini-test-dev-model",
            f"SESSION_SECRET={'s' * 32}",
            f"IP_HASH_SECRET={'i' * 32}",
            'ADMIN_EMAILS=["admin@example.com"]',
        ]
    ),
    encoding="utf-8",
)
os.environ.setdefault("SECRETS_FILE", str(_TEST_SECRETS))

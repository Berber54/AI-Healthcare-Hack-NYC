import os

import pytest
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")


@pytest.fixture(autouse=True)
def _skip_without_supabase(request):
    if request.node.get_closest_marker("requires_supabase") and not (SUPABASE_URL and SUPABASE_KEY):
        pytest.skip("SUPABASE_URL/SUPABASE_KEY not set - skipping data-layer tests")


@pytest.fixture(scope="session")
def supabase_client():
    # Session-scoped fixtures are set up before function-scoped autouse ones,
    # so this needs its own guard - it can't rely on _skip_without_supabase
    # having run first.
    if not SUPABASE_URL or not SUPABASE_KEY:
        pytest.skip("SUPABASE_URL/SUPABASE_KEY not set - skipping data-layer tests")

    from app.data import _get_client

    return _get_client()

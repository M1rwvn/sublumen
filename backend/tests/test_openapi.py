import json, os
from sublumen.tools.openapi import build

def test_openapi_file_lists_every_route():
    p = os.path.join(os.path.dirname(__file__), "..", "..", "docs", "openapi.json")
    assert json.load(open(p)) == json.loads(json.dumps(build())), "docs/openapi.json is stale: run python -m sublumen.tools.openapi"

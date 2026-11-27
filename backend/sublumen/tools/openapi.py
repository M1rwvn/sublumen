"""Generate docs/openapi.json from the live Flask routes (paths, methods, auth requirement, first docstring line).
Run from backend/: python -m sublumen.tools.openapi. A test fails when a route is missing from the committed file."""
import json, os, re, sys, tempfile
from ..api.app import create_app
from ..config import Config

SUMMARY = {"/api/health": "Service health", "/api/auth/login": "Log in, returns a bearer token", "/api/users": "Create a user (admin)",
           "/api/stego/embed": "Encrypt a message (AES-GCM) and embed it in a PNG/BMP cover", "/api/stego/extract": "Extract and decrypt a message",
           "/api/stego/capacity": "Payload capacity of a cover", "/api/cases": "Cases (POST creates, GET lists)", "/api/evidence": "Upload evidence into a case (hashed on intake)",
           "/api/analyses": "Run forensic indicators + ML score on evidence (no verdict is issued)", "/api/compare": "Compare two images (SSIM, PSNR, MSE, diff maps)",
           "/api/models": "Registered model versions and recorded metrics", "/api/reports": "Generate a PDF forensic report for a case", "/api/benchmarks": "Recorded benchmark runs"}

def build():
    d = tempfile.mkdtemp(); os.environ.setdefault("SS_ADMIN_EMAIL", "a@x.org"); os.environ.setdefault("SS_ADMIN_PASSWORD", "adminpass1")
    app = create_app(Config(data_dir=d, db_uri="sqlite:///" + d + "/o.db", secret="x"))
    paths = {}
    for r in sorted(app.url_map.iter_rules(), key=lambda r: r.rule):
        if not r.rule.startswith("/api/"): continue
        p = re.sub(r"<(?:int:)?(\w+)>", r"{\1}", r.rule)
        for meth in sorted(r.methods - {"HEAD", "OPTIONS"}):
            params = [{"name": n, "in": "path", "required": True, "schema": {"type": "string"}} for n in re.findall(r"{(\w+)}", p)]
            op = {"summary": SUMMARY.get(p, r.endpoint.replace("_", " ")), "operationId": f"{meth.lower()}_{r.endpoint}", "parameters": params,
                  "responses": {"2XX": {"description": "OK (JSON, status field 'ok')"}, "4XX": {"description": "Error (JSON, status 'error' with code and message)"}}}
            if p not in ("/api/health", "/api/auth/login"): op["security"] = [{"bearer": []}]
            paths.setdefault(p, {})[meth.lower()] = op
    return {"openapi": "3.0.3", "info": {"title": "Sublumen API", "version": "1.0", "description": "Find what the pixels hide. Analysis responses are indicators, never a verdict."},
            "components": {"securitySchemes": {"bearer": {"type": "http", "scheme": "bearer"}}}, "paths": paths}

if __name__ == "__main__":
    out = os.path.join(os.path.dirname(__file__), "..", "..", "..", "docs", "openapi.json")
    json.dump(build(), open(out, "w"), indent=1, sort_keys=True); print("wrote", os.path.abspath(out), sum(len(v) for v in build()["paths"].values()), "operations")

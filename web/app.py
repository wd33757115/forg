"""Forge FastAPI Web service — HTTP API over the multi-agent pipeline."""

from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse

from forge.main import SCENARIO_QUESTIONS, detect_scenario_label, run_forge
from forge.utils.result_serializer import build_api_response
from web.models import HealthResponse, SolveRequest, SolveResponse

app = FastAPI(
    title="Forge",
    description="项目级 AI 操作系统 — 多 Agent 协作 API",
    version="0.1.0",
)

_HOME_HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <title>Forge</title>
  <style>
    body { font-family: system-ui, sans-serif; max-width: 720px; margin: 2rem auto; padding: 0 1rem; }
    h1 { color: #1a56db; }
    code { background: #f3f4f6; padding: 2px 6px; border-radius: 4px; }
    pre { background: #111827; color: #e5e7eb; padding: 1rem; border-radius: 8px; overflow-x: auto; }
  </style>
</head>
<body>
  <h1>Forge — 项目级 AI 操作系统</h1>
  <p>面向系统集成、等保合规、ITIL 运维的多 Agent 协作引擎。</p>
  <h2>流水线</h2>
  <p>ProblemSolver → Security/Operations → Compliance → Document → PMAdvisor</p>
  <h2>API</h2>
  <ul>
    <li><code>GET /health</code> — 健康检查</li>
    <li><code>POST /solve</code> — 提交问题，运行完整流程，返回 JSON</li>
    <li><code>GET /docs</code> — OpenAPI 交互文档</li>
  </ul>
  <h3>示例请求</h3>
  <pre>curl -X POST http://127.0.0.1:8000/solve \\
  -H "Content-Type: application/json" \\
  -d '{"question": "等保三级登录401故障，请诊断", "scenario": "security"}'</pre>
</body>
</html>"""


def _resolve_question(body: SolveRequest) -> tuple[str, str]:
    """Return (question text, scenario label)."""
    if body.scenario != "auto":
        question = body.question
        if body.question.strip() in SCENARIO_QUESTIONS.values():
            return question, body.scenario
        # Allow scenario preset to override only when question is empty-ish — keep user question
        return question, body.scenario
    return body.question, detect_scenario_label(body.question)


@app.get("/", response_class=HTMLResponse)
def home() -> str:
    """Simple landing page describing Forge and API usage."""
    return _HOME_HTML


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse()


@app.post("/solve", response_model=SolveResponse)
def solve(body: SolveRequest) -> SolveResponse:
    """
    Run the full Forge agent pipeline for the given question.

    Returns structured JSON with outputs from all participating agents.
    """
    question = body.question.strip()
    if not question:
        raise HTTPException(status_code=422, detail="question 不能为空")

    try:
        result = run_forge(
            question,
            project_id=body.project_id,
            protection_level=body.protection_level,
        )
        payload = build_api_response(
            result,
            question=question,
            scenario=detect_scenario_label(question),
        )
        return SolveResponse(**payload)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Forge 执行失败: {exc}") from exc

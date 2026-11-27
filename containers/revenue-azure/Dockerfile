FROM ghcr.io/astral-sh/uv@sha256:fc93e9ecd7218e9ec8fba117af89348eef8fd2463c50c13347478769aaedd0ce AS uv
FROM python@sha256:f0fa218d5b06f9b9235024fa061cde2cb141f726de52134471053d2d9b5324a3 AS build
WORKDIR /app
COPY --from=uv /uv /usr/local/bin/uv
COPY pyproject.toml uv.lock ./
COPY harness/ harness/
COPY projects/ projects/
RUN UV_PYTHON_DOWNLOADS=never uv sync --locked --no-default-groups --package production-agent-revenue-integrity --extra web --no-editable

FROM python@sha256:f0fa218d5b06f9b9235024fa061cde2cb141f726de52134471053d2d9b5324a3
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY --from=build /app/.venv .venv/
COPY revenue_azure_demo.py revenue_demo.py revenue_demo_web.py revenue_assessment.py ./
COPY revenue_demo_web.html revenue_demo_web.css revenue_demo_web.js ./
COPY revenue_profiled_runtime.py revenue_profiling.py ./
USER 65532:65532
EXPOSE 8080
ENTRYPOINT ["/app/.venv/bin/python", "-m", "revenue_azure_demo"]
CMD ["serve"]

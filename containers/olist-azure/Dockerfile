# Official Python 3.13.18 slim and uv 0.11.1 image indices.
FROM ghcr.io/astral-sh/uv@sha256:fc93e9ecd7218e9ec8fba117af89348eef8fd2463c50c13347478769aaedd0ce AS uv
FROM python@sha256:f0fa218d5b06f9b9235024fa061cde2cb141f726de52134471053d2d9b5324a3 AS build
WORKDIR /app
COPY --from=uv /uv /usr/local/bin/uv
COPY pyproject.toml uv.lock ./
COPY harness/ harness/
COPY projects/ projects/
RUN UV_PYTHON_DOWNLOADS=never uv sync --locked --no-default-groups --package production-agent-olist-support --extra web --no-editable

FROM python@sha256:f0fa218d5b06f9b9235024fa061cde2cb141f726de52134471053d2d9b5324a3
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY --from=build /app/.venv .venv/
COPY olist_azure_staging.py olist_azure_bootstrap.py olist_demo_host.py ./
COPY olist_demo_fixtures.py olist_demo_acceptance.py uv.lock ./
COPY olist_demo_planner.py olist_nemotron.py ./
COPY docs/evaluation/olist_semantic_candidate.py docs/evaluation/
USER 65532:65532
EXPOSE 8080
ENTRYPOINT ["/app/.venv/bin/python", "-m", "olist_azure_staging"]

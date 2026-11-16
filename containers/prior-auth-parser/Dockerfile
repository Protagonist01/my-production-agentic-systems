FROM python@sha256:a5a7017efc5969e00ae2b91c8eb0631049a569652aa4ffc4501769049ae45c72
RUN apt-get update && apt-get install -y --no-install-recommends poppler-utils tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt /build/requirements.txt
RUN python -m pip install --no-cache-dir --require-hashes -r /build/requirements.txt \
    && rm -rf /build
COPY agent_harness /app/agent_harness
COPY prior_auth /app/prior_auth
COPY prior_auth_documents.py prior_auth_profiling.py prior_auth_parser_worker.py /app/
ENV PYTHONDONTWRITEBYTECODE=1 OMP_THREAD_LIMIT=1 TMPDIR=/tmp
WORKDIR /app
USER 65532:65532
ENTRYPOINT ["python", "prior_auth_parser_worker.py"]

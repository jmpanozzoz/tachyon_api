ARG PYTHON_IMAGE=python:3.13-slim-bookworm@sha256:a5a7017efc5969e00ae2b91c8eb0631049a569652aa4ffc4501769049ae45c72
FROM ${PYTHON_IMAGE} AS build
WORKDIR /build
COPY pyproject.toml setup.py README.md LICENSE ./
COPY tachyon_api ./tachyon_api
RUN python -m pip wheel --no-deps --wheel-dir /wheel .

FROM ${PYTHON_IMAGE}
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app
RUN useradd --create-home --uid 10001 reference
COPY --from=build /wheel /wheel
COPY example ./example
RUN python -m pip install --no-cache-dir /wheel/*.whl -r example/requirements-runtime.txt
USER reference
EXPOSE 8000
CMD ["uvicorn", "example.app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2", "--limit-concurrency", "128", "--no-access-log", "--log-config", "example/logging.json", "--timeout-graceful-shutdown", "20", "--ws-max-size", "4096"]

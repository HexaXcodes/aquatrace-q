# Deliberately 3.13, not 3.11: requirements.txt pins numpy==2.5.2, which
# has no wheels for <3.12. The alternative -- downgrading numpy to stay
# on 3.11-slim -- would mean shipping a numpy version nothing in this
# codebase (43 tests, the live-server manual runs, this container's own
# build) has ever actually run against. 3.13 matches the dev venv that
# produced every one of those results, and every other pinned dependency
# (scipy, scikit-learn, qiskit, shapely, pyproj, ...) already resolves
# clean prebuilt cp313 wheels here -- there's no live problem this would
# be fixing, only a hypothetical one it would introduce. Revisit if a
# pinned dependency ever lacks a 3.13 wheel.
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# libpq for psycopg2, and a compiler toolchain in case a wheel isn't
# available for the target arch -- kept minimal on purpose.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq-dev gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

RUN mkdir -p data uploads outputs models

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

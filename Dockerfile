FROM python:3-slim

WORKDIR /app
COPY poetry.lock pyproject.toml ./

RUN pip install poetry
RUN poetry config virtualenvs.create false && poetry install

COPY app.py tokens.jsonc ./
CMD [ "python", "app.py" ]

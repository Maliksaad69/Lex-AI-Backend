FROM python:3.12.alpine

WORKDIR /code

COPY requirements.txt /code/requirements.txt

RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt

COPY ./app /code/app

CMD ["python3", "uvicorn", "main:app", "--port","8000"]
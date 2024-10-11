FROM python:3.12

WORKDIR /irfanium_prime_mk_iv

COPY . /irfanium_prime_mk_iv

RUN pip install --no-cache-dir -r requirements.txt

RUN apt-get update && apt-get install -y ffmpeg

CMD [ "python", "main.py"]
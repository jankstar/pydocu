# Pull base image
FROM python:3.9

WORKDIR /home

# Set environment varibles
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
ENV HF_HOME "/home/build" 


# Install files
COPY *.py /home
COPY *.txt /home
COPY *.sh /home
COPY *.ini /home
##RUN mkdir /build
COPY build /home/build

# Install dependencies
RUN pip install -r requirements.txt

# start server
EXPOSE 8000
##CMD ["python", "main.py"]
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
ARG BUILD_FROM
FROM ${BUILD_FROM}

# Install dependencies
RUN apk add --no-cache \
    python3 \
    py3-pip \
    chromium \
    chromium-chromedriver \
    tzdata

# Set timezone (adjust as needed)
RUN cp /usr/share/zoneinfo/America/Sao_Paulo /etc/localtime && \
    echo "America/Sao_Paulo" > /etc/timezone

# Install Python packages
COPY scraper/requirements.txt /app/
RUN pip3 install -r /app/requirements.txt

# Copy scraper files
COPY scraper/ /app/scraper/
COPY run.sh /

RUN chmod a+x /run.sh

CMD [ "/run.sh" ]
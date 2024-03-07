FROM python:3.10-bookworm

ARG COMBINE_BRANCH
ENV COMBINE_BRANCH=$COMBINE_BRANCH

# Install additional packages
RUN apt update --fix-missing && \
    apt install -y default-libmysqlclient-dev libmariadb-dev libmariadb-java python3-dev default-mysql-client vim nodejs npm && \
    apt clean && \
    rm -rf /var/lib/apt/lists/*

# App requirments
ADD app/pyproject.toml /pyproject.toml

# App scripts
COPY app/combine.sql /tmp/combine.sql
COPY app/combine_db_prepare.sh /tmp/combine_db_prepare.sh
COPY app/root.my.cnf /etc/.my.cnf

# Copy App
COPY app/ /opt/combine/


# Install dependencies
# Using poetry to avoid dependecy conflicts.
RUN pip install poetry && \
    poetry install

# Install Livy client (note related to args is gone)
ARG LIVY_TAGGED_RELEASE
ARG SCALA_VERSION
ENV LIVY_TAGGED_RELEASE=$LIVY_TAGGED_RELEASE
ENV SCALA_VERSION=$SCALA_VERSION
RUN pip install livy

# Install ElasticDump
RUN npm install elasticdump -g
RUN pip install git+https://github.com/MI-DPLA/es2csv.git@python3

# Install Mongo-Tools
RUN wget https://downloads.mongodb.com/compass/mongodb-mongosh_2.1.5_amd64.deb && \
    apt install ./mongodb-* && rm ./mongodb-*
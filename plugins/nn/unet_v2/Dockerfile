ARG REGISTRY
ARG TAG
#FROM ${REGISTRY}/base-pytorch:${TAG}
FROM ${REGISTRY}/base-pytorch:6.0.17

# temp solution
RUN pip install plotly==4.11.0
RUN pip install docker
RUN pip install fuzzywuzzy

# to support pandas.read_excel
RUN pip install xlrd
RUN pip install google-cloud-storage
RUN pip install python-slugify
RUN pip install psutil==5.4.5
RUN pip install cython

############### copy code ###############
ARG MODULE_PATH
COPY $MODULE_PATH /workdir
COPY supervisely_lib /workdir/supervisely_lib

ENV PYTHONPATH /workdir:/workdir/src:/workdir/supervisely_lib/worker_proto:$PYTHONPATH
WORKDIR /workdir/src
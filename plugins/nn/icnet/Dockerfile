ARG REGISTRY
ARG TAG
#FROM ${REGISTRY}/base-pytorch-v04:${TAG}
FROM ${REGISTRY}/base-pytorch-v04:6.0.17

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

# TODO move to base.
RUN conda install -y -c pytorch \
        pytorch=0.4.1 \
        torchvision=0.2.1 \
        cuda90=1.0 \
    && conda clean --all --yes

############### copy code ###############
ARG MODULE_PATH
COPY $MODULE_PATH /workdir
COPY supervisely_lib /workdir/supervisely_lib

ENV PYTHONPATH /workdir:/workdir/src:/workdir/supervisely_lib/worker_proto:$PYTHONPATH
WORKDIR /workdir/src

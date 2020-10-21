ARG REGISTRY
ARG TAG
FROM ${REGISTRY}/base-py:${TAG}
##############################################################################
# Additional project libraries
##############################################################################

RUN apt-get update
#RUN apt-get install libpcl-dev -y
#RUN pip install python-pcl
RUN conda install -c conda-forge scikit-image
RUN python -m pip install open3d==0.11.0

############### copy code ###############
ARG MODULE_PATH
COPY $MODULE_PATH /workdir
COPY supervisely_lib /workdir/supervisely_lib

ENV PYTHONPATH /workdir:/workdir/src:/workdir/supervisely_lib/worker_proto:$PYTHONPATH
WORKDIR /workdir/src
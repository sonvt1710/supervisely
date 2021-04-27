ARG REGISTRY
ARG TAG
FROM ${REGISTRY}/base-py:${TAG}

#RUN pip install -U git+https://github.com/pydicom/pydicom.git@c5852160e5942f51ba18d5522b15f656b00b54fc
#RUN conda install -c conda-forge gdcm=2.8.8

RUN pip install pydicom==2.1.2
RUN pip install gdcm==1.1
RUN pip install SimpleITK==2.0.2
RUN pip install pylibjpeg pylibjpeg-libjpeg
############### copy code ###############
ARG MODULE_PATH
COPY $MODULE_PATH /workdir
COPY supervisely_lib /workdir/supervisely_lib

ENV PYTHONPATH /workdir:/workdir/src:/workdir/supervisely_lib/worker_proto:$PYTHONPATH
WORKDIR /workdir/src
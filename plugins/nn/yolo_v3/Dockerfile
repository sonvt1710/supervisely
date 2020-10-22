ARG REGISTRY
ARG TAG
FROM ${REGISTRY}/base-py:${TAG}

##############################################################################
# devel components
##############################################################################
#ENV NCCL_VERSION 2.7.8
# TODO: https://gitlab.com/nvidia/container-images/cuda/-/commit/8df3d50221d673066e95d57decc683670457dd28
RUN apt-get update
RUN apt-get update && apt-get install -y --no-install-recommends \
        cuda-libraries-dev-$CUDA_PKG_VERSION \
        cuda-nvml-dev-$CUDA_PKG_VERSION \
        cuda-minimal-build-$CUDA_PKG_VERSION \
        cuda-command-line-tools-$CUDA_PKG_VERSION \
        cuda-core-9-0=9.0.176.3-1 \
        cuda-cublas-dev-9-0=9.0.176.4-1 && \
    rm -rf /var/lib/apt/lists/*
#libnccl-dev=$NCCL_VERSION-1+cuda9.0 && \

ENV LIBRARY_PATH /usr/local/cuda/lib64/stubs
ENV CUDNN_VERSION 7.4.2.24

RUN apt-get update && apt-get install -y --no-install-recommends --allow-change-held-packages --allow-downgrades \
            libcudnn7=$CUDNN_VERSION-1+cuda9.0 \
            libcudnn7-dev=$CUDNN_VERSION-1+cuda9.0

ENV LD_LIBRARY_PATH=/usr/local/cuda/lib64:$LD_LIBRARY_PATH

RUN apt-get update && apt-get install -y libopencv-dev=2.4.9.1+dfsg-1.5ubuntu1.1

RUN pip install --no-cache-dir \
        pyclipper \
        cython

# OpenCV with version 3.4.1 (in base) has bug for C headers.
#RUN conda install --no-update-deps -y opencv=3.4.1
conda install --no-update-deps -y -c conda-forge/label/gcc7 opencv
#RUN conda install -y -c conda-forge opencv

############### copy code ###############
ARG MODULE_PATH
COPY $MODULE_PATH /workdir
COPY supervisely_lib /workdir/supervisely_lib

RUN cd /workdir/src/darknet && make

ENV PYTHONPATH /workdir:/workdir/src:/workdir/supervisely_lib/worker_proto:$PYTHONPATH
WORKDIR /workdir/src

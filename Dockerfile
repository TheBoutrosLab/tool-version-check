ARG MINIFORGE_VERSION=26.1.1-2
ARG UBUNTU_VERSION=24.04
ARG CONDA_ENV_PATH=/opt/conda/envs/versioncheck

FROM condaforge/miniforge3:${MINIFORGE_VERSION} AS builder

ARG CONDA_ENV_PATH
ARG VERSIONCHECK_VERSION=0+unknown

WORKDIR /tmp/versioncheck

COPY pyproject.toml README.md LICENSE ./
COPY versioncheck ./versioncheck

RUN mamba create -qy -p ${CONDA_ENV_PATH} \
    -c conda-forge \
    python \
    pip \
    hatchling \
    hatch-vcs \
    packaging \
    pyyaml \
    requests && \
    SETUPTOOLS_SCM_PRETEND_VERSION="${VERSIONCHECK_VERSION#v}" \
        ${CONDA_ENV_PATH}/bin/pip install --no-build-isolation --no-deps . && \
    mamba clean -afy && \
    rm -rf /tmp/versioncheck

# Deploy versioncheck into a smaller base image.
FROM ubuntu:${UBUNTU_VERSION} AS final

ARG CONDA_ENV_PATH

COPY --from=builder ${CONDA_ENV_PATH} ${CONDA_ENV_PATH}

ENV CONDA_ENV_PATH="${CONDA_ENV_PATH}" \
    HOME="/home/bldocker" \
    PATH="${CONDA_ENV_PATH}/bin:${PATH}"

# Add a non-root user/group called bldocker.
RUN groupadd -g 500001 bldocker && \
    useradd -m -d /home/bldocker -r -u 500001 -g bldocker bldocker

# Change the default user to bldocker from root.
USER bldocker

LABEL   maintainer="Yash Patel <ypatel@sbpdiscovery.org>" \
        org.opencontainers.image.source=https://github.com/TheBoutrosLab/tool-version-check

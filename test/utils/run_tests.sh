#!/bin/sh

if [ "${SHIPPABLE}" = "true" ]; then
    echo "It appears this job is running on Shippable instead of Travis."
    if [ "${IS_PULL_REQUEST}" = "true" ]; then
        echo "Please rebase the branch used for this pull request."
    else
        echo "This branch needs to be updated to work with Shippable."
    fi
    exit 1
fi

set -e
set -u
set -x

LINKS="--link=httptester:ansible.http.tests --link=httptester:sni1.ansible.http.tests --link=httptester:sni2.ansible.http.tests --link=httptester:fail.ansible.http.tests"
TOXENV=${TOXENV:-}
TARGET_OPTIONS="${TARGET_OPTIONS:-}"
TEST_FLAGS=${TEST_FLAGS:-}
MAKE_TARGET=${MAKE_TARGET:-}
TESTS_KEEP_CONTAINER=${TESTS_KEEP_CONTAINER:-}
TARGET=${TARGET:-centos7}
ANSIBLE_SRC_DIR=${ANSIBLE_SRC_DIR:-}

DEFAULT_IMAGE_PREFIX="ansible/ansible"
DOCKER_IMAGE_PREFIX="${DOCKER_IMAGE_PREFIX:-${DEFAULT_IMAGE_PREFIX}}"

DEFAULT_IMAGE_NAME="${DOCKER_IMAGE_PREFIX}:${TARGET}"
DOCKER_IMAGE="${DOCKER_IMAGE:-${DEFAULT_IMAGE_NAME}}"

DOCKER_RUN_ENV=${DOCKER_RUN_ENV:-"HTTPTESTER=1"}

echo "$DEFAULT_IMAGE_PREFIX $DOCKER_IMAGE_PREFIX $DEFAULT_IMAGE_NAME $DOCKER_IMAGE"

echo "DOCKER_IMAGE=${DOCKER_IMAGE}"
echo "TARGET_OPTIONS=${TARGET_OPTIONS}"
echo "TARGET=${TARGET}"
echo "MAKE_TARGET=${MAKE_TARGET}"
echo "TESTS_KEEP_CONTAINER=${TESTS_KEEP_CONTAINER}"
echo "LINKS=${LINKS}"
echo "PWD=${PWD}"

# any particular reason the container name is random?
container_name () {
    # $RANDOM is a bashism, so this will break on DEC ULTRIX once someone ports docker to it.
    RANDOM_CONTAINER_NAME="testAbull_$$_${RANDOM}_${2}"
    CONTAINER_NAME="${CONTAINER_NAME:-${RANDOM_CONTAINER_NAME}}"
}

guess_root_of_ansible_src_dir () {
    if [ -z "${ANSIBLE_SRC_DIR}" ] ; then
    # TODO: check various 'git root' tools
    #   cd up until we find a .git/config with line ~= "url=git@github.com:/ansible/ansible.git" ?
        # previous behavior assumed running for root of checkout
        ANSIBLE_SRC_DIR="${PWD}"
    fi
}
if [ "${TARGET}" = "sanity" ]; then
    ./test/code-smell/replace-urlopen.sh .
    ./test/code-smell/use-compat-six.sh lib
    ./test/code-smell/boilerplate.sh
    ./test/code-smell/required-and-default-attributes.sh

    if [ "${TOXENV}" != 'py24' ] ; then
        tox;
    fi

    if [ "${TOXENV}" = 'py24' ] ; then
        python2.4 -V && python2.4 -m compileall -fq -x 'module_utils/(a10|rax|openstack|ec2|gce|docker_common|azure_rm_common|vca|vmware).py' lib/ansible/module_utils ;
    fi
else
    if [ ! -e /tmp/cid_httptester ]; then
        docker pull ansible/ansible:httptester
        docker run -d --name=httptester ansible/ansible:httptester > /tmp/cid_httptester
    fi

    container_name "${TARGET}" "${TOXENV}"
    export CONTAINER_NAME

    echo docker pull "${DOCKER_IMAGE}"
    docker pull "${DOCKER_IMAGE}"

    echo "CONTAINER_NAME=${CONTAINER_NAME}"

    # enable colors if output is going to a terminal
    COLOR_SETTINGS=""
    if [ -t 1 ]; then
	COLOR_SETTINGS="--env TERM=$TERM"
    fi
    
    guess_root_of_ansible_src_dir

    CONTAINER_ID=$(docker run -d --volume=${ANSIBLE_SRC_DIR}:/root/ansible:Z ${LINKS} --name ${CONTAINER_NAME} --env "${DOCKER_RUN_ENV}" ${TARGET_OPTIONS} ansible/ansible:${TARGET})
    echo "${CONTAINER_ID}"

    SHELL_COMMAND="(cd /root/ansible && pwd && . hacking/env-setup && cd test/integration && LC_ALL=en_US.utf-8 TEST_FLAGS=\"${TEST_FLAGS}\" make ${MAKE_TARGET})"
    docker exec -ti "${CONTAINER_ID}" /bin/sh -c "${SHELL_COMMAND}"

    docker kill "${CONTAINER_ID}"

    if [ -z "${TESTS_KEEP_CONTAINER}" ]; then
        docker rm -vf "${CONTAINER_NAME}"
    fi
fi

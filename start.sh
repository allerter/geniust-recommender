#! /usr/bin/env sh
# from https://github.com/tiangolo/uvicorn-gunicorn-docker
set -e

if [ -f /gtr/main.py ]; then
    DEFAULT_MODULE_NAME=gtr.main
elif [ -f /main.py ]; then
    DEFAULT_MODULE_NAME=main
fi
MODULE_NAME=${MODULE_NAME:-$DEFAULT_MODULE_NAME}
VARIABLE_NAME=${VARIABLE_NAME:-gtr}
export APP_MODULE=${APP_MODULE:-"$MODULE_NAME:$VARIABLE_NAME"}

if [ -f /gtr/gunicorn_conf.py ]; then
    DEFAULT_GUNICORN_CONF=/gtr/gunicorn_conf.py
else
    DEFAULT_GUNICORN_CONF=gunicorn_conf.py
fi
export GUNICORN_CONF=${GUNICORN_CONF:-$DEFAULT_GUNICORN_CONF}
export WORKER_CLASS=${WORKER_CLASS:-"uvicorn.workers.UvicornWorker"}

# If there's a prestart.sh script in the /gtr directory or other path specified, run it before starting
PRE_START_PATH=${PRE_START_PATH:-/gtr/prestart.sh}
echo "Checking for script in $PRE_START_PATH"
if [ -f $PRE_START_PATH ] ; then
    echo "Running script $PRE_START_PATH"
    . "$PRE_START_PATH"
else 
    echo "There is no script $PRE_START_PATH"
fi

# Start Gunicorn
exec gunicorn -k "$WORKER_CLASS" -c "$GUNICORN_CONF" "$APP_MODULE"

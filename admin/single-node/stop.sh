#! /bin/sh

set +e
set -u

if [ -f "logs/server.pid" ]; then
    SERVER_PID=`cat logs/server.pid`
    echo "ydbd stop: Stopping process ${SERVER_PID}..."
    kill -TERM ${SERVER_PID}
    while true; do
        if kill -0 "$SERVER_PID" >/dev/null 2>&1; then
            break;
        else
            sleep 1
        fi
    done
    rm -fv logs/server.pid
else
    echo "ydbd stop: Server pid file does not exist."
fi

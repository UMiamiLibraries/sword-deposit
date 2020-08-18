#! /usr/bin/env sh
set -e

start_sshd(){
  echo "starting sshd"
  /usr/sbin/sshd -D
}

start_server(){
  echo "running uwsgi-nginx-entrypoint.sh"
  /uwsgi-nginx-entrypoint.sh

# Explicitly add installed Python packages and uWSGI Python packages to PYTHONPATH
# Otherwise uWSGI can't import Flask
export PYTHONPATH=$PYTHONPATH:/usr/local/lib/python3.6/site-packages:/usr/lib/python3.6/site-packages

# Get the URL for static files from the environment variable
USE_STATIC_URL=${STATIC_URL:-'/static'}
# Get the absolute path of the static files from the environment variable
USE_STATIC_PATH=${STATIC_PATH:-'/app/static'}
# Get the listen port for Nginx, default to 80
USE_LISTEN_PORT=${LISTEN_PORT:-80}

# copy over the custom nginx.conf that contains ssl certs
cp /etc/nginx/conf.d/nginx.conf.dist /etc/nginx/conf.d/nginx.conf

echo "running supervisord"
supervisord
}

start_server &
start_sshd
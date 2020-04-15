#!/usr/bin/env python
"""Set Up Django with Postgres, Nginx, and Gunicorn on Debian 10."""
import pwd
import os
import subprocess

_PROJECT_PATH = os.path.dirname(os.path.abspath(__file__))
_PW_NAME = pwd.getpwuid(os.getuid()).pw_name

print(_PROJECT_PATH)

class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    ERROR = '\033[91m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    END = '\033[0m'


def repeat_run_command_until_success(command: str):
    if os.system(command) != 0:
        repeat_run_command_until_success(command)


def run_commands(commands):
    for command in commands:
        print(bcolors.OKBLUE, 'Running command:', command, bcolors.END)
        if os.system(command) != 0:
            print(bcolors.ERROR, 'Error executing command:', command, bcolors.END)
            break


def create_file(
        content: str,
        file_path: str
):
    f = open(file_path, "w")
    f.write(content)
    f.close()
    print(bcolors.OKGREEN, file_path, '- successfully created.', bcolors.END)


def set_new_passwd():
    ok = input(bcolors.OKBLUE + 'Do you want to set a new password for the user who is currently logged in? [y/n]: ' + bcolors.END)
    if ok == 'y':
        repeat_run_command_until_success('sudo passwd')


def create_database(name: str, username: str, password: str):
    process = subprocess.Popen(
        ["sudo", "-u", "postgres", "psql"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        bufsize=0,
        universal_newlines=True,
    )
    process.stdin.write("CREATE DATABASE " + name + ";")
    process.stdin.write("CREATE USER " + username + " WITH PASSWORD '" + password + "';")
    process.stdin.write("ALTER ROLE " + username + " SET client_encoding TO 'utf8';")
    process.stdin.write("ALTER ROLE " + username + " SET default_transaction_isolation TO 'read committed';")
    process.stdin.write("ALTER ROLE " + username + " SET timezone TO 'UTC';")
    process.stdin.write("GRANT ALL PRIVILEGES ON DATABASE " + name + " TO " + username + ";")
    process.stdin.write("\q")
    out, err = process.communicate()
    print(bcolors.OKGREEN, out, bcolors.END)
    print(bcolors.ERROR, err, bcolors.END)


print(bcolors.HEADER, '''
####################################################################################################
## Step 1 - Initial Server Setup with Debian 10 ####################################################
####################################################################################################
''', bcolors.END)

set_new_passwd()

run_commands([
    'sudo apt update',
    'sudo apt install ufw',
    'sudo ufw app list',
    'sudo ufw allow OpenSSH',
    'sudo ufw enable',
    'sudo ufw status',
])


print(bcolors.HEADER, '''
####################################################################################################
## Step 2 - Installing the Packages from the Debian 10 Repositories ################################
####################################################################################################
''', bcolors.END)

run_commands([
    'sudo apt update',
    'sudo apt install python3-pip python3-dev libpq-dev postgresql postgresql-contrib nginx curl',
])


print(bcolors.HEADER, '''
####################################################################################################
## Step 3 - Creating the PostgreSQL Database and User. #############################################
####################################################################################################
''', bcolors.END)

_DATABASE_NAME = input('Database Name: ')
_DATABASE_USERNAME = input('Database username: ')
_DATABASE_PASSWORD = input('Database password: ')

create_database(
    name=_DATABASE_NAME,
    username=_DATABASE_USERNAME,
    password=_DATABASE_PASSWORD
)


print(bcolors.HEADER, '''
####################################################################################################
## Step 4 - Creating a Python Virtual Environment for your Project #################################
####################################################################################################
''', bcolors.END)

run_commands([
    'sudo -H pip3 install --upgrade pip',
    'sudo -H pip3 install virtualenv',
    'virtualenv venv'
])


print(bcolors.HEADER, '''
####################################################################################################
<<<<<<< HEAD
## Step 5 - Creating Production Settings for a Django Project ######################################
####################################################################################################
''', bcolors.END)

_DOMAIN = input('Domain without protocol (for example.com): ')

create_file(content="""\
from .base import *

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = ['""" + _DOMAIN + """']

# Database
# https://docs.djangoproject.com/en/3.0/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql_psycopg2',
        'HOST': 'localhost',
        'NAME': '""" + _DATABASE_NAME + """',
        'PASSWORD': '""" + _DATABASE_PASSWORD + """',
        'PORT': '',
        'USER': '""" + _DATABASE_USERNAME + """'
    }
}
""", file_path=os.path.join(_PROJECT_PATH, 'core/settings/prod.py'))


print(bcolors.HEADER, '''
####################################################################################################
## Step 6 - Applying basic migrations and creating superuser #######################################
####################################################################################################
''', bcolors.END)

this_file = os.path.join(_PROJECT_PATH, 'venv/bin/activate_this.py')

exec(open(this_file).read(), {'__file__': this_file})

run_commands([
    'pip install -r requirements.txt',
    'pip install gunicorn psycopg2-binary',
    'python manage.py makemigrations',
    'python manage.py migrate',
    'python manage.py createsuperuser',
    'python manage.py collectstatic',
])


print(bcolors.HEADER, '''
####################################################################################################
## Step 7 - Creating Systemd Socket and Service Files for Gunicorn #################################
####################################################################################################
''', bcolors.END)

run_commands([
    'mkdir ' + os.path.join(_PROJECT_PATH, 'tmp')
])

create_file(content="""\
[Unit]
Description=gunicorn socket

[Socket]
ListenStream=/run/gunicorn.sock

[Install]
WantedBy=sockets.target
""", file_path=os.path.join(_PROJECT_PATH, 'tmp/gunicorn.socket'))

create_file(content="""\
[Unit]
Description=gunicorn daemon
Requires=gunicorn.socket
After=network.target

[Service]
User=""" + _PW_NAME + """
Group=www-data
WorkingDirectory=""" + _PROJECT_PATH + """
ExecStart=""" + _PROJECT_PATH + """/venv/bin/gunicorn \\
          --access-logfile - \\
          --workers 3 \\
          --bind unix:/run/gunicorn.sock \\
          core.wsgi:application

[Install]
WantedBy=multi-user.target
""", file_path=os.path.join(_PROJECT_PATH, 'tmp/gunicorn.service'))

run_commands([
    'sudo cp ' + os.path.join(_PROJECT_PATH, 'tmp/gunicorn.socket') + ' /etc/systemd/system/gunicorn.socket',
    'sudo cp ' + os.path.join(_PROJECT_PATH, 'tmp/gunicorn.service') + ' /etc/systemd/system/gunicorn.service',
    'sudo systemctl start gunicorn.socket',
    'sudo systemctl enable gunicorn.socket',
    'sudo systemctl status gunicorn.socket',
    'file /run/gunicorn.sock',
    'sudo journalctl -u gunicorn.socket'
])


print(bcolors.HEADER, '''
####################################################################################################
## Step 8 - Configure Nginx to Proxy Pass to Gunicorn ##############################################
####################################################################################################
''', bcolors.END)

create_file(content="""\
server {
    listen 80;
    server_name """ + _DOMAIN + """;

    location = /favicon.ico { access_log off; log_not_found off; }

    location /static/ {
        root """ + _PROJECT_PATH + """;
    }

    location /media/ {
        root """ + _PROJECT_PATH + """;
    }

    location / {
        include proxy_params;
        proxy_pass http://unix:/run/gunicorn.sock;
    }
}
""", file_path=os.path.join(_PROJECT_PATH, 'tmp/site.conf'))


run_commands([
    'sudo cp ' + os.path.join(_PROJECT_PATH, 'tmp/site.conf') + ' /etc/nginx/sites-available/' + _DOMAIN,
    'sudo ln -s /etc/nginx/sites-available/' + _DOMAIN + ' /etc/nginx/sites-enabled',
    'sudo nginx -t',
    'sudo systemctl restart nginx',
])


print(bcolors.HEADER, '''
####################################################################################################
## Step 9 - Create the SSL Certificate with Let's Encrypt ##########################################
####################################################################################################
''', bcolors.END)

run_commands([
    'sudo apt install python3-certbot-nginx',
    'sudo apt install python3-acme',
    'sudo apt install python3-certbot',
    'sudo apt install python3-mock',
    'sudo apt install python3-openssl',
    'sudo apt install python3-pkg-resources',
    'sudo apt install python3-pyparsing',
    'sudo apt install python3-zope.interface',
    "sudo ufw allow 'Nginx Full'",
    'sudo certbot --nginx -d ' + _DOMAIN,
    'sudo certbot renew --dry-run',
])


print(bcolors.OKGREEN, '''
####################################################################################################
# FINISH ## FINISH ## FINISH ## FINISH ## FINISH ## FINISH ## FINISH ## FINISH ## FINISH ## FINISH #
####################################################################################################
# Enjoy your site at https://''' + _DOMAIN + '''
####################################################################################################
# FINISH ## FINISH ## FINISH ## FINISH ## FINISH ## FINISH ## FINISH ## FINISH ## FINISH ## FINISH #
####################################################################################################
''', bcolors.END)

#!/bin/bash

#yell() { echo "$0: $*" >&2; }
#die() { yell "$*"; exit 111; }
#try() { "$@" || die "cannot $*"; }

set -e

if [ $# -gt 0 ]; then 
    dbname=$1
else
    dbname="yaya_orl"    
fi
TIME_ZONE="America/New_York" 
apt-get update && apt-get upgrade
echo "$TIME_ZONE" > /etc/timezone

apt-get install -y sudo

echo "debconf debconf/frontend select noninteractive" | sudo debconf-set-selections

packages=("apt-utils" "cryptsetup" "postgresql" "postgresql-contrib")
for p in "${packages[@]}"; do
    echo "Checking for '$p' on system..."
    if dpkg -l | grep -q " ${p} "; then
        echo "'$p' was found on system"
    else
        echo "'$p' was NOT found on system. Attempting to install it..."
        { # Bash 'Try'
            apt-get install -y $p && echo "Successful!" 
        } || { # Bash 'Catch'
            echo "Could not install $p! Quitting!!!"
            exit -1
        }
    fi
done

echo -n "Enter postgreSQL username: "
read username
password=$(/lib/cryptsetup/askpass "Enter postgreSQL password:")

# Start postgres server
/etc/init.d/postgresql start

sudo -u postgres psql postgres << EOF
    CREATE DATABASE $dbname;
    CREATE USER $username WITH PASSWORD '$password';
    ALTER ROLE $username SET client_encoding TO 'utf8';
    ALTER ROLE $username SET default_transaction_isolation TO 'read committed';
    ALTER ROLE $username SET timezone to 'UTC';
    GRANT ALL PRIVILEGES ON DATABASE $dbname TO $username;
    ALTER USER $username CREATEDB;
    \q 
EOF


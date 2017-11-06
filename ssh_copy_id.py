#!/usr/bin/env python
# coding:utf-8

import argparse
import getpass
import json
import logging
import os
import paramiko

logger = logging.getLogger(__file__)
logger.setLevel(logging.INFO)

ch = logging.StreamHandler()
ch.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))

logger.addHandler(ch)

RSA_PUBKEY = '~/.ssh/id_rsa.pub'
DSA_PUBKEY = '~/.ssh/id_dsa.pub'

def get_pubkey():
    for f in map(lambda f: os.path.expanduser(f), [RSA_PUBKEY, DSA_PUBKEY]):
        if os.path.isfile(f):
            return f
    return None


def copy_pubkey(hostname, username, passwd, port, timeout=8):
    pubkey = get_pubkey()
    if not pubkey:
        print "Make sure ~/.ssh/(id_rsa|id_dsa).pub exists"
        sys.exit(1)
    with open(pubkey) as f:
        buf = f.read()    

    cmd = """
    mkdir -p $HOME/.ssh/ && echo "%s" >> $HOME/.ssh/authorized_keys && chmod 600 $HOME/.ssh/authorized_keys && chmod 700 $HOME/.ssh
    """ % buf
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(hostname=hostname, port=port, username=username, password=passwd, timeout=timeout)
        stdin, stdout, stderr = client.exec_command(cmd)
        logger.info('Stdin', stdin)
        logger.info('Stdout', stdout)
        logger.info('Stderr', stderr)
    except Exception as e:
        logger.warning('Hostname %s: %s'%(hostname, e))
        return False
    return True
        

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--hostlist", help="A hostlist file")
    args = parser.parse_args()
    current_user = getpass.getuser()

    fn = args.hostlist if args.hostlist else "hosts"
    perm = 'r+' if os.path.isfile(fn) else 'a+'
    data = dict()
    with open(fn, perm) as f:
        try:
            data = json.load(f)
            if len(data) > 0:
                for hostname, kw in data.items():
                    if kw.get('done'):
                        logger.info('Skip %s..', hostname)
                        continue
                    port = kw.get('port', '22')
                    username = kw.get('username', current_user)
                    passwd = kw.get('passwd', os.getenv('COMMON_PASSWD'))
                    if copy_pubkey(hostname, username, passwd, int(port)):
                        data[hostname]['done'] = True
        except ValueError:
            data['precise_hostname'] = {'port': 22, 'user': '', 'passwd': ''}
            print """
\033[91mInitialize hostlist file **hosts**, edit file before rerun command\033[0m"""
        f.seek(0)
        json.dump(data, f, indent=4)
        f.truncate()
            

if __name__ == '__main__':
    main()

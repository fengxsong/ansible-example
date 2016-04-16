#!/usr/bin/env python
# -*- coding:utf-8 -*-

from collections import namedtuple
from ansible.parsing.dataloader import DataLoader
from ansible.vars import VariableManager
from ansible.inventory import Inventory
from ansible.playbook.play import Play
from ansible.executor.task_queue_manager import TaskQueueManager

OPTS = namedtuple('OPTS', ['listtags', 'listtasks', 'listhosts', 'syntax', 'connection', 'module_path', 'forks', 'remote_user', 'private_key_file',
                           'ssh_common_args', 'ssh_extra_args', 'sftp_extra_args', 'scp_extra_args', 'become', 'become_method', 'become_user', 'verbosity', 'check'])


class MyRunner:

    def __init__(self, task_name, hosts, module_name, module_args='', gather_facts='no', task_list=None, **kwargs):
        self.task_name = task_name
        self.hosts = hosts
        self.module_name = module_name
        self.module_args = module_args
        self.gather_facts = gather_facts
        self.task_list = task_list
        self.playbook = kwargs.get('playbook', None)
        self.inventory_file = kwargs.get(
            'inventory_file', '/etc/ansible/hosts')
        self._listtags = kwargs.get('listtags', False)
        self._listtasks = kwargs.get('listtasks', False)
        self._listhosts = kwargs.get('listhosts', False)
        self._syntax = kwargs.get('syntax', False)
        self._connection = kwargs.get('connection', 'ssh')
        self._module_path = kwargs.get('module_path', None)
        self._forks = kwargs.get('forks', 100)
        self._remote_user = kwargs.get('remote_user', 'root')
        self._private_key_file = kwargs.get('private_key_file', None)
        self._ssh_common_args = kwargs.get('ssh_common_args', None)
        self._ssh_extra_args = kwargs.get('ssh_extra_args', None)
        self._sftp_extra_args = kwargs.get('sftp_extra_args', None)
        self._scp_extra_args = kwargs.get('scp_extra_args', None)
        self._become = kwargs.get('become', True)
        self._become_method = kwargs.get('become_method', None)
        self._become_user = kwargs.get('become_user', 'root')
        self._verbosity = kwargs.get('verbosity', None)
        self._check = kwargs.get('check', False)
        self._variable_manager = self.init_variable_manager()
        self._loader = self.init_loader()
        self._passwords = self.init_passwords()
        self._inventory = self.init_inventory()

    def get_opts(self):
        return OPTS(
            listtags=self._listtags,
            listtasks=self._listtasks,
            listhosts=self._listhosts,
            syntax=self._syntax,
            connection=self._connection,
            module_path=self._module_path,
            forks=self._forks,
            remote_user=self._remote_user,
            private_key_file=self._private_key_file,
            ssh_common_args=self._ssh_common_args,
            ssh_extra_args=self._ssh_extra_args,
            sftp_extra_args=self._sftp_extra_args,
            scp_extra_args=self._scp_extra_args,
            become=self._become,
            become_method=self._become_method,
            become_user=self._become_user,
            verbosity=self._verbosity,
            check=self._check
        )

    def init_variable_manager(self):
        return VariableManager()

    def init_loader(self):
        return DataLoader()

    def init_passwords(self):
        return dict(vault_pass='secret')

    def init_inventory(self):
        return Inventory(loader=self.init_loader(), variable_manager=self.init_variable_manager(), host_list=self.inventory_file)

    def get_play_source(self):
        if not self.playbook:
            return dict(
                name=self.task_name,
                hosts=self.hosts,
                gather_facts=self.gather_facts,
                tasks=self.get_task_list()
            )
        return self.playbook

    def get_task_list(self):
        if not self.task_list:
            # if self.module_name in ['command', 'raw', 'script', 'shell']:
            #     pass
            return [
                dict(action=dict(module=self.module_name,
                                 args=self.module_args), register='stdout'),
                dict(action=dict(module='debug',
                                 args=dict(msg='{{stdout}}')))
            ]
        return self.task_list

    def run(self):
        self._variable_manager.set_inventory(self._inventory)
        play = Play().load(self.get_play_source(),
                           variable_manager=self._variable_manager, loader=self._loader)
        tqm = None
        try:
            tqm = TaskQueueManager(
                inventory=self._inventory,
                variable_manager=self._variable_manager,
                loader=self._loader,
                options=self.get_opts(),
                passwords=self._passwords,
                stdout_callback='default',
            )
            result = tqm.run(play)
        finally:
            if tqm is not None:
                tqm.cleanup()

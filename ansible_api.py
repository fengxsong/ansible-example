#!/usr/bin/env python
# -*- coding:utf-8 -*-

from collections import namedtuple, OrderedDict
from ansible.parsing.dataloader import DataLoader
from ansible.vars import VariableManager
from ansible.inventory import Inventory
from ansible.playbook.play import Play
from ansible.executor.task_queue_manager import TaskQueueManager
from ansible.plugins.callback import CallbackBase
import ansible.constants as C
from tempfile import NamedTemporaryFile
import jinja2

Options = namedtuple('Options', ['listtags', 'listtasks', 'listhosts', 'syntax', 'connection', 'module_path', 'forks',
                                 'remote_user', 'private_key_file', 'ssh_common_args', 'ssh_extra_args',
                                 'sftp_extra_args', 'scp_extra_args', 'become', 'become_method', 'become_user',
                                 'verbosity', 'check'])


class HostPatternError(BaseException):
    pass


class ResultsCollector(CallbackBase):

    def __init__(self, *args, **kwargs):
        super(ResultsCollector, self).__init__(*args, **kwargs)
        self.host_ok = {}
        self.host_unreachable = {}
        self.host_failed = {}
        self.result = OrderedDict()

    def v2_runner_on_unreachable(self, result):
        ip = result._host.get_name()
        task_name = result._task.name

        self.host_unreachable.setdefault(task_name, {})
        self.host_unreachable[task_name][ip] = result

        self.result.setdefault(task_name, {}.setdefault(ip, {}))
        self.result[task_name][ip] = {'status': 'unreachable', 'result': result._result}

    def v2_runner_on_ok(self, result,  *args, **kwargs):
        ip = result._host.get_name()
        task_name = result._task.name

        self.host_ok.setdefault(task_name, {})
        self.host_ok[task_name][ip] = result

        self.result.setdefault(task_name, {}.setdefault(ip, {}))
        self.result[task_name][ip] = {'status': 'ok', 'result': result._result}

    def v2_runner_on_failed(self, result,  *args, **kwargs):
        ip = result._host.get_name()
        task_name = result._task.name

        self.host_failed.setdefault(task_name, {})
        self.host_failed[task_name][ip] = result

        self.result.setdefault(task_name, {}.setdefault(ip, {}))
        self.result[task_name][ip] = {'status': 'failed', 'result': result._result}


class AnsibleRunner(object):

    class Task(dict):
        def __init__(self, name, module_name, module_args=None, register=''):
            super(self.__class__, self).__init__(
                name=name,
                action=dict(
                    module=module_name,
                    args=module_args if module_args else ''
                )
            )
            if register:
                self['register'] = register

    class Playbook(dict):
        def __init__(self, name="Ansible Playbook", pattern='all', task_list=None, gather_facts='no'):
            super(self.__class__, self).__init__(name=name, hosts=pattern, tasks=task_list, gather_facts=gather_facts)

    def __init__(self, task_name='Ansible Playbook', task_list=None, playbook=None, host_list=None, pattern='all', **kwargs):
        if not task_list and not playbook:
            raise RuntimeError('You should instance `task_list` or `playbook`')
        self.task_name = task_name
        self.patterns = pattern
        self.task_list = task_list
        if isinstance(self.task_list, list):
            len(set([_task['name'] for _task in task_list])) == len(task_list)

        self.playbook = playbook
        self.gather_facts = kwargs.get('gather_facts', 'no')
        self.host_list = host_list
        if host_list:
            self.inventory_file = self.gen_inventory(host_list)
        else:
            self.inventory_file = kwargs.get(
                'inventory_file', '/etc/ansible/hosts')
        self.options = Options(
            listtags=kwargs.get('listtags', False),
            listtasks=kwargs.get('listtasks', False),
            listhosts=kwargs.get('listhosts', False),
            syntax=kwargs.get('syntax', False),
            connection=kwargs.get('connection', 'ssh'),
            module_path=kwargs.get('module_path', None),
            forks=kwargs.get('forks', 100),
            remote_user=kwargs.get('remote_user', 'root'),
            private_key_file=kwargs.get('private_key_file', None),
            ssh_common_args=kwargs.get('ssh_common_args', None),
            ssh_extra_args=kwargs.get('ssh_extra_args', None),
            sftp_extra_args=kwargs.get('sftp_extra_args', None),
            scp_extra_args=kwargs.get('scp_extra_args', None),
            become=kwargs.get('become', False),
            become_method=kwargs.get('become_method', C.DEFAULT_BECOME_METHOD),
            become_user=kwargs.get('become_user', 'root'),
            verbosity=kwargs.get('verbosity', None),
            check=kwargs.get('check', False)
        )

        self.variable_manager = self.initialize_variable_manager()
        self.loader = self.initialize_loader()
        self.passwords = self.initialize_passwords()
        self.inventory = self.initialize_inventory()
        for pattern in self.patterns.split(','):
            if len(self.inventory.get_hosts(pattern)) == 0:
                raise HostPatternError(
                    'ERROR! Specified hosts \033[91m{}\033[0m options do not match any hosts'.format(pattern))

    def initialize_variable_manager(self):
        return VariableManager()

    def initialize_loader(self):
        return DataLoader()

    def initialize_passwords(self):
        return dict(vault_pass='secret')

    def initialize_inventory(self):
        return Inventory(
            loader=self.loader,
            variable_manager=self.variable_manager,
            host_list=self.inventory_file
        )

    def create_play_tasks(self):
        if not self.playbook:
            return dict(
                name=self.task_name,
                hosts=self.patterns,
                gather_facts=self.gather_facts,
                tasks=self.get_task_list()
            )
        return self.playbook

    def get_task_list(self):
        if isinstance(self.task_list, dict):
            return [self.task_list]
        return self.task_list

    def gen_inventory(self, data):
        """
        生成Ansible的inventory库文件
        :param data: 字典对象。格式：{'section1':['ip1', 'ip2',...], 'section2':[...]}
        :return:
        """
        if isinstance(data, dict):
            inventory = """
{% for i,val in data.items() %}
[{{i}}]{% for v in val %}
{{v}}{% endfor %}
{% endfor %}
"""
        elif isinstance(data, list):
            inventory = """\n[tmp]{% for i in data %}\n{{ i }}{% endfor %}\n"""
        else:
            raise Exception("Data format is Error!")

        inventory_template = jinja2.Template(inventory)
        rendered_inventory = inventory_template.render({
            'data': data
        })

        # Create a temporary file and write the template string to it
        hosts = NamedTemporaryFile(delete=False)
        hosts.write(rendered_inventory)
        hosts.close()
        print '-----------'
        print rendered_inventory
        print '==========='
        return hosts.name

    def run(self, callback=None):
        self.variable_manager.set_inventory(self.inventory)
        play = Play().load(self.create_play_tasks(),
                           variable_manager=self.variable_manager, loader=self.loader)
        tqm = None
        if not callback:
            callback = ResultsCollector()
        try:
            tqm = TaskQueueManager(
                inventory=self.inventory,
                variable_manager=self.variable_manager,
                loader=self.loader,
                options=self.options,
                passwords=self.passwords,
                stdout_callback=callback
            )
            result = tqm.run(play)
        finally:
            if tqm is not None:
                tqm.cleanup()
        return result, callback


def main():
    # 定义playbook任务列表
    task_list = [AnsibleRunner.Task('task1', 'shell', 'ls ~'),
                 AnsibleRunner.Task('task2', 'shell', 'ls /')]

    # 定义playbook对象
    p2 = AnsibleRunner.Playbook(name='Ansible Play', task_list=task_list)

    # 执行playbook
    runner = AnsibleRunner(playbook=p2)
    # 执行单个任务或多个任务
    # runner = AnsibleRunner(task_list=task_list[0])
    # runner = AnsibleRunner(task_list=task_list)
    code, result = runner.run()
    for task_name, t in result.result.items():
        print task_name
        for ip, r in t.items():
            print "\t", ip
            print '\t' * 2, r


if __name__ == '__main__':
    main()
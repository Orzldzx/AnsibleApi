# -*- coding: utf-8 -*-

# @Author: seven
# @Date:   2018-01-03T14:19:23+08:00
# @Filename: MyApi.py
# @Last modified by:   seven
# @Last modified time: 2018-01-05T16:47:26+08:00


import os
import sys
import json
import shutil
import ansible.constants as C
from collections import namedtuple
from ansible.parsing.dataloader import DataLoader
from ansible.vars.manager import VariableManager
from ansible.inventory.manager import InventoryManager
from ansible.playbook.play import Play
from ansible.executor.task_queue_manager import TaskQueueManager
from ansible.executor.playbook_executor import PlaybookExecutor
from ansible.plugins.callback import CallbackBase


class ResultsCollector(CallbackBase):
    """
    自定义状态回调输出内容
    具体方法参考: CallbackBase 类
    result 包含:
        '_check_key', '_host', '_result', '_task', '_task_fields',
        'is_changed', 'is_failed', 'is_skipped', 'is_unreachable', 'task_name'
    """

    def __init__(self, *args):
        super(ResultsCollector, self).__init__(display=None)
        self.status_ok = dict()
        self.status_fail = dict()
        self.status_unreachable = dict()
        self.status_playbook = ''
        self.status_no_hosts = False
        self.host_ok = dict()
        self.host_failed = dict()
        self.host_unreachable = dict()

    def v2_runner_on_ok(self, result):
        # 任务成功
        host = result._host.get_name()
        self.runner_on_ok(host, result._result)
        # self.status_ok = json.dumps({host: result._result},indent=4)
        #if not self.status_ok.get(result.task_name):
        #    self.status_ok[result.task_name] = list()
        #self.status_ok[result.task_name].append({host: result._result})
        if not self.host_ok.get(host):
            self.host_ok[host] = list()
        self.host_ok[host].append(result)

    def v2_runner_on_failed(self, result, ignore_errors=False):
        # 任务失败
        host = result._host.get_name()
        self.runner_on_failed(host, result._result, ignore_errors)
        # self.status_fail = json.dumps({host: result._result},indent=4)
        if not self.status_fail.get(result.task_name):
            self.status_fail[result.task_name] = list()
        self.status_fail[result.task_name].append({host: result._result})
        self.host_failed[host] = result

    def v2_runner_on_unreachable(self, result):
        # 主机无法访问
        host = result._host.get_name()
        self.runner_on_unreachable(host, result._result)
        # self.status_unreachable=json.dumps({host: result._result},indent=4)
        if not self.status_unreachable.get(result.task_name):
            self.status_unreachable[result.task_name] = list()
        self.status_unreachable[result.task_name].append({host: result._result})
        self.host_unreachable[host] = result

    def v2_playbook_on_no_hosts_matched(self):
        self.playbook_on_no_hosts_matched()
        self.status_no_hosts=True

    def v2_playbook_on_play_start(self, play):
        self.playbook_on_play_start(play.name)
        self.playbook_path=play.name


class MyApi(object):
    """
    通用对象并行执行模块.
    resource 格式:
    hostname    变量 ...      (/etc/ansible/hosts 文件格式)

    {
        "<groupname>": {
            "hosts": {
                "<hostname>": {
                    "ansible_ssh_host": "<ip addr>",
                    "ansible_ssh_user": "<user>",
                    "ansible_ssh_port": <port>,
                    "ansible_ssh_pass": "<passwd>"
                }
            }
        }
    }
    """

    def __init__(self, resource, *args, **kwargs):
        self.resource = resource
        self.inventory = None
        self.variable_manager = None
        self.loader = None
        self.options = None
        self.passwords = None
        self.callback = None
        self.__initializeData()
        self.results_raw = {}

        if not os.path.exists(self.resource):
            print('[INFO] The [%s] inventory does not exist' % resource)
            sys.exit()

    def __initializeData(self):
        """
        初始化 ansible 配置参数
        如需其他参数, 可自行添加
        """

        # 定义选项
        Options = namedtuple(
            'Options', [
                'connection',
                'module_path',
                'forks',
                'timeout',
                'remote_user',
                'ask_pass',
                'private_key_file',
                'ssh_common_args',
                'ssh_extra_args',
                'sftp_extra_args',
                'scp_extra_args',
                'become',
                'become_method',
                'become_user',
                'ask_value_pass',
                'verbosity',
                'check',
                'listhosts',
                'listtasks',
                'listtags',
                'diff',
                'syntax'
            ]
        )

        # 初始化需要的对象(参数)
        self.variable_manager = VariableManager()
        # 用来加载解析yaml文件或JSON内容, 并且支持vault的解密
        self.loader = DataLoader()
        # 定义选项
        self.options = Options(
            connection='smart',
            module_path='/usr/share/ansible',
            forks=100,
            timeout=10,
            remote_user='root',
            ask_pass=False,
            private_key_file=None,
            ssh_common_args=None,
            ssh_extra_args=None,
            sftp_extra_args=None,
            scp_extra_args=None,
            become=None,
            become_method=None,
            become_user='root',
            ask_value_pass=False,
            verbosity=None,
            check=False,
            listhosts=False,
            listtasks=False,
            listtags=False,
            diff=False,
            syntax=False
        )

        # 默认密码, 主机未定义密码的时候才生效
        self.passwords = dict(sshpass=None, becomepass=None)
        # 加载 host 列表
        self.inventory = InventoryManager(
            loader=self.loader, sources=[self.resource])
        # 初始化变量, 包括主机、组、扩展等变量
        self.variable_manager = VariableManager(
            loader=self.loader, inventory=self.inventory)

    def run(self, host_list, module_name, module_args=None):
        """
        从 andible ad-hoc 运行模块.
        module_name: ansible 模块名称 (-m)
        module_args: ansible 模块参数 (-a)
        """

        # 创建任务
        play_source = dict(
            name="Ansible Play",
            hosts=host_list,
            gather_facts='no',
            tasks=[
                dict(
                    action=dict(
                        module=module_name,
                        args=module_args
                    )
                ),
                # dict(action=dict(module='shell', args="id"), register='shell_out'),
                # dict(action=dict(module='debug', args=dict(msg='{{shell_out.stdout}}')), async=0, poll=15)
            ]
        )
        play = Play().load(play_source, variable_manager=self.variable_manager, loader=self.loader)

        # 实际运行
        # TaskQueueManager 是创建进程池, 负责输出结果和多进程间数据结构或者队列的共享协作
        tqm = None
        # 结果回调类实例化
        self.callback = ResultsCollector()
        try:
            tqm = TaskQueueManager(
                inventory=self.inventory,
                variable_manager=self.variable_manager,
                loader=self.loader,
                options=self.options,
                passwords=self.passwords,
                stdout_callback=self.callback,
            )
            tqm.run(play)
        finally:
            if tqm is not None:
                tqm.cleanup()
            if self.loader:
                self.loader.cleanup_all_tmp_files()
            shutil.rmtree(C.DEFAULT_LOCAL_TMP, True)

    def run_playbook(self, host_list, playbook_path):
        """
        执行 ansible palybook
        """

        try:
            self.callback = ResultsCollector()
            # playbook的路径
            pbfiles = playbook_path.split()
            for pbfile in pbfiles:
                if not os.path.exists(pbfile):
                    print('[INFO] The [%s] playbook does not exist' % pbfile)
                    sys.exit()

            # 额外的参数 sudoers.yml以及模板中的参数，它对应ansible-playbook test.yml --extra-vars "host='aa' name='cc'"
            extra_vars = {}
            extra_vars['host_list'] = host_list
            self.variable_manager.extra_vars = extra_vars
            # actually run it
            executor = PlaybookExecutor(
                playbooks=pbfiles,
                inventory=self.inventory,
                variable_manager=self.variable_manager,
                loader=self.loader,
                options=self.options,
                passwords=self.passwords,
            )
            executor._tqm._stdout_callback = self.callback
            executor.run()
        except Exception as e:
            print("error:", e.message)

    def get_result(self):
        # 获取结束回调
        self.result_all = {'success': {}, 'fail': {}, 'unreachable': {}}
        # print result_all
        # print dir(self.callback)
        for host, results in self.callback.host_ok.items():
            for result in results:
                if not self.result_all['success'].get(host):
                    self.result_all['success'][host] = dict()
                task_name = result.task_name
                _result = result._result
                if not self.result_all['success'][host].get(task_name):
                    self.result_all['success'][host][task_name] = list()
                self.result_all['success'][host][task_name].append(_result)

        for host, result in self.callback.host_failed.items():
            for result in results:
                if not self.result_all['failed'].get(host):
                    self.result_all['failed'][host] = dict()
                task_name = result.task_name
                _result = result._result
                if not self.result_all['failed'][host].get(task_name):
                    self.result_all['failed'][host][task_name] = list()
                self.result_all['failed'][host][task_name].append(_result['msg'])
            # self.result_all['failed'][host] = _result['msg']

        for host, result in self.callback.host_unreachable.items():
            for result in results:
                if not self.result_all['unreachable'].get(host):
                    self.result_all['unreachable'][host] = dict()
                task_name = result.task_name
                _result = result._result
                if not self.result_all['unreachable'][host].get(task_name):
                    self.result_all['unreachable'][host][task_name] = list()
                self.result_all['unreachable'][host][task_name].append(_result['msg'])

        for i in self.result_all['success'].keys():
            # print i,self.result_all['success'][i]
            return self.result_all
        # print self.result_all['fail']
        # print self.result_all['unreachable']
        # print self.result_all

    def get_json(self):
        d = self.get_result()
        data = json.dumps(d, ensure_ascii=False, indent=4, encoding='utf-8')
        print(data)

# http://www.mindg.cn/?p=2004

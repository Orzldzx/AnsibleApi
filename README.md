# Usage:

```python
#!/usr/bin/env python3
# -*- coding: utf8 -*-


from AnsibleApi import MyApi


api = Mysql(<hostfile>)

# 执行 Ad-hoc
api.run(<host>, <module>, <module_args>)

# 执行 playbook
api.run_playbook(<host>, <playbookfile>)

# 获取返回值
api.get_result()    # 字典
api.get_json()      # json
```

# hosts 文件格式

- ini

```
[group1]
host1   ansible_ssh_host = xxx.xx.xx.xxx
```

- 字典

```
{
    'group1': {
        'hosts': [
            '1.1.1.1', '2.2.2.2'
        ],
        'vars': {
            'some_vars': 'some_values'
        },
        'children': [
            'other_group'
        ]
    },
    'group2': {
        'hosts': {
            'host1': {
                'ansible_ssh_host': '1.1.1.1',
                'ansible_ssh_pass': '123456',
                'ansible_ssh_user': 'root'
            },
            'host2': {
                'ansible_ssh_host': '2.2.2.2',
                'ansible_ssh_pass': '123456'
            }
        }
    }
}
```

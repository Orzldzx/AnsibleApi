# Usage:

```python
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

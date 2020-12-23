# coding:utf-8
import json
from typing import IO, Any

import yaml
import os
import json
from yamlinclude import YamlIncludeConstructor

curPath = os.path.dirname(os.path.realpath(__file__))
YamlIncludeConstructor.add_to_loader_class(loader_class=yaml.FullLoader, base_dir=curPath)

if __name__ == '__main__':
    # 获取yaml文件路径
    yamlPath = os.path.join(curPath, "object.yml")
    # open方法打开直接读出来
    with open(yamlPath, 'r', encoding='utf-8') as f:
        cfg = f.read()
        d = yaml.load(cfg, Loader=yaml.FullLoader)  # 用load方法转字典
        print(json.dumps(d, indent=4, ensure_ascii=False))

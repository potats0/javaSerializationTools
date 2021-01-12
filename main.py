import json

from JavaMetaClass import javaContent2Yaml
from serializationDump import ObjectStream


class MyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, bytes):
            return obj.hex()
        return json.JSONEncoder.default(self, obj)


if __name__ == '__main__':
    with open("tests/7u21.ser", "rb") as f:
        obj = ObjectStream(f).readContent()
        d = javaContent2Yaml(obj)
        print("------------------------------------")
        print(d)
        print("------------------------------------")
        print(json.dumps(d, indent=2, cls=MyEncoder, ensure_ascii=False))
        # import yaml
        #
        # f = open('dns.yaml', 'w+')
        # yaml.dump(d, f, allow_unicode=True)

        # TODO:
        # 1. 已解决，父类ObjectANnotation但是子类没有，导致少一个字节的问题
        #
        # 2. 对象互相引用，打印问题，导致过早输出所有值，例父子类互相引用
        #
        # 3. 已解决，classANnontion 去掉handle添加
        #
        # 4. 已解决，object计算handle问题
        #
        # 5. 已解决 父子类计算handle，重复添加

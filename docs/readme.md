## 一、为什么会有这个项目？
目前渗透攻击人员编写Java反序列化漏洞EXP时，会采取两种方式：

1.使用脚本语言编写，python，go等，执行不同命令时动态拼接字节码。

2.使用Java编写，直接Java生成序列化数据

3.上面两种结合，python命令行调用ysoserial等jar包，生成序列化数据，再使用pythoon读取

上面方式各有优劣：

使用python编写，执行不同命令拼接字节码时工作量大；

使用Java编写，没有可以媲美requests的http库，编写成本较高，且需要目标依赖库过于臃肿，且会遇到suid不匹配等问题；

第三种看起来结合前两种优势，但是命令行调用总不优雅，且某些条件下并不适用

javaSerializationDump，支持通过JSON数据配置的方式动态生成Java序列化字节码，省去了exp编写人员肉眼分析序列化字节码，同时还可以使用python快速编写出攻击逻辑。
<br><br>

## 二、使用方式
### 1.读取序列化文件转为json

```
gadget = "gadgets/8u20.ser"
with open("gadget", "rb") as f:
    a = ObjectStream(f)
    obj = a.readContent()
    obj1 = copy.deepcopy(obj)
    d = javaContent2Yaml(obj)
    payload = json.dumps(d, indent=2, cls=MyEncoder, ensure_ascii=False)
```
### 2.更改json数据
空

### 3.生成新的反序列化文件
空


## 三、目前支持的Gadget
7u21

8u20

BeanShell1

Clojure

CommonsBeanutils1

CommonsCollections1

CVE-2020-2551

DNSLOG

Groovy1

Hibernate1

JavassistWeld1

JSON1

jythhon1

MozillaRhino1

MozillaRhino2

Spring1

Spring2

Vaadin1



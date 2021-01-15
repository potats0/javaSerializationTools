from collections import OrderedDict


class JavaEndBlock:
    pass


"""
两种block的区别在于size的大小，一个为byte，一个为int
"""


class JavaBLockData:
    def __init__(self, size, data):
        self.size = size
        self.data = data


class JavaLongBLockData:
    def __init__(self, size, data):
        self.size = size
        self.data = data


class JavaClass:
    def __init__(self, name, suid, flags):
        self.name = name
        self.suid = suid
        self.flags = flags
        self.superJavaClass = None
        self.fields = []
        self.classAnnotations = []

    def __str__(self):
        return f"javaclass {self.name}"


class JavaProxyClass:
    def __init__(self, interfaces):
        self.interfaces = interfaces
        self.classAnnotations = []
        self.superJavaClass = None
        self.fields = []
        self.hasWriteObjectData = False
        self.name = "Dynamic proxy"


class JavaException:
    def __init__(self, exception):
        self.exception = exception


class JavaArray:
    def __init__(self, length, singature):
        self.singature = singature
        self.length = length
        self.list = []

    def add(self, __obj__):
        self.list.append(__obj__)


class JavaEnum:
    def __init__(self, javaClass):
        self.javaClass = javaClass
        self.enumConstantName = None


class JavaString:
    def __init__(self, string):
        self.string = string

    def startswith(self, string):
        return self.string.startswith(string)

    def __str__(self):
        return self.string


class JavaObject:
    def __init__(self, javaClass):
        self.javaClass = javaClass
        # fields 保存类的字段，队列数据结构。父类在最前，子类在最后
        self.fields = []
        self.objectAnnotation = []

    def __str__(self):
        return f"className {self.javaClass.name}\t extend {self.javaClass.superJavaClass}"


class JavaField:
    def __init__(self, name, singature, value):
        self.fieldName = name
        self.singature = singature
        self.value = value


def javaClass2Yaml(javaClass):
    if isinstance(javaClass, JavaProxyClass):
        return JavaproxyClass2Yaml(javaClass)
    else:
        d = dict()
        d['name'] = javaClass.name
        d['suid'] = javaClass.suid
        d['flags'] = javaClass.flags
        field = []
        for classfield in javaClass.fields:
            field.append({"name": classfield['name'], 'singature': javaContent2Yaml(classfield['signature'])})
        d['fields'] = field
        if javaClass.superJavaClass:
            d['superClass'] = javaClass2Yaml(javaClass.superJavaClass)
        else:
            d['superClass'] = None
        d['classAnnotations'] = list()
        for i in javaClass.classAnnotations:
            d['classAnnotations'].append(javaContent2Yaml(i))
        return {"javaClass": d}


def javaEnum2Yaml(javaEnum):
    d = dict()
    d['classDesc'] = javaClass2Yaml(javaEnum.javaClass)
    d['enumConstantName'] = javaContent2Yaml(javaEnum.enumConstantName)
    return {'javaenum': d}


def javaArray2Yaml(javaArray):
    d = dict()
    if isinstance(javaArray.singature, JavaClass):
        d['singature'] = javaClass2Yaml(javaArray.singature)
    else:
        d['singature'] = javaArray.javaClass
    d['length'] = javaArray.length
    d['values'] = list()
    for o in javaArray.list:
        d['values'].append(javaContent2Yaml(o))
    else:
        # 针对xalan payload的bytes表示
        if all([isinstance(i, bytes) for i in javaArray.list]):
            d['values'] = b"".join(javaArray.list)
    return {"javaArray": d}


def javaObject2Yaml(javaObject):
    d = dict()
    d['classDesc'] = javaClass2Yaml(javaObject.javaClass)
    # 打印对象的值，先打印父类得值，再打印子类得值
    superClassList = []
    superClass = javaObject.javaClass
    while True:
        if superClass:
            superClassList.append(superClass.name)
            superClass = superClass.superJavaClass
        else:
            break
    allValues = []
    while len(javaObject.fields):
        # 从父类开始，一直到子类。数组按顺序排列。类名+值
        currentObjFields = javaObject.fields.pop(0)
        className = superClassList.pop()
        value = []
        allValues.append({className: value})
        for currentObjField in currentObjFields:
            data = {'type': javaContent2Yaml(currentObjField.singature), 'fieldName': currentObjField.fieldName,
                    'value': javaContent2Yaml(currentObjField.value)}
            value.append({'data': data})

    d['Values'] = allValues
    objectAnnotation = []
    for o in javaObject.objectAnnotation:
        objectAnnotation.append(javaContent2Yaml(o))
    else:
        d['objectAnnotation'] = objectAnnotation
    return {'javaObject': d}


def javaString2Yaml(javaString):
    return {'javaString': javaString.string}


def javaException2Yaml(javaException):
    return {'javaException': javaContent2Yaml(javaException.exception)}


def javaBlockData2Yaml(blockData):
    return {'javaBlockData': {"size": blockData.size, 'data': blockData.data}}


def javaLongBlockData2Yaml(blockData):
    return {'javaLongBlockData': {"size": blockData.size, 'data': blockData.data}}


def JavaproxyClass2Yaml(javaproxyClass):
    d = dict()
    d['interfaces'] = []
    for i in javaproxyClass.interfaces:
        d['interfaces'].append(i)
    d['classAnnotations'] = []
    for i in javaproxyClass.classAnnotations:
        d['classAnnotations'].append(javaContent2Yaml(i))
    d['superClass'] = javaContent2Yaml(javaproxyClass.superJavaClass)
    return {'JavaproxyClass': d}


def javaEndBLock2Yaml(JavaEndBLock):
    return {'javaEndBLock': 'javaEndBLock'}


def javaContent2Yaml(java):
    if isinstance(java, JavaObject):
        return javaObject2Yaml(java)
    elif isinstance(java, JavaClass):
        return javaClass2Yaml(java)
    elif isinstance(java, JavaEnum):
        return javaEnum2Yaml(java)
    elif isinstance(java, JavaArray):
        return javaArray2Yaml(java)
    elif isinstance(java, JavaString):
        return javaString2Yaml(java)
    elif isinstance(java, JavaException):
        return javaException2Yaml(java)
    elif isinstance(java, JavaBLockData):
        return javaBlockData2Yaml(java)
    elif isinstance(java, JavaLongBLockData):
        return javaLongBlockData2Yaml(java)
    elif isinstance(java, JavaProxyClass):
        return JavaproxyClass2Yaml(java)
    elif isinstance(java, JavaEndBlock):
        return javaEndBLock2Yaml(java)
    elif isinstance(java, list) and all([isinstance(i, bytes) for i in java]):
        return b"".join(java)
    else:
        return java

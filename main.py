import copy
import json
from collections import OrderedDict

from Constants import Constants
from JavaMetaClass import javaContent2Yaml, JavaClass, JavaEndBlock, JavaString, JavaObject, JavaField, JavaBLockData, \
    JavaArray, JavaException, JavaProxyClass
from serializationDump import ObjectStream, ObjectIO


class MyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, bytes):
            return obj.hex()
        return json.JSONEncoder.default(self, obj)


class ObjectWrite:
    def __init__(self, stream):
        self.handles = []
        self.stream = ObjectIO(stream)
        self.writeStreamHeader()

    def writeStreamHeader(self):
        self.stream.writeBytes(b'\xac\xed')
        self.stream.writeBytes(b'\x00\x05')

    def writeContent(self, content):
        if isinstance(content, JavaObject):
            self.writeObject(content)
        elif isinstance(content, JavaEndBlock):
            self.writeEndBlock(content)
        elif isinstance(content, JavaString):
            self.writeTypeString(content)
        elif isinstance(content, JavaField):
            self.writeJavaField(content)
        elif isinstance(content, JavaBLockData):
            self.writeJavaBlockData(content)
        elif isinstance(content, JavaArray):
            self.writeJavaArray(content)
        elif isinstance(content, JavaException):
            self.writeJavaException(content)
        elif isinstance(content, JavaClass):
            self.writeJavaClass(content)
        elif isinstance(content, JavaProxyClass):
            self.writeJavaProxyClass(content)
        elif content == 'null':
            self.stream.writeBytes(Constants.TC_NULL)
        else:
            print(content)

    def writeObject(self, javaObject):
        if javaObject in self.handles:
            self.writeHandle(javaObject)
            return
        self.stream.writeBytes(Constants.TC_OBJECT)
        self.writeClassDesc(javaObject.javaClass)
        self.handles.append(javaObject)

        superClassList = []
        superClass = javaObject.javaClass
        while True:
            if superClass:
                superClassList.append(superClass)
                superClass = superClass.superJavaClass
            else:
                break
        for field in javaObject.fields:
            classDesc = superClassList.pop()
            for i in field:
                self.writeContent(i)
            if classDesc.hasWriteObjectData:
                self.writeObjectAnnotations(javaObject.objectAnnotation)

    def writeClassDesc(self, javaClass):
        if javaClass in self.handles:
            self.writeHandle(javaClass)
            return
        if isinstance(javaClass, JavaProxyClass):
            return self.writeJavaProxyClass(javaClass)
        self.stream.writeBytes(Constants.TC_CLASSDESC)
        self.stream.writeString(javaClass.name)
        self.stream.writeLong(javaClass.suid)
        self.stream.writeBytes(javaClass.flags.to_bytes(1, 'big'))
        self.stream.writeShort(len(javaClass.fields))
        self.handles.append(javaClass)
        writeTypeString = False
        for i in javaClass.fields:
            if i['signature'].startswith('L') or i['signature'].startswith('['):
                self.stream.writeBytes(i['signature'].string[0].encode())
                writeTypeString = True
            else:
                self.stream.writeBytes(i['signature'].encode())
            self.stream.writeString(i['name'])
            if writeTypeString:
                self.writeTypeString(i['signature'])
        self.writeClassAnnotations(javaClass.classAnnotations)
        if javaClass.superJavaClass is not None:
            self.writeClassDesc(javaClass.superJavaClass)
        else:
            self.stream.writeBytes(Constants.TC_NULL)

    def writeHandle(self, obj):
        handle = self.handles.index(obj)
        print(hex(handle))
        handle = Constants.baseWireHandle + handle
        self.stream.writeBytes(Constants.TC_REFERENCE)
        self.stream.writeInt(handle)

    def writeTypeString(self, javaString):
        if javaString in self.handles:
            self.writeHandle(javaString)
            return
        else:
            self.stream.writeBytes(Constants.TC_STRING)
            self.stream.writeString(javaString.string)
            self.handles.append(javaString)

    def writeClassAnnotations(self, classAnnotations):
        for i in classAnnotations:
            self.writeContent(i)

    def writeEndBlock(self, content):
        self.stream.writeBytes(Constants.TC_ENDBLOCKDATA)

    def writeJavaField(self, content):
        if content.singature.startswith('L') or content.singature.startswith('['):
            self.writeContent(content.value)
        elif content.singature == "B":
            self.stream.writeBytes(content.value)
        elif content.singature == "C":
            self.stream.writeChar(content.value)
        elif content.singature == "D":
            self.stream.writeDouble(content.value)
        elif content.singature == "F":
            self.stream.writeFloat(content.value)
        elif content.singature == 'I':
            self.stream.writeInt(content.value)
        elif content.singature == 'J':
            self.stream.writeLong(content.value)
        elif content.singature == 'S':
            self.stream.writeShort(content.value)
        elif content.singature == 'Z':
            self.stream.writeBoolean(content.value)
        else:
            print("unsupport", content)

    def writeObjectAnnotations(self, objectAnnotation):
        # if len(objectAnnotation):
            while len(objectAnnotation):
                i = objectAnnotation.pop(0)
                self.writeContent(i)
                if i == JavaEndBlock:
                    return
        # else:
        #     self.stream.writeBytes(Constants.TC_ENDBLOCKDATA)

    def writeJavaBlockData(self, content):
        self.stream.writeBytes(Constants.TC_BLOCKDATA)
        self.stream.writeBytes(content.size.to_bytes(1, 'big'))
        self.stream.writeBytes(content.data)

    def writeJavaArray(self, content):
        if content in self.handles:
            return self.writeHandle(content)
        else:
            self.stream.writeBytes(Constants.TC_ARRAY)
            self.writeClassDesc(content.singature)
            self.stream.writeInt(content.length)
            self.handles.append(content)
            for i in content.list:
                if content.singature.name[1:].startswith("[") or content.singature.name[1:].startswith("L"):
                    self.writeContent(i)
                else:
                    self.writeJavaField(JavaField(None, content.singature.name[1:], i))

    def writeJavaException(self, content):
        self.stream.writeBytes(Constants.TC_EXCEPTION)
        self.handles = []
        self.writeContent(content.exception)
        self.handles = []

    def writeJavaClass(self, content):
        if content in self.handles:
            return self.writeHandle(content)
        else:
            self.stream.writeBytes(Constants.TC_CLASS)
            self.writeClassDesc(content)
            self.handles.append(content)

    def writeJavaProxyClass(self, content):
        if content in self.handles:
            return self.writeHandle(content)
        self.stream.writeBytes(Constants.TC_PROXYCLASSDESC)
        self.stream.writeInt(len(content.interfaces))
        for i in content.interfaces:
            self.stream.writeString(i)
        self.handles.append(content)
        for i in content.classAnnotations:
            self.writeContent(i)
        if content.superJavaClass:
            self.writeClassDesc(content.superJavaClass)
        else:
            self.stream.writeBytes(Constants.TC_NULL)


def Yaml2JavaObject(yaml):
    javaClass = Yaml2JavaClass(yaml['classDesc'])
    javaObject = JavaObject(javaClass)
    superClassList = []
    superClass = javaObject.javaClass
    while True:
        if superClass:
            superClassList.append(superClass)
            superClass = superClass.superJavaClass
        else:
            break
    for value in yaml['Values']:
        currentClass = superClassList.pop()
        currentField = []
        if value[currentClass.name] is not None:
            for data in value[currentClass.name]:
                data = data['data']
                type = Yaml2JavaContent(data['type'])
                value = Yaml2JavaContent(data['value'])
                javaField = JavaField(data['fieldName'], type, value)
                currentField.append(javaField)
        javaObject.fields.append(currentField)

    for o in yaml['objectAnnotation']:
        javaObject.objectAnnotation.append(Yaml2JavaContent(o))

    return javaObject


def Yaml2JavaClass(yaml):
    javaClassYaml = yaml['javaClass']
    name = javaClassYaml['name']
    suid = javaClassYaml['suid']
    flags = javaClassYaml['flags']

    javaClass = JavaClass(name, suid, flags)
    if javaClassYaml['superClass'] is not None:
        javaClass.superJavaClass = Yaml2JavaClass(javaClassYaml['superClass'])
    else:
        javaClass.superJavaClass = None
    for i in javaClassYaml['classAnnotations']:
        javaClass.classAnnotations.append(Yaml2JavaContent(i))
    for field in javaClassYaml['fields']:
        fieldMap = dict()
        if isinstance(field['singature'], dict):
            fieldMap['singature'] = Yaml2JavaContent(field['singature'])
        else:
            fieldMap['singature'] = field['singature']
        fieldMap['name'] = field['name']
        javaClass.fields.append(fieldMap)
    return javaClass


def Yaml2JavaEnum(yaml):
    pass


def Yaml2JavaArray(yaml):
    pass


def Yaml2JavaString(yaml):
    return JavaString(yaml)


def Yaml2JavaBLockData(yaml):
    size = yaml['size']
    data = bytes.fromhex(yaml['data'])
    return JavaBLockData(size, data)


def Yaml2JavaEndBlock(yaml):
    return JavaEndBlock()


def Yaml2JavaContent(yaml):
    if isinstance(yaml, dict):
        for k in yaml:
            if k == 'javaObject':
                return Yaml2JavaObject(yaml[k])
            elif k == 'javaClass':
                return Yaml2JavaClass(yaml[k])
            elif k == 'JavaEnum':
                return Yaml2JavaEnum(yaml[k])
            elif k == 'JavaArray':
                return Yaml2JavaArray(yaml[k])
            elif k == 'javaString':
                return Yaml2JavaString(yaml[k])
            elif k == 'javaBlockData':
                return Yaml2JavaBLockData(yaml[k])
            elif k == 'javaEndBLock':
                return Yaml2JavaEndBlock(yaml[k])
            else:
                print(k)
                print(yaml[k])
                return k
    else:
        return yaml


if __name__ == '__main__':
    payload = ""
    obj1 = ""
    with open("tests/payload.ser", "rb") as f:
        a = ObjectStream(f)
        obj = a.readContent()
        # obj1 = copy.deepcopy(obj)
        # d = javaContent2Yaml(obj)
        print("------------------------------------")
        # print(d)
        print("------------------------------------")
        # print(json.dumps(d, indent=2, cls=MyEncoder, ensure_ascii=False))
        # payload = json.dumps(d, indent=2, cls=MyEncoder, ensure_ascii=False)
        # print(payload)
        # exit()
    print(obj == obj1)
    with open("test.ser", 'wb') as f:
        o = ObjectWrite(f)
        o.writeContent(obj)
        pass
    with open("test.ser", 'rb') as f:
        obj1 = ObjectStream(f).readContent()
        # d = javaContent2Yaml(obj)
        print(obj == obj1)

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

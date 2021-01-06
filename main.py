import json
from queue import Queue
from struct import *

from collections import OrderedDict

from Constants import Constants


class ObjectIO:
    def __init__(self, base_stream):
        self.base_stream = base_stream

    def readByte(self) -> bytes:
        return self.base_stream.read(1)

    def peekByte(self) -> bytes:
        return self.base_stream.peek()[:1]

    def readUnsignedShort(self) -> int:
        number = self.readBytes(2)
        number = int.from_bytes(number, 'big')
        return number & 0xFFFF

    def readUnsignedLong(self) -> int:
        number = self.readBytes(8)
        return int.from_bytes(number, 'big') & 0xFFFFFFFFFFFFFFFF

    def readInt(self) -> int:
        return int.from_bytes(self.readBytes(4), 'big')

    def readBytes(self, length) -> int:
        return self.base_stream.read(length)

    def readString(self) -> str:
        length = self.readUnsignedShort()
        return self.readBytes(length).decode()

    def readFloat(self):
        num = self.readBytes(4)
        return unpack('f', num)[0]

    def readBoolean(self):
        tc = int.from_bytes(self.readByte(), 'big')
        return True if tc == 0 else False

    def writeBytes(self, value):
        self.base_stream.write(value)

    def writeString(self, value):
        length = len(value)
        self.writeUInt16(length)
        self.pack(str(length) + 's', value)

    def pack(self, fmt, data):
        return self.writeBytes(pack(fmt, data))

    def unpack(self, fmt, length=1):
        return unpack(fmt, self.readBytes(length))[0]


class ObjectStream:
    def __init__(self, stream):
        self.bin = stream
        self.handles = []
        self.readStreamHeader()

    def newHandles(self, obj):
        self.handles.append(obj)
        handle = len(self.handles) - 1 + Constants.baseWireHandle
        return len(self.handles) - 1 + Constants.baseWireHandle

    def readStreamHeader(self):
        magic = self.bin.readUnsignedShort()
        version = self.bin.readUnsignedShort()
        if magic != Constants.magic or version != Constants.version:
            print(f"invalid bin header {magic:#2x} {version:#2x}")
            exit(-1)

    def readClassDescriptor(self):
        """
        读取非动态代理类的结构
        :return:
        """
        tc = self.bin.peekByte()
        if tc == Constants.TC_CLASSDESC:
            javaClass = self.__readClassDesc__()
            # TODO: add classAnnotation to class structs
            self.readClassAnnotations()
            superjavaClass = self.readSuperClassDesc()
            javaClass.superJavaClass = superjavaClass
        elif tc == Constants.TC_REFERENCE:
            javaClass = self.readHandle()
        else:
            print("tc unsupport in read class desc")
            exit(-1)
        return javaClass

    def readProxyClassDescriptor(self):
        """
        读取动态代理类的结构
        :return:
        """
        tc = self.bin.readByte()
        if tc != Constants.TC_PROXYCLASSDESC:
            print("error")
            return
        interfaceCount = self.bin.readInt()
        print(f"Interface count {interfaceCount}")
        for i in range(interfaceCount):
            interfaceName = self.bin.readString()
            print("--------------")
            print(interfaceName)
        classDesc = JavaClass(f"Dynamic Proxy Class {interfaceName}", 0, 0)
        handle = self.newHandles(classDesc)
        print(f"TC_PROXYCLASSDESC new handle from {hex(handle)}")
        self.readClassAnnotations()
        classDesc.superJavaClass = self.readSuperClassDesc()
        return classDesc

    def __readClassDesc__(self):
        tc = self.bin.readByte()
        if tc != Constants.TC_CLASSDESC:
            print("InternalError")
            return
        # read Class name from bin
        className = self.bin.readString()
        suid = self.bin.readUnsignedLong()
        flags = self.bin.readByte()
        flags = int.from_bytes(flags, 'big')
        numFields = self.bin.readUnsignedShort()
        externalizable = flags & Constants.SC_EXTERNALIZABLE != 0
        sflag = flags & Constants.SC_SERIALIZABLE != 0
        hasWriteObjectData = flags & Constants.SC_WRITE_METHOD != 0
        hasBlockExternalData = flags & Constants.SC_BLOCK_DATA != 0
        if externalizable and sflag:
            print("serializable and externalizable flags conflict")

        print(f"className {className}")
        print(f"suid {suid}")
        print(f"number of fields {numFields}")
        classDesc = JavaClass(className, suid, flags)
        classDesc.hasWriteObjectData = hasWriteObjectData
        classDesc.hasBlockExternalData = hasBlockExternalData
        handle = self.newHandles(classDesc)
        print(f"TC_CLASSDESC new handle from {hex(handle)} className {className}")
        fields = []
        for i in range(numFields):
            tcode = self.bin.readByte()
            fname = self.bin.readString()
            if tcode == b'L' or tcode == b'[':
                signature = self.readTypeString()
            else:
                signature = tcode.decode()
            fields.append({'name': fname, 'signature': signature})
            print(f"name {fname} signature {signature}")
            classDesc.fields = fields
        return classDesc

    def readClassAnnotations(self):
        """
        读取类的附加信息
        """
        print(f"ClassAnnotations start ")
        while True:
            obj = self.readContent()
            if obj == 'end':
                break
        print(f"ClassAnnotations end ")

    def readSuperClassDesc(self):
        """
        读取父类的的class信息，一直到父类为空，类似于链表。java不支持多继承
        :return:
        """
        tc = self.bin.peekByte()
        print(f"Super Class start")
        if tc != Constants.TC_NULL:
            superJavaClass = self.readClassDescriptor()
            # 父子类重复计算handle
            # handle = self.newHandles(superJavaClass)
            # print(f"readSuperClassDesc new handle from {hex(handle)}")
        else:
            self.bin.readByte()
            superJavaClass = None
        print(f"Super Class End")
        return superJavaClass

    def readObject(self):
        tc = self.bin.readByte()
        if tc != Constants.TC_OBJECT:
            print("读取object错误，tc不为object！")
            return
        tc = self.bin.peekByte()
        if tc == Constants.TC_CLASSDESC:
            javaClass = self.__readClassDesc__()
            # TODO: add classAnnotation to class structs
            self.readClassAnnotations()
            superjavaClass = self.readSuperClassDesc()
            javaClass.superJavaClass = superjavaClass
            javaObject = JavaObject(javaClass)
            handle = self.newHandles(javaObject)
            print(f"readObject new handle from {hex(handle)}")
            self.readClassData(javaObject)
        elif tc == Constants.TC_NULL:
            return self.readNull()
        elif tc == Constants.TC_REFERENCE:
            javaClass = self.readHandle()
            javaObject = JavaObject(javaClass)
            handle = self.newHandles(javaObject)
            print(f"readObject new handle from {hex(handle)}")
            self.readClassData(javaObject)
        elif tc == Constants.TC_PROXYCLASSDESC:
            javaObject = self.readProxyClassDescriptor()
            self.newHandles(javaObject)
        else:
            printInvalidTypeCode(tc)

        return javaObject

    def readClassData(self, javaObject):
        """
        读取对象的值，先读取父类的值，再读取子类的值
        :return:
        """
        superClass = javaObject.javaClass
        superClassList = []
        while superClass:
            superClassList.append(superClass)
            superClass = superClass.superJavaClass

        while superClassList:
            classDesc = superClassList.pop()
            # fields = fieldStack.pop()
            fields = classDesc.fields
            currentField = []
            for field in fields:
                singature = field['signature']
                if singature.startswith('L') or singature.startswith('['):
                    value = self.readContent()
                elif singature == 'I':
                    value = self.bin.readInt()
                elif singature == 'F':
                    value = self.bin.readFloat()
                elif singature == "Z":
                    value = self.bin.readBoolean()
                else:
                    print(f"unsupport singatyre{singature}")
                print(f"name {field['name']}  value {value}")
                currentField.append({field['name']: [value, field['signature']]})
            javaObject.fields.put(currentField)
            if classDesc.hasWriteObjectData:
                self.readObjectAnnotations(javaObject)

    def readHandle(self):
        """
        反序列化中是不会出现两个一摸一样的值，第二个值一般都是引用
        :return:
        """
        tc = self.bin.readByte()
        handle = self.bin.readInt()
        print(hex(handle))
        handle = handle - Constants.baseWireHandle
        obj = self.handles[handle]
        if isinstance(obj, JavaClass):
            return obj
        elif isinstance(obj, JavaString):
            return obj.string
        elif isinstance(obj, JavaObject):
            return obj
        else:
            print("unsuppprt type")
            return None

    def readTypeString(self):
        tc = self.bin.peekByte()
        if tc == Constants.TC_NULL:
            return self.readNull()
        elif tc == Constants.TC_REFERENCE:
            return self.readHandle()
        elif tc == Constants.TC_STRING:
            return self.readString()
        elif tc == Constants.TC_LONGSTRING:
            return self.readString()
        else:
            printInvalidTypeCode(tc)

    def readString(self):
        tc = self.bin.readByte()
        string = self.bin.readString()
        handle = self.newHandles(JavaString(string))
        print(f"readString new handle from {hex(handle)} value {string}")
        return string

    def readContent(self):
        tc = self.bin.peekByte()
        if tc == Constants.TC_NULL:
            return self.readNull()
        elif tc == Constants.TC_REFERENCE:
            return self.readHandle()
        elif tc == Constants.TC_CLASS:
            self.bin.readByte()
            clazz = self.readClassDescriptor()
            handle = self.newHandles(clazz)
            print(f"TC_CLASS new handle from {hex(handle)}")
            return clazz
        elif tc == Constants.TC_CLASSDESC:
            return self.readClassDescriptor()
        elif tc == Constants.TC_PROXYCLASSDESC:
            return self.readProxyClassDescriptor()
        elif tc == Constants.TC_STRING or tc == Constants.TC_LONGSTRING:
            return self.readTypeString()
        elif tc == Constants.TC_ENUM:
            exit(-3)
        elif tc == Constants.TC_OBJECT:
            return self.readObject()
        elif tc == Constants.TC_EXCEPTION:
            exit(-3)
        elif tc == Constants.TC_ARRAY:
            return self.readArray()
        elif tc == Constants.TC_BLOCKDATA:
            return self.readBlockData()
        elif tc == Constants.TC_BLOCKDATALONG:
            exit(-3)
        elif tc == Constants.TC_ENDBLOCKDATA:
            print("------TC_ENDBLOCKDATA")
            self.bin.readByte()
            return 'end'
        else:
            printInvalidTypeCode(tc)
            exit(-1)

    def readBlockData(self):
        tc = self.bin.readByte()
        length = int.from_bytes(self.bin.readByte(), 'big')
        data = self.bin.readBytes(length)
        print(data)
        return data

    def readObjectAnnotations(self, javaObject):
        print("reading readObjectAnnotations")
        while True:
            obj = self.readContent()
            print(obj)
            if obj == 'end':
                break
            else:
                javaObject.objectAnnotation.append(obj)

    def readNull(self):
        tc = self.bin.readByte()
        return 'null'

    def readArray(self):
        self.bin.readByte()
        tc = self.bin.peekByte()
        if tc == Constants.TC_CLASSDESC:
            javaClass = self.readClassDescriptor()
        elif tc == Constants.TC_REFERENCE:
            javaClass = self.readHandle()
        else:
            print("unsupport type")
        size = self.bin.readInt()
        print(javaClass)
        print(f"array size {size}")
        array = []
        handle = self.newHandles(array)
        print(f"TC_ARRAY new handle from {hex(handle)}")
        for i in range(size):
            signature = javaClass.name[1:]
            if signature.startswith("L") or signature.startswith("["):
                obj = self.readContent()
            elif signature == 'B':
                obj = self.bin.readByte()
            else:
                print(print(f"unsupport singatyre{signature}"))
            array.append(obj)
        return array


def printInvalidTypeCode(code: bytes):
    print(f"invalid type code {int.from_bytes(code, 'big'):#2x}")


class JavaClass:
    def __init__(self, name, suid, flags):
        self.name = name
        self.suid = suid
        self.flags = flags
        self.superJavaClass = None
        self.fields = []

    def __str__(self):
        return f"{self.name}"


class JavaString:
    def __init__(self, string):
        self.string = string

    def __str__(self):
        return self.string


class JavaObject:
    def __init__(self, javaClass):
        self.javaClass = javaClass
        # fields 保存类的字段，队列数据结构。父类在最前，子类在最后
        self.fields = Queue()
        self.objectAnnotation = ["NULL"]

    def __str__(self):
        return f"className {self.javaClass.name}\t extend {self.javaClass.superJavaClass}"


def javaClass2Yaml(javaClass):
    d = OrderedDict()
    d['suid'] = javaClass.suid
    d['flags'] = javaClass.flags
    d['classAnnotation'] = None
    # TODO classAnnotation
    if javaClass.superJavaClass:
        d['superClass'] = javaClass2Yaml(javaClass.superJavaClass)
    else:
        d['superClass'] = None
    return {javaClass.name: d}


def javaObject2Yaml(javaObject):
    d = javaClass2Yaml(javaObject.javaClass)
    # d['suid'] = javaObject.javaClass.suid
    # d['flags'] = javaObject.javaClass.flags
    # d['classAnnotation'] = None
    # # TODO classAnnotation
    # if javaObject.javaClass.superJavaClass:
    #     d['superClass'] = javaClass2Yaml(javaObject.javaClass.superJavaClass)
    # else:
    #     d['superClass'] = None
    superClassList = []
    superClass = javaObject.javaClass
    while True:
        if superClass:
            superClassList.append(superClass.name)
            superClass = superClass.superJavaClass
        else:
            break
    allValues = []
    while javaObject.fields.qsize():
        currentObjFields = javaObject.fields.get()
        className = superClassList.pop()
        value = []
        values = {className: value}
        allValues.append(values)
        for currentObjField in currentObjFields:
            for k, v in currentObjField.items():
                data = {'type': v[1], 'fieldName': k}
                if isinstance(v[0], JavaObject):
                    data['value'] = javaObject2Yaml(v[0])
                elif isinstance(v[0], JavaClass):
                    data['value'] = javaClass2Yaml(v[0])
                elif isinstance(v[0], list):
                    valueList = []
                    if all([isinstance(i, bytes) for i in v[0]]):
                        data['value'] = b"".join(v[0])
                    for o in v[0]:
                        if isinstance(o, JavaObject):
                            valueList.append(javaObject2Yaml(o))
                        elif isinstance(o, JavaClass):
                            valueList.append(javaClass2Yaml(o))
                        elif all([isinstance(i, bytes) for i in o]):
                            valueList.append(b"".join(o))
                        else:
                            valueList.append(o)
                    data['value'] = valueList
                else:
                    data['value'] = v[0]
                value.append({'data': data})

    d[javaObject.javaClass.name]['Fields'] = allValues
    objectAnnotation = []
    for o in javaObject.objectAnnotation:
        if isinstance(o, JavaObject):
            o = javaObject2Yaml(o)
        objectAnnotation.append(o)
    if objectAnnotation:
        d[javaObject.javaClass.name]['objectAnnotation'] = objectAnnotation
    else:
        d[javaObject.javaClass.name]['objectAnnotation'] = None
    return d


class MyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, bytes):
            return obj.hex()
        return json.JSONEncoder.default(self, obj)


if __name__ == '__main__':
    f = open("dns.ser", "rb")
    s = ObjectIO(f)
    obj = ObjectStream(s).readContent()
    print(obj)
    d = javaObject2Yaml(obj)
    print("------------------------------------")
    print(d)
    print("------------------------------------")
    print(json.dumps(d, indent=4, cls=MyEncoder, ensure_ascii=False))
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

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

    def readLong(self) -> int:
        number = self.readBytes(8)
        return int.from_bytes(number, 'big')

    def readShort(self) -> int:
        number = self.readBytes(2)
        return int.from_bytes(number, 'big')

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

    def readChar(self):
        tc = self.readBytes(2)
        return tc.decode()

    def readDouble(self):
        tc = self.readBytes(8)
        return unpack('d', tc)[0]

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
        return len(self.handles) - 1 + Constants.baseWireHandle

    def readStreamHeader(self):
        magic = self.bin.readUnsignedShort()
        version = self.bin.readUnsignedShort()
        if magic != Constants.magic or version != Constants.version:
            print(f"invalid bin header {magic:#2x} {version:#2x}")
            exit(-1)

    def readClassDescriptor(self):
        """
        读取非动态代理类的结构, 已经将读取到的classdesc添加到handle中
        :return:
        """
        tc = self.bin.peekByte()
        if tc == Constants.TC_CLASSDESC:
            javaClass = self.__readClassDesc__()
        elif tc == Constants.TC_REFERENCE:
            javaClass = self.readHandle()
        else:
            print("tc unsupport in read class desc")
            exit(-1)
        return javaClass

    def readProxyClassDescriptor(self):
        """
        读取动态代理类的结构
        # TODO: 此处可能有问题，需要进一步检查
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
        self.readClassAnnotations(classDesc)
        classDesc.superJavaClass = self.readSuperClassDesc()
        classDesc.hasWriteObjectData = False
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
        self.readClassAnnotations(classDesc)
        superjavaClass = self.readSuperClassDesc()
        classDesc.superJavaClass = superjavaClass
        return classDesc

    def readClassAnnotations(self, classDesc):
        """
        读取类的附加信息
        """
        print(f"ClassAnnotations start ")
        while True:
            obj = self.readContent()
            if isinstance(obj, JavaEndBlock):
                break
            else:
                classDesc.classAnnotations.append(obj)
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
            javaClass = self.readClassDescriptor()
        elif tc == Constants.TC_NULL:
            return self.readNull()
        elif tc == Constants.TC_REFERENCE:
            javaClass = self.readHandle()
        elif tc == Constants.TC_PROXYCLASSDESC:
            javaClass = self.readProxyClassDescriptor()
        else:
            printInvalidTypeCode(tc)

        javaObject = JavaObject(javaClass)
        handle = self.newHandles(javaObject)
        print(f"readObject new handle from {hex(handle)}")
        self.readClassData(javaObject)
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
            fields = classDesc.fields
            currentField = []
            for field in fields:
                singature = field['signature']
                value = self.readFieldValue(singature)
                javaField = JavaField(field['name'], singature, value)
                currentField.append(javaField)
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
        javaString = JavaString(string)
        handle = self.newHandles(javaString)
        print(f"readString new handle from {hex(handle)} value {string}")
        return javaString

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
            return self.readEnum()
        elif tc == Constants.TC_OBJECT:
            return self.readObject()
        elif tc == Constants.TC_EXCEPTION:
            return self.readException()
        elif tc == Constants.TC_RESET:
            self.readReset()
        elif tc == Constants.TC_ARRAY:
            return self.readArray()
        elif tc == Constants.TC_BLOCKDATA:
            return self.readBlockData()
        elif tc == Constants.TC_BLOCKDATALONG:
            return self.readLongBLockData()
        elif tc == Constants.TC_ENDBLOCKDATA:
            return self.readEndBlock()
        else:
            printInvalidTypeCode(tc)
            exit(-1)

    def readBlockData(self):
        tc = self.bin.readByte()
        length = int.from_bytes(self.bin.readByte(), 'big')
        data = self.bin.readBytes(length)
        print(data)
        blockData = JavaBLockData(length, data)
        return blockData

    def readEndBlock(self):
        self.bin.readByte()
        endBD = JavaEndBlock()
        return endBD

    def readObjectAnnotations(self, javaObject):
        print("reading readObjectAnnotations")
        while True:
            obj = self.readContent()
            if isinstance(obj, JavaEndBlock):
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
        javaarray = JavaArray(size, javaClass)
        handle = self.newHandles(javaarray)
        print(f"TC_ARRAY new handle from {hex(handle)}")
        for i in range(size):
            signature = javaClass.name[1:]
            javaarray.add(self.readFieldValue(signature))
        return javaarray

    def readFieldValue(self, singature: str):
        """
        读取字段的值，根据字段的类型
        """
        if singature.startswith("L") or singature.startswith("["):
            return self.readContent()
        elif singature == 'B':
            return self.bin.readByte()
        elif singature == 'C':
            return self.bin.readChar()
        elif singature == 'D':
            return self.bin.readDouble()
        elif singature == 'F':
            return self.bin.readFloat()
        elif singature == 'I':
            return self.bin.readInt()
        elif singature == 'J':
            return self.bin.readLong()
        elif singature == 'S':
            return self.bin.readShort()
        elif singature == "Z":
            return self.bin.readBoolean()
        else:
            print(f"unsupport singature  {singature}")

    def readEnum(self):
        tc = self.bin.readByte()
        javaClass = self.readClassDescriptor()
        javaEnum = JavaEnum(javaClass)
        handle = self.newHandles(javaEnum)
        print(f"read enum new handle {handle}")
        enumConstantName = self.readContent()
        javaEnum.enumConstantName = enumConstantName
        return javaEnum

    def readReset(self):
        tc = self.bin.readByte()
        self.handles = []

    def readException(self):
        tc = self.bin.readByte()
        self.handles = []
        exception = self.readObject()
        self.handles = []
        javaException = JavaException(exception)
        return javaException

    def readLongBLockData(self):
        tc = self.bin.readByte()
        length = int.from_bytes(self.bin.readBytes(4), 'big')
        data = self.bin.readBytes(length)
        print(data)
        blockData = JavaLongBLockData(length, data)
        return blockData


def printInvalidTypeCode(code: bytes):
    print(f"invalid type code {int.from_bytes(code, 'big'):#2x}")


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


class JavaException:
    def __init__(self, exception):
        self.exception = exception


class JavaArray:
    def __init__(self, length, singature):
        self.singature = singature
        self.length = length
        self.list = []

    def add(self, obj):
        self.list.append(obj)


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
        self.fields = Queue()
        self.objectAnnotation = []

    def __str__(self):
        return f"className {self.javaClass.name}\t extend {self.javaClass.superJavaClass}"


class JavaField:
    def __init__(self, name, singature, value):
        self.fieldName = name
        self.singature = singature
        self.value = value


def javaClass2Yaml(javaClass):
    d = OrderedDict()
    d['name'] = javaClass.name
    d['suid'] = javaClass.suid
    d['flags'] = javaClass.flags
    d['classAnnotation'] = None
    # TODO classAnnotation
    if javaClass.superJavaClass:
        d['superClass'] = javaClass2Yaml(javaClass.superJavaClass)
    else:
        d['superClass'] = None
    d['classAnnotations'] = list()
    for i in javaClass.classAnnotations:
        d['classAnnotations'].append(i)
    return {"javaClass": d}


def javaEnum2Yaml(javaEnum):
    d = OrderedDict()
    d['classDesc'] = javaClass2Yaml(javaEnum.javaClass)
    d['enumConstantName'] = javaEnum.enumConstantName
    return {'javaenum': d}


def javaArray2Yaml(javaArray):
    d = OrderedDict()
    if isinstance(javaArray.singature, JavaClass):
        d['singature'] = javaClass2Yaml(javaArray.singature)
    else:
        d['singature'] = javaArray.javaClass
    d['length'] = javaArray.length
    d['values'] = list()
    for o in javaArray.list:
        d['values'].append(javaContent2Yaml(o))
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
    while javaObject.fields.qsize():
        # 从父类开始，一直到子类。数组按顺序排列。类名+值
        currentObjFields = javaObject.fields.get()
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
    elif isinstance(java, list) and all([isinstance(i, bytes) for i in java]):
        return b"".join(java)
    else:
        return java


class MyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, bytes):
            return obj.hex()
        return json.JSONEncoder.default(self, obj)


if __name__ == '__main__':
    with open("tests/dns.ser", "rb") as f:
        obj = ObjectStream(ObjectIO(f)).readContent()
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

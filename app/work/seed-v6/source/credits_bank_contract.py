"""Read the independently qualified, fixed credits-donor bank without external tools."""
import hashlib,json,struct,xml.etree.ElementTree as ET
from pathlib import Path
def readback(bank,root):
    data=Path(bank).read_bytes();contract=json.loads((Path(root)/'credits-bank-contract.json').read_text())
    if hashlib.sha256(data).hexdigest()!=contract['bank_sha256']:raise ValueError('Credits donor differs from the independently qualified bank contract')
    chunks={};pos=0
    while pos<len(data):
        tag,size=struct.unpack_from('<4sI',data,pos);end=pos+8+size
        if end>len(data) or tag in chunks:raise ValueError('Invalid credits bank chunk layout')
        chunks[tag]=data[pos+8:end];pos=end
    body=chunks[b'HIRC'];count=struct.unpack_from('<I',body)[0];pos=4;kinds=[]
    for _ in range(count):
        kind,size=struct.unpack_from('<BI',body,pos);end=pos+5+size
        if end>len(body) or size<4:raise ValueError('Invalid credits HIRC object')
        kinds.append(kind);pos=end
    if pos!=len(body) or kinds.count(11)!=2 or kinds.count(10)!=2:raise ValueError('Credits track/segment count differs')
    tree=ET.Element('bank')
    def readfield(field,parent):
        fmt={'u8':'<B','u32':'<I','tid':'<I','d64':'<d','f32':'<f'}[field['type']]
        actual=struct.unpack_from(fmt,data,field['offset'])[0]
        if actual!=field['value']:raise ValueError('Credits donor field differs: '+field['name'])
        ET.SubElement(parent,'field',name=field['name'],value=str(actual))
    for item in contract['objects']:
        obj=ET.SubElement(tree,'object',name=item['name'])
        for field in item['fields']:
            readfield(field,obj)
        if item.get('volume_fields'):
            params=ET.SubElement(obj,'object',name='NodeInitialParams')
            prop=ET.SubElement(params,'object',name='volume')
            for field in item['volume_fields']:readfield(field,prop)
    return ET.ElementTree(tree)

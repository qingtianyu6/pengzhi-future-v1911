MAX_FRAME = 128
def encode(seq, kind, *args):
    if not 1<=seq<=2147483647 or kind not in ('ENV','SET','STOP','PING','ACK','ERR'):
        raise ValueError('invalid sequence or type')
    fields=['V1',str(seq),kind,*map(str,args)]
    if any(any(c in f for c in ',*\r\n') for f in fields):
        raise ValueError('invalid field')
    body=','.join(fields).encode('ascii')
    checksum=0
    for b in body: checksum^=b
    frame=body+f'*{checksum:02X}\n'.encode()
    if len(frame)>MAX_FRAME: raise ValueError('oversize frame')
    return frame

def decode(frame):
    if not isinstance(frame,bytes) or len(frame)>MAX_FRAME or not frame.endswith(b'\n'):
        raise ValueError('invalid frame length/terminator')
    try:
        body,crc=frame[:-1].rsplit(b'*',1)
        checksum=0
        for b in body: checksum^=b
        if len(crc)!=2 or int(crc,16)!=checksum: raise ValueError('checksum')
        fields=body.decode('ascii').split(',')
        if len(fields)<3 or fields[0]!='V1' or not fields[1].isdigit(): raise ValueError('header')
        seq=int(fields[1]); kind=fields[2]
        if not 1<=seq<=2147483647 or kind not in ('ENV','SET','STOP','PING','ACK','ERR'):
            raise ValueError('header')
        return seq,kind,fields[3:]
    except (UnicodeError,IndexError) as e:
        raise ValueError('invalid ASCII frame') from e

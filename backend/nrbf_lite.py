"""Read .NET BinaryFormatter (MS-NRBF) streams as inert Python data structures.

No .NET assemblies are executed or loaded. Designed for legacy NOVA .nox files.
Does not support remoting MethodCall/MethodReturn records.
"""
from __future__ import annotations
import io
import struct
from dataclasses import dataclass


@dataclass(frozen=True)
class Ref:
    target: int


@dataclass(frozen=True)
class NullRun:
    count: int


class NrbfError(ValueError):
    pass


class Reader:
    MAX_ITEMS = 5_000_000
    MAX_STR = 64_000_000
    def __init__(self, file):
        self.f = file
        self.objects = {}
        self.metadata = {}
        self.libraries = {}
        self.record_count = 0

    def read(self, count):
        b = self.f.read(count)
        if len(b) != count:
            raise NrbfError(f"Truncated data at {self.f.tell()} (wanted {count} bytes)")
        return b

    def u8(self): return self.read(1)[0]
    def i32(self): return struct.unpack('<i', self.read(4))[0]
    def u32(self): return struct.unpack('<I', self.read(4))[0]

    def str(self):
        length=0
        for offset in range(0, 35, 7):
            byte = self.u8()
            length |= (byte & 0x7f) << offset
            if not byte & 0x80:
                if length > self.MAX_STR:
                    raise NrbfError(f"String too large: {length}")
                return self.read(length).decode('utf-8', errors='replace')
        raise NrbfError("Invalid 7-bit string length")

    def primitive(self, prim):
        formats = {1:'?', 2:'B', 6:'d', 7:'h', 8:'i', 9:'q', 10:'b', 11:'f', 12:'q', 13:'q', 14:'H', 15:'I', 16:'Q'}
        if prim in formats:
            fmt = '<' + formats[prim]
            return struct.unpack(fmt, self.read(struct.calcsize(fmt)))[0]
        if prim == 3:  # UTF-8 character
            lead = self.u8()
            size = 1 if lead < 128 else 2 if lead < 224 else 3 if lead < 240 else 4
            return (bytes([lead])+self.read(size-1)).decode('utf-8', 'replace')
        if prim == 5:  # 16-byte Decimal
            lo, mid, hi, flags = struct.unpack('<IIII', self.read(16))
            scale=(flags >> 16) & 0xFF
            value=(hi << 64) | (mid << 32) | lo
            return (-1 if flags & 0x80000000 else 1) * value / (10 ** scale)
        if prim == 17: return None
        if prim == 18: return self.str()
        raise NrbfError(f"Unsupported primitive type: {prim} at {self.f.tell()}")

    def primitive_array(self, prim, length):
        formats = {1:'?',2:'B',6:'d',7:'h',8:'i',9:'q',10:'b',11:'f',12:'q',13:'q',14:'H',15:'I',16:'Q'}
        if prim in formats:
            fmt=formats[prim]
            count=struct.calcsize('<'+fmt)
            raw=self.read(count * length)
            return [x[0] for x in struct.iter_unpack('<'+fmt, raw)]
        return [self.primitive(prim) for _ in range(length)]

    def type_info(self, types):
        extra=[]
        for kind in types:
            if kind in (0,7): extra.append(self.u8())
            elif kind == 3: extra.append(self.str())
            elif kind == 4: extra.append((self.str(), self.i32()))
            elif kind in (1,2,5,6): extra.append(None)
            else: raise NrbfError(f"Unknown BinaryType {kind}")
        return extra

    def read_members(self, obj, names, types, extra):
        for name,kind,aux in zip(names,types,extra):
            if kind == 0:
                obj[name] = self.primitive(aux)
            else:
                obj[name] = self.record()

    def class_full(self, system):
        object_id = self.i32()
        classname = self.str()
        count = self.i32()
        if not 0 <= count <= 10000: raise NrbfError('Invalid class member count')
        names = [self.str() for _ in range(count)]
        types = list(self.read(count))
        extra = self.type_info(types)
        if not system: self.i32() # library id
        self.metadata[object_id]=(classname,names,types,extra)
        obj={'__class__':classname}
        self.objects[object_id]=obj
        self.read_members(obj,names,types,extra)
        return obj

    def class_with_id(self):
        object_id=self.i32()
        meta_id=self.i32()
        if meta_id not in self.metadata:
            raise NrbfError(f"Unknown class metadata ID {meta_id}")
        classname,names,types,extra=self.metadata[meta_id]
        obj={'__class__':classname}
        self.objects[object_id]=obj
        self.read_members(obj,names,types,extra)
        return obj

    def read_array(self, object_id, count, typ, aux=None):
        if not 0 <= count <= self.MAX_ITEMS:
            raise NrbfError(f"Invalid array length {count}")
        result=[]
        self.objects[object_id]=result
        # BinaryType.PrimitiveArray (7) contains array records, not raw scalars.
        # Only BinaryType.Primitive (0) can be decoded as a flat primitive block.
        if typ==0:
            result.extend(self.primitive_array(aux,count))
        else:
            while len(result)<count:
                value=self.record()
                if isinstance(value,NullRun):
                    if value.count > count-len(result):
                        raise NrbfError('Null run exceeds remaining array length')
                    result.extend([None]*value.count)
                else:
                    result.append(value)
        return result

    def binary_array(self):
        oid=self.i32()
        array_kind=self.u8()
        rank=self.i32()
        if not 1 <= rank <= 8: raise NrbfError('Invalid array rank')
        shape=[self.i32() for _ in range(rank)]
        if array_kind in (3,4,5):
            offsets=[self.i32() for _ in range(rank)]
        if array_kind > 5: raise NrbfError('Invalid array kind')
        count=1
        for n in shape:
            if n<0: raise NrbfError('Negative array size')
            count *= n
            if count>self.MAX_ITEMS: raise NrbfError('Array too long')
        typ=self.u8()
        aux=self.type_info([typ])[0]
        return self.read_array(oid,count,typ,aux)

    def record(self):
        while True:
            self.record_count += 1
            if self.record_count > 1_000_000: raise NrbfError('Too many records')
            opcode=self.u8()
            if opcode == 12:
                libid=self.i32(); self.libraries[libid]=self.str(); continue
            if opcode == 0:
                root=self.i32(); header=self.i32(); major=self.i32(); minor=self.i32()
                if (major, minor)!=(1,0): raise NrbfError(f"Unknown stream version {major}.{minor}")
                return ('HEADER',root)
            if opcode == 1: return self.class_with_id()
            if opcode == 4: return self.class_full(True)
            if opcode == 5: return self.class_full(False)
            if opcode == 6:
                oid=self.i32(); value=self.str(); self.objects[oid]=value; return value
            if opcode == 7: return self.binary_array()
            if opcode == 8: return self.primitive(self.u8())
            if opcode == 9: return Ref(self.i32())
            if opcode == 10: return None
            if opcode == 11: return ('END',)
            if opcode in (13,14):
                count=self.u8() if opcode==13 else self.i32()
                if count <= 0: raise NrbfError('Null run must have positive length')
                return NullRun(count)
            if opcode == 15:
                oid=self.i32(); length=self.i32(); prim=self.u8()
                return self.read_array(oid,length,0,prim)
            if opcode in (16,17):
                return self.read_array(self.i32(),self.i32(),2)
            if opcode in (2,3):
                raise NrbfError(f"Old-style classes (record {opcode}) not supported yet")
            raise NrbfError(f"Unsupported NRBF record {opcode} at byte {self.f.tell()-1}")

    def parse(self):
        first=self.record()
        if not isinstance(first,tuple) or len(first)!=2 or first[0]!='HEADER':
            raise NrbfError('Not an NRBF stream')
        rid=first[1]
        while True:
            rec=self.record()
            if isinstance(rec,tuple) and rec[0]=='END': break
        if rid not in self.objects:
            raise NrbfError(f'Missing root object {rid}')
        return self.objects[rid]


def all_streams(source):
    """Read consecutive BinaryFormatter streams from a NOVA file."""
    output=[]
    with open(source,'rb') as f:
        while True:
            where=f.tell()
            if f.read(1)==b'':break
            f.seek(where)
            reader=Reader(f)
            obj=reader.parse()
            output.append((obj,reader))
            if len(output)>10:raise NrbfError('Too many NRBF streams')
    return output


def deref(value, objects):
    """Resolve a one-hop .NET MemberReference; do not materialize cyclic graphs."""
    if isinstance(value,Ref):
        return objects.get(value.target)
    return value

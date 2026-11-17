import portable_paths as _portable
"""Development-only backing storage for inactive pooled actor initialization.
Declared ENE records and encounter metadata remain unchanged. Added rows are
outside the declared count. Resource selection and gameplay still need testing.
"""
import struct,hashlib
STRIDE=0x70
def extend_pool_storage(data,capacity):
 original=bytes(data)
 if type(capacity) is not int or not 1<=capacity<=64:raise ValueError('Unverified capacity range')
 if len(original)<32:raise ValueError('Truncated ENE header')
 count=struct.unpack_from('<H',original,2)[0];offset=struct.unpack_from('<I',original,4)[0]
 if offset!=32:raise ValueError('Unsupported record offset')
 if len(original)!=offset+count*STRIDE:raise ValueError('Auxiliary data or pre-existing storage requires separate audit')
 if struct.unpack_from('<H',original,0x12)[0]!=0:raise ValueError('Auxiliary ENE records require separate audit')
 if capacity<=count:return original,dict(changed=False,declared_records=count,backing_records=count)
 row=original[offset:offset+STRIDE] if count else bytes(STRIDE)
 result=original+row*(capacity-count)
 assert result[:len(original)]==original
 assert struct.unpack_from('<H',result,2)[0]==count
 for i in range(capacity):assert offset+i*STRIDE+16<=len(result)
 return result,dict(changed=True,declared_records=count,backing_records=capacity,additional_bytes=len(result)-len(original),original_payload_preserved=True,declared_count_preserved=True,source_sha256=hashlib.sha256(original).hexdigest(),output_sha256=hashlib.sha256(result).hexdigest(),gameplay_verified=False)

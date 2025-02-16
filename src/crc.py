def crc16(data: bytes) -> bytes:
    crc = 0xFFFF
    for n in range(len(data)):
        crc ^= data[n]
        for i in range(8):
            if crc & 1:
                crc >>= 1
                crc ^= 0xA001
            else:
                crc >>= 1
    return crc.to_bytes(2, 'little')
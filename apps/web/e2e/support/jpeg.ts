// Reads width and height from the first JPEG inside a buffer (e.g. a multipart body).
export function jpegSize(buffer: Buffer): { width: number; height: number } | null {
  let offset = buffer.indexOf(Buffer.from([0xff, 0xd8, 0xff]));
  if (offset < 0) return null;
  offset += 2;
  while (offset + 9 < buffer.length) {
    if (buffer[offset] !== 0xff) return null;
    const marker = buffer[offset + 1];
    const length = buffer.readUInt16BE(offset + 2);
    // SOF0..SOF15 except DHT (C4), JPG (C8), DAC (CC) carry the frame size.
    if (marker >= 0xc0 && marker <= 0xcf && ![0xc4, 0xc8, 0xcc].includes(marker)) {
      return { height: buffer.readUInt16BE(offset + 5), width: buffer.readUInt16BE(offset + 7) };
    }
    offset += 2 + length;
  }
  return null;
}

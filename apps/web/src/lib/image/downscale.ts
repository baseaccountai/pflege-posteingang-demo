// Photos are prepared in the browser before the upload (F02-AC3): at most 2000 px on the
// long edge, EXIF orientation applied, sent as JPEG with quality 0.85. Phone photos (often
// 4000 × 3000, 3–8 MB) then fit the 4 MB limit and OCR gets an upright page.
// PDFs are sent unchanged; anything the browser cannot decode is passed on as it is, so the
// server's content check rejects it with a clear message.

export const MAX_EDGE = 2000;
export const JPEG_QUALITY = 0.85;

type Size = { width: number; height: number };
type Bitmap = Size & { close(): void };

/** Browser parts behind an interface, so the logic is testable without a real canvas. */
export type ImageCodec = {
  decode(file: Blob, options: { imageOrientation: "from-image" }): Promise<Bitmap>;
  encode(bitmap: Bitmap, size: Size, type: "image/jpeg", quality: number): Promise<Blob>;
};

export function targetSize(width: number, height: number): Size {
  const scale = Math.min(1, MAX_EDGE / Math.max(width, height));
  return { width: Math.round(width * scale), height: Math.round(height * scale) };
}

export const browserCodec: ImageCodec = {
  // imageOrientation "from-image" turns the pixels as the EXIF tag says.
  decode: (file, options) => createImageBitmap(file, options),
  encode: async (bitmap, size, type, quality) => {
    const canvas = new OffscreenCanvas(size.width, size.height);
    const context = canvas.getContext("2d");
    if (!context) throw new Error("no 2d context");
    context.drawImage(bitmap as unknown as CanvasImageSource, 0, 0, size.width, size.height);
    return canvas.convertToBlob({ type, quality });
  },
};

export async function prepareUpload(file: File, codec: ImageCodec = browserCodec): Promise<File> {
  if (!file.type.startsWith("image/")) return file;
  let bitmap: Bitmap;
  try {
    bitmap = await codec.decode(file, { imageOrientation: "from-image" });
  } catch {
    return file;
  }
  try {
    const blob = await codec.encode(bitmap, targetSize(bitmap.width, bitmap.height), "image/jpeg", JPEG_QUALITY);
    const name = file.name.replace(/\.[^.]+$/, "") + ".jpg";
    return new File([blob], name, { type: "image/jpeg" });
  } finally {
    bitmap.close();
  }
}

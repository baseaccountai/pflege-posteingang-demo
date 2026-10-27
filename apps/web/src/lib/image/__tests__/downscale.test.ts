// F02-AC3: photos are made smaller in the browser (≤ 2000 px, EXIF orientation, JPEG 0.85).
import { describe, expect, it, vi } from "vitest";

import { prepareUpload, targetSize, type ImageCodec } from "../downscale";

describe("targetSize", () => {
  it("shrinks the long edge to 2000 px and keeps the aspect ratio", () => {
    expect(targetSize(4000, 3000)).toEqual({ width: 2000, height: 1500 });
    expect(targetSize(3000, 4000)).toEqual({ width: 1500, height: 2000 });
    expect(targetSize(4032, 3024)).toEqual({ width: 2000, height: 1500 });
  });

  it("never enlarges a small image", () => {
    expect(targetSize(1000, 800)).toEqual({ width: 1000, height: 800 });
    expect(targetSize(2000, 10)).toEqual({ width: 2000, height: 10 });
  });
});

function fakeCodec(width: number, height: number) {
  const bitmap = { width, height, close: vi.fn() };
  return {
    bitmap,
    codec: {
      decode: vi.fn().mockResolvedValue(bitmap),
      encode: vi.fn().mockResolvedValue(new Blob(["jpeg-bytes"], { type: "image/jpeg" })),
    } satisfies ImageCodec,
  };
}

describe("prepareUpload", () => {
  it("decodes with the EXIF orientation applied and sends a JPEG with quality 0.85", async () => {
    const { codec, bitmap } = fakeCodec(4000, 3000);
    const photo = new File(["raw"], "IMG_0001.HEIC.jpg", { type: "image/jpeg" });
    const result = await prepareUpload(photo, codec);

    expect(codec.decode).toHaveBeenCalledWith(photo, { imageOrientation: "from-image" });
    expect(codec.encode).toHaveBeenCalledWith(bitmap, { width: 2000, height: 1500 }, "image/jpeg", 0.85);
    expect(result.type).toBe("image/jpeg");
    expect(result.name).toBe("IMG_0001.HEIC.jpg".replace(/\.[^.]+$/, "") + ".jpg");
    expect(bitmap.close).toHaveBeenCalled();
  });

  it("also converts a PNG to JPEG", async () => {
    const { codec } = fakeCodec(800, 600);
    const result = await prepareUpload(new File(["x"], "scan.png", { type: "image/png" }), codec);
    expect(result.name).toBe("scan.jpg");
    expect(codec.encode).toHaveBeenCalledWith(expect.anything(), { width: 800, height: 600 }, "image/jpeg", 0.85);
  });

  it("passes a PDF through untouched", async () => {
    const { codec } = fakeCodec(1, 1);
    const pdf = new File(["%PDF"], "brief.pdf", { type: "application/pdf" });
    expect(await prepareUpload(pdf, codec)).toBe(pdf);
    expect(codec.decode).not.toHaveBeenCalled();
  });

  it("passes files it cannot decode through, so the server check can reject them", async () => {
    const codec = { decode: vi.fn().mockRejectedValue(new Error("no image")), encode: vi.fn() };
    const odd = new File(["?"], "notiz.txt", { type: "text/plain" });
    expect(await prepareUpload(odd, codec)).toBe(odd);
  });
});

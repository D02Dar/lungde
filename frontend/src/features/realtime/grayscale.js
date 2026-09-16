"use strict";

export function toGrayscale(imageData) {
  const source = imageData.data || imageData;
  const grayscale = new Uint8Array(source.length / 4);
  for (let pixel = 0, index = 0; index < source.length; index += 4, pixel += 1) {
    grayscale[pixel] = Math.round(0.299 * source[index] + 0.587 * source[index + 1] + 0.114 * source[index + 2]);
  }
  return grayscale;
}

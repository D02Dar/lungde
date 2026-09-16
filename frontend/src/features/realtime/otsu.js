"use strict";

export function otsuThreshold(grayscale) {
  if (!grayscale?.length) return 0;
  const histogram = new Uint32Array(256);
  let totalSum = 0;
  for (const value of grayscale) {
    histogram[value] += 1;
    totalSum += value;
  }
  let backgroundWeight = 0;
  let backgroundSum = 0;
  let bestThreshold = 0;
  let bestVariance = -1;
  for (let threshold = 0; threshold < 256; threshold += 1) {
    backgroundWeight += histogram[threshold];
    if (!backgroundWeight) continue;
    const foregroundWeight = grayscale.length - backgroundWeight;
    if (!foregroundWeight) break;
    backgroundSum += threshold * histogram[threshold];
    const backgroundMean = backgroundSum / backgroundWeight;
    const foregroundMean = (totalSum - backgroundSum) / foregroundWeight;
    const between = backgroundWeight * foregroundWeight * (backgroundMean - foregroundMean) ** 2;
    if (between > bestVariance) {
      bestVariance = between;
      bestThreshold = threshold;
    }
  }
  return bestThreshold;
}

export function countSubjectPixels(grayscale, threshold, polarity = "dark", width = null, height = null) {
  if (!width || !height || width * height !== grayscale.length) {
    let count = 0;
    const dark = polarity !== "light";
    for (const value of grayscale) {
      if (dark ? value <= threshold : value > threshold) count += 1;
    }
    return count;
  }

  const largest = segmentSubjectMask(grayscale, threshold, polarity, width, height);

  let count = 0;
  for (const value of largest) {
    if (value) count += 1;
  }
  return count;
}

export function measureSubjectSignal(grayscale, threshold, polarity = "dark", width = null, height = null) {
  if (!width || !height || width * height !== grayscale.length) {
    return { value: countSubjectPixels(grayscale, threshold, polarity), method: "threshold_pixel_count" };
  }
  const largest = segmentSubjectMask(grayscale, threshold, polarity, width, height);
  if (polarity !== "light") {
    let value = 0;
    for (const pixel of largest) if (pixel) value += 1;
    return { value, method: "dark_component_area" };
  }

  // The Position guide anchors the back on the right. For white clothing,
  // measure from the anterior/left contour to that fixed anchor so a bright
  // arm joining the rear of the shirt cannot inflate the breathing signal.
  let value = 0;
  for (let y = 0; y < height; y += 1) {
    const row = y * width;
    for (let x = 0; x < width; x += 1) {
      if (!largest[row + x]) continue;
      value += width - x;
      break;
    }
  }
  return { value, method: "light_front_contour" };
}

export function segmentSubjectMask(grayscale, threshold, polarity, width, height) {
  const binary = new Uint8Array(grayscale.length);
  const dark = polarity !== "light";
  for (let i = 0; i < grayscale.length; i += 1) {
    binary[i] = (dark ? grayscale[i] <= threshold : grayscale[i] > threshold) ? 255 : 0;
  }
  const morphed = morphologyClose(binary, width, height, 3);
  const opened = morphologyOpen(morphed, width, height, 3);
  return extractLargestComponent(opened, width, height);
}

function morphologyClose(binary, width, height, radius) {
  const dilated = dilate(binary, width, height, radius);
  return erode(dilated, width, height, radius);
}

function morphologyOpen(binary, width, height, radius) {
  const eroded = erode(binary, width, height, radius);
  return dilate(eroded, width, height, radius);
}

function dilate(binary, width, height, radius) {
  const output = new Uint8Array(binary.length);
  for (let y = 0; y < height; y += 1) {
    for (let x = 0; x < width; x += 1) {
      let maxVal = 0;
      for (let dy = -radius; dy <= radius; dy += 1) {
        for (let dx = -radius; dx <= radius; dx += 1) {
          if (dx * dx + dy * dy > radius * radius) continue;
          const ny = y + dy, nx = x + dx;
          if (ny >= 0 && ny < height && nx >= 0 && nx < width) {
            maxVal = Math.max(maxVal, binary[ny * width + nx]);
          }
        }
      }
      output[y * width + x] = maxVal;
    }
  }
  return output;
}

function erode(binary, width, height, radius) {
  const output = new Uint8Array(binary.length);
  for (let y = 0; y < height; y += 1) {
    for (let x = 0; x < width; x += 1) {
      let minVal = 255;
      for (let dy = -radius; dy <= radius; dy += 1) {
        for (let dx = -radius; dx <= radius; dx += 1) {
          if (dx * dx + dy * dy > radius * radius) continue;
          const ny = y + dy, nx = x + dx;
          if (ny >= 0 && ny < height && nx >= 0 && nx < width) {
            minVal = Math.min(minVal, binary[ny * width + nx]);
          }
        }
      }
      output[y * width + x] = minVal;
    }
  }
  return output;
}

function extractLargestComponent(binary, width, height) {
  const labels = new Int32Array(binary.length);
  const areas = [];
  let nextLabel = 1;

  for (let y = 0; y < height; y += 1) {
    for (let x = 0; x < width; x += 1) {
      const idx = y * width + x;
      if (binary[idx] && !labels[idx]) {
        const area = floodFill(binary, labels, width, height, x, y, nextLabel);
        areas.push({ label: nextLabel, area });
        nextLabel += 1;
      }
    }
  }

  if (areas.length === 0) return new Uint8Array(binary.length);

  const largest = areas.reduce((a, b) => a.area > b.area ? a : b);
  const output = new Uint8Array(binary.length);
  for (let i = 0; i < labels.length; i += 1) {
    output[i] = labels[i] === largest.label ? 255 : 0;
  }
  return output;
}

function floodFill(binary, labels, width, height, startX, startY, label) {
  const stack = [[startX, startY]];
  let area = 0;
  while (stack.length) {
    const [x, y] = stack.pop();
    const idx = y * width + x;
    if (x < 0 || x >= width || y < 0 || y >= height) continue;
    if (!binary[idx] || labels[idx]) continue;
    labels[idx] = label;
    area += 1;
    stack.push([x + 1, y], [x - 1, y], [x, y + 1], [x, y - 1]);
  }
  return area;
}

"use strict";

import { toGrayscale } from "../realtime/grayscale.js";
import { otsuThreshold } from "../realtime/otsu.js";

export const SILHOUETTE_DEFAULTS = Object.freeze({
  minimumContrast: 24,
  minimumBandOccupancy: 0.08,
  maximumBandOccupancy: 0.88,
  maximumTopContact: 0.28,
  maximumBottomContact: 0.42,
  maximumFrontContact: 0.48,
});

export function evaluatePositionSilhouette(imageData, options = {}) {
  const settings = { ...SILHOUETTE_DEFAULTS, ...options };
  const width = Number(imageData?.width) || 0;
  const height = Number(imageData?.height) || 0;
  if (!width || !height || !imageData?.data?.length) return failure("no_signal");

  const grayscale = toGrayscale(imageData);
  const threshold = otsuThreshold(grayscale);
  const candidates = ["dark", "light"].map((polarity) => evaluatePolarity(
    grayscale,
    width,
    height,
    threshold,
    polarity,
    settings,
  ));
  const passing = candidates.filter((candidate) => candidate.pass);
  return [...(passing.length ? passing : candidates)].sort((a, b) => a.selectionPenalty - b.selectionPenalty)[0];
}

function evaluatePolarity(grayscale, width, height, threshold, polarity, settings) {
  const mask = new Uint8Array(grayscale.length);
  let subjectSum = 0, subjectCount = 0, backgroundSum = 0, backgroundCount = 0;
  for (let index = 0; index < grayscale.length; index += 1) {
    const subject = polarity === "dark" ? grayscale[index] <= threshold : grayscale[index] > threshold;
    mask[index] = subject ? 1 : 0;
    if (subject) { subjectSum += grayscale[index]; subjectCount += 1; }
    else { backgroundSum += grayscale[index]; backgroundCount += 1; }
  }
  if (!subjectCount || !backgroundCount) return failure("no_signal", { threshold, polarity, selectionPenalty: Number.POSITIVE_INFINITY });
  const subjectMean = subjectSum / subjectCount;
  const backgroundMean = backgroundSum / backgroundCount;
  const contrast = polarity === "dark" ? backgroundMean - subjectMean : subjectMean - backgroundMean;

  const bands = [
    bandRatio(mask, width, height, 0, .18),
    bandRatio(mask, width, height, .18, .43),
    bandRatio(mask, width, height, .43, .76),
    bandRatio(mask, width, height, .76, 1),
  ];
  const edge = {
    top: edgeRatio(mask, width, height, "top"),
    bottom: edgeRatio(mask, width, height, "bottom"),
    left: edgeRatio(mask, width, height, "left"),
    right: edgeRatio(mask, width, height, "right"),
  };
  const frontContact = edge.left;
  const occupancy = subjectCount / grayscale.length;
  const selectionPenalty = polarityPenalty({ contrast, bands, edge, occupancy }, settings);
  const details = { threshold, polarity, contrast, bands, edge, occupancy, selectionPenalty };
  if (contrast < settings.minimumContrast) return failure("low_contrast", details);
  if (bands.some((ratio) => ratio < settings.minimumBandOccupancy)) return failure("incomplete_silhouette", details);
  if (bands.some((ratio) => ratio > settings.maximumBandOccupancy)) return failure("box_too_tight", details);
  if (edge.top > settings.maximumTopContact) return failure("head_cropped", details);
  if (edge.bottom > settings.maximumBottomContact) return failure("waist_cropped", details);
  if (frontContact > settings.maximumFrontContact) return failure("front_cropped", details);

  return {
    status: "pass",
    pass: true,
    reason: "ok",
    ...details,
  };
}

function polarityPenalty({ contrast, bands, edge, occupancy }, settings) {
  const contrastPenalty = Math.max(0, settings.minimumContrast - contrast) / settings.minimumContrast;
  const bandPenalty = bands.reduce((sum, ratio) => (
    sum
    + Math.max(0, settings.minimumBandOccupancy - ratio) / settings.minimumBandOccupancy
    + Math.max(0, ratio - settings.maximumBandOccupancy) / (1 - settings.maximumBandOccupancy)
  ), 0);
  const edgePenalty = (
    Math.max(0, edge.top - settings.maximumTopContact) / settings.maximumTopContact
    + Math.max(0, edge.bottom - settings.maximumBottomContact) / settings.maximumBottomContact
    + Math.max(0, edge.left - settings.maximumFrontContact) / settings.maximumFrontContact
  );
  const borderContact = (edge.top + edge.bottom + edge.left + edge.right) / 4;
  return contrastPenalty + bandPenalty + edgePenalty + borderContact + Math.abs(occupancy - 0.42) * 0.1;
}

function failure(reason, details = {}) {
  return { status: "fail", pass: false, reason, contrast: null, bands: [], edge: {}, ...details };
}

function bandRatio(mask, width, height, startRatio, endRatio) {
  const start = Math.max(0, Math.floor(height * startRatio));
  const end = Math.min(height, Math.max(start + 1, Math.ceil(height * endRatio)));
  let count = 0;
  for (let y = start; y < end; y += 1) {
    const row = y * width;
    for (let x = 0; x < width; x += 1) count += mask[row + x];
  }
  return count / ((end - start) * width);
}

function edgeRatio(mask, width, height, edge) {
  const thickness = Math.max(1, Math.round(Math.min(width, height) * .025));
  let count = 0, total = 0;
  if (edge === "top" || edge === "bottom") {
    const start = edge === "top" ? 0 : height - thickness;
    const end = edge === "top" ? thickness : height;
    for (let y = start; y < end; y += 1) for (let x = 0; x < width; x += 1) { count += mask[y * width + x]; total += 1; }
  } else {
    const start = edge === "left" ? 0 : width - thickness;
    const end = edge === "left" ? thickness : width;
    for (let y = 0; y < height; y += 1) for (let x = start; x < end; x += 1) { count += mask[y * width + x]; total += 1; }
  }
  return total ? count / total : 0;
}

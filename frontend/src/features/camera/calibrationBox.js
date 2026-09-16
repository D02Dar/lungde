"use strict";
// Ratios are relative to the operator-adjusted head-to-waist frame. Keeping one
// versioned default makes records comparable while frame resizing absorbs
// differences in camera distance and body size. New postures need validated
// profiles instead of silently changing these values.
export const DEFAULT_ROI_PROFILE = Object.freeze({
  id: "standing-side-upper-body-v1",
  defaultBox: Object.freeze({ x: 0.28, y: 0.07, width: 0.48, height: 0.78 }),
  minimumBox: Object.freeze({ width: 0.34, height: 0.38 }),
  chest: Object.freeze({ topOffset: 0.22, height: 0.55 }),
  offlineSearch: Object.freeze({ width: 0.34, height: 0.18, leftOffset: 0.33, topOffset: 0.10 }),
});
export const DEFAULT_BOX = DEFAULT_ROI_PROFILE.defaultBox;
export const MIN_WIDTH = DEFAULT_ROI_PROFILE.minimumBox.width;
export const MIN_HEIGHT = DEFAULT_ROI_PROFILE.minimumBox.height;
export const CHEST_TOP_OFFSET = DEFAULT_ROI_PROFILE.chest.topOffset;
export const CHEST_HEIGHT_RATIO = DEFAULT_ROI_PROFILE.chest.height;
export const CHEST_ROI_HEURISTIC_VERSION = "upper-body-fixed-22-55-v1";
export const OFFLINE_ROI_HEURISTIC_VERSION = "upper-body-chest-area-v1";
export const ROI_CONTRACT_VERSION = "went-roi-v2";

export function clampBox(box) {
  const width = Math.max(MIN_WIDTH, Math.min(1, Number(box.width) || DEFAULT_BOX.width));
  const height = Math.max(MIN_HEIGHT, Math.min(1, Number(box.height) || DEFAULT_BOX.height));
  return {
    x: Math.max(0, Math.min(1 - width, Number(box.x) || 0)),//limit the x value to be within the range of 0 to 1 - width, ensuring that the box does not extend beyond the right edge of the frame
    y: Math.max(0, Math.min(1 - height, Number(box.y) || 0)),
    width, height,
  };
}

export function resizeBoxFromCorner(box, corner, deltaX, deltaY) {
  const safe = clampBox(box);
  let left = safe.x;
  let right = safe.x + safe.width;
  let top = safe.y;
  let bottom = safe.y + safe.height;
  if (corner.includes("w")) left = Math.max(0, Math.min(right - MIN_WIDTH, left + deltaX));
  if (corner.includes("e")) right = Math.min(1, Math.max(left + MIN_WIDTH, right + deltaX));
  if (corner.includes("n")) top = Math.max(0, Math.min(bottom - MIN_HEIGHT, top + deltaY));
  if (corner.includes("s")) bottom = Math.min(1, Math.max(top + MIN_HEIGHT, bottom + deltaY));
  return clampBox({ x: left, y: top, width: right - left, height: bottom - top });
}

export function deriveChestRoi(box) {
  const safe = clampBox(box);
  const y = safe.y + safe.height * CHEST_TOP_OFFSET;
  const height = safe.height * CHEST_HEIGHT_RATIO;
  return {
    x: safe.x,
    y: Math.max(0, Math.min(1 - height, y)),
    width: safe.width,
    height,
  };
}
//  positioned towards the top-left corner, with a fixed width and height ratio relative to the evidence box
export function deriveOfflineSearchRoi(box) {
  const safe = clampBox(box);
  const rule = DEFAULT_ROI_PROFILE.offlineSearch;
  const width = safe.width * rule.width;
  const height = safe.height * rule.height;
  return {
    x: Math.max(safe.x, Math.min(safe.x + safe.width - width, safe.x + safe.width * rule.leftOffset)),
    y: Math.max(safe.y, Math.min(safe.y + safe.height - height, safe.y + safe.height * rule.topOffset)),
    width,
    height,
  };
}
// Build a complete ROI contract for the current operator box, including derived chest and offline search ROIs, frame dimensions, and position quality status
export function buildRoiContract(box, frameWidth, frameHeight, positionQuality = {}) {
  const operatorRoi = clampBox(box);
  return {
    roi: operatorRoi,
    operator_roi: operatorRoi,
    realtime_chest_roi: deriveChestRoi(operatorRoi),
    offline_search_roi: deriveOfflineSearchRoi(operatorRoi),
    frame_width: frameWidth,
    frame_height: frameHeight,
    mirrored: false,
    roi_contract_version: ROI_CONTRACT_VERSION,
    roi_profile_id: DEFAULT_ROI_PROFILE.id,
    position_quality: { status: "locked", ...positionQuality },
    chest_roi_rule: CHEST_ROI_HEURISTIC_VERSION,
    offline_roi_rule: OFFLINE_ROI_HEURISTIC_VERSION,
  };
}
//像素归一化，将box的值转换为像素值
export function pixelRoi(box, videoWidth, videoHeight) {
  const width = Math.max(0, Math.min(1, Number(box?.width) || 0));
  const height = Math.max(0, Math.min(1, Number(box?.height) || 0));
  const x = Math.max(0, Math.min(1 - width, Number(box?.x) || 0));
  const y = Math.max(0, Math.min(1 - height, Number(box?.y) || 0));
  return {
    x: Math.round(x * videoWidth), y: Math.round(y * videoHeight),
    width: Math.max(1, Math.round(width * videoWidth)), height: Math.max(1, Math.round(height * videoHeight)),
  };
}

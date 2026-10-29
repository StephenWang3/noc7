/* 工作台 postMessage 只接受本页来源，或 NOC7_WORKBENCH_ORIGINS 里写明的来源。 */
function noc7AcceptOrigin(eventOrigin, pageOrigin, extraCsv) {
  if (!eventOrigin || !pageOrigin) return false;
  if (eventOrigin === pageOrigin) return true;
  const extra = String(extraCsv || "").split(",").map((s) => s.trim()).filter(Boolean);
  return extra.indexOf(eventOrigin) !== -1;
}

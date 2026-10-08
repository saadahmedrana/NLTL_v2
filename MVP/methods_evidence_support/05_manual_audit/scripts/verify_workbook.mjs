import fs from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const auditRoot = new URL("../", import.meta.url);
const original = await SpreadsheetFile.importXlsx(await FileBlob.load(fileURLToPath(new URL("originals/NLTL_Manual_Audit.xlsx", auditRoot))));
const ready = await SpreadsheetFile.importXlsx(await FileBlob.load(fileURLToPath(new URL("NLTL_Manual_Audit_ready.xlsx", auditRoot))));

function sameRange(sheetName, address) {
  const left = original.worksheets.getItem(sheetName).getRange(address);
  const right = ready.worksheets.getItem(sheetName).getRange(address);
  if (JSON.stringify(left.values) !== JSON.stringify(right.values)) throw new Error(`Values changed unexpectedly: ${sheetName}!${address}`);
  if (JSON.stringify(left.formulas) !== JSON.stringify(right.formulas)) throw new Error(`Formulas changed unexpectedly: ${sheetName}!${address}`);
}

for (const [sheet, range] of [
  ["Guide", "A1:B27"], ["Rubric", "A1:G40"], ["Results", "A1:H38"],
  ["Batches", "A1:G33"], ["CaseReview", "A1:V2192"],
  ["RawResults", "A1:V6564"], ["RequirementScores", "A1:J810"],
]) sameRange(sheet, range);
for (const sheet of ["V2", "NoSemantic", "SingleShot"]) {
  sameRange(sheet, "A1:E274");
  sameRange(sheet, "W1:AL274");
}

const results = ready.worksheets.getItem("Results").getRange("A6:H12").values;
const expected = {
  V2_FALLBACK25: [1612, 0.737419945105215, 0.8021100753212255, 118, 108, 259, 207],
  NO_SEMANTIC: [1513, 0.692131747483989, 0.7577577494186881, 115, 81, 386, 206],
  SINGLESHOT: [1349, 0.6171088746569076, 0.6813994343354124, 98, 78, 352, 407],
};
for (const row of results) {
  if (expected[row[0]] && JSON.stringify(row.slice(1)) !== JSON.stringify(expected[row[0]])) {
    throw new Error(`Baseline changed: ${row[0]} ${JSON.stringify(row.slice(1))}`);
  }
}
const statuses = ready.worksheets.getItem("Batches").getRange("H7:H33").values.flat();
if (statuses.some((value) => value !== "PACKAGED")) throw new Error("Not every batch is marked PACKAGED");

const errors = await ready.inspect({
  kind: "match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!",
  options: { useRegex: true, maxResults: 300 },
  summary: "final formula error scan",
});
console.log(errors.ndjson);

for (const [sheetName, range, name] of [
  ["Batches", "A1:H33", "qa_ready_batches.png"],
  ["V2", "A1:AP16", "qa_ready_v2.png"],
  ["NoSemantic", "A1:AP16", "qa_ready_no_semantic.png"],
  ["SingleShot", "A1:AP16", "qa_ready_singleshot.png"],
  ["Results", "A1:H38", "qa_ready_results.png"],
]) {
  const preview = await ready.render({ sheetName, range, autoCrop: "all", scale: 1.2, format: "png" });
  await fs.writeFile(new URL(name, import.meta.url), new Uint8Array(await preview.arrayBuffer()));
}
console.log(JSON.stringify({ preservedRanges: 13, baselineResultsPreserved: true, batchStatuses: 27, renderedViews: 5 }));

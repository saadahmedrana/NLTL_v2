import fs from "node:fs/promises";
import path from "node:path";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const batchRoot = path.resolve(process.argv[2]);
const workbookPath = path.join(batchRoot, "batch01_vocabulary_and_fixture_tracker.xlsx");
const previewRoot = path.join(batchRoot, "validation", "workbook_previews");
await fs.mkdir(previewRoot, { recursive: true });
const workbook = await SpreadsheetFile.importXlsx(await FileBlob.load(workbookPath));

const overview = await workbook.inspect({
  kind: "workbook,sheet,table", maxChars: 12000, tableMaxRows: 8, tableMaxCols: 14, tableMaxCellChars: 120,
});
const errors = await workbook.inspect({
  kind: "match", searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",
  options: { useRegex: true, maxResults: 300 }, summary: "final formula error scan",
});
const specs = [
  ["SUMMARY", "A1:D20"], ["README", "A1:B15"], ["REQUIREMENTS", "A1:O20"],
  ["PREFLIGHT", "A1:K18"], ["DRAFT_TERMS", "A1:E28"], ["R2_INDEX_GAPS", "A1:D28"],
  ["DEVELOPMENT_TERMS", "A1:J22"], ["OWNERSHIP", "A1:F22"], ["STABILIZATION", "A1:E15"], ["RDF_CASES", "A1:M22"],
  ["CALIBRATION_ANALYSIS", "A1:L22"],
];
const previews = [];
for (let index = 0; index < specs.length; index += 1) {
  const [sheetName, range] = specs[index];
  const blob = await workbook.render({ sheetName, range, scale: 1, format: "png" });
  const file = `${String(index + 1).padStart(2, "0")}_${sheetName}.png`;
  await fs.writeFile(path.join(previewRoot, file), new Uint8Array(await blob.arrayBuffer()));
  previews.push({ sheetName, range, file });
}
const result = {
  workbook: workbookPath,
  overview: overview.ndjson,
  formulaErrorScan: errors.ndjson,
  previews,
};
await fs.writeFile(path.join(batchRoot, "validation", "workbook_verification.json"), JSON.stringify(result, null, 2) + "\n");
console.log(JSON.stringify({ formulaErrorScan: errors.ndjson, previews }));

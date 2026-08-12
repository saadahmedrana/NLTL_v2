import fs from "node:fs/promises";
import path from "node:path";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const [workbookPath, payloadPath, previewDirectory] = process.argv.slice(2);
if (!workbookPath || !payloadPath || !previewDirectory) {
  throw new Error("Usage: verify_tracker.mjs workbook.xlsx payload.json previews/");
}
await fs.mkdir(previewDirectory, { recursive: true });
const workbook = await SpreadsheetFile.importXlsx(await FileBlob.load(workbookPath));
const payload = JSON.parse(await fs.readFile(payloadPath, "utf8"));

const inspections = [];
inspections.push(JSON.parse((await workbook.inspect({
  kind: "workbook,sheet,table",
  maxChars: 12000,
  tableMaxRows: 8,
  tableMaxCols: 16,
  tableMaxCellChars: 120,
})).ndjson.split("\n").filter(Boolean)[0]));
const errors = await workbook.inspect({
  kind: "match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",
  options: { useRegex: true, maxResults: 300 },
  summary: "final formula error scan",
});

function columnName(index) {
  let value = index + 1;
  let result = "";
  while (value > 0) {
    const remainder = (value - 1) % 26;
    result = String.fromCharCode(65 + remainder) + result;
    value = Math.floor((value - 1) / 26);
  }
  return result;
}

const renderSpecs = [{ name: "SUMMARY", columns: 4, rows: 18 }];
for (const spec of payload.sheets) {
  renderSpecs.push({
    name: spec.name,
    columns: spec.headers.length,
    rows: Math.min(28, Math.max(6, 4 + spec.rows.length)),
  });
}
const previews = [];
for (const spec of renderSpecs) {
  const range = `A1:${columnName(spec.columns - 1)}${spec.rows}`;
  const blob = await workbook.render({ sheetName: spec.name, range, scale: 1, format: "png" });
  const filename = `${String(previews.length + 1).padStart(2, "0")}_${spec.name}.png`;
  await fs.writeFile(path.join(previewDirectory, filename), new Uint8Array(await blob.arrayBuffer()));
  previews.push({ sheet: spec.name, range, file: filename });
}
const verification = {
  workbook: workbookPath,
  formulaErrorScan: errors.ndjson,
  previews,
};
await fs.writeFile(
  path.join(previewDirectory, "verification.json"),
  JSON.stringify(verification, null, 2) + "\n",
);
console.log(JSON.stringify(verification));


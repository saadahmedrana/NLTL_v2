import fs from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const auditRoot = new URL("../", import.meta.url);
const inputPath = new URL("originals/NLTL_Manual_Audit.xlsx", auditRoot);
const workbook = await SpreadsheetFile.importXlsx(await FileBlob.load(fileURLToPath(inputPath)));

const overview = await workbook.inspect({
  kind: "workbook,sheet,table,definedName",
  maxChars: 12000,
  tableMaxRows: 8,
  tableMaxCols: 12,
  tableMaxCellChars: 100,
});
console.log(overview.ndjson);

for (const sheetName of ["Guide", "Batches", "V2", "NoSemantic", "SingleShot", "CaseReview", "RawResults", "RequirementScores", "Results"]) {
  const sheet = workbook.worksheets.getItem(sheetName);
  const used = sheet.getUsedRange();
  console.log(JSON.stringify({ sheet: sheetName, usedRange: used?.address ?? null }));
  if (used) {
    const sample = await workbook.inspect({
      kind: "table",
      sheetId: sheetName,
      range: used.address,
      include: "values,formulas",
      maxChars: sheetName === "Guide" ? 18000 : 6000,
      tableMaxRows: sheetName === "Guide" ? 60 : 10,
      tableMaxCols: 18,
      tableMaxCellChars: 180,
    });
    console.log(sample.ndjson);
  }
}

const preview = await workbook.render({ sheetName: "Guide", autoCrop: "all", scale: 1, format: "png" });
await fs.writeFile(new URL("guide_original.png", import.meta.url), new Uint8Array(await preview.arrayBuffer()));

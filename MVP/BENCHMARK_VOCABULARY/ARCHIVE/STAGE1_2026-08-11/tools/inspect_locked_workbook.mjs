import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const source = process.argv[2];
if (!source) throw new Error("Usage: node inspect_locked_workbook.mjs workbook.xlsx");
const wb = await SpreadsheetFile.importXlsx(await FileBlob.load(source));
const summary = await wb.inspect({
  kind: "workbook,sheet,table",
  maxChars: 20000,
  tableMaxRows: 12,
  tableMaxCols: 16,
  tableMaxCellChars: 240,
});
console.log(summary.ndjson);
for (const sheet of wb.worksheets.items) {
  const used = sheet.getUsedRange(true);
  if (!used) continue;
  const region = await wb.inspect({
    kind: "region",
    sheetId: sheet.name,
    range: used.address,
    maxChars: 30000,
    tableMaxRows: 20,
    tableMaxCols: 20,
    tableMaxCellChars: 400,
  });
  console.log(region.ndjson);
}

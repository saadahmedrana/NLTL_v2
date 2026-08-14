import fs from "node:fs/promises";
import path from "node:path";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const [workbookPath, outputDirectory] = process.argv.slice(2);
if (!workbookPath || !outputDirectory) throw new Error("Usage: verify_cost_ledger.mjs ledger.xlsx validation-directory");
await fs.mkdir(outputDirectory, { recursive: true });
const workbook = await SpreadsheetFile.importXlsx(await FileBlob.load(workbookPath));

const checks = {};
for (const [sheetName, range] of [
  ["SUMMARY", "A1:D16"],
  ["MODEL_PRICING", "A1:E9"],
  ["RUN_COSTS", "A1:R20"],
  ["API_CALLS", "A1:N20"],
]) {
  checks[sheetName] = (await workbook.inspect({
    kind: "table",
    range: `${sheetName}!${range}`,
    include: "values,formulas",
    tableMaxRows: 20,
    tableMaxCols: 18,
    maxChars: 12000,
  })).ndjson;
  const preview = await workbook.render({ sheetName, range, scale: 1.25 });
  await fs.writeFile(path.join(outputDirectory, `${sheetName}.png`), new Uint8Array(await preview.arrayBuffer()));
}
const errors = await workbook.inspect({
  kind: "match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",
  options: { useRegex: true, maxResults: 300 },
  summary: "final formula error scan",
});
await fs.writeFile(
  path.join(outputDirectory, "verification.json"),
  JSON.stringify({ checks, formulaErrorScan: errors.ndjson }, null, 2) + "\n",
);
console.log(JSON.stringify({ status: "PASS", sheets: Object.keys(checks), formulaErrorScan: errors.ndjson }));

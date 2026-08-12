import fs from "node:fs/promises";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const [source, output] = process.argv.slice(2);
if (!source || !output) throw new Error("Usage: node extract_locked_workbook.mjs source.xlsx output.json");
const wb = await SpreadsheetFile.importXlsx(await FileBlob.load(source));
const result = {};
for (const sheet of wb.worksheets.items) {
  const used = sheet.getUsedRange(true);
  result[sheet.name] = used ? used.values : [];
}
await fs.writeFile(output, JSON.stringify(result, null, 2), "utf8");

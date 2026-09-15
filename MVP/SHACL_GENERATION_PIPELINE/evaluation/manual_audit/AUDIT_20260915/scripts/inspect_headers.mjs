import { fileURLToPath } from "node:url";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const path = fileURLToPath(new URL("../originals/NLTL_Manual_Audit.xlsx", import.meta.url));
const workbook = await SpreadsheetFile.importXlsx(await FileBlob.load(path));
for (const sheetName of ["V2", "NoSemantic", "SingleShot"]) {
  const result = await workbook.inspect({
    kind: "table",
    sheetId: sheetName,
    range: "A6:AP8",
    include: "values,formulas",
    maxChars: 20000,
    tableMaxRows: 3,
    tableMaxCols: 42,
    tableMaxCellChars: 200,
  });
  console.log(result.ndjson);
}

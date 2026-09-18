import fs from "node:fs";
import { Workbook, SpreadsheetFile } from "@oai/artifact-tool";

const [inputPath, outputPath, previewDir] = process.argv.slice(2);
if (!inputPath || !outputPath || !previewDir) throw new Error("usage: builder input.json output.xlsx preview-dir");
const input = JSON.parse(fs.readFileSync(inputPath, "utf8"));
const workbook = Workbook.create();

const scoring = workbook.worksheets.add("Scoring");
const headers = ["Requirement ID", "Family", "Complexity Category", "Artifact ID"];
for (const item of input.rubric) headers.push(`${item.code} Score`, `${item.code} Evidence`);
headers.push(
  "Semantic Total / 14", "Semantic-fidelity normalized score",
  "Implementation Total / 6", "Implementation-quality normalized score",
  "Critical defect", "Primary semantic verdict", "Reviewer evidence/justification",
  "Suspected benchmark/RDF fault", "Adjudication required", "Reviewer", "Review date"
);
scoring.getRangeByIndexes(0, 0, 1, headers.length).values = [headers];

const rows = input.rows.map((r) => {
  const values = [r.requirement_id, r.family, r.category, r.opaque_id];
  for (const _item of input.rubric) values.push("", "");
  values.push("", "", "", "", "", "", "", "", "", "", "");
  return values;
});
scoring.getRangeByIndexes(1, 0, rows.length, headers.length).values = rows;

const semScoreCols = [4, 6, 8, 10, 12, 14, 16];
const cqScoreCols = [18, 20, 22];
const semTotalCol = 24, semNormCol = 25, cqTotalCol = 26, cqNormCol = 27;
for (let r = 2; r <= rows.length + 1; r++) {
  const semRefs = semScoreCols.map((c) => scoring.getCell(r - 1, c).address.split("!").pop());
  const cqRefs = cqScoreCols.map((c) => scoring.getCell(r - 1, c).address.split("!").pop());
  scoring.getCell(r - 1, semTotalCol).formulas = [[`=IF(COUNT(${semRefs.join(",")})=7,SUM(${semRefs.join(",")}),"")`]];
  scoring.getCell(r - 1, semNormCol).formulas = [[`=IF(${scoring.getCell(r - 1, semTotalCol).address.split("!").pop()}="","",${scoring.getCell(r - 1, semTotalCol).address.split("!").pop()}/14)`]];
  scoring.getCell(r - 1, cqTotalCol).formulas = [[`=IF(COUNT(${cqRefs.join(",")})=3,SUM(${cqRefs.join(",")}),"")`]];
  scoring.getCell(r - 1, cqNormCol).formulas = [[`=IF(${scoring.getCell(r - 1, cqTotalCol).address.split("!").pop()}="","",${scoring.getCell(r - 1, cqTotalCol).address.split("!").pop()}/6)`]];
}

const header = scoring.getRangeByIndexes(0, 0, 1, headers.length);
header.format = { fill: "#17365D", font: { bold: true, color: "#FFFFFF" }, wrapText: true, verticalAlignment: "center" };
header.format.rowHeight = 36;
scoring.freezePanes.freezeRows(1);
scoring.freezePanes.freezeColumns(4);
scoring.getRangeByIndexes(0, 0, rows.length + 1, headers.length).format.verticalAlignment = "top";
scoring.getRangeByIndexes(1, 0, rows.length, 4).format.fill = "#EAF2F8";
for (const col of [...semScoreCols, ...cqScoreCols]) {
  const range = scoring.getRangeByIndexes(1, col, rows.length, 1);
  range.format.fill = "#FFF2CC";
  range.dataValidation = { rule: { type: "wholeNumber", operator: "between", formula1: 0, formula2: 2 } };
  range.format.columnWidth = 11;
}
for (const col of [5, 7, 9, 11, 13, 15, 17, 19, 21, 23, 30]) {
  scoring.getRangeByIndexes(1, col, rows.length, 1).format.wrapText = true;
  scoring.getRangeByIndexes(0, col, rows.length + 1, 1).format.columnWidth = col === 30 ? 34 : 25;
}
scoring.getRangeByIndexes(1, semNormCol, rows.length, 1).format.numberFormat = "0.0%";
scoring.getRangeByIndexes(1, cqNormCol, rows.length, 1).format.numberFormat = "0.0%";
scoring.getRangeByIndexes(1, 28, rows.length, 1).dataValidation = { rule: { type: "list", formula1: '"YES,NO"' } };
scoring.getRangeByIndexes(1, 29, rows.length, 1).dataValidation = { rule: { type: "list", formula1: '"CORRECT,MINOR_DEFECT,MAJOR_DEFECT,NOT_ASSESSABLE,UNCLEAR"' } };
scoring.getRangeByIndexes(1, 32, rows.length, 1).dataValidation = { rule: { type: "list", formula1: '"YES,NO"' } };
scoring.getRangeByIndexes(1, 34, rows.length, 1).format.numberFormat = "yyyy-mm-dd";
scoring.getRange("A:A").format.columnWidth = 15;
scoring.getRange("B:B").format.columnWidth = 12;
scoring.getRange("C:C").format.columnWidth = 22;
scoring.getRange("D:D").format.columnWidth = 11;
scoring.getRangeByIndexes(0, 24, rows.length + 1, 11).format.columnWidth = 18;
scoring.getRangeByIndexes(1, 28, rows.length, 7).format.fill = "#FFF2CC";
scoring.getRangeByIndexes(0, 0, rows.length + 1, headers.length).format.autofitRows();
scoring.getRangeByIndexes(0, 0, rows.length + 1, headers.length).format.borders = {
  top: { color: "#D9E2F3", style: "continuous" }, bottom: { color: "#D9E2F3", style: "continuous" },
  left: { color: "#D9E2F3", style: "continuous" }, right: { color: "#D9E2F3", style: "continuous" }
};

const rubric = workbook.worksheets.add("Rubric");
rubric.getRange("A1:D1").values = [["Code", "Criterion", "Dimension", "Score guidance"]];
rubric.getRangeByIndexes(1, 0, input.rubric.length, 4).values = input.rubric.map((r) => [r.code, r.criterion, r.dimension, "0 = absent/incorrect; 1 = partial/minor defect; 2 = complete/correct"]);
rubric.getRange("A13:B19").values = [
  ["Additional field", "Allowed value / use"],
  ["Critical defect", "YES / NO"],
  ["Primary semantic verdict", "CORRECT / MINOR_DEFECT / MAJOR_DEFECT / NOT_ASSESSABLE / UNCLEAR"],
  ["Semantic-fidelity normalized score", "Calculated as Q1–Q7 total divided by 14"],
  ["Implementation-quality normalized score", "Calculated as CQ1–CQ3 total divided by 6"],
  ["Suspected benchmark/RDF fault", "Record the suspected fault and evidence, or leave blank"],
  ["Adjudication required", "YES / NO"],
];
rubric.getRange("A1:D1").format = { fill: "#17365D", font: { bold: true, color: "#FFFFFF" } };
rubric.getRange("A13:B13").format = { fill: "#17365D", font: { bold: true, color: "#FFFFFF" } };
rubric.getRange("A1:D19").format.wrapText = true;
rubric.getRange("A:A").format.columnWidth = 20;
rubric.getRange("B:B").format.columnWidth = 42;
rubric.getRange("C:C").format.columnWidth = 24;
rubric.getRange("D:D").format.columnWidth = 55;
rubric.getRange("A1:D19").format.autofitRows();
rubric.freezePanes.freezeRows(1);

workbook.recalculate();
const check = workbook.inspect({ kind: "table", range: `Scoring!A1:AI6`, include: "values,formulas", tableMaxRows: 6, tableMaxCols: 35 });
console.log(check.ndjson);
const errors = workbook.inspect({ kind: "match", searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A", options: { useRegex: true, maxResults: 100 }, summary: "formula error scan" });
if (errors.ndjson && errors.ndjson.trim()) throw new Error(`Workbook formula errors: ${errors.ndjson}`);
fs.mkdirSync(previewDir, { recursive: true });
for (const sheetName of ["Scoring", "Rubric"]) {
  const image = await workbook.render({ sheetName, autoCrop: "all", scale: 1 });
  fs.writeFileSync(`${previewDir}/${sheetName}.png`, Buffer.from(await image.arrayBuffer()));
}
const exported = await SpreadsheetFile.exportXlsx(workbook);
await exported.save(outputPath);

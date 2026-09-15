import fs from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const auditRoot = new URL("../", import.meta.url);
const inputPath = fileURLToPath(new URL("originals/NLTL_Manual_Audit.xlsx", auditRoot));
const selectionPath = fileURLToPath(new URL("audit_selection.json", auditRoot));
const outputPath = fileURLToPath(new URL("NLTL_Manual_Audit_ready.xlsx", auditRoot));
const selection = JSON.parse(await fs.readFile(selectionPath, "utf8"));
const workbook = await SpreadsheetFile.importXlsx(await FileBlob.load(inputPath));

const sheets = {
  V2_FALLBACK25: "V2",
  NO_SEMANTIC: "NoSemantic",
  SINGLESHOT: "SingleShot",
};
const records = new Map(selection.records.map((record) => [`${record.architecture}|${record.requirement_id}`, record]));

for (const [architecture, sheetName] of Object.entries(sheets)) {
  const sheet = workbook.worksheets.getItem(sheetName);
  const identityResult = await workbook.inspect({
    kind: "table", sheetId: sheetName, range: "C7:C274", include: "values",
    maxChars: 30000, tableMaxRows: 268, tableMaxCols: 1, tableMaxCellChars: 40,
  });
  const identity = JSON.parse(identityResult.ndjson);
  const requirementIds = identity.values.map((row) => row[0]);
  const automaticLeft = [];
  const automaticRight = [];
  for (const requirementId of requirementIds) {
    const record = records.get(`${architecture}|${requirementId}`);
    if (!record) throw new Error(`Missing workbook record: ${architecture}|${requirementId}`);
    const observations = record.selected_observations;
    if (!Array.isArray(observations) || observations.length !== 2) {
      throw new Error(`Expected two selected observations: ${architecture}|${requirementId}`);
    }
    const metrics = record.full_case_metrics;
    automaticLeft.push([
      record.selected_generation_run,
      record.output_origin,
      record.original_generation_status,
      record.parse_status,
      record.deterministic_status,
      metrics.cases_executed,
      metrics.cases_total,
      metrics.cases_correct,
      metrics.every_case_correct,
      observations[0].case_id,
      observations[0].expected_outcome,
      observations[0].actual_verdict,
      observations[0].outcome_class,
      observations[1].case_id,
      observations[1].expected_outcome,
      observations[1].actual_verdict,
      observations[1].outcome_class,
    ]);
    automaticRight.push([
      record.triage_flags ?? "",
      record.source_clause ?? "",
      record.shape_path ?? "MISSING",
      record.shape_sha256 ?? "UNAVAILABLE",
    ]);
  }
  sheet.getRange("F7:V274").values = automaticLeft;
  sheet.getRange("AM7:AP274").values = automaticRight;
}

workbook.worksheets.getItem("Batches").getRange("H7:H33").values =
  Array.from({ length: 27 }, () => ["PACKAGED"]);

workbook.recalculate();
const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(outputPath);
console.log(JSON.stringify({ output: outputPath, sheetsUpdated: Object.values(sheets), batchesPackaged: 27 }));

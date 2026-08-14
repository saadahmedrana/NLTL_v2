import fs from "node:fs/promises";
import path from "node:path";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const here = path.dirname(new URL(import.meta.url).pathname);
const root = process.env.NLTL_BATCH_ROOT || path.resolve(here, "..");
const definition = JSON.parse(await fs.readFile(path.join(root, "batch_definition.json"), "utf8"));
const queue = JSON.parse(await fs.readFile(path.join(root, "generation_queue.json"), "utf8"));
const workbook = Workbook.create();

const navy = "#17324D";
const teal = "#137C8B";
const pale = "#E9F3F5";
const green = "#DDF3E4";
const amber = "#FFF0C2";
const red = "#FADBD8";
const white = "#FFFFFF";
const border = "#CCD6DD";

function title(sheet, text, endColumn) {
  sheet.showGridLines = false;
  const range = sheet.getRange(`A1:${endColumn}1`);
  range.merge();
  range.values = [[text]];
  range.format = { fill: navy, font: { color: white, bold: true, size: 16 }, rowHeight: 28 };
}

function header(range) {
  range.format = {
    fill: teal,
    font: { color: white, bold: true },
    wrapText: true,
    verticalAlignment: "center",
    borders: { preset: "inside", style: "thin", color: border },
  };
  range.format.rowHeight = 32;
}

const readme = workbook.worksheets.add("README");
title(readme, "Remaining 190 — development generation readiness", "F");
readme.getRange("A3:B13").values = [
  ["Field", "Value"],
  ["Batch ID", definition.batch_id],
  ["Vocabulary binding", definition.development_vocabulary_id],
  ["Pipeline configuration", definition.pipeline_config],
  ["Selection rule", definition.selection_rule],
  ["All requirements", definition.counts.all_requirements],
  ["Generation eligible", definition.counts.generation_eligible],
  ["Excluded in Batch 01", definition.counts.excluded_batch01],
  ["Queued here", definition.counts.selected],
  ["Ready", definition.counts.ready],
  ["Ready with review flags", definition.counts.ready_with_review_flags],
];
header(readme.getRange("A3:B3"));
readme.getRange("A4:A13").format.font = { bold: true, color: navy };
readme.getRange("A3:B13").format.borders = { preset: "outside", style: "thin", color: border };
readme.getRange("A15:F18").merge();
readme.getRange("A15:F18").values = [[
  "Purpose: this is a development queue, not a final experimental sample. It verifies that every remaining eligible requirement can receive a vocabulary-grounded context before API calls. The queue is bound to R8.1 and will be rejected if a different configuration is active."
]];
readme.getRange("A15:F18").format = { fill: pale, wrapText: true, verticalAlignment: "top", font: { color: navy } };
readme.getRange("A:A").format.columnWidth = 28;
readme.getRange("B:B").format.columnWidth = 72;

const summary = workbook.worksheets.add("SUMMARY");
title(summary, "Readiness summary", "H");
summary.getRange("A3:B7").values = [
  ["Readiness", "Count"],
  ["READY", definition.counts.ready],
  ["READY_WITH_REVIEW_FLAGS", definition.counts.ready_with_review_flags],
  ["BLOCKED", definition.counts.blocked],
  ["TOTAL", definition.counts.selected],
];
header(summary.getRange("A3:B3"));
summary.getRange("A4:B4").format.fill = green;
summary.getRange("A5:B5").format.fill = amber;
summary.getRange("A6:B6").format.fill = red;
summary.getRange("A7:B7").format = { fill: pale, font: { bold: true, color: navy } };
const categories = Object.entries(definition.category_counts).sort((a, b) => a[0].localeCompare(b[0]));
summary.getRange(`D3:E${3 + categories.length}`).values = [["Category", "Count"], ...categories];
header(summary.getRange("D3:E3"));
const sources = Object.entries(definition.source_sheet_counts).sort((a, b) => a[0].localeCompare(b[0]));
summary.getRange(`G3:H${3 + sources.length}`).values = [["Source sheet", "Count"], ...sources];
header(summary.getRange("G3:H3"));
summary.getRange("A:H").format.columnWidth = 23;

const queueSheet = workbook.worksheets.add("QUEUE");
title(queueSheet, "API generation queue — one run per requirement", "J");
const queueHeaders = ["Sequence", "Requirement ID", "Source", "Page", "Clause", "Category", "Encoding pattern", "Target owner", "Readiness", "Repetitions"];
const queueRows = definition.requirements.map((r) => [
  r.sequence, r.requirement_id, r.source_sheet, r.page, r.clause, r.category,
  r.encoding_pattern, r.target_owner, r.readiness, queue.repetitions,
]);
queueSheet.getRange(`A3:J${3 + queueRows.length}`).values = [queueHeaders, ...queueRows];
header(queueSheet.getRange("A3:J3"));
queueSheet.freezePanes.freezeRows(3);
queueSheet.getRange(`A4:J${3 + queueRows.length}`).format.borders = { preset: "inside", style: "thin", color: "#E6ECEF" };
queueSheet.getRange(`I4:I${3 + queueRows.length}`).format.fill = green;
queueSheet.getRange("A:A").format.columnWidth = 10;
queueSheet.getRange("B:B").format.columnWidth = 18;
queueSheet.getRange("C:C").format.columnWidth = 18;
queueSheet.getRange("D:E").format.columnWidth = 11;
queueSheet.getRange("F:F").format.columnWidth = 22;
queueSheet.getRange("G:G").format.columnWidth = 34;
queueSheet.getRange("H:J").format.columnWidth = 20;

const audit = workbook.worksheets.add("READINESS_AUDIT");
title(audit, "Static vocabulary/context readiness audit", "Q");
const auditHeaders = [
  "Sequence", "Requirement ID", "Indexed terms", "Context terms", "Target owner",
  "Required owners", "Direct paths", "Missing path owners", "Missing unit terms",
  "Semantic obligations", "Exclusive groups", "Context error", "Blockers", "Review flags",
  "Readiness", "Clause", "Normalized requirement",
];
const auditRows = definition.requirements.map((r) => [
  r.sequence, r.requirement_id, r.indexed_term_count, r.context_term_count, r.target_owner,
  r.required_owners.join(" | "), r.direct_paths.join(" | "), r.owners_without_direct_path.join(" | "),
  r.missing_unit_terms.join(" | "), r.semantic_obligation_count, r.exclusive_group_count,
  r.context_error, r.blockers.join(" | "), r.review_flags.join(" | "), r.readiness, r.clause,
  r.normalized_requirement,
]);
audit.getRange(`A3:Q${3 + auditRows.length}`).values = [auditHeaders, ...auditRows];
header(audit.getRange("A3:Q3"));
audit.freezePanes.freezeRows(3);
audit.freezePanes.freezeColumns(2);
audit.getRange(`A4:Q${3 + auditRows.length}`).format.borders = { preset: "inside", style: "thin", color: "#E6ECEF" };
audit.getRange(`O4:O${3 + auditRows.length}`).format.fill = green;
audit.getRange("A:A").format.columnWidth = 10;
audit.getRange("B:B").format.columnWidth = 18;
audit.getRange("C:D").format.columnWidth = 14;
audit.getRange("E:E").format.columnWidth = 20;
audit.getRange("F:N").format.columnWidth = 22;
audit.getRange("O:P").format.columnWidth = 18;
audit.getRange("Q:Q").format.columnWidth = 80;
audit.getRange(`Q4:Q${3 + auditRows.length}`).format.wrapText = true;

for (const sheet of [readme, summary, queueSheet, audit]) {
  const used = sheet.getUsedRange();
  used.format.font = { name: "Aptos", size: 10 };
  sheet.getRange("1:1").format.font = { name: "Aptos Display", size: 16, bold: true, color: white };
}

await fs.mkdir(path.join(root, "validation/previews"), { recursive: true });
for (const sheetName of ["README", "SUMMARY", "QUEUE", "READINESS_AUDIT"]) {
  const preview = await workbook.render({ sheetName, autoCrop: "all", scale: 1, format: "png" });
  await fs.writeFile(path.join(root, "validation/previews", `${sheetName}.png`), new Uint8Array(await preview.arrayBuffer()));
}
const inspect = await workbook.inspect({ kind: "match", searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A", options: { useRegex: true, maxResults: 300 }, summary: "final formula error scan" });
await fs.writeFile(path.join(root, "validation/workbook_formula_scan.ndjson"), inspect.ndjson || "", "utf8");
const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(path.join(root, "remaining_190_readiness_tracker.xlsx"));
console.log(JSON.stringify({ output: path.join(root, "remaining_190_readiness_tracker.xlsx"), sheets: 4, rows: definition.requirements.length }, null, 2));

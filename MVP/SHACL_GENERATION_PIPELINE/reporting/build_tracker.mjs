import fs from "node:fs/promises";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const [payloadPath, outputPath] = process.argv.slice(2);
if (!payloadPath || !outputPath) {
  throw new Error("Usage: build_tracker.mjs payload.json output.xlsx");
}
const payload = JSON.parse(await fs.readFile(payloadPath, "utf8"));
const workbook = Workbook.create();

const colors = {
  navy: "#17324D",
  teal: "#0F766E",
  pale: "#E8F1F5",
  white: "#FFFFFF",
  gray: "#5B6573",
  line: "#CBD5E1",
  green: "#DCFCE7",
  red: "#FEE2E2",
  amber: "#FEF3C7",
};

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

function sensibleWidth(header, rows, columnIndex) {
  let width = String(header).length + 2;
  for (const row of rows.slice(0, 350)) {
    width = Math.max(width, String(row[columnIndex] ?? "").length + 2);
  }
  const explicit = {
    RUN_ID: 42,
    SESSION_ID: 36,
    EVENT_ID: 16,
    REQUIREMENT_ID: 18,
    LOCAL_NAME: 38,
    CANONICAL_LOCAL_NAME: 40,
    IRI: 52,
    CANONICAL_IRI: 52,
    RANGE: 46,
    MODEL: 30,
    ACTIVE_STATUS: 42,
    ARTIFACT_TYPE: 28,
    ARTIFACT_PATH: 52,
    SHA256: 36,
    ISSUE_TYPE: 24,
    TIMESTAMP_UTC: 25,
    STARTED_UTC: 25,
    FINISHED_UTC: 25,
  };
  if (explicit[header]) {
    return explicit[header];
  }
  if (/FEEDBACK|DETAIL|ERROR|WARNING|SOURCE|NOTES|REASON|IRI|PATH|TEXT/.test(header)) {
    return Math.min(Math.max(width, 20), 52);
  }
  return Math.min(Math.max(width, 11), 24);
}

function addDataSheet(spec, sheetIndex) {
  const sheet = workbook.worksheets.add(spec.name);
  sheet.showGridLines = false;
  sheet.getRange("A1").values = [[payload.title]];
  sheet.getRange("A1").format = {
    fill: colors.navy,
    font: { bold: true, color: colors.white, size: 16 },
  };
  const lastColumn = columnName(Math.max(0, spec.headers.length - 1));
  sheet.getRange(`A1:${lastColumn}1`).format.fill = colors.navy;
  sheet.getRange("A2").values = [[`${spec.name} | ${payload.subtitle}`]];
  sheet.getRange(`A2:${lastColumn}2`).format = {
    fill: colors.pale,
    font: { color: colors.gray, italic: true },
  };
  sheet.getRange(`A4:${lastColumn}4`).values = [spec.headers];
  sheet.getRange(`A4:${lastColumn}4`).format = {
    fill: colors.teal,
    font: { bold: true, color: colors.white },
    wrapText: true,
    verticalAlignment: "center",
    borders: { preset: "outside", style: "thin", color: colors.line },
  };
  sheet.getRange(`A4:${lastColumn}4`).format.rowHeight = 30;

  if (spec.rows.length > 0) {
    const lastRow = 4 + spec.rows.length;
    sheet.getRange(`A5:${lastColumn}${lastRow}`).values = spec.rows;
    sheet.getRange(`A5:${lastColumn}${lastRow}`).format = {
      verticalAlignment: "top",
      borders: { insideHorizontal: { style: "thin", color: colors.line } },
    };
    sheet.tables.add(`A4:${lastColumn}${lastRow}`, true, `T${sheetIndex}_${spec.name.replace(/[^A-Za-z0-9]/g, "")}`);

    for (let col = 0; col < spec.headers.length; col += 1) {
      const letter = columnName(col);
      const header = spec.headers[col];
      const dataRange = sheet.getRange(`${letter}5:${letter}${lastRow}`);
      dataRange.format.columnWidth = sensibleWidth(header, spec.rows, col);
      if (/FEEDBACK|DETAIL|ERROR|WARNING|SOURCE|NOTES|REASON|IRI|PATH|TEXT|ACTIVE_STATUS/.test(header)) {
        dataRange.format.wrapText = true;
      }
      if (/_UTC$/.test(header)) {
        dataRange.format.numberFormat = "yyyy-mm-dd hh:mm:ss.000";
      } else if (/SCORE$/.test(header)) {
        dataRange.format.numberFormat = "0.000";
      } else if (/MS$/.test(header)) {
        dataRange.format.numberFormat = "#,##0.000";
      } else if (/TOKENS$|COUNT$|ATTEMPTS$|BYTES$|PAGE$|ITERATION$|TRIPLES$/.test(header)) {
        dataRange.format.numberFormat = "#,##0";
      }
      if (/STATUS|DECISION|ELIGIBILITY/.test(header)) {
        dataRange.conditionalFormats.add("containsText", { text: "ACCEPT", format: { fill: colors.green } });
        dataRange.conditionalFormats.add("containsText", { text: "ELIGIBLE", format: { fill: colors.green } });
        dataRange.conditionalFormats.add("containsText", { text: "PASS", format: { fill: colors.green } });
        dataRange.conditionalFormats.add("containsText", { text: "GAP", format: { fill: colors.red } });
        dataRange.conditionalFormats.add("containsText", { text: "FAIL", format: { fill: colors.red } });
        dataRange.conditionalFormats.add("containsText", { text: "DEFERRED", format: { fill: colors.amber } });
      }
    }
  } else {
    sheet.getRange("A5").values = [["No records for this run."]];
    sheet.getRange("A5").format.font = { italic: true, color: colors.gray };
  }
  sheet.freezePanes.freezeRows(4);
  sheet.getRange(`A1:${lastColumn}${Math.max(5, 4 + spec.rows.length)}`).format.font.name = "Aptos";
  return sheet;
}

const summary = workbook.worksheets.add("SUMMARY");
summary.showGridLines = false;
summary.getRange("A1:D1").format.fill = colors.navy;
summary.getRange("A1").values = [[payload.title]];
summary.getRange("A1").format.font = { bold: true, color: colors.white, size: 16 };
summary.getRange("A2").values = [[payload.subtitle]];
summary.getRange("A2:D2").format = { fill: colors.pale, font: { color: colors.gray, italic: true } };
summary.getRange("A4:B4").values = [["METRIC", "VALUE"]];
summary.getRange("A4:B4").format = { fill: colors.teal, font: { bold: true, color: colors.white } };

const byName = Object.fromEntries(payload.sheets.map((sheet) => [sheet.name, sheet]));
if (payload.kind === "evaluation") {
  const resultSpec = byName.EVALUATION_RESULTS;
  const resultLast = 4 + resultSpec.rows.length;
  const executionCol = columnName(resultSpec.headers.indexOf("EXECUTION_OK"));
  const matchCol = columnName(resultSpec.headers.indexOf("EXPECTED_MATCH"));
  const elapsedCol = columnName(resultSpec.headers.indexOf("ELAPSED_MS"));
  summary.getRange("A5:A9").values = [["Evaluation records"], ["Executed successfully"], ["Expected outcomes matched"], ["Expected outcomes mismatched"], ["Mean evaluation elapsed ms"]];
  summary.getRange("B5:B9").formulas = [
    [`=COUNTA('EVALUATION_RESULTS'!$A$5:$A$${resultLast})`],
    [`=COUNTIF('EVALUATION_RESULTS'!$${executionCol}$5:$${executionCol}$${resultLast},"TRUE")`],
    [`=COUNTIF('EVALUATION_RESULTS'!$${matchCol}$5:$${matchCol}$${resultLast},"TRUE")`],
    [`=COUNTIF('EVALUATION_RESULTS'!$${matchCol}$5:$${matchCol}$${resultLast},"FALSE")`],
    [`=IFERROR(AVERAGE('EVALUATION_RESULTS'!$${elapsedCol}$5:$${elapsedCol}$${resultLast}),0)`],
  ];
} else {
  const queueLast = 4 + (byName.REGULATION_QUEUE?.rows.length ?? 0);
  const runsLast = 4 + (byName.RUNS?.rows.length ?? 0);
  const apiLast = 4 + (byName.API_CALLS?.rows.length ?? 0);
  const qEligibleCol = columnName(byName.REGULATION_QUEUE.headers.indexOf("QUEUE_ELIGIBILITY"));
  const runStatusCol = columnName(byName.RUNS.headers.indexOf("FINAL_STATUS"));
  const apiElapsedCol = columnName(byName.API_CALLS.headers.indexOf("ELAPSED_MS"));
  summary.getRange("A5:A10").values = [["Requirements tracked"], ["Generation eligible"], ["Runs represented"], ["Accepted runs"], ["API/LLM records"], ["Mean API/LLM elapsed ms"]];
  summary.getRange("B5:B10").formulas = [
    [`=COUNTA('REGULATION_QUEUE'!$A$5:$A$${queueLast})`],
    [`=COUNTIF('REGULATION_QUEUE'!$${qEligibleCol}$5:$${qEligibleCol}$${queueLast},"ELIGIBLE")`],
    [`=COUNTA('RUNS'!$A$5:$A$${runsLast})`],
    [`=COUNTIF('RUNS'!$${runStatusCol}$5:$${runStatusCol}$${runsLast},"GENERATION_ACCEPTED")`],
    [`=COUNTA('API_CALLS'!$A$5:$A$${apiLast})`],
    [`=IFERROR(AVERAGE('API_CALLS'!$${apiElapsedCol}$5:$${apiElapsedCol}$${apiLast}),0)`],
  ];
}
summary.getRange("A5:B10").format.borders = { insideHorizontal: { style: "thin", color: colors.line } };
summary.getRange("A5:A10").format.font = { bold: true, color: colors.navy };
if (payload.kind === "evaluation") {
  summary.getRange("B5:B8").format.numberFormat = "#,##0";
  summary.getRange("B9").format.numberFormat = "#,##0.000";
} else {
  summary.getRange("B5:B9").format.numberFormat = "#,##0";
  summary.getRange("B10").format.numberFormat = "#,##0.000";
}
const summaryNotes = payload.kind === "evaluation" ? [[
  "INTERPRETATION", "EXPECTED_MATCH = TRUE means the SHACL result matched the independently declared pass/fail expectation.", "", ""
], [
  "RESULT DETAIL", "The workbook contains concise messages; evaluation_results.csv and evaluation_results.jsonl retain complete SHACL reports.", "", ""
], ["BOUNDARY", "This evaluator makes no LLM or API calls and never repairs a generated shape.", "", ""], ["REPRODUCIBILITY", "The manifest links every RDF variant to the exact frozen generated SHACL file.", "", ""]] : [[
  "INTERPRETATION", "Generation acceptance means syntax, structure, vocabulary, datatype/unit, target/path, and semantic review passed. It is not an RDF ship-compliance verdict.", "", ""
], [
  "NEXT GATE", "Accepted shapes remain in RDF_TEST_QUEUE until the separate evaluator is run.", "", ""
], ["RAW AUDIT", "events.jsonl is the durable append-only record for this run.", "", ""], ["LOCKING", "Only final/final_shape.ttl is the accepted candidate artifact.", "", ""]];
summary.getRange("A12:D15").values = summaryNotes;
summary.getRange("A12:A15").format = { fill: colors.pale, font: { bold: true, color: colors.navy } };
summary.getRange("B12:D15").format.wrapText = true;
summary.getRange("A12:B15").format.rowHeight = 38;
summary.getRange("A1:D15").format.font.name = "Aptos";
summary.getRange("A1:A15").format.columnWidth = 24;
summary.getRange("B1:B15").format.columnWidth = 78;
summary.getRange("C1:D15").format.columnWidth = 8;
summary.freezePanes.freezeRows(4);

let index = 1;
for (const spec of payload.sheets) {
  addDataSheet(spec, index);
  index += 1;
}

const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(outputPath);

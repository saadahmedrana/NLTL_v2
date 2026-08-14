import fs from "node:fs/promises";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const [payloadPath, outputPath] = process.argv.slice(2);
if (!payloadPath || !outputPath) throw new Error("Usage: build_cost_ledger.mjs payload.json output.xlsx");
const payload = JSON.parse(await fs.readFile(payloadPath, "utf8"));
const workbook = Workbook.create();
const colors = { navy: "#17324D", teal: "#0F766E", pale: "#E8F1F5", white: "#FFFFFF", gray: "#5B6573", line: "#CBD5E1", green: "#DCFCE7", amber: "#FEF3C7" };

function columnName(index) {
  let value = index + 1;
  let result = "";
  while (value > 0) {
    result = String.fromCharCode(65 + ((value - 1) % 26)) + result;
    value = Math.floor((value - 1) / 26);
  }
  return result;
}

function title(sheet, lastColumn, subtitle) {
  sheet.showGridLines = false;
  sheet.getRange(`A1:${lastColumn}1`).format.fill = colors.navy;
  sheet.getRange("A1").values = [[payload.title]];
  sheet.getRange("A1").format.font = { bold: true, color: colors.white, size: 16 };
  sheet.getRange(`A2:${lastColumn}2`).format = { fill: colors.pale, font: { italic: true, color: colors.gray } };
  sheet.getRange("A2").values = [[subtitle]];
  sheet.getRange(`A1:${lastColumn}2`).format.font.name = "Aptos";
}

function addTableSheet(name, headers, rows, widths) {
  const sheet = workbook.worksheets.add(name);
  const lastColumn = columnName(headers.length - 1);
  title(sheet, lastColumn, `${name} | ${payload.subtitle}`);
  sheet.getRange(`A4:${lastColumn}4`).values = [headers];
  sheet.getRange(`A4:${lastColumn}4`).format = { fill: colors.teal, font: { bold: true, color: colors.white }, wrapText: true, rowHeight: 30 };
  if (rows.length) {
    const lastRow = rows.length + 4;
    sheet.getRange(`A5:${lastColumn}${lastRow}`).values = rows;
    sheet.getRange(`A5:${lastColumn}${lastRow}`).format = { verticalAlignment: "top", borders: { insideHorizontal: { style: "thin", color: colors.line } } };
    sheet.tables.add(`A4:${lastColumn}${lastRow}`, true, `T_${name}`);
  }
  headers.forEach((header, index) => {
    const letter = columnName(index);
    const width = widths[header] ?? (/PATH|SOURCE|BASIS/.test(header) ? 52 : /MODEL|RUN_ID|SESSION_ID/.test(header) ? 36 : 18);
    sheet.getRange(`${letter}1:${letter}${Math.max(5, rows.length + 4)}`).format.columnWidth = width;
    if (/PATH|SOURCE|BASIS|MODEL|ROLES/.test(header)) sheet.getRange(`${letter}5:${letter}${Math.max(5, rows.length + 4)}`).format.wrapText = true;
    if (/_UTC$/.test(header)) sheet.getRange(`${letter}5:${letter}${Math.max(5, rows.length + 4)}`).format.numberFormat = "yyyy-mm-dd hh:mm:ss.000";
    if (/TOKENS|CALLS|UNKNOWN/.test(header)) sheet.getRange(`${letter}5:${letter}${Math.max(5, rows.length + 4)}`).format.numberFormat = "#,##0";
    if (/USD|RATE/.test(header)) sheet.getRange(`${letter}5:${letter}${Math.max(5, rows.length + 4)}`).format.numberFormat = '"$"#,##0.000000';
  });
  sheet.freezePanes.freezeRows(4);
  sheet.getRange(`A1:${lastColumn}${Math.max(5, rows.length + 4)}`).format.font.name = "Aptos";
  return sheet;
}

const summary = workbook.worksheets.add("SUMMARY");
title(summary, "D", payload.subtitle);
summary.getRange("A4:B4").values = [["METRIC", "VALUE"]];
summary.getRange("A4:B4").format = { fill: colors.teal, font: { bold: true, color: colors.white } };
summary.getRange("A5:A11").values = [["Runs with recorded calls"], ["Completed API calls"], ["Input tokens"], ["Output tokens"], ["Total tokens"], ["Estimated cumulative cost (USD)"], ["Calls without a known price"]];
summary.getRange("A5:A11").format.font = { bold: true, color: colors.navy };
summary.getRange("B5:B9").format.numberFormat = "#,##0";
summary.getRange("B10").format.numberFormat = '"$"#,##0.00';
summary.getRange("B11").format.numberFormat = "#,##0";
summary.getRange("A13:D16").values = [
  ["BASIS", payload.pricing_basis, "", ""],
  ["PRICE SOURCE", payload.pricing_source, "", ""],
  ["COUNTING RULE", "Only api_call_completed events are counted. Transport-attempt logs are excluded to prevent double-counting retries.", "", ""],
  ["INTERPRETATION", "This is an indicative research-budget estimate, not an Aalto invoice. Historical calls retain the price of the exact model recorded in each event.", "", ""],
];
summary.getRange("A13:A16").format = { fill: colors.pale, font: { bold: true, color: colors.navy } };
summary.getRange("B13:D16").format.wrapText = true;
summary.getRange("A13:D16").format.rowHeight = 42;
summary.getRange("A1:A16").format.columnWidth = 31;
summary.getRange("B1:B16").format.columnWidth = 80;
summary.getRange("C1:D16").format.columnWidth = 8;
summary.getRange("A1:D16").format.font.name = "Aptos";
summary.freezePanes.freezeRows(4);

addTableSheet("MODEL_PRICING", ["MODEL", "INPUT_RATE_USD", "OUTPUT_RATE_USD", "RATE_BASIS", "SOURCE_URL"], payload.pricing_rows, { MODEL: 34, RATE_BASIS: 22, SOURCE_URL: 60 });
const runSheet = addTableSheet("RUN_COSTS", ["STARTED_UTC", "FINISHED_UTC", "SESSION_ID", "RUN_ID", "REQUIREMENT_ID", "PIPELINE_VERSION", "STATUS", "ACCEPTED", "API_CALLS", "INPUT_TOKENS", "OUTPUT_TOKENS", "TOTAL_TOKENS", "MODELS", "ROLES", "ESTIMATED_RUN_USD", "CUMULATIVE_USD", "UNKNOWN_PRICE_CALLS", "RUN_PATH"], payload.run_rows, { STARTED_UTC: 25, FINISHED_UTC: 25, RUN_ID: 43, REQUIREMENT_ID: 18, PIPELINE_VERSION: 34, STATUS: 28, MODELS: 38, ROLES: 32, RUN_PATH: 52 });
const callSheet = addTableSheet("API_CALLS", ["TIMESTAMP_UTC", "SESSION_ID", "RUN_ID", "REQUIREMENT_ID", "ROLE", "MODEL", "INPUT_TOKENS", "OUTPUT_TOKENS", "TOTAL_TOKENS", "INPUT_RATE_USD", "OUTPUT_RATE_USD", "ESTIMATED_CALL_USD", "RESPONSE_ID", "EVENTS_PATH"], payload.call_rows, { TIMESTAMP_UTC: 25, RUN_ID: 43, REQUIREMENT_ID: 18, ROLE: 22, MODEL: 34, RESPONSE_ID: 45, EVENTS_PATH: 58 });

const callLastRow = payload.call_rows.length + 4;
const runLastRow = payload.run_rows.length + 4;
if (payload.call_rows.length) {
  callSheet.getRange("L5").formulas = [["=G5/1000000*J5+H5/1000000*K5"]];
  callSheet.getRange(`L5:L${callLastRow}`).fillDown();
}
if (payload.run_rows.length) {
  runSheet.getRange("O5").formulas = [[`=SUMIF('API_CALLS'!$C$5:$C$${callLastRow},D5,'API_CALLS'!$L$5:$L$${callLastRow})`]];
  runSheet.getRange(`O5:O${runLastRow}`).fillDown();
  runSheet.getRange("P5").formulas = [["=SUM($O$5:O5)"]];
  runSheet.getRange(`P5:P${runLastRow}`).fillDown();
}
summary.getRange("B5:B11").formulas = [
  [`=COUNTA('RUN_COSTS'!$D$5:$D$${runLastRow})`],
  [`=COUNTA('API_CALLS'!$C$5:$C$${callLastRow})`],
  [`=SUM('API_CALLS'!$G$5:$G$${callLastRow})`],
  [`=SUM('API_CALLS'!$H$5:$H$${callLastRow})`],
  [`=SUM('API_CALLS'!$I$5:$I$${callLastRow})`],
  [`=SUM('API_CALLS'!$L$5:$L$${callLastRow})`],
  [`=COUNTBLANK('API_CALLS'!$J$5:$J$${callLastRow})`],
];

const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(outputPath);

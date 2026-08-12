import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const file = process.argv[2];
const wb = await SpreadsheetFile.importXlsx(await FileBlob.load(file));
const expected = {
  README: 33,
  SOURCE_MANIFEST: 21,
  TERMINOLOGY_SHORTLIST: 824,
  NAMING_AUDIT: 824,
  NAMING_POLICY: 8,
  REQUIREMENT_COVERAGE: 314,
  NAMESPACE_COMPATIBILITY: 11,
  DECISIONS: 11,
  PUBLICATION_LIMITATIONS: 4,
  UNRESOLVED: 2,
};
const actual = {};
for (const sheet of wb.worksheets.items) {
  const used = sheet.getUsedRange(true);
  actual[sheet.name] = used ? used.rowCount : 0;
}
for (const [name, rows] of Object.entries(expected)) {
  if (actual[name] !== rows) throw new Error(`${name}: expected ${rows} rows, got ${actual[name]}`);
}
const termSheet = wb.worksheets.getItem("TERMINOLOGY_SHORTLIST");
const termValues = termSheet.getRange(`A1:AV${expected.TERMINOLOGY_SHORTLIST}`).values;
const headers = termValues[0];
const localIx = headers.indexOf("Proposed_Local_Name");
const qaIx = headers.indexOf("Name_QA_Status");
const confIx = headers.indexOf("Confidence");
const locals = termValues.slice(1).map(r => String(r[localIx] ?? ""));
if (new Set(locals).size !== locals.length) throw new Error("Duplicate proposed local names found");
const badLexical = locals.filter(n => !/^[a-z][A-Za-z0-9]*$/.test(n));
if (badLexical.length) throw new Error(`Non-lowerCamelCase/ASCII names: ${badLexical.join(", ")}`);
const opaque = locals.filter(n => /^(term|clause)/.test(n) || /(?:Sigma|Gamma)[A-Z0-9]*$/.test(n));
if (opaque.length) throw new Error(`Opaque names remain: ${opaque.join(", ")}`);
const badQa = termValues.slice(1).filter(r => !String(r[qaIx] ?? "").startsWith("Passed -"));
if (badQa.length) throw new Error(`${badQa.length} names did not pass naming QA`);
const badConfidence = termValues.slice(1).filter(r => !["High","Medium"].includes(String(r[confIx] ?? "")));
if (badConfidence.length) throw new Error(`${badConfidence.length} names have unsupported confidence values`);
const errors = await wb.inspect({
  kind: "match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",
  options: { useRegex: true, maxResults: 300 },
  summary: "verification error scan",
  maxChars: 3000,
});
console.log(JSON.stringify({ sheets: actual, errorScan: errors.ndjson }, null, 2));

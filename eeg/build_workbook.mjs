// Build a compact Excel companion from the completed scientific analysis.
import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { Workbook, SpreadsheetFile } from '@oai/artifact-tool';

const root = path.dirname(fileURLToPath(import.meta.url));
const data = JSON.parse(await fs.readFile(path.join(root, 'reports/analysis.json'), 'utf8'));
const out = path.join(root, 'reports/outputs/npg_eda');
const previewDir = path.join(root, 'reports/_preview');
await fs.mkdir(out, { recursive: true });
await fs.mkdir(previewDir, { recursive: true });

const wb = Workbook.create();
const overview = wb.worksheets.add('Overview');
const channels = wb.worksheets.add('Channel statistics');
const navy = '#203B62';
const font = { name: 'Arial', size: 10, color: '#172033' };
for (const sheet of [overview, channels]) {
  sheet.showGridLines = false;
}
overview.getRange('B2:H34').format.font = font;
overview.getRange('B2:H34').format.rowHeight = 23;
overview.getRange('B2:H34').format.verticalAlignment = 'center';
overview.getRange('B2').values = [['NPG recording quality']];
overview.getRange('B2').format.font = { ...font, size: 16, bold: true };
overview.getRange('B4').values = [['Six exported recordings. YES/NO answers included speaking.']];
overview.getRange('B4').format.font = { ...font, color: '#526177', italic: true };
overview.getRange('B7:H7').values = [['Recording', 'Sample rows', 'Invalid cells', 'Counter breaks', 'Segments', 'Flagged rows', 'Duration* (s)']];
overview.getRange('B7:H7').format = {
  fill: navy, font: { ...font, bold: true, color: '#FFFFFF' },
  wrapText: true, horizontalAlignment: 'center', verticalAlignment: 'center', rowHeight: 36,
};
overview.getRange('B8:G13').values = data.quality_summary.map(r => [r.dataset.toUpperCase(), r.rows,
  r.invalid_numeric_cells, r.counter_discontinuities, r.segments, r.flagged_amplitude_rows]);
overview.getRange('H8:H13').formulas = data.quality_summary.map((_, i) => [`=C${i + 8}/$C$18`]);
overview.getRange('C8:G15').setNumberFormat('#,##0');
overview.getRange('H8:H15').setNumberFormat('0.00');
overview.getRange('B15').values = [['TOTAL']];
overview.getRange('C15:H15').formulas = [[...['C','D','E','F','G','H'].map(c => `=SUM(${c}8:${c}13)`)]];
overview.getRange('B15:H15').format.font = { ...font, bold: true };
overview.getRange('B15:H15').format.borders = { top: { style: 'thin', color: '#9AA9BE' } };
overview.getRange('B18').values = [['Analysis rate (Hz)']];
overview.getRange('C18').values = [[data.configuration.analysis_sample_rate_hz]];
overview.getRange('C18').format.fill = '#FFF2CC';
overview.getRange('C18').setNumberFormat('0');
overview.getRange('D18').values = [['Assumed; not clock-verified']];
overview.getRange('B20:C26').values = [
  ['*Duration', 'Sample count / assumed rate. Excludes unknown time across counter breaks.'],
  ['Rate evidence', 'About 2 minutes per recording; around 60,000 samples.'],
  ['Export processing', 'Brain mode reported; exact filters and scaling unknown.'],
  ['Answer task', 'Thought about answers and spoke aloud. No onset markers supplied.'],
  ['Cleaning', 'Annotations only. All rows and finite signal values retained.'],
  ['Units', 'Native exported values; not verified microvolts.'],
  ['Channels 1–6', 'C3, C4, F3, F4, P3, P4 (user-reported order).'],
];
overview.getRange('B28').values = [['Source exports']];
overview.getRange('B28').format.font = { ...font, bold: true };
overview.getRange('B29:C34').values = data.recordings.map(r => [r.id.toUpperCase(), r.filename]);
overview.getRange('B8:B34').format.columnWidth = 23;
overview.getRange('C8:C34').format.columnWidth = 16;
overview.getRange('D8:G34').format.columnWidth = 15;
overview.getRange('H8:H34').format.columnWidth = 18;
overview.getRange('C20:C34').format.wrapText = false;
overview.getRange('D8:D13').conditionalFormats.add('cellIs', {
  operator: 'greaterThan', formula: 0, format: { fill: '#FEE2E2', font: { color: '#991B1B' } },
});
overview.getRange('E8:E13').conditionalFormats.add('cellIs', {
  operator: 'greaterThan', formula: 0, format: { fill: '#FFF2CC', font: { color: '#7C4A03' } },
});
overview.getRange('G8:G13').conditionalFormats.add('cellIs', {
  operator: 'greaterThan', formula: 0, format: { fill: '#FFF7ED' },
});

channels.getRange('A2:L42').format.font = font;
channels.getRange('A2:L42').format.rowHeight = 22;
channels.getRange('A2').values = [['Channel measurements']];
channels.getRange('A2').format.font = { ...font, size: 16, bold: true };
channels.getRange('A4').values = [['Native exported units. Amplitude flags identify review candidates, not proven artifacts.']];
channels.getRange('A4').format.font = { ...font, color: '#526177', italic: true };
channels.getRange('A6:L6').values = [['Recording', 'Channel', 'Position', 'Mean', 'Std. dev.', 'RMS', 'Minimum', 'Maximum', 'MAD', 'Flagged samples', 'Flagged fraction', 'Valid samples']];
channels.getRange('A6:L6').format = {
  fill: navy, font: { ...font, bold: true, color: '#FFFFFF' }, wrapText: true,
  horizontalAlignment: 'center', verticalAlignment: 'center', rowHeight: 36,
};
channels.getRange('A7:J42').values = data.channel_statistics.map(r => [r.dataset.toUpperCase(), r.channel, r.position,
  r.mean, r.std, r.rms, r.minimum, r.maximum, r.mad, r.flagged_amplitude_samples]);
channels.getRange('L7:L42').values = data.channel_statistics.map(r => [r.valid_samples]);
channels.getRange('K7:K42').formulas = data.channel_statistics.map((_,i) => [`=J${i+7}/L${i+7}`]);
channels.getRange('D7:I42').setNumberFormat('0.00000');
channels.getRange('J7:J42').setNumberFormat('#,##0');
channels.getRange('K7:K42').setNumberFormat('0.00%');
channels.getRange('L7:L42').setNumberFormat('#,##0');
channels.getRange('A7:C42').format.columnWidth = 13;
channels.getRange('D7:I42').format.columnWidth = 12;
channels.getRange('J7:L42').format.columnWidth = 16;
channels.freezePanes.freezeRows(6);

// Verify that the only adjustable rate input drives the displayed durations.
overview.getRange('C18').values = [[1000]];
wb.recalculate();
if (Math.abs(overview.getRange('H8').values[0][0] - data.quality_summary[0].rows / 1000) > 1e-9) {
  throw new Error('Duration formula does not respond to the rate input.');
}
overview.getRange('C18').values = [[data.configuration.analysis_sample_rate_hz]];
wb.recalculate();
if (overview.getRange('C15').values[0][0] !== data.total_rows) throw new Error('Sample total mismatch.');
for (let i=0; i<data.channel_statistics.length; i++) {
  const expected = data.channel_statistics[i].flagged_amplitude_fraction;
  if (Math.abs(channels.getRange(`K${i+7}`).values[0][0] - expected) > 1e-12) throw new Error('Flag fraction mismatch.');
}
const scan = await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#NUM!|#N/A|#NULL!',options:{useRegex:true,maxResults:50},summary:'Formula error scan'});
console.log(scan.ndjson);
console.log((await wb.inspect({kind:'table',range:'Overview!B7:H15',include:'values,formulas',tableMaxRows:9,tableMaxCols:7,maxChars:1800})).ndjson);
for (const [sheetName, range, name] of [['Overview','B2:H34','overview.png'], ['Channel statistics','A2:L42','channel_statistics.png']]) {
  const image = await wb.render({sheetName,range,scale:1.5,format:'png'});
  await fs.writeFile(path.join(previewDir,name),new Uint8Array(await image.arrayBuffer()));
}
const file = await SpreadsheetFile.exportXlsx(wb);
await file.save(path.join(out,'quality_summary.xlsx'));
console.log('Exported two-sheet quality workbook; formulas and source totals verified.');

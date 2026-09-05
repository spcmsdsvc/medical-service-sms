import base64
import hashlib
import json
import pathlib
import re
import subprocess
import unittest
import zipfile

from pypdf import PdfReader

from tests.sw_cache_version import assert_cache_version_at_least


ROOT = pathlib.Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / 'static' / 'templates' / 'calibration-report' / 'calibration-report-template.docx'
RUNTIME = ROOT / 'static' / 'vendor' / 'jszip' / 'jszip.min.js'
LICENSE = ROOT / 'static' / 'vendor' / 'jszip' / 'LICENSE'
CERT_TEMPLATE = ROOT / 'static' / 'templates' / 'calibration-certificate' / 'calibration-certificate-template.pdf'
CERT_RUNTIME_TEMPLATE = ROOT / 'static' / 'templates' / 'calibration-certificate' / 'calibration-certificate-runtime-v2.pdf'
CERT_DATA = ROOT / 'static' / 'templates' / 'calibration-certificate' / 'calibration-certificate-template-data.js'
CERT_RUNTIME = ROOT / 'static' / 'vendor' / 'pdf-lib' / 'pdf-lib.min.js'
CERT_LICENSE = ROOT / 'static' / 'vendor' / 'pdf-lib' / 'LICENSE'
EXPECTED_TEMPLATE_SHA256 = '31B6FE282CBE227B407870F5893493C1B7C529685892CD1997E25C9D4CC5A79E'
EXPECTED_CERT_TEMPLATE_SHA256 = 'C06F43E221C297229D5108E0F3BA0348FF0C1C6F299A791FF4359D60E9F17EBC'
EXPECTED_CERT_RUNTIME_SHA256 = '20C84569CB120F90E9F9998D68021E99ABCBD65E3C9085C7640754C6F0EBE2D8'
DOCX_MIME = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
NODE = pathlib.Path(r'C:\Users\Jonamar\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe')
MOBILE_DART_MODELS = [
    'MobileDart Evolution MX9 Premium',
    'MobileDart Evolution MX9c Premium',
    'MobileDart Evolution MX9v Premium',
    'MobileDart Evolution MX9k Premium',
    'MobileDart Evolution MX9',
    'MobileDart Evolution MX9c',
    'MobileDart Evolution MX9v',
    'MobileDart Evolution MX9k',
    'MobileDart Evolution MX8',
    'MobileDart Evolution MX8c',
    'MobileDart Evolution MX8v',
    'MobileDart Evolution MX8k',
]


NODE_BEHAVIOR_SCRIPT = r'''
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const root = process.cwd();
const templatePath = path.join(root, 'static', 'templates', 'calibration-report', 'calibration-report-template.docx');
const runtimePath = path.join(root, 'static', 'vendor', 'jszip', 'jszip.min.js');
const png = 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAHgAAAAeCAYAAADnydqVAAAAVElEQVR42u3WsQkAMAwEsdt/aWeDlMEEHfwCVuNGX5cTABZgARZgARZgAQYswAIswAKsJ8CVLRtgwIABy5MlwAIswAIswIAFWIAFWIAFWJcOqjWBWhan81EAAAAASUVORK5CYII=';
const records = new Map();
const documents = { value: '' };
let addedDocuments = 0;
let removedDocuments = 0;
let failBlobSaves = false;
let finalModalOpen = true;
let finalPersisted = { source:'localstorage', attachments_not_durable:true };
let finalStatus = '';
let fallbackModalStayedOpen = false;
let indexedModalClosed = false;
const deletedBlobIds = [];
let currentTSR = {};
let selectedSchedule = null;
let templateBytes = fs.readFileSync(templatePath);
class FakeElement {
  constructor(attributes) {
    this.attributes = attributes || {};
    this.value = '';
    this.listeners = {};
    this.focused = false;
    this.classList = { toggle: () => {} };
  }
  getAttribute(name) { return this.attributes[name] || null; }
  matches(selector) {
    const match = String(selector).match(/^\[([^\]=]+)\]$/);
    return !!(match && Object.prototype.hasOwnProperty.call(this.attributes, match[1]));
  }
  addEventListener(name, handler) { (this.listeners[name] ||= []).push(handler); }
  dispatch(name, event) { for (const handler of this.listeners[name] || []) handler(event || { target: this }); }
  focus() { this.focused = true; }
  scrollIntoView() {}
}
const editor = new FakeElement();
Object.defineProperty(editor, 'innerHTML', {
  set(value) {
    this.html = value;
    this.elements = [];
    for (const attribute of ['data-cr-field', 'data-cr-check', 'data-cr-exposure', 'data-cr-performance']) {
      const pattern = new RegExp('<(?:input|textarea)\\b[^>]*' + attribute + '="([^"]+)"[^>]*>', 'g');
      let match;
      while ((match = pattern.exec(value))) this.elements.push(new FakeElement({ [attribute]: match[1] }));
    }
  },
  get() { return this.html || ''; }
});
editor.elements = [];
const finalOverlay = {
  classList: {
    contains: () => finalModalOpen,
    add: () => { finalModalOpen = true; },
    remove: () => { finalModalOpen = false; }
  },
  setAttribute: () => {},
  removeAttribute: () => {},
  querySelectorAll: () => []
};
const context = {
  console,
  Blob,
  Uint8Array,
  ArrayBuffer,
  Promise,
  Date,
  Math,
  JSON,
  setTimeout,
  clearTimeout,
  atob,
  btoa,
  URL: { createObjectURL: () => 'blob:test', revokeObjectURL: () => {} }
};
context.window = context;
context.self = context;
context.globalThis = context;
context.document = {
  querySelector: selector => selector === '#tsr-documents' ? documents : (selector === '#calibration-report-editor' ? editor : (selector === '#calibration-report-overlay' ? finalOverlay : null)),
  querySelectorAll: selector => editor.elements.filter(element => element.matches(selector)),
  createElement: () => ({}),
  addEventListener: () => {}
};
context.CalibrationReportConfig = {
  templateUrl: '/static/templates/calibration-report/calibration-report-template.docx',
  certificateCatalog: JSON.parse(fs.readFileSync(path.join(root, 'static', 'templates', 'calibration-certificate', 'calibration-certificate-catalog.json'), 'utf8'))
};
context.fetch = async () => ({
  ok: true,
  arrayBuffer: async () => templateBytes
});
context.saveOfflineTSRBlobRecord = async record => { if (failBlobSaves) throw new Error('simulated Blob write failure'); records.set(record.id, record); };
context.loadOfflineTSRBlobRecord = async id => records.get(id) || null;
context.deleteOfflineTSRBlobRecord = async id => { deletedBlobIds.push(id); records.delete(id); };
context.addTSRDocument = label => { addedDocuments += 1; documents.value = documents.value ? `${documents.value},${label}` : label; };
context.removeTSRDocument = label => { removedDocuments += 1; documents.value = documents.value.split(',').filter(item => item !== label).join(','); };
context.collectTSRData = () => currentTSR;
context.getSelectedStandaloneSchedule = () => selectedSchedule;
context.showTSRStatus = message => { finalStatus = String(message || ''); };
context.saveStandaloneTSRDraft = async () => finalPersisted;
context.offlineTSRConfirm = async () => true;

vm.createContext(context);
vm.runInContext(fs.readFileSync(runtimePath, 'utf8'), context);
vm.runInContext(fs.readFileSync(path.join(root, 'static', 'js', 'app-calibration-report.js'), 'utf8'), context);

(async () => {
const api = context.calibrationReport;
const legacy = {
  status: 'draft',
  facility: { name: 'Legacy Client', address: 'Legacy Address' },
  signature: { name: 'Legacy Engineer', data_url: png },
  performance_results: ['Pass', 'Pass', 'ignored third result']
};
api.apply(legacy);
const migrated = api.collect();
if (migrated.signature.image !== png || Object.prototype.hasOwnProperty.call(migrated.signature, 'data_url')) throw new Error('legacy signature migration failed');
if (migrated.machine.manufacturer !== 'Shimadzu') throw new Error('legacy blank manufacturer was not normalized to Shimadzu');
if (api.getSource().performance.length !== 2) throw new Error('performance criteria count is not two');
api.apply({ status:'draft', machine:{ manufacturer:' \t ' } });
if (api.collect().machine.manufacturer !== 'Shimadzu') throw new Error('blank manufacturer was not normalized to Shimadzu');
const customManufacturer = '  Custom Imaging  ';
api.apply({ status:'draft', machine:{ manufacturer:customManufacturer } });
const customManufacturerPreserved = api.collect().machine.manufacturer === customManufacturer;
if (!customManufacturerPreserved) throw new Error('custom manufacturer was not preserved');

currentTSR = {
  'tsr-contact-no': '0917-current',
  'tsr-email-add': 'current@example.test',
  'tsr-department': 'Radiology',
  'tsr-equipment-model': 'Current Model',
  'tsr-serial-no': 'CURRENT-SERIAL',
  'tsr-service-date': '2026-08-20',
  'tsr-serviced-by': 'Current Engineer'
};
selectedSchedule = {
  client_name: 'Scheduled Client',
  client_address: 'Scheduled Address',
  client_contact: { phone: '0917-contact', email: 'contact@example.test' },
  product_name: 'Scheduled Model',
  product_id: 'SCHEDULED-SERIAL',
  date_iso: '2026-08-19',
  serviced_by: 'Scheduled Engineer'
};
api.reset();
api.create();
if (addedDocuments !== 0) throw new Error('incomplete report added the document chip');
const filled = api.collect();
if (filled.facility.name !== 'Scheduled Client' || filled.facility.address !== 'Scheduled Address') throw new Error('schedule client autofill failed');
if (filled.facility.telephone !== '0917-current' || filled.facility.email !== 'current@example.test') throw new Error('current TSR contact precedence failed');
if (filled.facility.location !== 'Radiology') throw new Error('department-to-location autofill failed');
if (filled.machine.model !== 'Scheduled Model' || filled.machine.serial_number !== 'SCHEDULED-SERIAL') throw new Error('schedule product autofill failed');
if (filled.calibration.machine_calibration_date !== '2026-08-19' || filled.calibration.engineer_name !== 'Scheduled Engineer') throw new Error('schedule date/engineer autofill failed');
if (filled.machine.manufacturer !== 'Shimadzu') throw new Error('blank report did not default the manufacturer');

const complete = {
  status: 'draft',
  facility: { name:'Client & Sons', address:'123 Main <Street>', telephone:'Phone', email:'client@example.test', location:'Radiology' },
  machine: { manufacturer:'Shimadzu', modality:'Digital Angiography System', model:'Mobile Dart Evolution MX9', serial_number:'SN-1', console_model:'Console 1', console_serial:'CON-1', tube1_model:'Tube 1', tube1_serial:'TUBE-1', tube2_model:'Tube 2', tube2_serial:'TUBE-2', installation_date:'2024-01-02' },
  technical: { max_tube_current_ma:'500', max_tube_voltage_kv:'150', tube_current_mas_range:'10-500', tube_voltage_kvp_range:'40-150', exposure_time_range:'1-500', max_rated_power_kw:'50', power_supply:'220V', total_inherent_filtration:'2.5mm Al' },
  calibration: { machine_calibration_date:'2026-08-19', next_calibration_date:'2027-08-19', test_tool_manufacturer:'Tool Co', test_tool_model:'Tool 1', test_tool_serial:'TOOL-1', test_tool_calibration_date:'2026-08-01', engineer_name:'Engineer' },
  mechanical_checks: [{ result:'Pass' }],
  generator_checks: [{ result:'Pass' }, { result:'Pass & verified' }, { result:'Pass' }, { result:'Pass' }],
  exposure: { small:[{ nominal_kvp:'80', measured_kvp:'80.2', ma_mas:'100mA', dose_mgy:'1.2', dose_rate:'2.4', time_msec:'10', measured_time:'0.010' }], large:[{ nominal_kvp:'100' }] },
  performance_results: ['Pass', 'Pass'],
  signature: { name:'Engineer', image: png }
};
api.apply(complete);
const fitRules = api.getExactFitRules();
const boundaryCases = [
  ['facility.name', 'page1_value'],
  ['machine.console_model', 'page1_narrow'],
  ['mechanical_checks.0.result', 'page2_result'],
  ['calibration.test_tool_model', 'page2_detail'],
  ['exposure.small.0.nominal_kvp', 'page3_exposure'],
  ['performance_results.0', 'page3_performance']
];
function setNested(root, path, value) {
  const parts = path.split('.');
  let target = root;
  for (const part of parts.slice(0, -1)) target = target[part];
  target[parts[parts.length - 1]] = value;
}
for (const [fieldPath, ruleName] of boundaryCases) {
  const accepted = JSON.parse(JSON.stringify(complete));
  setNested(accepted, fieldPath, 'x'.repeat(fitRules[ruleName].maxLength));
  if (!api.validateForFinalSave({ calibration_report:accepted }).ok) throw new Error(`accepted exact-fit boundary rejected for ${fieldPath}`);
  const rejected = JSON.parse(JSON.stringify(complete));
  setNested(rejected, fieldPath, 'x'.repeat(fitRules[ruleName].maxLength + 1));
  const rejectedValidation = api.validateForFinalSave({ calibration_report:rejected });
  if (rejectedValidation.ok || rejectedValidation.fit[0].path !== fieldPath) throw new Error(`first rejected exact-fit boundary accepted for ${fieldPath}`);
  const newline = JSON.parse(JSON.stringify(complete));
  setNested(newline, fieldPath, 'x\ny');
  if (api.validateForFinalSave({ calibration_report:newline }).ok) throw new Error(`embedded line break accepted for ${fieldPath}`);
}
const overflow = JSON.parse(JSON.stringify(complete));
setNested(overflow, 'facility.name', 'x'.repeat(fitRules.page1_value.maxLength + 1));
let overflowCode = '';
try { await api.preparePayload({ calibration_report:overflow, attachments:[] }, 'node-overflow', { regenerate:true }); }
catch (error) { overflowCode = error.code || ''; }
if (overflowCode !== 'calibration_report_exact_fit' || records.size) throw new Error('exact-fit overflow was not blocked before Blob creation');
if (addedDocuments !== 0) throw new Error('complete report without a generated Blob added the document chip');
const prepared = await api.preparePayload({ calibration_report: complete, attachments: [] }, 'node-test', { regenerate:true });
const generated = prepared.calibration_report.generated;
if (!generated.blob_id || !records.has(generated.blob_id)) throw new Error('generated blob was not stored before metadata');
if (generated.filename.slice(-5) !== '.docx') throw new Error('generated filename is not DOCX');
const generatedRecord = records.get(generated.blob_id);
if (generatedRecord.type !== 'application/vnd.openxmlformats-officedocument.wordprocessingml.document') throw new Error('generated record MIME is not DOCX');
if (generatedRecord.blob.type !== generatedRecord.type) throw new Error('generated Blob MIME is not DOCX');
if (addedDocuments !== 1 || documents.value !== 'Calibration Report') throw new Error('ready report did not add exactly one document chip');
const generatedZip = await context.JSZip.loadAsync(await generatedRecord.blob.arrayBuffer());
const generatedDocument = await generatedZip.file('word/document.xml').async('string');
const generatedRels = await generatedZip.file('word/_rels/document.xml.rels').async('string');
const generatedContentTypes = await generatedZip.file('[Content_Types].xml').async('string');
const sourceZip = await context.JSZip.loadAsync(fs.readFileSync(templatePath));
for (const part of ['word/footer1.xml', 'word/footer2.xml', 'word/footer3.xml', 'word/_rels/footer2.xml.rels']) {
  const sourcePart = await sourceZip.file(part).async('string');
  const generatedPart = await generatedZip.file(part).async('string');
  if (sourcePart !== generatedPart) throw new Error(`generated DOCX changed supplied footer part ${part}`);
}
if ((generatedDocument.match(/<w:footerReference\b/g) || []).length !== 3) throw new Error('generated DOCX lost source footer references');
if (!generatedRels.includes('Target="footer1.xml"') || !generatedRels.includes('Target="footer2.xml"') || !generatedRels.includes('Target="footer3.xml"')) throw new Error('generated DOCX lost source footer relationships');
if (!generatedDocument.includes('Client &amp; Sons') || !generatedDocument.includes('123 Main &lt;Street&gt;')) throw new Error('page one data was not XML escaped into the DOCX');
for (const marker of ['Shimadzu', 'Mobile Dart Evolution MX9', 'SN-1', '2026-08-19', 'Tool Co', '80.2', 'Pass &amp; verified']) {
  if (!generatedDocument.includes(marker)) throw new Error(`generated DOCX is missing ${marker}`);
}
if ((generatedDocument.match(/<w:tbl\b/g) || []).length !== 5) throw new Error('generated DOCX changed source table count');
if ((generatedDocument.match(/<w:tr\b/g) || []).length < 60) throw new Error('generated DOCX lost source table rows');
if (!generatedDocument.includes('CALIBRATION REPORT') || !generatedDocument.includes('PERFORMANCE CRITERIA')) throw new Error('generated DOCX lost source wording');
if (!generatedDocument.includes('RESULT: Pass') || !generatedDocument.includes('RESULT: Pass &amp; verified')) throw new Error('result lines were not filled');
if (generatedDocument.includes('________________')) throw new Error('result underscores were not removed');
if (!generatedDocument.includes('Calibration signature') || !generatedRels.includes('media/calibration-signature.png')) throw new Error('signature relationship was not added');
if (!generatedContentTypes.includes('PartName="/word/media/calibration-signature.png"')) throw new Error('signature content type was not added');
if (!generatedZip.file('word/media/calibration-signature.png')) throw new Error('signature media was not added');
if (prepared.attachments.length !== 1 || prepared.attachments[0].type !== generatedRecord.type || prepared.attachments[0].source !== 'generated_calibration_report') throw new Error('generated DOCX attachment metadata is wrong');
if (process.env.CALIBRATION_REPORT_PROOF_PATH) fs.writeFileSync(process.env.CALIBRATION_REPORT_PROOF_PATH, Buffer.from(await generatedRecord.blob.arrayBuffer()));

const brokenZip = await context.JSZip.loadAsync(templateBytes);
brokenZip.remove('word/document.xml');
templateBytes = await brokenZip.generateAsync({ type:'uint8array', compression:'STORE' });
context.CalibrationReportConfig.templateUrl = '/broken-template.docx';
let missingSlotCode = '';
try { await api.preparePayload({ calibration_report: complete }, 'node-test', { regenerate:true }); }
catch (error) { missingSlotCode = error.code || ''; }
if (missingSlotCode !== 'calibration_report_template_slot_missing') throw new Error('missing template slot was not rejected');
templateBytes = fs.readFileSync(templatePath);
context.CalibrationReportConfig.templateUrl = '/static/templates/calibration-report/calibration-report-template.docx';

records.delete(generated.blob_id);
api.apply(prepared.calibration_report);
await new Promise(resolve => setTimeout(resolve, 0));
if (removedDocuments !== 1 || documents.value) throw new Error('missing Blob did not remove the ready document chip');
let missingCode = '';
try { await api.preparePayload({ calibration_report: prepared.calibration_report }, 'node-test'); }
catch (error) { missingCode = error.code || ''; }
if (missingCode !== 'calibration_report_blob_missing') throw new Error('missing blob did not require regeneration');
const regenerated = await api.preparePayload({ calibration_report: prepared.calibration_report }, 'node-test', { regenerate:true });
if (!records.has(regenerated.calibration_report.generated.blob_id)) throw new Error('explicit regeneration did not write a replacement blob');
if (addedDocuments !== 2 || documents.value !== 'Calibration Report') throw new Error('regeneration did not restore the ready document chip');
const supersededBlobId = regenerated.calibration_report.generated.blob_id;
api.apply(regenerated.calibration_report);
const modelInput = editor.elements.find(element => element.getAttribute('data-cr-field') === 'machine.model');
if (!modelInput) throw new Error('real Calibration Report model input was not built');
modelInput.value = 'MobileDart Evolution MX8';
editor.dispatch('input', { target:modelInput });
const editedAfterInput = api.collect();
if (editedAfterInput.generated.blob_id || !editedAfterInput.generated_cleanup.blob_ids.includes(supersededBlobId)) throw new Error('real input did not retain the superseded Blob cleanup reference');
if (documents.value) throw new Error('real input did not remove the ready document chip');
failBlobSaves = true;
let failedReplacement = false;
try { await api.preparePayload({ calibration_report: editedAfterInput }, 'node-test', { regenerate:true }); }
catch (error) { failedReplacement = /simulated Blob write failure/.test(error.message); }
if (!failedReplacement || !records.has(supersededBlobId) || api.collect().generated.blob_id) throw new Error('failed replacement did not preserve the recoverable old Blob');
failBlobSaves = false;
const replacement = await api.preparePayload({ calibration_report: editedAfterInput }, 'node-test', { regenerate:true });
if (replacement.calibration_report.generated.blob_id === supersededBlobId || records.has(supersededBlobId) || !records.has(replacement.calibration_report.generated.blob_id)) throw new Error('edited regeneration did not replace the superseded Blob');
if (replacement.calibration_report.generated_cleanup.blob_ids.length) throw new Error('successful replacement retained a stale cleanup reference');
const mainTsrBlobId = 'main-tsr-pdf-blob';
const supportingBlobId = 'supporting-upload-blob';
records.set(mainTsrBlobId, { id:mainTsrBlobId });
records.set(supportingBlobId, { id:supportingBlobId });
await api.remove();
if (records.has(replacement.calibration_report.generated.blob_id) || documents.value) throw new Error('Remove did not clean up the current generated report Blob');
if (!records.has(mainTsrBlobId) || !records.has(supportingBlobId)) throw new Error('Remove deleted a non-report Blob');
if (!deletedBlobIds.includes(replacement.calibration_report.generated.blob_id)) throw new Error('Remove did not target the current report Blob');
const supersededBlobRemoved = !records.has(supersededBlobId);

currentTSR = { calibration_report:prepared.calibration_report, attachments:[] };
api.apply(prepared.calibration_report);
api.open();
finalModalOpen = true;
finalPersisted = { source:'localstorage', attachments_not_durable:true };
await api.saveFinalReport();
if (!finalModalOpen || !/durable|storage/i.test(finalStatus)) throw new Error('non-durable final persistence falsely closed or lacked an actionable error');
fallbackModalStayedOpen = finalModalOpen;
const finalFallbackBlobId = api.collect().generated.blob_id;
if (!finalFallbackBlobId || !records.has(finalFallbackBlobId)) throw new Error('non-durable final persistence discarded the generated Blob');
api.open();
finalModalOpen = true;
finalPersisted = { source:'offline_tsr_page' };
await api.saveFinalReport();
if (finalModalOpen || !records.has(api.collect().generated.blob_id)) throw new Error('durable final persistence did not close or retain the generated Blob');
indexedModalClosed = !finalModalOpen;

if (process.env.CALIBRATION_REPORT_BOUNDARY_DIR) {
  api.apply(complete);
  documents.value = 'Calibration Report';
  for (const [fieldPath, ruleName] of boundaryCases) {
    const boundary = JSON.parse(JSON.stringify(complete));
    setNested(boundary, fieldPath, 'x'.repeat(fitRules[ruleName].maxLength));
    const boundaryPayload = await api.preparePayload({ calibration_report:boundary, attachments:[] }, 'node-boundary', { regenerate:true });
    const boundaryRecord = records.get(boundaryPayload.calibration_report.generated.blob_id);
    fs.writeFileSync(path.join(process.env.CALIBRATION_REPORT_BOUNDARY_DIR, ruleName + '.docx'), Buffer.from(await boundaryRecord.blob.arrayBuffer()));
  }
}

console.log(JSON.stringify({
  migratedSignature: migrated.signature.image === png,
  manufacturerDefault: migrated.machine.manufacturer === 'Shimadzu' && filled.machine.manufacturer === 'Shimadzu',
  manufacturerCustomPreserved: customManufacturerPreserved,
  performanceCriteria: api.getSource().performance.length,
  autofill: { client: filled.facility.name, phone: filled.facility.telephone, email: filled.facility.email, location: filled.facility.location, model: filled.machine.model, serial: filled.machine.serial_number, engineer: filled.calibration.engineer_name },
  docxMime: generatedRecord.type,
  docxFilename: generated.filename,
  sourceTableCount: (generatedDocument.match(/<w:tbl\b/g) || []).length,
  signatureRelationship: generatedRels.includes('media/calibration-signature.png'),
  missingSlotCode,
  missingBlobCode: missingCode,
  documentChipLifecycle: { added: addedDocuments, removed: removedDocuments },
  supersededBlobRemoved,
  regenerated: true,
  finalStorageFallbackOpen: fallbackModalStayedOpen,
  finalIndexedDBClosed: indexedModalClosed,
  finalBlobRetained: records.has(api.collect().generated.blob_id)
}));
})().catch(error => { console.error(error.stack || error); process.exitCode = 1; });
'''

NODE_ENTRY_PAGE_SCRIPT = r'''
const fs = require("fs");
const path = require("path");
const vm = require("vm");
const root = process.cwd();
const png = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAHgAAAAeCAYAAADnydqVAAAAVElEQVR42u3WsQkAMAwEsdt/aWeDlMEEHfwCVuNGX5cTABZgARZgARZgAQYswAIswAKsJ8CVLRtgwIABy5MlwAIswAIswIAFWIAFWIAFWJcOqjWBWhan81EAAAAASUVORK5CYII=";
const records = new Map();
let doc;
const hiddenFocusAttempts = [];
class ClassList {
  constructor(owner, value) { this.owner = owner; this.values = new Set(String(value || "").split(/\s+/).filter(Boolean)); }
  add(value) { this.values.add(value); }
  remove(value) { this.values.delete(value); }
  contains(value) { return this.values.has(value); }
  toggle(value, force) { const next = force === undefined ? !this.values.has(value) : !!force; if(next) this.add(value); else this.remove(value); return next; }
}
class Element {
  constructor(attributes, tag) {
    this.attributes = attributes || {}; this.tagName = tag || "div"; this.value = this.attributes.value || ""; this.textContent = "";
    this.listeners = {}; this.classList = new ClassList(this, this.attributes.class); this.hidden = false; this.disabled = false; this.style = {}; this.scrollTop = 0; this.parentElement = null;
  }
  getAttribute(name) { return Object.prototype.hasOwnProperty.call(this.attributes, name) ? this.attributes[name] : null; }
  setAttribute(name, value) { this.attributes[name] = String(value); if(name === "class") this.classList = new ClassList(this, value); if(name === "hidden") this.hidden = true; }
  removeAttribute(name) { delete this.attributes[name]; if(name === "hidden") this.hidden = false; }
  getClientRects() { let node = this; while(node) { if(node.hidden || node.getAttribute("hidden") !== null || (node.classList && node.classList.contains("d-none")) || (node.classList && node.classList.contains("calibration-report-page") && !node.classList.contains("is-active"))) return []; node = node.parentElement || null; } return [{}]; }
  matches(selector) {
    if(selector === ".calibration-report-tab") return this.classList.contains("calibration-report-tab");
    const id = String(selector).match(/^#(.+)$/); if(id) return this.getAttribute("id") === id[1];
    const attr = String(selector).match(/^\[([^=\]]+)(?:="([^"]*)")?\]$/); if(attr) return this.getAttribute(attr[1]) !== null && (!attr[2] || this.getAttribute(attr[1]) === attr[2]);
    return false;
  }
  addEventListener(name, handler) { (this.listeners[name] ||= []).push(handler); }
  dispatch(name, event) { const next = event || {}; next.target ||= this; next.currentTarget = this; for(const handler of this.listeners[name] || []) handler(next); return next; }
  focus() { if(this.getClientRects().length === 0) hiddenFocusAttempts.push(this); doc.activeElement = this; this.focused = true; }
  contains(element) { return element === this || this._focusables?.includes(element) || false; }
  scrollIntoView() {}
}
const ids = new Map();
function register(element) { if(element.getAttribute("id")) ids.set(element.getAttribute("id"), element); return element; }
const editor = register(new Element({ id:"calibration-report-editor" }));
Object.defineProperty(editor, "innerHTML", {
  set(value) {
    this.html = value; this.elements = [];
    const tagPattern = /<\/?([a-z]+)\b([^>]*)>/gi; let match; let activePanel = null;
    while((match = tagPattern.exec(value))) {
      if(match[0][1] === "/") { if(match[1].toLowerCase() === "section") activePanel = null; continue; }
      const attributes = {}; for(const item of match[2].matchAll(/([:\w-]+)(?:="([^"]*)")?/g)) attributes[item[1]] = item[2] || "";
      if(attributes.id === "cr-signature-pad") continue;
      if(!attributes.id && !attributes.class && !Object.keys(attributes).some(key => key.indexOf("data-cr-") === 0)) continue;
      const element = register(new Element(attributes, match[1])); element.parentElement = activePanel || editor; this.elements.push(element);
      if(attributes["data-cr-page-panel"]) activePanel = element;
    }
  },
  get() { return this.html || ""; }
});
editor.elements = [];
const overlay = register(new Element({ id:"calibration-report-overlay" }));
const workspace = new Element({ class:"calibration-report-workspace" });
const closeButton = register(new Element({ id:"calibration-report-close" }, "button"));
const saveButton = register(new Element({ id:"calibration-report-save" }, "button"));
const generateButton = register(new Element({ id:"calibration-report-generate" }, "button"));
const generateLabel = register(new Element({ id:"calibration-report-generate-label" }));
const downloadButton = register(new Element({ id:"calibration-report-download", class:"d-none" }, "button"));
const removeButton = register(new Element({ id:"calibration-report-toolbar-remove", class:"d-none" }, "button"));
const entryButton = register(new Element({ id:"calibration-report-create-btn" }, "button"));
const entryLabel = register(new Element({ id:"calibration-report-entry-label" }));
const status = register(new Element({ id:"calibration-report-status" }));
const summary = register(new Element({ id:"calibration-report-summary" }));
const filename = register(new Element({ id:"calibration-report-filename" }));
const capacity = register(new Element({ id:"calibration-report-capacity" }));
const note = register(new Element({ id:"calibration-report-attachment-note" }));
const documents = register(new Element({ id:"tsr-documents" }));
documents.value = "";
const negativeTabButton = new Element({ id:"negative-tabindex-control", tabindex:"-1" }, "button");
overlay._focusables = [closeButton, saveButton, generateButton, downloadButton, removeButton, negativeTabButton];
overlay._focusables.forEach(element => { element.parentElement = overlay; });
editor.parentElement = overlay;
overlay.querySelectorAll = selector => {
  if(selector.indexOf("button,") !== 0) return [];
  const candidates = overlay._focusables.concat(editor.elements);
  return candidates.filter((element, index) => {
    if(candidates.indexOf(element) !== index) return false;
    const tag = String(element.tagName || "").toLowerCase();
    return ["button","a","input","select","textarea"].includes(tag) || (element.getAttribute("tabindex") !== null && element.getAttribute("tabindex") !== "-1");
  });
};
overlay.contains = element => overlay.querySelectorAll("button, [href], input, select, textarea, [tabindex]:not([tabindex=\"-1\"])").includes(element);
const documentListeners = {};
doc = {
  activeElement: null,
  querySelector(selector) {
    if(selector[0] === "#") return ids.get(selector.slice(1)) || editor.elements.find(element => element.getAttribute("id") === selector.slice(1)) || null;
    if(selector === ".calibration-report-workspace") return workspace;
    if(selector === ".calibration-report-tab") return editor.elements.find(element => element.matches(selector)) || null;
    return null;
  },
  querySelectorAll(selector) { return editor.elements.filter(element => element.matches(selector)); },
  createElement: tag => new Element({}, tag),
  addEventListener(name, handler) { if(name === "DOMContentLoaded") handler(); else (documentListeners[name] ||= []).push(handler); },
  dispatch(name, event) { for(const handler of documentListeners[name] || []) handler(event || {}); }
};
const context = { console, Blob, Uint8Array, ArrayBuffer, Promise, Date, Math, JSON, setTimeout, clearTimeout, document:doc, URL:{ createObjectURL:() => "blob:test", revokeObjectURL:() => {} } };
context.window = context; context.self = context; context.globalThis = context;
context.CalibrationReportConfig = {
  templateUrl:"/unused.docx",
  certificateCatalog:JSON.parse(fs.readFileSync(path.join(root, "static", "templates", "calibration-certificate", "calibration-certificate-catalog.json"), "utf8"))
};
context.getTSRAttachmentCapacity = () => ({ total:0, max:10 });
context.collectTSRData = () => ({});
context.getSelectedStandaloneSchedule = () => ({ client_name:"Scheduled Client", client_address:"Scheduled Address", client_contact:{ phone:"0917-schedule", email:"schedule@example.test" }, product_name:"Scheduled Model", product_id:"SCHEDULED-1", date_iso:"2026-08-19", serviced_by:"Scheduled Engineer" });
context.showTSRStatus = () => {};
context.offlineTSRConfirm = async () => true;
context.loadOfflineTSRBlobRecord = async id => records.get(id) || null;
context.deleteOfflineTSRBlobRecord = async id => { records.delete(id); };
context.addTSRDocument = label => { documents.value = label; };
context.removeTSRDocument = () => { documents.value = ""; };
vm.createContext(context);
vm.runInContext(fs.readFileSync(path.join(root, "static/js/app-calibration-report.js"), "utf8"), context);
function fail(message) { throw new Error(message); }
function keyboardEvent(key, shiftKey) { return { key, shiftKey:!!shiftKey, defaultPrevented:false, preventDefault(){ this.defaultPrevented = true; } }; }
function focusableDialogElements() { return overlay.querySelectorAll('button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])').filter(element => !element.disabled && !element.hidden && element.getAttribute("tabindex") !== "-1" && element.getAttribute("aria-hidden") !== "true" && !(element.classList && element.classList.contains("d-none")) && element.getClientRects().length > 0); }
function editorControl(path) { return editor.elements.find(element => element.getAttribute("data-cr-field") === path) || null; }
function pagePanel(page) { return editor.elements.find(element => element.getAttribute("data-cr-page-panel") === String(page)) || null; }
function pageControls(page, visible) { const panel = pagePanel(page); return visible.filter(element => element.parentElement === panel); }
function exercisePage(page, tab, label, errors) {
  tab.dispatch("click");
  const visible = focusableDialogElements(); const controls = pageControls(page, visible); const first = visible[0]; const last = visible[visible.length - 1];
  if(!pagePanel(page) || !controls.length || first !== closeButton || last !== controls[controls.length - 1]) errors.push(label + " exact visible endpoints were not identified");
  const inactive = page === 1 ? editorControl("calibration.test_tool_model") : editorControl("facility.name");
  if(inactive && inactive.getClientRects().length !== 0) errors.push(label + " inactive display:none panel still has layout geometry");
  hiddenFocusAttempts.length = 0; if(last) last.focus();
  const forward = keyboardEvent("Tab", false); doc.dispatch("keydown", forward);
  if(!forward.defaultPrevented || doc.activeElement !== closeButton || hiddenFocusAttempts.length) errors.push(label + " forward wrap was contaminated by an inactive display:none panel");
  hiddenFocusAttempts.length = 0; closeButton.focus();
  const backward = keyboardEvent("Tab", true); doc.dispatch("keydown", backward);
  if(!backward.defaultPrevented || doc.activeElement !== last || hiddenFocusAttempts.length) errors.push(label + " backward Shift+Tab wrap was contaminated by an inactive display:none panel");
}
function fnv(value) { let hash = 2166136261; for(const character of value) { hash ^= character.charCodeAt(0); hash = Math.imul(hash, 16777619); } return ("00000000" + (hash >>> 0).toString(16)).slice(-8); }
function setReadyFields(report) {
  Object.assign(report.facility, { name:"Ready Client", address:"Ready Address", telephone:"0917", email:"ready@example.test", location:"Radiology" });
   Object.assign(report.machine, { manufacturer:"Shimadzu", modality:"Digital Angiography System", model:"Mobile Dart Evolution MX9", serial_number:"READY-1" });
  Object.assign(report.calibration, { machine_calibration_date:"2026-08-19", next_calibration_date:"2027-08-19", test_tool_manufacturer:"Tool Co", test_tool_model:"Tool 1", test_tool_serial:"TOOL-1", test_tool_calibration_date:"2026-08-01", engineer_name:"Engineer" });
  report.mechanical_checks.forEach(item => { item.result = "Pass"; }); report.generator_checks.forEach(item => { item.result = "Pass"; });
  report.exposure.small[0].nominal_kvp = "80"; report.exposure.large[0].nominal_kvp = "100"; report.performance_results = report.performance_results.map(() => "Pass"); report.signature = { name:"Engineer", image:png }; return report;
}
(async () => {
  const api = context.calibrationReport;
  if(entryLabel.textContent !== "Create Calibration Report" || status.textContent !== "Not Started") fail("inactive card state is wrong");
  api.create();
  if(entryLabel.textContent !== "Continue Calibration Report" || status.textContent !== "Draft") fail("draft card state is wrong");
  if(!overlay.classList.contains("is-open")) fail("create did not open the editor");
const draft = api.collect(); if(draft.facility.name !== "Scheduled Client" || draft.machine.model !== "Scheduled Model") fail("create did not autofill the schedule");
if(draft.machine.manufacturer !== "Shimadzu") fail("blank report did not default the manufacturer");
const manufacturerInput = editorControl("machine.manufacturer");
if(!manufacturerInput || String(manufacturerInput.tagName).toLowerCase() !== "input" || manufacturerInput.getAttribute("type") !== "text" || manufacturerInput.getAttribute("readonly") !== null || manufacturerInput.getAttribute("disabled") !== null || manufacturerInput.value !== "Shimadzu") fail("Manufacturer control is not an editable Shimadzu text input");
const customManufacturer = "  Custom Imaging  ";
api.apply({ status:"draft", machine:{ manufacturer:customManufacturer } });
if(api.collect().machine.manufacturer !== customManufacturer) fail("custom manufacturer was not preserved");
api.apply(draft);
const backInput = editorControl("facility.name"); if(!backInput) fail("Back persistence field was not built");
  const backValue = "Back Persisted Facility"; backInput.value = backValue; editor.dispatch("input", { target:backInput });
  workspace.scrollTop = 321; closeButton.dispatch("click");
  const backState = api.collect();
  if(overlay.classList.contains("is-open") || doc.activeElement !== entryButton || !backState || backState.facility.name !== backValue) fail("Back did not preserve the edited report value and restore entry focus");
  api.apply(backState); api.open();
  if(workspace.scrollTop !== 321 || doc.activeElement !== closeButton || backInput.value !== backValue) fail("Back value or scroll/focus state was not restored on reopen");
  const escapeInput = editorControl("machine.model"); if(!escapeInput) fail("Escape persistence field was not built");
  const escapeValue = "Escape Persisted Model"; escapeInput.value = escapeValue; editor.dispatch("input", { target:escapeInput });
  const escapeEvent = keyboardEvent("Escape", false); doc.dispatch("keydown", escapeEvent);
  const escapeState = api.collect();
  if(!escapeEvent.defaultPrevented || overlay.classList.contains("is-open") || doc.activeElement !== entryButton || !escapeState || escapeState.facility.name !== backValue || escapeState.machine.model !== escapeValue) fail("Escape did not preserve edited report values and restore entry focus");
  api.apply(escapeState); api.open();
  if(backInput.value !== backValue || escapeInput.value !== escapeValue) fail("Escape values were not restored in the editor on reopen");
  const tab1 = doc.querySelector("#calibration-report-tab-1"); const tab2 = doc.querySelector("#calibration-report-tab-2");
  if(tab1.getAttribute("aria-selected") !== "true" || tab1.getAttribute("tabindex") !== "0" || tab2.getAttribute("aria-selected") !== "false" || tab2.getAttribute("tabindex") !== "-1") fail("tab ARIA state is wrong");
  tab1.dispatch("keydown", { key:"ArrowRight", preventDefault(){} }); if(tab2.getAttribute("aria-selected") !== "true" || doc.activeElement !== tab2) fail("tab arrow navigation is wrong");
  const tab3 = doc.querySelector("#calibration-report-tab-3");
  tab1.dispatch("click");
  const ariaPanel = pagePanel(1); const ariaProbe = editorControl("facility.name");
  if(!ariaPanel || !ariaProbe) fail("ARIA-only geometry probe was not built");
  ariaPanel.setAttribute("aria-hidden", "true"); if(ariaProbe.getClientRects().length === 0) fail("aria-hidden incorrectly changed layout geometry"); ariaPanel.setAttribute("aria-hidden", "false");
  const geometryProbe = new Element({}); geometryProbe.setAttribute("hidden", ""); if(geometryProbe.getClientRects().length !== 0) fail("self hidden geometry was not suppressed"); geometryProbe.removeAttribute("hidden"); geometryProbe.classList.add("d-none"); if(geometryProbe.getClientRects().length !== 0) fail("self d-none geometry was not suppressed");
  if(focusableDialogElements().includes(negativeTabButton)) fail("tabindex=-1 control was treated as a visible dialog endpoint");
  const wrapErrors = [];
  exercisePage(1, tab1, "Page 1", wrapErrors); exercisePage(2, tab2, "Page 2", wrapErrors); exercisePage(3, tab3, "Page 3", wrapErrors);
  if(wrapErrors.length) fail(wrapErrors.join(" | "));
  const finalEscapeEvent = keyboardEvent("Escape", false); doc.dispatch("keydown", finalEscapeEvent);
  if(!finalEscapeEvent.defaultPrevented || overlay.classList.contains("is-open") || doc.activeElement !== entryButton) fail("final Escape did not close and restore focus");
  api.open(); const ready = setReadyFields(api.collect()); api.apply(ready); const clean = api.collect(); const stable = JSON.stringify(clean, (key, value) => ["status","updated_at","auto_fill","generated","generated_cleanup","auto_document","certificate","certificate_approval"].includes(key) ? undefined : value); const fingerprint = fnv(stable); const blobId = "calibration-report-" + fingerprint;
  clean.generated = { fingerprint, attachment_id:blobId, blob_id:blobId, filename:"ready.docx", size:4 }; records.set(blobId, { blob:new Blob(["ready"]) }); api.apply(clean); await new Promise(resolve => setTimeout(resolve, 0));
   if(entryLabel.textContent !== "Open Calibration Report" || status.textContent !== "Final Saved" || downloadButton.classList.contains("d-none") || removeButton.classList.contains("d-none")) fail("ready card or toolbar state is wrong");
   if(!context.document.querySelector("#calibration-report-generate-label") || context.document.querySelector("#calibration-report-generate-label").textContent !== "Generate Sample DOCX") fail("ready toolbar did not expose sample generation");
  const ordinaryId = "ordinary-attachment"; records.set(ordinaryId, { blob:new Blob(["ordinary"]) }); await api.remove(); if(entryLabel.textContent !== "Create Calibration Report" || records.has(blobId) || !records.has(ordinaryId)) fail("Remove did not clean only the generated report");
  console.log(JSON.stringify({ inactive:"Not Started", draft:"Draft", ready:"Ready", labels:["Create Calibration Report","Continue Calibration Report","Open Calibration Report"], autofill:true, backValueRestored:true, escapeValueRestored:true, scrollRestored:true, tabAria:true, forwardTabWrapped:true, backwardShiftTabWrapped:true, toolbar:true, narrowCleanup:true }));
})().catch(error => { console.error(error.stack || error); process.exitCode = 1; });
'''


class CalibrationReportContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app_source = (ROOT / 'app.py').read_text(encoding='utf-8')
        cls.template_source = (ROOT / 'templates' / 'offline_tsr.html').read_text(encoding='utf-8')
        cls.script_source = (ROOT / 'static' / 'js' / 'app-calibration-report.js').read_text(encoding='utf-8')
        cls.css_source = (ROOT / 'static' / 'css' / 'app-calibration-report.css').read_text(encoding='utf-8')

    def test_supplied_docx_template_is_byte_exact_and_has_expected_package(self):
        self.assertTrue(TEMPLATE.is_file())
        self.assertEqual(hashlib.sha256(TEMPLATE.read_bytes()).hexdigest().upper(), EXPECTED_TEMPLATE_SHA256)
        with zipfile.ZipFile(TEMPLATE) as package:
            names = set(package.namelist())
            self.assertEqual(len(names), 26)
            for part in ('[Content_Types].xml', 'word/document.xml', 'word/_rels/document.xml.rels', 'word/footer2.xml'):
                self.assertIn(part, names)
            document = package.read('word/document.xml').decode('utf-8')
            relationships = package.read('word/_rels/document.xml.rels').decode('utf-8')
            self.assertEqual(len(re.findall(r'<w:tbl(?:\s|>)', document)), 5)
            for footer in ('word/footer1.xml', 'word/footer2.xml', 'word/footer3.xml'):
                self.assertIn(footer, names)
            self.assertEqual(len(re.findall(r'<w:footerReference\b', document)), 3)
            for footer in ('footer1.xml', 'footer2.xml', 'footer3.xml'):
                self.assertIn(f'Target="{footer}"', relationships)
            for marker in ('CALIBRATION REPORT', 'AVERAGE EXPOSURE OUTPUT', 'FOCAL SIZE', '0.6', '1.0', 'SID: 100cm', 'PERFORMANCE CRITERIA'):
                self.assertIn(marker, document)
            for forbidden in ('<w:sdt', '<w:bookmarkStart', '<w:fldChar', '<w:instrText'):
                self.assertNotIn(forbidden, document)

    def test_local_docx_runtime_license_and_cache_are_present(self):
        self.assertGreater(RUNTIME.stat().st_size, 90_000)
        self.assertIn('MIT License', LICENSE.read_text(encoding='utf-8'))
        assert_cache_version_at_least(self, 120, self.app_source)
        self.assertIn("'/static/templates/calibration-report/calibration-report-template.docx'", self.app_source)
        self.assertIn("'/static/vendor/jszip/jszip.min.js'", self.app_source)
        self.assertIn("'/static/templates/calibration-certificate/calibration-certificate-template-data.js?v=2'", self.app_source)
        self.assertIn('calibration-certificate-template.pdf', self.app_source)
        self.assertNotIn('calibration-certificate-template.bin', self.app_source)
        self.assertIn("'/static/vendor/pdf-lib/pdf-lib.min.js'", self.app_source)
        assert_cache_version_at_least(self, 93, self.app_source)

    def test_supplied_certificate_template_is_byte_exact_letter_and_expected_form(self):
        self.assertTrue(CERT_TEMPLATE.is_file())
        self.assertEqual(hashlib.sha256(CERT_TEMPLATE.read_bytes()).hexdigest().upper(), EXPECTED_CERT_TEMPLATE_SHA256)
        self.assertFalse((CERT_TEMPLATE.parent / 'calibration-certificate-template.bin').exists())
        reader = PdfReader(str(CERT_TEMPLATE))
        self.assertFalse(reader.is_encrypted)
        self.assertEqual(len(reader.pages), 1)
        self.assertEqual(tuple(float(value) for value in reader.pages[0].mediabox), (0.0, 0.0, 612.0, 792.0))
        self.assertEqual(set(reader.get_fields() or {}), {'Textfield', 'Text1', 'Text2', 'Text3', 'Text4', 'Text5', 'Text6', 'Textfield-0', 'Rodito Aretano Jr'})
        self.assertGreater(CERT_RUNTIME.stat().st_size, 400_000)
        self.assertIn('MIT License', CERT_LICENSE.read_text(encoding='utf-8'))
        self.assertTrue(CERT_RUNTIME_TEMPLATE.is_file())
        self.assertEqual(hashlib.sha256(CERT_RUNTIME_TEMPLATE.read_bytes()).hexdigest().upper(), EXPECTED_CERT_RUNTIME_SHA256)
        runtime_reader = PdfReader(str(CERT_RUNTIME_TEMPLATE))
        self.assertEqual(tuple(float(value) for value in runtime_reader.pages[0].mediabox), (0.0, 0.0, 612.0, 792.0))
        runtime_text = runtime_reader.pages[0].extract_text() or ''
        self.assertNotIn('Senior Service Manager', runtime_text)
        self.assertNotIn('Medical Systems Division', runtime_text)

    def test_certificate_template_data_is_javascript_and_decodes_exact_canonical_bytes(self):
        self.assertTrue(CERT_DATA.is_file())
        source_bytes = CERT_DATA.read_bytes()
        self.assertFalse(source_bytes.startswith(b'%PDF-'))
        source = source_bytes.decode('utf-8')
        self.assertIn("Object.defineProperty(config, 'certificateTemplateData'", source)
        self.assertNotIn('calibration-certificate-template.pdf', source)
        self.assertNotIn('calibration-certificate-template.bin', source)
        match = re.search(r"byteLength: (\d+), sha256: '([0-9A-F]+)', base64: \[(.*?)\]\.join", source, re.DOTALL)
        self.assertIsNotNone(match)
        encoded = ''.join(re.findall(r"'([A-Za-z0-9+/=]*)'", match.group(3)))
        decoded = base64.b64decode(encoded, validate=True)
        self.assertEqual(int(match.group(1)), len(decoded))
        self.assertEqual(int(match.group(1)), CERT_RUNTIME_TEMPLATE.stat().st_size)
        self.assertEqual(match.group(2), EXPECTED_CERT_RUNTIME_SHA256)
        self.assertEqual(hashlib.sha256(decoded).hexdigest().upper(), EXPECTED_CERT_RUNTIME_SHA256)
        self.assertEqual(decoded, CERT_RUNTIME_TEMPLATE.read_bytes())
        self.assertEqual(decoded[:5], b'%PDF-')

    def test_report_module_is_docx_only_and_page_has_no_calibration_pdf_workflow(self):
        self.assertIn('JSZip.loadAsync', self.script_source)
        self.assertIn('application/vnd.openxmlformats-officedocument.wordprocessingml.document', self.script_source)
        self.assertIn('calibration-report-template.docx', self.template_source)
        self.assertIn('calibration-certificate-template-data.js', self.template_source)
        self.assertIn('generateCertificateSample', self.script_source)
        self.assertIn('Generate Sample DOCX', self.template_source)
        self.assertIn('Download Final DOCX', self.template_source)
        for forbidden in ('buildPdf', 'calibration-report-template.pdf', 'calibration-report-preview', 'calibration-report-pdf-frame', 'certificateTemplateUrl', 'calibration-certificate-template.bin', 'certificateRetryUrl', 'certificateResponseContentType'):
            self.assertNotIn(forbidden, self.script_source)
        for forbidden in ('calibration-report-template.pdf', 'calibration-report-preview', 'calibration-report-pdf-frame', 'calibration-certificate-template.bin'):
            self.assertNotIn(forbidden, self.template_source)
        self.assertNotIn('id="calibration-report-preview-btn"', self.template_source)
        self.assertNotIn('id="calibration-report-preview-download"', self.template_source)
        self.assertIn('rawSignature.data_url', self.script_source)  # legacy migration only

    def test_sample_final_page3_and_clear_form_contract(self):
        self.assertIn('Generate Sample DOCX', self.template_source)
        self.assertIn('Save Final Report', self.template_source)
        self.assertIn('Download Final DOCX', self.template_source)
        self.assertIn('Clear Form', self.template_source)
        self.assertIn('focal_spots', self.script_source)
        self.assertIn('focal_sizes', self.script_source)
        self.assertIn('SAMPLE_', self.script_source)
        self.assertIn('calibration_report_not_finalized', self.script_source)
        self.assertIn('FOCAL SIZE:', self.script_source)
        self.assertIn('compactPageThreeGap', self.script_source)
        self.assertIn('outline:2px solid rgba(37,99,235', self.css_source)

    def test_certificate_catalog_and_final_save_contract(self):
        catalog_path = ROOT / 'static' / 'templates' / 'calibration-certificate' / 'calibration-certificate-catalog.json'
        catalog = json.loads(catalog_path.read_text(encoding='utf-8'))
        self.assertEqual(len(catalog['equipment_names']), 6)
        self.assertEqual(len(catalog['models']), 47)
        self.assertEqual(catalog['models'][27:39], MOBILE_DART_MODELS)
        self.assertEqual(len(set(catalog['models'])), 47)
        payload = json.dumps(
            {'equipment_names': catalog['equipment_names'], 'models': catalog['models']},
            ensure_ascii=False,
            sort_keys=True,
            separators=(',', ':'),
        ).encode('utf-8')
        self.assertEqual(hashlib.sha256(payload).hexdigest().upper(), 'A3B0DF1616AC5DDAB53F3B6C142294D1ECDB2928AA7E85121A98C7BCA6FC969E')
        self.assertIn('certificateCatalog', self.template_source)
        self.assertIn("var DEFAULT_MANUFACTURER = 'Shimadzu';", self.script_source)
        self.assertIn('equipmentNameMarkup', self.script_source)
        self.assertIn('modelMarkup', self.script_source)
        self.assertIn('certificateModelMatch', self.script_source)
        self.assertIn('certificate.equipment_model', self.script_source)
        self.assertIn('required aria-required="true"', self.script_source)
        persistence = self.script_source.index('await window.saveStandaloneTSRDraft(true)')
        close = self.script_source.index('close();', persistence)
        self.assertGreater(close, persistence)
        self.assertIn('Select an exact catalog Equipment Model before saving', self.script_source)

    def test_node_behavior_covers_sample_final_page3_clear_and_unicode(self):
        self.assertTrue(NODE.is_file(), f'Bundled Node runtime missing: {NODE}')
        result = subprocess.run([str(NODE), '-e', NODE_SAMPLE_FINAL_SCRIPT], cwd=ROOT, text=True, capture_output=True, check=False)
        self.assertEqual(result.returncode, 0, msg=result.stderr or result.stdout)
        payload = json.loads(result.stdout.strip().splitlines()[-1])
        for key in ('legacyDefaults', 'smallOnly', 'largeOnly', 'bothSelected', 'smallOnlyOutput', 'largeOnlyOutput', 'missingSizeRejected', 'incompleteSampleWarning', 'sampleUnattached', 'unfinalizedRefused', 'finalAttached', 'unicodePreserved', 'focalSizesInDocx', 'page3FocalGapPreserved', 'page3FooterGapCompacted', 'page3MeasurementsCentered', 'signatureNameOmitted', 'signatureIsLarger', 'editInvalidates', 'clearPreservesSchedule'):
            self.assertTrue(payload[key], key)

    def test_entry_page_has_single_card_action_and_accessible_dialog_contract(self):
        card = self.template_source.split('id="calibration-report-card"', 1)[1].split('<div class="card p-3 p-md-4 mb-3 no-print">', 1)[0]
        documents_label = self.template_source.index('Submitted Original Documents')
        documents_card = self.template_source.rfind('<div class="card', 0, documents_label)
        calibration_card = self.template_source.rfind('<div class="card', 0, self.template_source.index('id="calibration-report-card"'))
        self.assertEqual(self.template_source[documents_card:calibration_card].count('<div class="card'), 1)
        self.assertLess(calibration_card, self.template_source.index('Offline TSR Attachments', calibration_card))
        button_ids = re.findall(r'<button\b[^>]*id="([^"]+)"[^>]*>', card)
        self.assertEqual(button_ids, ['calibration-report-create-btn'])
        self.assertNotIn('calibration-report-edit-btn', card)
        self.assertNotIn('calibration-report-generate-btn', card)
        self.assertNotIn('calibration-report-download-btn', card)
        self.assertNotIn('calibration-report-remove-btn', card)
        self.assertIn('Create Calibration Report', self.script_source)
        self.assertIn('Continue Calibration Report', self.script_source)
        self.assertIn('Open Calibration Report', self.script_source)
        self.assertIn('id="calibration-report-toolbar-remove"', self.template_source)
        for forbidden_binding in ('#calibration-report-edit-btn', '#calibration-report-generate-btn', '#calibration-report-download-btn', '#calibration-report-remove-btn'):
            self.assertNotIn(forbidden_binding, self.script_source)
        self.assertIn('aria-modal="true"', self.template_source)
        self.assertIn('inert', self.script_source)
        self.assertIn('aria-selected', self.script_source)
        self.assertIn('aria-controls', self.script_source)
        self.assertIn('tabindex', self.script_source)
        self.assertIn('focusDialog', self.script_source)
        self.assertIn("getAttribute('tabindex') !== '-1'", self.script_source)
        self.assertIn('getClientRects().length > 0', self.script_source)
        self.assertIn("css/app-calibration-report.css') }}?v=7", self.template_source)
        self.assertIn("calibration-certificate-template-data.js') }}?v=2", self.template_source)
        self.assertIn("js/app-calibration-report.js') }}?v=22", self.template_source)
        self.assertIn("'/static/js/app-calibration-report.js?v=22'", self.app_source)
        assert_cache_version_at_least(self, 120, self.app_source)
        self.assertIn('id="calibration-report-modal-status"', self.template_source)
        self.assertIn('calibration-report-modal-status is-visible tone-', self.script_source)
    def test_node_behavior_covers_entry_page_state_focus_scroll_toolbar_and_cleanup(self):
        self.assertTrue(NODE.is_file(), f'Bundled Node runtime missing: {NODE}')
        result = subprocess.run([str(NODE), '-e', NODE_ENTRY_PAGE_SCRIPT], cwd=ROOT, text=True, capture_output=True, check=False)
        self.assertEqual(result.returncode, 0, msg=result.stderr or result.stdout)
        payload = json.loads(result.stdout.strip().splitlines()[-1])
        self.assertEqual(payload['labels'], ['Create Calibration Report', 'Continue Calibration Report', 'Open Calibration Report'])
        for key in ('autofill', 'backValueRestored', 'escapeValueRestored', 'scrollRestored', 'tabAria', 'forwardTabWrapped', 'backwardShiftTabWrapped', 'toolbar', 'narrowCleanup'):
            self.assertTrue(payload[key], key)

    def test_certificate_toolbar_state_release_and_cache_contract(self):
        self.assertIn('id="calibration-report-bsid"', self.template_source)
        self.assertIn('maxlength="40"', self.template_source)
        self.assertIn('id="calibration-report-certificate-number"', self.template_source)
        self.assertIn('id="calibration-report-certificate-generate"', self.template_source)
        generate_index = self.template_source.index('id="calibration-report-generate"')
        certificate_index = self.template_source.index('id="calibration-report-certificate-controls"')
        self.assertLess(generate_index, certificate_index)
        self.assertLess(certificate_index, self.template_source.index('id="calibration-report-final-save"'))
        self.assertNotIn('certificateTemplateUrl', self.template_source)
        self.assertIn("'/static/templates/calibration-certificate/calibration-certificate-template-data.js?v=2'", self.app_source)
        self.assertIn('calibration-certificate-template.pdf', self.app_source)
        self.assertNotIn('calibration-certificate-template.bin', self.app_source)
        self.assertIn("'/static/vendor/pdf-lib/pdf-lib.min.js'", self.app_source)
        self.assertIn('2026-08-24-calibration-certificate-approval', (ROOT / 'static' / 'changelog' / 'releases.json').read_text(encoding='utf-8'))
        self.assertIn('certificate: { bsid:', self.script_source)
        self.assertIn("'certificate','certificate_approval'].includes(key)", self.script_source)
        self.assertIn('certificateTemplateData', self.script_source)
        self.assertNotIn('certificateTemplateUrl', self.script_source)
        self.assertNotIn('fetch(attempt.url', self.script_source)
        self.assertIn('generateCertificateSample', self.script_source)
        self.assertIn('Textfield-0', self.script_source)
        self.assertIn("form.flatten()", self.script_source)
        self.assertIn('certificateDataFontSize', self.script_source)
        self.assertIn('setFontSize(dataSize)', self.script_source)
        self.assertNotIn('drawRectangle', self.script_source)

    def test_node_catalog_fail_closed_controls(self):
        self.assertTrue(NODE.is_file(), f'Bundled Node runtime missing: {NODE}')
        result = subprocess.run([str(NODE), '-e', NODE_INVALID_CATALOG_SCRIPT], cwd=ROOT, text=True, capture_output=True, check=False)
        self.assertEqual(result.returncode, 0, msg=result.stderr or result.stdout)
        payload = json.loads(result.stdout.strip().splitlines()[-1])
        for key in ('missingCatalogRejected', 'malformedCatalogRejected', 'sampleFailureActionable'):
            self.assertTrue(payload[key], key)

    def test_node_behavior_covers_certificate_mapping_persistence_incomplete_and_failure_guards(self):
        self.assertTrue(NODE.is_file(), f'Bundled Node runtime missing: {NODE}')
        import os
        import tempfile
        with tempfile.TemporaryDirectory() as temp_dir:
            proof = pathlib.Path(temp_dir) / 'certificate.pdf'
            env = dict(os.environ, CALIBRATION_CERTIFICATE_PROOF_PATH=str(proof))
            result = subprocess.run([str(NODE), '-e', NODE_CERTIFICATE_SCRIPT], cwd=ROOT, text=True, capture_output=True, check=False, env=env)
            self.assertEqual(result.returncode, 0, msg=result.stderr or result.stdout)
            payload = json.loads(result.stdout.strip().splitlines()[-1])
            for key in ('legacyDefaults', 'mobileDartCatalog', 'mobileDartMatches', 'mobileDartCertificateMappings', 'normalizedBsid', 'mapping', 'embeddedDataAsset', 'embeddedTemplateExact', 'noRawPdfFetch', 'bsidPreservesFinal', 'completeSample', 'exactlyOneSampleBlobDownload', 'noRawTemplateDownload', 'incompleteSample', 'missingRuntimeNoDownload', 'missingEncodedNoDownload', 'corruptEncodedNoDownload', 'missingFieldsNoDownload'):
                self.assertTrue(payload[key], key)
            self.assertEqual(payload['composed'], '2026-0820-B-42')
            self.assertTrue(proof.is_file())
            reader = PdfReader(str(proof))
            self.assertEqual(len(reader.pages), 1)
            self.assertIsNone(reader.get_fields())
            self.assertIsNone(reader.trailer['/Root'].get('/AcroForm'))
            self.assertIn(reader.pages[0].get('/Annots'), (None, []))
            extracted = reader.pages[0].extract_text() or ''
            for marker in ('2026-0820-B-43', 'Digital Angiography System', 'MobileDart Evolution MX9', 'SN-42', '2026/08/20', '2027/08/20', "St. Mary's", 'TSR-77'):
                self.assertIn(marker, extracted)

    def test_node_behavior_covers_migration_autofill_docx_generation_and_regeneration(self):
        self.assertTrue(NODE.is_file(), f'Bundled Node runtime missing: {NODE}')
        result = subprocess.run([str(NODE), '-e', NODE_BEHAVIOR_SCRIPT], cwd=ROOT, text=True, capture_output=True, check=False)
        self.assertEqual(result.returncode, 0, msg=result.stderr or result.stdout)
        payload = json.loads(result.stdout.strip().splitlines()[-1])
        self.assertTrue(payload['migratedSignature'])
        self.assertTrue(payload['manufacturerDefault'])
        self.assertTrue(payload['manufacturerCustomPreserved'])
        self.assertEqual(payload['performanceCriteria'], 2)
        self.assertEqual(payload['autofill'], {
            'client': 'Scheduled Client',
            'phone': '0917-current',
            'email': 'current@example.test',
            'location': 'Radiology',
            'model': 'Scheduled Model',
            'serial': 'SCHEDULED-SERIAL',
            'engineer': 'Scheduled Engineer',
        })
        self.assertEqual(payload['docxMime'], DOCX_MIME)
        self.assertTrue(payload['docxFilename'].endswith('.docx'))
        self.assertEqual(payload['sourceTableCount'], 5)
        self.assertTrue(payload['signatureRelationship'])
        self.assertEqual(payload['missingSlotCode'], 'calibration_report_template_slot_missing')
        self.assertEqual(payload['missingBlobCode'], 'calibration_report_blob_missing')
        self.assertEqual(payload['documentChipLifecycle'], {'added': 4, 'removed': 3})
        self.assertTrue(payload['supersededBlobRemoved'])
        self.assertTrue(payload['regenerated'])
        self.assertTrue(payload['finalStorageFallbackOpen'])
        self.assertTrue(payload['finalIndexedDBClosed'])
        self.assertTrue(payload['finalBlobRetained'])

    def test_report_only_draft_persistence_and_truthful_status(self):
        self.assertTrue(NODE.is_file(), f'Bundled Node runtime missing: {NODE}')
        result = subprocess.run([str(NODE), '-e', NODE_DRAFT_PERSISTENCE_SCRIPT], cwd=ROOT, text=True, capture_output=True, check=False)
        self.assertEqual(result.returncode, 0, msg=result.stderr or result.stdout)
        payload = json.loads(result.stdout.strip().splitlines()[-1])
        self.assertTrue(payload['meaningful'])
        self.assertTrue(payload['persistenceInvoked'])
        self.assertTrue(payload['reportValueRestored'])
        self.assertTrue(payload['successStatus'])
        self.assertEqual(payload['failureStatuses'], ['skipped', 'failed', 'none', 'missing'])

    def test_attachment_capacity_guard_does_not_allow_silent_truncation(self):
        self.assertIn('function getTSRAttachmentCapacity', self.template_source)
        self.assertIn("errorCode:'too_many_attachments'", self.template_source)
        self.assertIn('no file will be truncated', self.template_source)
        self.assertNotIn('.slice(0, TSR_SUPPORTING_ATTACHMENT_MAX_COUNT)', self.template_source)

NODE_DRAFT_PERSISTENCE_SCRIPT = r'''
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const root = process.cwd();
const template = fs.readFileSync(path.join(root, 'templates', 'offline_tsr.html'), 'utf8');
const gateStart = template.indexOf('function isStandaloneTSRDraftMeaningful(data){');
const gateEnd = template.indexOf('\n}', gateStart) + 2;
if (gateStart < 0 || gateEnd <= gateStart) throw new Error('draft meaningfulness gate not found');
const gateContext = {
  buildComplaintFromSelectedSchedule: () => '',
  normalizeStandaloneDraftComparable: value => String(value || '').trim().toLowerCase().replace(/\s+/g, ' ')
};
vm.createContext(gateContext);
vm.runInContext(template.slice(gateStart, gateEnd), gateContext);
const reportOnlyPayload = {
  selectedSchedule: {},
  calibration_report: { status:'draft', facility:{ name:'Calibration-only Facility' } }
};
if (!gateContext.isStandaloneTSRDraftMeaningful(reportOnlyPayload)) throw new Error('active report-only payload was treated as empty');
if (gateContext.isStandaloneTSRDraftMeaningful({ selectedSchedule:{} })) throw new Error('empty TSR became meaningful');
if (gateContext.isStandaloneTSRDraftMeaningful({ selectedSchedule:{}, calibration_report:{ status:'not_started' } })) throw new Error('not-started report became meaningful');
if (!gateContext.isStandaloneTSRDraftMeaningful({ selectedSchedule:{}, 'tsr-remarks':'ordinary TSR detail' })) throw new Error('ordinary TSR draft stopped being meaningful');

const statuses = [];
const context = {
  console,
  Blob,
  Uint8Array,
  ArrayBuffer,
  Promise,
  Date,
  Math,
  JSON,
  setTimeout,
  clearTimeout,
  URL: { createObjectURL:() => 'blob:test', revokeObjectURL:() => {} },
  document: { querySelector:() => null, querySelectorAll:() => [], createElement:() => ({}), addEventListener:() => {} },
  CalibrationReportConfig: {},
  showTSRStatus: (message, tone) => statuses.push({ message, tone })
};
context.window = context;
context.self = context;
context.globalThis = context;
vm.createContext(context);
vm.runInContext(fs.readFileSync(path.join(root, 'static', 'js', 'app-calibration-report.js'), 'utf8'), context);

const api = context.calibrationReport;
const savedRecords = [];
let saveMode = 'success';
let saveCalls = 0;
context.collectTSRData = () => ({ calibration_report: api.collect() });
context.saveStandaloneTSRDraft = async silent => {
  if (!silent) throw new Error('test only covers the local draft path');
  saveCalls += 1;
  const payload = context.collectTSRData();
  if (saveMode === 'success') {
    savedRecords.push({ payload, source:'offline_tsr_page' });
    return savedRecords[savedRecords.length - 1];
  }
  if (saveMode === 'skipped') return { skipped:true, reason:'empty_tsr_draft' };
  if (saveMode === 'failed') return { failed:true, source:'none' };
  if (saveMode === 'none') return { source:'none' };
  return undefined;
};

(async () => {
  api.apply(reportOnlyPayload.calibration_report);
  await api.saveDraft();
  if (saveCalls !== 1 || savedRecords[0]?.payload?.calibration_report?.facility?.name !== 'Calibration-only Facility') {
    throw new Error('report-only save did not invoke persistence with the entered value');
  }
  api.reset();
  api.apply(savedRecords[0].payload.calibration_report);
  if (api.collect()?.facility?.name !== 'Calibration-only Facility') throw new Error('saved report value was not restored on reopen/apply');
  if (statuses.at(-1)?.message !== 'Calibration Report draft saved with the TSR draft.' || statuses.at(-1)?.tone !== 'success') throw new Error('successful save did not show the success status');

  const failureModes = ['skipped', 'failed', 'none', 'missing'];
  for (const mode of failureModes) {
    saveMode = mode;
    await api.saveDraft();
    const status = statuses.at(-1);
    if (status?.message !== 'Calibration Report draft could not be saved on this device.' || status?.tone !== 'danger') throw new Error(mode + ' save incorrectly showed success');
  }
  console.log(JSON.stringify({ meaningful:true, persistenceInvoked:true, reportValueRestored:true, successStatus:true, failureStatuses:failureModes }));
})().catch(error => { console.error(error.stack || error); process.exitCode = 1; });

'''

NODE_SAMPLE_FINAL_SCRIPT = r'''
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const root = process.cwd();
const templatePath = path.join(root, 'static', 'templates', 'calibration-report', 'calibration-report-template.docx');
const runtimePath = path.join(root, 'static', 'vendor', 'jszip', 'jszip.min.js');
const certificateCatalog = JSON.parse(fs.readFileSync(path.join(root, 'static', 'templates', 'calibration-certificate', 'calibration-certificate-catalog.json'), 'utf8'));
const png = 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAHgAAAAeCAYAAADnydqVAAAAVElEQVR42u3WsQkAMAwEsdt/aWeDlMEEHfwCVuNGX5cTABZgARZgARZgAQYswAIswAKsJ8CVLRtgwIABy5MlwAIswAIswIAFWIAFWIAFWJcOqjWBWhan81EAAAAASUVORK5CYII=';
const records = new Map();
const documents = { value: '' };
const modalStatus = { textContent:'', className:'', setAttribute:()=>{} };
let savedDrafts = 0;
let persistedPayload = null;
let currentTSR = {};
let schedule = { client_name:'Schedule Client', client_address:'Schedule Address', product_name:'Schedule Model', product_id:'SCHEDULE-SERIAL', date_iso:'2026-08-20', serviced_by:'Schedule Engineer', client_contact:{} };

class FakeElement {
  constructor(attributes = {}) { this.attributes = attributes; this.value = ''; this.listeners = {}; this.classList = { toggle:()=>{}, contains:()=>false }; }
  getAttribute(name) { return Object.prototype.hasOwnProperty.call(this.attributes, name) ? this.attributes[name] : null; }
  matches(selector) { const match = String(selector).match(/^\[([^\]=]+)\]$/); return !!(match && this.getAttribute(match[1]) !== null); }
  addEventListener(name, handler) { (this.listeners[name] ||= []).push(handler); }
  dispatch(name, event = { target:this }) { for (const handler of this.listeners[name] || []) handler(event); }
  focus() {}
  scrollIntoView() {}
}
const editor = new FakeElement();
Object.defineProperty(editor, 'innerHTML', {
  set(value) {
    this.html = value;
    this.elements = [];
    for (const attribute of ['data-cr-field', 'data-cr-check', 'data-cr-exposure', 'data-cr-performance', 'data-cr-focal-spot', 'data-cr-focal-size']) {
      const pattern = new RegExp('<(?:input|textarea)\\b[^>]*' + attribute + '="([^"]+)"[^>]*>', 'g');
      let match;
      while ((match = pattern.exec(value))) this.elements.push(new FakeElement({ [attribute]:match[1] }));
    }
  },
  get() { return this.html || ''; }
});
editor.elements = [];
const link = { href:'', download:'', click:()=>{}, remove:()=>{} };
const context = {
  console, Blob, Uint8Array, ArrayBuffer, Promise, Date, Math, JSON, setTimeout, clearTimeout, atob, btoa,
  URL: { createObjectURL:()=> 'blob:test', revokeObjectURL:()=>{} },
  document: {
    activeElement:null,
    body: { appendChild:()=>{}, removeChild:()=>{} },
    querySelector: selector => selector === '#calibration-report-editor' ? editor : (selector === '#tsr-documents' ? documents : (selector === '#calibration-report-modal-status' ? modalStatus : null)),
    querySelectorAll: selector => editor.elements.filter(element => element.matches(selector)),
    createElement: () => link,
    addEventListener: () => {}
  },
  CalibrationReportConfig: { templateUrl:'/static/templates/calibration-report/calibration-report-template.docx', certificateCatalog },
  fetch: async () => ({ ok:true, arrayBuffer:async () => fs.readFileSync(templatePath) }),
  saveOfflineTSRBlobRecord: async record => records.set(record.id, record),
  loadOfflineTSRBlobRecord: async id => records.get(id) || null,
  deleteOfflineTSRBlobRecord: async id => records.delete(id),
  addTSRDocument: label => { documents.value = documents.value ? documents.value + ',' + label : label; },
  removeTSRDocument: label => { documents.value = documents.value.split(',').filter(item => item !== label).join(','); },
  offlineTSRConfirm: async () => true,
  showTSRStatus: () => {},
  getSelectedStandaloneSchedule: () => schedule,
  collectTSRData: () => currentTSR
};
context.window = context; context.self = context; context.globalThis = context;
vm.createContext(context);
vm.runInContext(fs.readFileSync(runtimePath, 'utf8'), context);
vm.runInContext(fs.readFileSync(path.join(root, 'static', 'js', 'app-calibration-report.js'), 'utf8'), context);

function report(overrides = {}) {
  const rows = [{ nominal_kvp:'80', measured_kvp:'80.2', ma_mas:'100mA', dose_mgy:'1.2', dose_rate:'2.4', time_msec:'10', measured_time:'0.010' }, {}, {}, {}, {}];
  const base = {
    status:'draft', facility:{ name:"St. Mary's & Niño Clinic", address:'123 Main Street', telephone:'Phone', email:'client@example.test', location:'Radiology' },
    machine:{ manufacturer:'Shimadzu', modality:'Mobile X-Ray System', model:'MobileDart Evolution MX9', serial_number:'SN-1' },
    technical:{}, calibration:{ machine_calibration_date:'2026-08-20', next_calibration_date:'2027-08-20', test_tool_manufacturer:'Tool Co', test_tool_model:'Tool 1', test_tool_serial:'TOOL-1', test_tool_calibration_date:'2026-08-01', engineer_name:'Engineer' },
    mechanical_checks:[{result:'Pass'}], generator_checks:[{result:'Pass'},{result:'Pass'},{result:'Pass'},{result:'Pass'}],
    exposure:{ small:rows, large:[Object.assign({}, rows[0], { nominal_kvp:'100' }), {}, {}, {}, {}] }, performance_results:['Pass','Pass'], signature:{ name:'Engineer', image:png },
    focal_spots:{ small:true, large:true }, focal_sizes:{ small:'0.6', large:'1.0' }
  };
  return Object.assign(base, overrides);
}

(async () => {
  const api = context.calibrationReport;
  const legacy = report(); delete legacy.focal_spots; delete legacy.focal_sizes;
  api.apply(legacy);
  const migrated = api.collect();
  const legacyDefaults = migrated.focal_spots.small && migrated.focal_spots.large && migrated.focal_sizes.small === '0.6' && migrated.focal_sizes.large === '1.0';

  const smallOnly = report({ focal_spots:{small:true, large:false}, focal_sizes:{small:'0.72', large:'1.14'}, exposure:{small:report().exposure.small, large:[{}, {}, {}, {}, {}]} });
  const largeOnly = report({ focal_spots:{small:false, large:true}, focal_sizes:{small:'0.72', large:'1.14'}, exposure:{small:[{}, {}, {}, {}, {}], large:report().exposure.large} });
  const fullRows = Array.from({length:5}, () => ({ nominal_kvp:'12', measured_kvp:'12', ma_mas:'12', dose_mgy:'12', dose_rate:'12', time_msec:'12', measured_time:'12' }));
  const bothSelected = report({ focal_sizes:{ small:'0.72', large:'1.14' }, exposure:{ small:fullRows.map(row => Object.assign({}, row)), large:fullRows.map(row => Object.assign({}, row)) } });
  const smallValidation = api.validateForFinalSave({ calibration_report:smallOnly }).ok;
  const largeValidation = api.validateForFinalSave({ calibration_report:largeOnly }).ok;
  const bothValidation = api.validateForFinalSave({ calibration_report:bothSelected }).ok;
  const missingSizeRejected = !api.validateForFinalSave({ calibration_report:report({ focal_sizes:{ small:'', large:'1.0' } }) }).ok;

  const incomplete = report({ facility:Object.assign({}, report().facility, { address:'' }) });
  api.apply(incomplete);
  currentTSR = { calibration_report:api.collect(), attachments:[] };
  await api.generateSample();
  const incompleteSampleWarning = link.download.startsWith('SAMPLE_') && records.size === 0 && modalStatus.className.includes('warning') && modalStatus.textContent.includes('missing');

  api.apply(bothSelected);
  currentTSR = { calibration_report:api.collect(), attachments:[] };
  let unfinalizedRefused = false;
  try { await api.preparePayload(currentTSR, 'calibration-unfinalized'); } catch (error) { unfinalizedRefused = error.code === 'calibration_report_not_finalized'; }
  await api.generateSample();
  const sampleUnattached = records.size === 0 && documents.value === '' && !api.getAttachment({ calibration_report:api.collect() }) && link.download.startsWith('SAMPLE_');
  context.saveStandaloneTSRDraft = async () => { savedDrafts += 1; persistedPayload = { calibration_report:api.collect(), attachments:[] }; return { source:'indexeddb', payload:persistedPayload }; };
  await api.saveFinalReport();
  const finalized = api.collect();
  const finalRecord = records.get(finalized.generated.blob_id);
  api.apply(persistedPayload.calibration_report);
  await new Promise(resolve => setTimeout(resolve, 0));
  const reopened = api.collect();
  const finalAttached = !!finalRecord && reopened.facility.name === "St. Mary's & Niño Clinic" && documents.value === 'Calibration Report' && savedDrafts === 1 && api.getAttachment({ calibration_report:reopened });
  if (process.env.CALIBRATION_REPORT_PROOF_PATH) fs.writeFileSync(process.env.CALIBRATION_REPORT_PROOF_PATH, Buffer.from(await finalRecord.blob.arrayBuffer()));
  const zip = await context.JSZip.loadAsync(await finalRecord.blob.arrayBuffer());
  const xml = await zip.file('word/document.xml').async('string');
  async function conditionalOutput(report, ownerId){
    const preparedReport = await api.preparePayload({ calibration_report:report, attachments:[] }, ownerId, { regenerate:true, finalize:true });
    const record = records.get(preparedReport.calibration_report.generated.blob_id);
    const archive = await context.JSZip.loadAsync(await record.blob.arrayBuffer());
    if(process.env.CALIBRATION_REPORT_CONDITIONAL_QA_DIR){
      fs.writeFileSync(path.join(process.env.CALIBRATION_REPORT_CONDITIONAL_QA_DIR, ownerId + '.docx'), Buffer.from(await record.blob.arrayBuffer()));
    }
    return await archive.file('word/document.xml').async('string');
  }
  const smallOnlyXml = await conditionalOutput(smallOnly, 'small-only');
  const largeOnlyXml = await conditionalOutput(largeOnly, 'large-only');
  const smallOnlyTables = directBlocks((smallOnlyXml.match(/<w:body>([\s\S]*)<\/w:body>/) || [])[1] || '', 'tbl');
  const largeOnlyTables = directBlocks((largeOnlyXml.match(/<w:body>([\s\S]*)<\/w:body>/) || [])[1] || '', 'tbl');
  const smallOnlyOutput = smallOnlyTables.length === 4 && !smallOnlyXml.includes('FOCAL SPOT       : LARGE') && smallOnlyXml.includes('0.72');
  const largeOnlyOutput = largeOnlyTables.length === 4 && !largeOnlyXml.includes('FOCAL SPOT       : SMALL') && largeOnlyXml.includes('1.14');
  const unicodePreserved = xml.includes('St. Mary&apos;s &amp; Niño Clinic');
  const focalSizesInDocx = xml.includes('0.72') && xml.includes('1.14');
  function directBlocks(xmlText, tag) {
    const blocks = []; let depth = 0; let start = -1;
    const matcher = new RegExp('<w:' + tag + '\\b[^>]*>|<\/w:' + tag + '>', 'g');
    let match;
    while ((match = matcher.exec(xmlText))) {
      if (match[0].startsWith('</')) {
        if (depth === 1 && start >= 0) blocks.push({ start, end:matcher.lastIndex });
        depth = Math.max(0, depth - 1);
      } else if (/\/\s*>$/.test(match[0])) {
        if (depth === 0) blocks.push({ start:match.index, end:matcher.lastIndex });
      } else {
        if (depth === 0) start = match.index;
        depth += 1;
      }
    }
    return blocks;
  }
  const body = (xml.match(/<w:body>([\s\S]*)<\/w:body>/) || [])[1] || '';
  const page3Tables = directBlocks(body, 'tbl');
  const focalGap = page3Tables.length >= 4 ? body.slice(page3Tables[2].end, page3Tables[3].start) : '';
  const page3Gap = page3Tables.length >= 5 ? body.slice(page3Tables[3].end, page3Tables[4].start) : '';
  const page3FocalGapPreserved = (focalGap.match(/<w:p\b/g) || []).length === 2;
  const page3FooterGapCompacted = (page3Gap.match(/<w:p\b/g) || []).length === 1;
  function measurementRowsAreCentered(tableBlock) {
    const tableXml = body.slice(tableBlock.start, tableBlock.end);
    const rows = directBlocks(tableXml, 'tr').slice(4, 9);
    return rows.length === 5 && rows.every(row => {
      const rowXml = tableXml.slice(row.start, row.end);
      const cells = directBlocks(rowXml, 'tc');
      return cells.length === 7 && cells.every(cell => {
        const cellXml = rowXml.slice(cell.start, cell.end);
        const paragraphs = directBlocks(cellXml, 'p');
        if (!paragraphs.length) return false;
        const paragraphXml = cellXml.slice(paragraphs[0].start, paragraphs[0].end);
        return /<w:jc\b[^>]*w:val="center"[^>]*\/>/.test(paragraphXml);
      });
    });
  }
  const page3MeasurementsCentered = page3Tables.length >= 4 && measurementRowsAreCentered(page3Tables[2]) && measurementRowsAreCentered(page3Tables[3]);
  const signatureExtent = xml.match(/<wp:extent cx="(\d+)" cy="(\d+)"\/><wp:effectExtent[^>]*\/\><wp:docPr id="2000000001"/);
  const signatureNameOmitted = !xml.includes('<w:t xml:space="preserve">Engineer</w:t><w:tab/>');
  const signatureIsLarger = !!signatureExtent && Number(signatureExtent[1]) >= 2400000 && Number(signatureExtent[2]) >= 500000;

  documents.value = '';
  const modelInput = editor.elements.find(element => element.getAttribute('data-cr-field') === 'machine.model');
  modelInput.value = 'Edited Model'; editor.dispatch('input', { target:modelInput });
  const editInvalidates = !api.collect().generated.blob_id && documents.value === '';

  api.apply(finalized);
  currentTSR = { calibration_report:api.collect(), attachments:[], 'tsr-customer-name':'Ordinary TSR' };
  await api.saveFinalReport();
  await api.clearForm();
  const cleared = api.collect();
  const clearPreservesSchedule = cleared.facility.name === 'Schedule Client' && cleared.machine.model === 'Schedule Model' && cleared.focal_spots.small && cleared.focal_spots.large && cleared.focal_sizes.small === '0.6' && cleared.focal_sizes.large === '1.0' && documents.value === '';
  console.log(JSON.stringify({ legacyDefaults, smallOnly:smallValidation, largeOnly:largeValidation, bothSelected:bothValidation, smallOnlyOutput, largeOnlyOutput, missingSizeRejected, incompleteSampleWarning, sampleUnattached, unfinalizedRefused, finalAttached, unicodePreserved, focalSizesInDocx, page3FocalGapPreserved, page3FooterGapCompacted, page3MeasurementsCentered, signatureNameOmitted, signatureIsLarger, editInvalidates, clearPreservesSchedule }));
})().catch(error => { console.error(error.stack || error); process.exitCode = 1; });
'''

NODE_CERTIFICATE_SCRIPT = r'''
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const root = process.cwd();
const canonicalTemplatePath = path.join(root, 'static', 'templates', 'calibration-certificate', 'calibration-certificate-runtime-v2.pdf');
const dataPath = path.join(root, 'static', 'templates', 'calibration-certificate', 'calibration-certificate-template-data.js');
const runtimePath = path.join(root, 'static', 'vendor', 'pdf-lib', 'pdf-lib.min.js');
const scriptPath = path.join(root, 'static', 'js', 'app-calibration-report.js');
const listeners = {};
const elements = new Map();
const downloads = [];
const statuses = [];
class FakeElement {
  constructor(attributes = {}) {
    this.attributes = attributes;
    this.value = '';
    this.textContent = '';
    this.listeners = {};
    this.classList = { toggle:() => {}, contains:() => false };
    this.hidden = false;
    this.disabled = false;
  }
  getAttribute(name) { return Object.prototype.hasOwnProperty.call(this.attributes, name) ? this.attributes[name] : null; }
  setAttribute(name, value) { this.attributes[name] = String(value); }
  removeAttribute(name) { delete this.attributes[name]; }
  matches(selector) {
    const match = String(selector).match(/^\[([^\]=]+)(?:="([^"]*)")?\]$/);
    return !!match && this.getAttribute(match[1]) !== null && (match[2] === undefined || this.getAttribute(match[1]) === match[2]);
  }
  addEventListener(name, handler) { (this.listeners[name] ||= []).push(handler); }
  dispatch(name, event = { target:this }) { for (const handler of this.listeners[name] || []) handler(event); }
  focus() {}
  scrollIntoView() {}
  getClientRects() { return [{}]; }
}
const editor = new FakeElement();
Object.defineProperty(editor, 'innerHTML', {
  set(value) {
    this.html = value;
    this.elements = [];
    for (const attribute of ['data-cr-field', 'data-cr-check', 'data-cr-exposure', 'data-cr-performance', 'data-cr-focal-spot', 'data-cr-focal-size']) {
      const pattern = new RegExp('<(?:input|textarea)\\b[^>]*' + attribute + '="([^"]+)"[^>]*>', 'g');
      let match;
      while ((match = pattern.exec(value))) this.elements.push(new FakeElement({ [attribute]:match[1] }));
    }
  },
  get() { return this.html || ''; }
});
editor.elements = [];
for (const id of ['#calibration-report-editor', '#calibration-report-bsid', '#calibration-report-certificate-number', '#calibration-report-certificate-generate', '#calibration-report-modal-status', '#tsr-documents', '#calibration-report-close', '#calibration-report-create-btn']) {
  elements.set(id, id === '#calibration-report-editor' ? editor : new FakeElement());
}
const link = new FakeElement();
link.click = () => downloads.push(link.download);
link.remove = () => {};
let currentTSR = {};
const rawFetchCalls = [];
const context = {
  console, Blob, Uint8Array, ArrayBuffer, Promise, Date, Math, JSON, setTimeout, clearTimeout, atob, btoa,
  URL: { createObjectURL:() => 'blob:test', revokeObjectURL:() => {} },
  document: {
    activeElement:null,
    body: { appendChild:() => {}, removeChild:() => {} },
    querySelector: selector => elements.get(selector) || null,
    querySelectorAll: selector => selector.includes('data-cr-') ? editor.elements : [],
    createElement: () => link,
    addEventListener: (name, handler) => { (listeners[name] ||= []).push(handler); }
  },
  CalibrationReportConfig: { certificateCatalog:JSON.parse(fs.readFileSync(path.join(root, 'static', 'templates', 'calibration-certificate', 'calibration-certificate-catalog.json'), 'utf8')) },
  fetch: async url => { rawFetchCalls.push(String(url)); throw new Error('raw certificate fetch should never run'); },
  collectTSRData: () => currentTSR,
  getEngineerInitialsSafe: () => 'JA',
  showTSRStatus: (message, tone) => statuses.push({ message, tone }),
  getSelectedStandaloneSchedule: () => null,
  saveStandaloneTSRDraft: async () => ({ source:'offline_tsr_page' })
};
context.window = context;
context.self = context;
context.globalThis = context;
vm.createContext(context);
vm.runInContext(fs.readFileSync(runtimePath, 'utf8'), context);
vm.runInContext(fs.readFileSync(dataPath, 'utf8'), context);
vm.runInContext(fs.readFileSync(scriptPath, 'utf8'), context);
for (const handler of listeners.DOMContentLoaded || []) handler();

function report(overrides = {}) {
  return Object.assign({
    status:'draft',
    facility:{ name:"St. Mary's & Niño Clinic" },
     machine:{ modality:'Digital Angiography System', model:'Mobile Dart Evolution MX9', serial_number:'SN-42' },
    calibration:{ machine_calibration_date:'2026-08-20', next_calibration_date:'2027-08-20' },
    certificate:{ bsid:'B-42' }
  }, overrides);
}

(async () => {
  const dataSource = fs.readFileSync(dataPath, 'utf8');
  const embeddedTemplateData = context.CalibrationReportConfig.certificateTemplateData;
  const embeddedTemplateBytes = Buffer.from(embeddedTemplateData.base64, 'base64');
  const embeddedDataAsset = !dataSource.startsWith('%PDF-') && dataSource.includes('certificateTemplateData') && !dataSource.includes('calibration-certificate-template.bin') && !dataSource.includes('calibration-certificate-template.pdf');
  const embeddedTemplateExact = embeddedTemplateBytes.equals(fs.readFileSync(canonicalTemplatePath)) && embeddedTemplateBytes.length === 517516 && embeddedTemplateData.sha256 === '20C84569CB120F90E9F9998D68021E99ABCBD65E3C9085C7640754C6F0EBE2D8';
  context.calibrationReport.apply({ status:'draft', facility:{ name:'Legacy' } });
  const legacyReport = context.calibrationReport.collect();
  const legacyDefaults = legacyReport.certificate.bsid === '' && legacyReport.machine.manufacturer === 'Shimadzu';
  const mobileDartModels = [
    'MobileDart Evolution MX9 Premium', 'MobileDart Evolution MX9c Premium',
    'MobileDart Evolution MX9v Premium', 'MobileDart Evolution MX9k Premium',
    'MobileDart Evolution MX9', 'MobileDart Evolution MX9c',
    'MobileDart Evolution MX9v', 'MobileDart Evolution MX9k',
    'MobileDart Evolution MX8', 'MobileDart Evolution MX8c',
    'MobileDart Evolution MX8v', 'MobileDart Evolution MX8k'
  ];
  const catalogModels = context.calibrationReport.getCertificateCatalog().models;
  const mobileDartCatalog = catalogModels.length === 47 && JSON.stringify(catalogModels.slice(27, 39)) === JSON.stringify(mobileDartModels) && new Set(catalogModels).size === 47;
  const mobileDartMatches = mobileDartModels.every(model => {
    const match = context.calibrationReport.getCertificateModelMatch(model);
    return match.status === 'exact' && match.value === model;
  });
  const complete = report();
  context.calibrationReport.apply(complete);
  const bsidInput = elements.get('#calibration-report-bsid');
  bsidInput.value = ' B-42 ';
  bsidInput.dispatch('input');
  const normalized = context.calibrationReport.collect();
  const composed = context.calibrationReport.getCertificateNumber(normalized);
  const fields = context.calibrationReport.getCertificateFields({ 'tsr-number':'TSR-77' }, normalized);
  const mapping = JSON.stringify(fields.values) === JSON.stringify({ Textfield:'2026-0820-B-42', Text1:'Digital Angiography System', Text2:'MobileDart Evolution MX9', Text3:'SN-42', Text4:'2026/08/20', Text5:'2027/08/20', Text6:"St. Mary's & Niño Clinic", 'Textfield-0':'TSR-77' });
  const mobileDartCertificateMappings = mobileDartModels.every(model => {
    const rawReport = report({ machine:Object.assign({}, complete.machine, { model }) });
    const mapped = context.calibrationReport.getCertificateFields({ 'tsr-number':'TSR-77' }, rawReport);
    return rawReport.machine.model === model && mapped.values.Text2 === model;
  });
  const finalized = Object.assign({}, normalized, { certificate:{ bsid:'B-43' }, generated:{ fingerprint:'kept', attachment_id:'kept', blob_id:'calibration-report-kept', filename:'kept.docx', size:1 } });
  context.calibrationReport.apply(finalized);
  bsidInput.value = 'B-43';
  bsidInput.dispatch('input');
  const bsidPreservesFinal = context.calibrationReport.collect().generated.blob_id === 'calibration-report-kept';

  currentTSR = { 'tsr-number':'TSR-77', calibration_report:context.calibrationReport.collect() };
  const built = await context.calibrationReport.generateCertificateSample();
  const completeSample = built && built.filename === 'SAMPLE_Calibration_Certificate_2026-0820-B-43.pdf' && built.missing.length === 0 && downloads.length === 1;
  const exactlyOneSampleBlobDownload = downloads.length === 1 && /^SAMPLE_Calibration_Certificate_.*\.pdf$/.test(downloads[0]);
  const noRawPdfFetch = rawFetchCalls.length === 0;
  if (process.env.CALIBRATION_CERTIFICATE_PROOF_PATH) fs.writeFileSync(process.env.CALIBRATION_CERTIFICATE_PROOF_PATH, Buffer.from(await built.blob.arrayBuffer()));

  context.calibrationReport.apply({ status:'draft' });
  currentTSR = { calibration_report:context.calibrationReport.collect() };
  const incompleteBuilt = await context.calibrationReport.generateCertificateSample();
  const incompleteSample = incompleteBuilt && incompleteBuilt.filename === 'SAMPLE_Calibration_Certificate.pdf' && incompleteBuilt.missing.length === 8 && downloads.length === 2 && statuses.at(-1)?.tone === 'warning';

  const savedPdfLib = context.PDFLib;
  context.PDFLib = null;
  await context.calibrationReport.generateCertificateSample();
  const missingRuntimeNoDownload = downloads.length === 2 && statuses.at(-1)?.tone === 'danger';
  context.PDFLib = savedPdfLib;

  delete context.CalibrationReportConfig.certificateTemplateData;
  await context.calibrationReport.generateCertificateSample();
  const missingEncodedNoDownload = downloads.length === 2 && statuses.at(-1)?.tone === 'danger' && statuses.at(-1)?.message.includes('embedded');
  Object.defineProperty(context.CalibrationReportConfig, 'certificateTemplateData', { value:Object.freeze(Object.assign({}, embeddedTemplateData, { base64:'not-base64' })), enumerable:true, configurable:true, writable:false });
  const originalLoad = context.PDFLib.PDFDocument.load;
  await context.calibrationReport.generateCertificateSample();
  const corruptEncodedNoDownload = downloads.length === 2 && statuses.at(-1)?.tone === 'danger' && statuses.at(-1)?.message.includes('corrupt');
  Object.defineProperty(context.CalibrationReportConfig, 'certificateTemplateData', { value:embeddedTemplateData, enumerable:true, configurable:true, writable:false });
  context.PDFLib.PDFDocument.load = async () => ({ getForm:() => ({ getFields:() => [{ getName:() => 'Textfield' }] }) });
  await context.calibrationReport.generateCertificateSample();
  const missingFieldsNoDownload = downloads.length === 2 && statuses.at(-1)?.tone === 'danger';
  context.PDFLib.PDFDocument.load = originalLoad;

  const noRawTemplateDownload = downloads.every(name => !String(name).includes('calibration-certificate-template') && /^SAMPLE_Calibration_Certificate(?:_.*)?\.pdf$/.test(name));
  console.log(JSON.stringify({ legacyDefaults, mobileDartCatalog, mobileDartMatches, mobileDartCertificateMappings, normalizedBsid:normalized.certificate.bsid === 'B-42', composed, mapping, embeddedDataAsset, embeddedTemplateExact, noRawPdfFetch, bsidPreservesFinal, completeSample, exactlyOneSampleBlobDownload, noRawTemplateDownload, incompleteSample, missingRuntimeNoDownload, missingEncodedNoDownload, corruptEncodedNoDownload, missingFieldsNoDownload }));
})().catch(error => { console.error(error.stack || error); process.exitCode = 1; });
'''

NODE_INVALID_CATALOG_SCRIPT = r'''
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const root = process.cwd();
const script = fs.readFileSync(path.join(root, 'static', 'js', 'app-calibration-report.js'), 'utf8');
const png = 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAHgAAAAeCAYAAADnydqVAAAAVElEQVR42u3WsQkAMAwEsdt/aWeDlMEEHfwCVuNGX5cTABZgARZgARZgAQYswAIswAKsJ8CVLRtgwIABy5MlwAIswAIswIAFWIAFWIAFWJcOqjWBWhan81EAAAAASUVORK5CYII=';

function run(catalog){
  const statuses = [];
  const context = {
    console, Blob, Uint8Array, ArrayBuffer, Promise, Date, Math, JSON, setTimeout, clearTimeout, atob, btoa,
    URL:{ createObjectURL:() => 'blob:test', revokeObjectURL:() => {} },
    CalibrationReportConfig:{ certificateCatalog:catalog },
    document:{ querySelector:() => null, querySelectorAll:() => [], createElement:() => ({}), addEventListener:() => {} },
    showTSRStatus:(message, tone) => statuses.push({ message:String(message || ''), tone }),
    collectTSRData:() => ({})
  };
  context.window = context; context.self = context; context.globalThis = context;
  vm.createContext(context);
  vm.runInContext(script, context);
  const api = context.calibrationReport;
  api.apply({ status:'draft' });
  const report = api.collect();
  report.status = 'draft';
  Object.assign(report.facility, { name:'Facility', address:'Address', telephone:'0917', email:'facility@example.test', location:'Radiology' });
  Object.assign(report.machine, { manufacturer:'Shimadzu', modality:'Raw Equipment', model:'Arbitrary Raw Model', serial_number:'SERIAL' });
  Object.assign(report.calibration, { machine_calibration_date:'2026-08-20', next_calibration_date:'2027-08-20', test_tool_manufacturer:'Tool Co', test_tool_model:'Tool 1', test_tool_serial:'TOOL-1', test_tool_calibration_date:'2026-08-01', engineer_name:'Engineer' });
  report.mechanical_checks.forEach(item => { item.result = 'Pass'; });
  report.generator_checks.forEach(item => { item.result = 'Pass'; });
  report.exposure.small[0].nominal_kvp = '80'; report.exposure.large[0].nominal_kvp = '100';
  report.performance_results = report.performance_results.map(() => 'Pass');
  report.signature = { name:'Engineer', image:png };
  const match = api.getCertificateModelMatch('Arbitrary Raw Model');
  const validation = api.validateForFinalSave({ calibration_report:report });
  return {
    match,
    validation,
    statuses,
    samplePromise: api.generateCertificateSample()
  };
}

(async () => {
  const missing = run({});
  const malformed = run({ equipment_names:['Raw Equipment'], models:Array(47).fill('Raw Model') });
  const sampleFailure = await missing.samplePromise;
  console.log(JSON.stringify({
    missingCatalogRejected:missing.match.status !== 'exact' && !missing.match.value && !missing.validation.ok,
    malformedCatalogRejected:malformed.match.status !== 'exact' && !malformed.match.value && !malformed.validation.ok,
    sampleFailureActionable:sampleFailure === null && missing.statuses.some(item => item.tone === 'danger' && /catalog/i.test(item.message))
  }));
})().catch(error => { console.error(error.stack || error); process.exitCode = 1; });
'''

if __name__ == '__main__':
    unittest.main()

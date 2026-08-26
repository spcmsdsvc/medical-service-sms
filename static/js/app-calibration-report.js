(function(){
  'use strict';

  var CONFIG = window.CalibrationReportConfig || {};
  var SOURCE = {
    mechanical: [
      {
        label: '4.1 Collimation Assessment',
        criteria: 'The total misalignment shall be within +-2% of SID. Each shall be within +-1% of SID.\nThe misalignment between X-Ray field and image receptor shall be within 1.5 degrees.\nThe X-Ray beam perpendicularity shall be within 1.5 degrees.'
      }
    ],
    generator: [
      { label: '5.1 Overload Circuit Protection', criteria: 'Present? Functioning?' },
      { label: '5.2 kVp Accuracy', criteria: 'For 100 kVp and below: The actual kVp shall be within +-6% of the set kVp.\nFor 101 kVp and above: The actual kVp shall be within +-6% of the set kVp.' },
      { label: '5.3 mA Accuracy /mA Linearity', criteria: 'The overall coefficient of linearity shall be <-0.1' },
      { label: '5.4 Exposure Time Accuracy', criteria: 'The actual time shall be within +-10% of the set time. For exposure time less than 100ms, +-20%' }
    ],
    performance: [
      'The average kVp shall not differ from the nominal kVp by ±6% for voltages less than or equal to 100kVp, or 6kV for voltages greater than 100kVp.',
      'The actual time shall be within +-10% of the set time. For exposure time less than 100ms, +-20%'
    ],
    exposureHeadersSmall: ['Nominal kVP Settings', 'Measured kVP', 'mA / mAs', 'Dose (mGy)', 'Dose Rate (mGy/s)', 'Time Settings (msec)', 'Measured Exposure Time (sec)'],
    exposureHeadersLarge: ['Nominal kVP Settings', 'Measured kVP', 'mA / mAs', 'Dose (mGy)', 'Dose Rate (mGy/s)', 'Time Settings (msec)', 'Measured Exposure Time (msec)']
  };
  var EXPOSURE_KEYS = ['nominal_kvp','measured_kvp','ma_mas','dose_mgy','dose_rate','time_msec','measured_time'];
  var DOCX_MIME = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document';
  var EXACT_FIT_CAPACITIES = {
    page1_value: { name:'page1_value', maxLength:40, label:'Page 1 identity/value' },
    page1_narrow: { name:'page1_narrow', maxLength:22, label:'Page 1 narrow value' },
    page2_result: { name:'page2_result', maxLength:28, label:'Page 2 check result' },
    page2_detail: { name:'page2_detail', maxLength:30, label:'Page 2 calibration detail' },
    page3_exposure: { name:'page3_exposure', maxLength:12, label:'Page 3 exposure value' },
    page3_performance: { name:'page3_performance', maxLength:36, label:'Page 3 performance result' }
  };
  var PAGE1_NARROW_FIELDS = ['machine.console_model','machine.console_serial','machine.tube1_model','machine.tube1_serial','machine.tube2_model','machine.tube2_serial'];
  var CERTIFICATE_CATALOG = CONFIG.certificateCatalog && typeof CONFIG.certificateCatalog === 'object' ? CONFIG.certificateCatalog : {};
  var CERTIFICATE_EQUIPMENT_NAMES = Array.isArray(CERTIFICATE_CATALOG.equipment_names) ? CERTIFICATE_CATALOG.equipment_names.map(String) : [];
  var CERTIFICATE_MODELS = Array.isArray(CERTIFICATE_CATALOG.models) ? CERTIFICATE_CATALOG.models.map(String) : [];
  var CERTIFICATE_CATALOG_ERROR = '';
  var CERTIFICATE_CATALOG_AVAILABLE = false;
  var EXACT_FIT_FIELD_PATHS = [
    'facility.name','facility.address','facility.telephone','facility.email','facility.location',
    'machine.manufacturer','machine.modality','machine.model','machine.serial_number','machine.console_model','machine.console_serial','machine.tube1_model','machine.tube1_serial','machine.tube2_model','machine.tube2_serial','machine.installation_date',
    'technical.max_tube_current_ma','technical.max_tube_voltage_kv','technical.tube_current_mas_range','technical.tube_voltage_kvp_range','technical.exposure_time_range','technical.max_rated_power_kw','technical.power_supply','technical.total_inherent_filtration',
    'calibration.machine_calibration_date','calibration.next_calibration_date','calibration.test_tool_manufacturer','calibration.test_tool_model','calibration.test_tool_serial','calibration.test_tool_calibration_date','calibration.engineer_name'
  ];

  function fitRuleForPath(path){
    path = String(path || '');
    if(PAGE1_NARROW_FIELDS.indexOf(path) >= 0) return EXACT_FIT_CAPACITIES.page1_narrow;
    if(/^(facility|machine|technical)\./.test(path)) return EXACT_FIT_CAPACITIES.page1_value;
    if(/^(mechanical_checks|generator_checks)\.\d+\.result$/.test(path)) return EXACT_FIT_CAPACITIES.page2_result;
    if(/^calibration\./.test(path)) return EXACT_FIT_CAPACITIES.page2_detail;
    if(/^exposure\.(small|large)\.\d+\./.test(path)) return EXACT_FIT_CAPACITIES.page3_exposure;
    if(/^performance_results\.\d+$/.test(path)) return EXACT_FIT_CAPACITIES.page3_performance;
    return null;
  }

  var state = blankState();
  var editorBuilt = false;
  var activePage = 1;
  var saveTimer = null;
  var signatureDrawing = false;
  var generatedBlobState = 'none';
  var overlayScrollTop = 0;
  var returnFocusElement = null;

  function clone(value){ return JSON.parse(JSON.stringify(value)); }

  function normalizeCatalogText(value){ return String(value === undefined || value === null ? '' : value).replace(/\s+/g,' ').trim(); }
  function normalizeCertificateModel(value){
    var text = String(value === undefined || value === null ? '' : value);
    try{ if(typeof text.normalize === 'function') text = text.normalize('NFKD'); }catch(error){}
    text = text.replace(/[\u0300-\u036f]/g,'').toLowerCase();
    return text.replace(/[^a-z0-9]/g,'');
  }
  function validateCertificateCatalog(catalog){
    if(!catalog || typeof catalog !== 'object' || catalog.available === false) return 'The Calibration Certificate catalog is unavailable.';
    var names = catalog.equipment_names; var models = catalog.models;
    if(!Array.isArray(names) || names.length !== 6) return 'The Calibration Certificate catalog has an invalid Equipment Name list.';
    if(!Array.isArray(models) || models.length !== 38) return 'The Calibration Certificate catalog has an invalid Equipment Model list.';
    var values = names.concat(models);
    if(values.some(function(value){ return typeof value !== 'string' || !normalizeCatalogText(value) || normalizeCatalogText(value) !== value; })) return 'The Calibration Certificate catalog contains an invalid value.';
    var normalized = values.map(normalizeCertificateModel);
    if(normalized.some(function(value){ return !value; }) || new Set(normalized).size !== normalized.length) return 'The Calibration Certificate catalog contains duplicate or unusable values.';
    return '';
  }
  CERTIFICATE_CATALOG_ERROR = validateCertificateCatalog(CERTIFICATE_CATALOG);
  CERTIFICATE_CATALOG_AVAILABLE = !CERTIFICATE_CATALOG_ERROR;
  function damerauLevenshtein(first, second){
    first = String(first || ''); second = String(second || '');
    if(first === second) return 0;
    if(!first) return second.length;
    if(!second) return first.length;
    var infinity = first.length + second.length;
    var matrix = Array.from({ length:first.length + 2 }, function(){ return Array(second.length + 2).fill(0); });
    matrix[0][0] = infinity;
    for(var row = 0; row <= first.length; row += 1){ matrix[row + 1][0] = infinity; matrix[row + 1][1] = row; }
    for(var column = 0; column <= second.length; column += 1){ matrix[0][column + 1] = infinity; matrix[1][column + 1] = column; }
    var lastSeen = {};
    for(var i = 1; i <= first.length; i += 1){
      var lastMatchColumn = 0;
      for(var j = 1; j <= second.length; j += 1){
        var previousMatchRow = lastSeen[second[j - 1]] || 0;
        var previousMatchColumn = lastMatchColumn;
        var cost = 1;
        if(first[i - 1] === second[j - 1]){ cost = 0; lastMatchColumn = j; }
        matrix[i + 1][j + 1] = Math.min(
          matrix[i][j] + cost,
          matrix[i + 1][j] + 1,
          matrix[i][j + 1] + 1,
          matrix[previousMatchRow][previousMatchColumn] + (i - previousMatchRow - 1) + 1 + (j - previousMatchColumn - 1)
        );
      }
      lastSeen[first[i - 1]] = i;
    }
    return matrix[first.length + 1][second.length + 1];
  }
  function certificateModelMatch(value){
    var raw = String(value === undefined || value === null ? '' : value).trim();
    var normalized = normalizeCertificateModel(raw);
    if(!CERTIFICATE_CATALOG_AVAILABLE) return { status:'catalog_unavailable', value:'', score:0, runner_up_score:0, suggestions:[] };
    if(!CERTIFICATE_MODELS.length) return normalized ? { status:'exact', value:raw, score:1, runner_up_score:0, suggestions:[raw] } : { status:'empty', value:'', score:0, runner_up_score:0, suggestions:[] };
    if(!normalized) return { status:'empty', value:'', score:0, runner_up_score:0, suggestions:CERTIFICATE_MODELS.slice(0,3) };
    var exact = CERTIFICATE_MODELS.find(function(model){ return normalizeCertificateModel(model) === normalized; });
    if(exact) return { status:'exact', value:exact, score:1, runner_up_score:0, suggestions:[exact] };
    var ranked = CERTIFICATE_MODELS.map(function(model, index){
      var candidate = normalizeCertificateModel(model);
      var score = 1 - damerauLevenshtein(normalized, candidate) / Math.max(normalized.length, candidate.length, 1);
      return { model:model, score:score, index:index };
    }).sort(function(first, second){ return second.score - first.score || first.index - second.index; });
    var best = ranked[0] || { model:'', score:0 }; var runner = ranked[1] || { score:0 };
    var accepted = best.score >= 0.82 && best.score - runner.score >= 0.04;
    return { status:accepted ? 'accepted' : (best.score - runner.score < 0.04 ? 'ambiguous' : 'weak'), value:accepted ? best.model : '', score:Number(best.score.toFixed(6)), runner_up_score:Number(runner.score.toFixed(6)), suggestions:ranked.slice(0,3).map(function(item){ return item.model; }) };
  }
  function syncCertificateModel(report){
    if(!report || typeof report !== 'object') return { status:'empty', value:'' };
    report.certificate = report.certificate && typeof report.certificate === 'object' ? report.certificate : {};
    var match = certificateModelMatch(report.machine?.model);
    report.certificate.equipment_model = match.value || '';
    return match;
  }

  function blankRows(){
    return [0,1,2,3,4].map(function(){
      return { nominal_kvp:'', measured_kvp:'', ma_mas:'', dose_mgy:'', dose_rate:'', time_msec:'', measured_time:'' };
    });
  }

  function blankState(){
    return {
      schema_version: 3,
      source: 'docx-calibration-report',
      status: 'not_started',
      updated_at: '',
      facility: { name:'', address:'', telephone:'', email:'', location:'' },
      machine: { manufacturer:'', modality:'', model:'', serial_number:'', console_model:'', console_serial:'', tube1_model:'', tube1_serial:'', tube2_model:'', tube2_serial:'', installation_date:'' },
      technical: { max_tube_current_ma:'', max_tube_voltage_kv:'', tube_current_mas_range:'', tube_voltage_kvp_range:'', exposure_time_range:'', max_rated_power_kw:'', power_supply:'', total_inherent_filtration:'' },
      mechanical_checks: SOURCE.mechanical.map(function(item){ return { label:item.label, criteria:item.criteria, result:'' }; }),
      generator_checks: SOURCE.generator.map(function(item){ return { label:item.label, criteria:item.criteria, result:'' }; }),
      calibration: { machine_calibration_date:'', next_calibration_date:'', test_tool_manufacturer:'', test_tool_model:'', test_tool_serial:'', test_tool_calibration_date:'', engineer_name:'' },
      exposure: { small:blankRows(), large:blankRows() },
      focal_spots: { small:true, large:true },
      focal_sizes: { small:'0.6', large:'1.0' },
      performance_results: ['', ''],
      signature: { name:'', image:'' },
      certificate: { bsid:'', equipment_model:'' },
      certificate_approval: { status:'queued', submission_id:'', revision_no:0, remarks:'', approver_name:'', approver_title:'', approved_at:'', signed_url:'', error:'' },
      auto_fill: { applied:false, fields:[] },
      generated: { fingerprint:'', attachment_id:'', blob_id:'', filename:'', size:0 },
      generated_cleanup: { blob_ids:[] },
      auto_document: false
    };
  }

  function normalizeState(raw){
    var base = blankState();
    if(!raw || typeof raw !== 'object') return base;
    ['facility','machine','technical','calibration','generated'].forEach(function(key){
      base[key] = Object.assign({}, base[key], raw[key] && typeof raw[key] === 'object' ? raw[key] : {});
    });
    var rawCertificate = raw.certificate && typeof raw.certificate === 'object' ? raw.certificate : {};
    base.certificate = { bsid:String(rawCertificate.bsid || '').replace(/[\r\n]/g,'').trim().slice(0,40), equipment_model:'' };
    var rawApproval = raw.certificate_approval && typeof raw.certificate_approval === 'object' ? raw.certificate_approval : {};
    base.certificate_approval = Object.assign({}, base.certificate_approval, rawApproval);
    var rawCleanup = raw.generated_cleanup && typeof raw.generated_cleanup === 'object' ? raw.generated_cleanup : {};
    base.generated_cleanup = { blob_ids:Array.isArray(rawCleanup.blob_ids) ? rawCleanup.blob_ids.map(String).filter(Boolean) : [] };
    base.auto_fill = Object.assign({}, base.auto_fill, raw.auto_fill && typeof raw.auto_fill === 'object' ? raw.auto_fill : {});
    base.auto_fill.fields = Array.isArray(base.auto_fill.fields) ? base.auto_fill.fields.map(String) : [];
    base.auto_document = !!raw.auto_document;
    base.updated_at = String(raw.updated_at || '');
    base.source = String(raw.source || base.source);
    var rawFocalSpots = raw.focal_spots && typeof raw.focal_spots === 'object' ? raw.focal_spots : {};
    var rawFocalSizes = raw.focal_sizes && typeof raw.focal_sizes === 'object' ? raw.focal_sizes : {};
    base.focal_spots = {
      small: typeof rawFocalSpots.small === 'boolean' ? rawFocalSpots.small : true,
      large: typeof rawFocalSpots.large === 'boolean' ? rawFocalSpots.large : true
    };
    base.focal_sizes = {
      small: Object.prototype.hasOwnProperty.call(rawFocalSizes, 'small') ? String(rawFocalSizes.small ?? '') : '0.6',
      large: Object.prototype.hasOwnProperty.call(rawFocalSizes, 'large') ? String(rawFocalSizes.large ?? '') : '1.0'
    };
    base.schema_version = 3;
    base.mechanical_checks = SOURCE.mechanical.map(function(item, index){
      var source = Array.isArray(raw.mechanical_checks) ? raw.mechanical_checks[index] : null;
      return { label:item.label, criteria:item.criteria, result:String(source && source.result || '') };
    });
    base.generator_checks = SOURCE.generator.map(function(item, index){
      var source = Array.isArray(raw.generator_checks) ? raw.generator_checks[index] : null;
      return { label:item.label, criteria:item.criteria, result:String(source && source.result || '') };
    });
    ['small','large'].forEach(function(key){
      var rawRows = raw.exposure && Array.isArray(raw.exposure[key]) ? raw.exposure[key] : [];
      base.exposure[key] = blankRows().map(function(row, index){ return Object.assign({}, row, rawRows[index] && typeof rawRows[index] === 'object' ? rawRows[index] : {}); });
    });
    base.performance_results = [0,1].map(function(index){ return String(Array.isArray(raw.performance_results) ? raw.performance_results[index] || '' : ''); });
    var rawSignature = raw.signature && typeof raw.signature === 'object' ? raw.signature : {};
    base.signature = { name:String(rawSignature.name || ''), image:String(rawSignature.image || rawSignature.data_url || '') };
    if(!String(base.calibration.engineer_name || '').trim() && base.signature.name) base.calibration.engineer_name = base.signature.name;
    base.status = raw.status === 'not_started' ? 'not_started' : 'draft';
    syncCertificateModel(base);
    return base;
  }

  function isActive(value){ return !!value && value.status !== 'not_started'; }
  function q(selector){ return document.querySelector(selector); }
  function qa(selector){ return Array.prototype.slice.call(document.querySelectorAll(selector)); }

  function escapeHtml(value){
    return String(value === undefined || value === null ? '' : value).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;');
  }

  function getPath(object, path){ return String(path || '').split('.').reduce(function(current, key){ return current && current[key] !== undefined ? current[key] : ''; }, object); }
  function setPath(object, path, value){
    var keys = String(path || '').split('.');
    var target = object;
    keys.slice(0,-1).forEach(function(key){ if(!target[key] || typeof target[key] !== 'object') target[key] = {}; target = target[key]; });
    target[keys[keys.length - 1]] = value;
  }
  function normalizeFitValue(value){ return String(value === undefined || value === null ? '' : value).trim(); }
  function exactFitLabel(path){
    var labels = {
      'facility.name':'Facility Name', 'facility.address':'Address', 'facility.telephone':'Telephone/Mobile No.', 'facility.email':'Email Address', 'facility.location':'Location within the Facility',
      'machine.manufacturer':'Manufacturer', 'machine.modality':'Equipment Name', 'machine.model':'Model', 'machine.serial_number':'Serial Number', 'machine.console_model':'Control Console Model', 'machine.console_serial':'Control Console Serial Number', 'machine.tube1_model':'X-ray Tube Model (1)', 'machine.tube1_serial':'X-ray Tube Serial Number (1)', 'machine.tube2_model':'X-ray Tube Model (2)', 'machine.tube2_serial':'X-ray Tube Serial Number (2)', 'machine.installation_date':'Date of Installation',
      'technical.max_tube_current_ma':'Maximum Tube Current mA', 'technical.max_tube_voltage_kv':'Maximum Tube Voltage kV', 'technical.tube_current_mas_range':'Tube Current X time mAs range', 'technical.tube_voltage_kvp_range':'Tube Voltage kVp range', 'technical.exposure_time_range':'Exposure Time Setting range', 'technical.max_rated_power_kw':'Maximum Rated Power kW', 'technical.power_supply':'Power Supply', 'technical.total_inherent_filtration':'Total Inherent Filtration',
      'calibration.machine_calibration_date':'Date of Machine Calibration', 'calibration.next_calibration_date':'Next Calibration Date', 'calibration.test_tool_manufacturer':'Test Tool Manufacturer', 'calibration.test_tool_model':'Test Tool Model', 'calibration.test_tool_serial':'Test Tool Serial Number', 'calibration.test_tool_calibration_date':'Test Tool Calibration Date', 'calibration.engineer_name':'Service Engineer Name'
    };
    return labels[path] || String(path).replace(/\./g,' ');
  }
  function exactFitEntries(report){
    var entries = [];
    function add(path, label){ var rule = fitRuleForPath(path); if(rule) entries.push({ path:path, label:label || exactFitLabel(path), rule:rule, value:getPath(report, path) }); }
    EXACT_FIT_FIELD_PATHS.forEach(function(path){ add(path); });
    [['mechanical_checks',report.mechanical_checks],['generator_checks',report.generator_checks]].forEach(function(group){
      (group[1] || []).forEach(function(item,index){ add(group[0] + '.' + index + '.result', (item.label || group[0]) + ' result'); });
    });
    ['small','large'].filter(function(key){ return report.focal_spots?.[key] !== false; }).forEach(function(key){
      (report.exposure?.[key] || []).forEach(function(row,rowIndex){ EXPOSURE_KEYS.forEach(function(field){ add('exposure.' + key + '.' + rowIndex + '.' + field, (key === 'small' ? 'Small' : 'Large') + ' focal spot row ' + (rowIndex + 1) + ' ' + field); }); });
    });
    (report.performance_results || []).forEach(function(_,index){ add('performance_results.' + index, 'Performance criterion ' + (index + 1) + ' result'); });
    return entries;
  }
  function exactFitViolations(report){
    return exactFitEntries(report).reduce(function(violations, entry){
      var raw = String(entry.value === undefined || entry.value === null ? '' : entry.value);
      if(/[\r\n\t]/.test(raw)){
        violations.push({ path:entry.path, label:entry.label, maxLength:entry.rule.maxLength, reason:'single_line', message:entry.label + ' must be a single-line value for the supplied Word form.' });
      }else if(normalizeFitValue(raw).length > entry.rule.maxLength){
        violations.push({ path:entry.path, label:entry.label, maxLength:entry.rule.maxLength, reason:'too_long', message:entry.label + ' is too long for the supplied Word form (maximum ' + entry.rule.maxLength + ' characters).' });
      }
      return violations;
    }, []);
  }
  function normalizeReportFitValues(report){
    var next = clone(report);
    exactFitEntries(next).forEach(function(entry){ setPath(next, entry.path, normalizeFitValue(entry.value)); });
    return next;
  }
  function currentTSRData(){ try{ return typeof window.collectTSRData === 'function' ? window.collectTSRData() : {}; }catch(err){ return {}; } }
  function currentSchedule(){ try{ return typeof window.getSelectedStandaloneSchedule === 'function' ? window.getSelectedStandaloneSchedule() : null; }catch(err){ return null; } }
  function showStatus(message, tone){
    var normalized = ['success','info','warning','danger'].indexOf(tone || 'info') >= 0 ? (tone || 'info') : 'info';
    if(typeof window.showTSRStatus === 'function') window.showTSRStatus(message, normalized);
    var modalStatus = q('#calibration-report-modal-status');
    if(modalStatus){ modalStatus.textContent = String(message || ''); modalStatus.className = 'calibration-report-modal-status is-visible tone-' + normalized; }
  }

  function fieldMarkup(path, label, type, placeholder){
    var rule = fitRuleForPath(path); var limit = rule ? ' maxlength="' + rule.maxLength + '" data-cr-fit-class="' + escapeHtml(rule.name) + '"' : '';
    return '<div class="calibration-report-field"><label>' + escapeHtml(label) + '</label><input data-cr-field="' + escapeHtml(path) + '" type="' + escapeHtml(type || 'text') + '" placeholder="' + escapeHtml(placeholder || '') + '"' + limit + '></div>';
  }
  function equipmentNameMarkup(){
    var options = '<option value="">Select Equipment Name</option>' + CERTIFICATE_EQUIPMENT_NAMES.map(function(name){ return '<option value="' + escapeHtml(name) + '">' + escapeHtml(name) + '</option>'; }).join('');
    var unavailable = !CERTIFICATE_CATALOG_AVAILABLE;
    var help = unavailable ? 'The Calibration Certificate catalog is unavailable or invalid. Reload Create TSR before final save.' : 'Choose the canonical equipment name used on the certificate.';
    return '<div class="calibration-report-field calibration-report-catalog-field"><label for="calibration-report-equipment-name">2.2 Equipment Name</label><select id="calibration-report-equipment-name" data-cr-field="machine.modality" required aria-required="true"' + (unavailable ? ' disabled aria-disabled="true"' : '') + '>' + options + '</select><small class="calibration-report-catalog-help">' + escapeHtml(help) + '</small></div>';
  }
  function modelMarkup(){
    var options = CERTIFICATE_MODELS.map(function(model){ return '<option value="' + escapeHtml(model) + '"></option>'; }).join('');
    return '<div class="calibration-report-field calibration-report-catalog-field"><label for="calibration-report-model">2.3 Model</label><input id="calibration-report-model" data-cr-field="machine.model" list="calibration-report-model-catalog" autocomplete="off" aria-describedby="calibration-report-model-match"><datalist id="calibration-report-model-catalog">' + options + '</datalist><div id="calibration-report-model-match" class="calibration-report-model-match" role="status" aria-live="polite"></div></div>';
  }

  function checkRows(kind, source){
    return source.map(function(item, index){
      var rule = fitRuleForPath(kind + '_checks.' + index + '.result');
      var limit = rule ? ' maxlength="' + rule.maxLength + '" data-cr-fit-class="' + escapeHtml(rule.name) + '"' : '';
      return '<tr><td><div class="calibration-report-check-label">' + escapeHtml(item.label) + '</div></td><td><div class="calibration-report-check-criteria">' + escapeHtml(item.criteria) + '</div></td><td><textarea class="calibration-report-check-result" data-cr-check="' + kind + ':' + index + '" placeholder="Enter result"' + limit + '></textarea></td></tr>';
    }).join('');
  }

  function exposureTable(key, title, headers){
    var body = [0,1,2,3,4].map(function(row){
      return '<tr>' + headers.map(function(header, column){ var rule = fitRuleForPath('exposure.' + key + '.' + row + '.' + EXPOSURE_KEYS[column]); var limit = rule ? ' maxlength="' + rule.maxLength + '" data-cr-fit-class="' + escapeHtml(rule.name) + '"' : ''; return '<td><input class="calibration-report-exposure-input" data-cr-exposure="' + escapeHtml(key + ':' + row + ':' + column) + '" aria-label="' + escapeHtml(title + ' row ' + (row + 1) + ' ' + header) + '"' + limit + '></td>'; }).join('') + '</tr>';
    }).join('');
    var label = key === 'small' ? 'SMALL' : 'LARGE';
    return '<div class="calibration-report-section calibration-report-focal-group" data-cr-focal-group="' + key + '"><div class="calibration-report-section-title">' + escapeHtml(title) + '</div><div class="calibration-report-reference-bar"><label class="calibration-report-focal-toggle"><input type="checkbox" data-cr-focal-spot="' + key + '" aria-label="Include ' + label + ' focal spot"> <span>Include ' + label + '</span></label><label class="calibration-report-focal-size">FOCAL SIZE: <input type="text" inputmode="decimal" maxlength="12" data-cr-focal-size="' + key + '" aria-label="' + label + ' focal size"></label><span>SID: 100cm</span></div><div class="calibration-report-exposure-scroll"><table class="calibration-report-exposure-table"><thead><tr>' + headers.map(function(header){ return '<th>' + escapeHtml(header) + '</th>'; }).join('') + '</tr></thead><tbody>' + body + '</tbody></table></div></div>';
  }

  function buildEditor(){
    var performanceRows = SOURCE.performance.map(function(criteria, index){ var rule = fitRuleForPath('performance_results.' + index); var limit = rule ? ' maxlength="' + rule.maxLength + '" data-cr-fit-class="' + escapeHtml(rule.name) + '"' : ''; return '<tr><td><div class="calibration-report-check-criteria">' + escapeHtml(criteria) + '</div></td><td><textarea class="calibration-report-performance-result" data-cr-performance="' + index + '" placeholder="Enter result"' + limit + '></textarea></td></tr>'; }).join('');
    var html = '<div class="calibration-report-tabs" role="tablist" aria-label="Calibration report pages"><button type="button" class="calibration-report-tab is-active" data-cr-page="1" id="calibration-report-tab-1" role="tab" aria-controls="calibration-report-page-1" aria-selected="true" tabindex="0">Page 1 · Identity</button><button type="button" class="calibration-report-tab" data-cr-page="2" id="calibration-report-tab-2" role="tab" aria-controls="calibration-report-page-2" aria-selected="false" tabindex="-1">Page 2 · Checks</button><button type="button" class="calibration-report-tab" data-cr-page="3" id="calibration-report-tab-3" role="tab" aria-controls="calibration-report-page-3" aria-selected="false" tabindex="-1">Page 3 · Output</button></div>'
      + '<div class="calibration-report-template-note"><i class="fa-solid fa-lock me-1" aria-hidden="true"></i>DOCX output uses the supplied Word form. Only its existing blank fields and signature area receive data.</div>'
      + '<section class="calibration-report-page is-active" data-cr-page-panel="1"><div class="calibration-report-paper-title">CALIBRATION REPORT</div>'
      + '<div class="calibration-report-section"><div class="calibration-report-section-title">1. FACILITY INFORMATION</div><div class="calibration-report-grid">'
      + fieldMarkup('facility.name','1.1 Facility Name') + fieldMarkup('facility.address','1.2 Address') + fieldMarkup('facility.telephone','1.3 Telephone/Mobile No.') + fieldMarkup('facility.email','1.4 Email Address','email') + fieldMarkup('facility.location','1.5 Location within the Facility') + '</div></div>'
       + '<div class="calibration-report-section"><div class="calibration-report-section-title">2. MACHINE DETAILS</div><div class="calibration-report-grid">'
       + fieldMarkup('machine.manufacturer','2.1 Manufacturer') + equipmentNameMarkup() + modelMarkup() + fieldMarkup('machine.serial_number','2.4 Serial Number')
      + fieldMarkup('machine.console_model','2.5 Control Console: Model') + fieldMarkup('machine.console_serial','2.5 Control Console: Serial Number') + fieldMarkup('machine.tube1_model','2.6 X-ray Tube/s Assembly: Model (1)') + fieldMarkup('machine.tube1_serial','2.6 X-ray Tube/s Assembly: Serial Number (1)') + fieldMarkup('machine.tube2_model','2.6 X-ray Tube/s Assembly: Model (2)') + fieldMarkup('machine.tube2_serial','2.6 X-ray Tube/s Assembly: Serial Number (2)') + fieldMarkup('machine.installation_date','2.7 Date of Installation','date') + '</div></div>'
      + '<div class="calibration-report-section"><div class="calibration-report-section-title">3. TECHNICAL SPECIFICATIONS</div><div class="calibration-report-grid">'
      + fieldMarkup('technical.max_tube_current_ma','3.1 Maximum Tube Current mA') + fieldMarkup('technical.max_tube_voltage_kv','3.2 Maximum Tube Voltage kV') + fieldMarkup('technical.tube_current_mas_range','3.3 Tube Current X time mAs range') + fieldMarkup('technical.tube_voltage_kvp_range','3.4 Tube Voltage kVp range') + fieldMarkup('technical.exposure_time_range','3.5 Exposure Time Setting range') + fieldMarkup('technical.max_rated_power_kw','3.6 Maximum Rated Power kW') + fieldMarkup('technical.power_supply','3.7 Power Supply') + fieldMarkup('technical.total_inherent_filtration','3.8 Total Inherent Filtration') + '</div></div></section>'
      + '<section class="calibration-report-page" data-cr-page-panel="2"><div class="calibration-report-paper-title">CALIBRATION TEST DETAILS</div>'
      + '<div class="calibration-report-section"><div class="calibration-report-section-title">4. MECHANICAL CHECKS</div><div class="calibration-report-check-table-wrap"><table class="calibration-report-check-table"><thead><tr><th>Check</th><th>Performance Criteria</th><th>Result</th></tr></thead><tbody>' + checkRows('mechanical', SOURCE.mechanical) + '</tbody></table></div></div>'
      + '<div class="calibration-report-section"><div class="calibration-report-section-title">5. GENERATOR CHECKS</div><div class="calibration-report-check-table-wrap"><table class="calibration-report-check-table"><thead><tr><th>Check</th><th>Performance Criteria</th><th>Result</th></tr></thead><tbody>' + checkRows('generator', SOURCE.generator) + '</tbody></table></div></div>'
      + '<div class="calibration-report-section"><div class="calibration-report-section-title">6. CALIBRATION TEST DETAILS</div><div class="calibration-report-calibration-grid">'
      + fieldMarkup('calibration.machine_calibration_date','6.1 Date of Machine Calibration','date') + fieldMarkup('calibration.next_calibration_date','6.2 Next Calibration Date','date') + fieldMarkup('calibration.test_tool_manufacturer','6.3 Test Tool Manufacturer') + fieldMarkup('calibration.test_tool_model','6.4 Test Tool Model') + fieldMarkup('calibration.test_tool_serial','6.5 Test Tool Serial Number') + fieldMarkup('calibration.test_tool_calibration_date','6.6 Test Tool Calibration Date','date')
      + '</div><div class="calibration-report-signature-panel"><label class="small fw-bold text-uppercase">6.7 Name and Signature of Service Engineer</label><input class="form-control mb-2" data-cr-field="calibration.engineer_name" placeholder="Service engineer name"><canvas id="cr-signature-pad" class="calibration-report-signature-canvas" width="1200" height="300" aria-label="Calibration service engineer signature"></canvas><div class="calibration-report-signature-actions"><span id="cr-signature-status" class="calibration-report-signature-status">No calibration signature saved.</span><button type="button" class="btn btn-outline-secondary btn-sm" id="cr-signature-clear">Clear Signature</button></div></div></div></section>'
      + '<section class="calibration-report-page" data-cr-page-panel="3"><div class="calibration-report-paper-title">AVERAGE EXPOSURE OUTPUT</div>'
      + exposureTable('small','FOCAL SPOT: SMALL', SOURCE.exposureHeadersSmall) + exposureTable('large','FOCAL SPOT: LARGE', SOURCE.exposureHeadersLarge)
      + '<div class="calibration-report-section"><div class="calibration-report-section-title">PERFORMANCE CRITERIA</div><div class="calibration-report-exposure-scroll"><table class="calibration-report-criteria-table"><thead><tr><th>Criteria</th><th>Test Result</th></tr></thead><tbody>' + performanceRows + '</tbody></table></div></div></section>';
    var editor = q('#calibration-report-editor');
    if(!editor) return;
    editor.innerHTML = html;
    editorBuilt = true;
    qa('.calibration-report-tab').forEach(function(button){ button.addEventListener('click', function(){ setEditorPage(Number(button.getAttribute('data-cr-page') || 1)); }); button.addEventListener('keydown', handleTabKeydown); });
    editor.addEventListener('input', onEditorInput);
    editor.addEventListener('change', onEditorInput);
    q('#cr-signature-clear')?.addEventListener('click', clearSignature);
    setupSignatureCanvas();
    applyDomFromState();
    setEditorPage(activePage);
  }
  function setEditorPage(page){
    activePage = Math.max(1, Math.min(3, Number(page) || 1));
    qa('[data-cr-page-panel]').forEach(function(panel){
      var pageNumber = Number(panel.getAttribute('data-cr-page-panel')) || 1;
      var selected = pageNumber === activePage;
      var panelId = 'calibration-report-page-' + pageNumber;
      panel.id = panelId;
      panel.setAttribute('role', 'tabpanel');
      panel.setAttribute('aria-labelledby', 'calibration-report-tab-' + pageNumber);
      panel.setAttribute('aria-hidden', selected ? 'false' : 'true');
      panel.setAttribute('tabindex', '0');
      panel.classList.toggle('is-active', selected);
    });
    qa('.calibration-report-tab').forEach(function(tab){
      var pageNumber = Number(tab.getAttribute('data-cr-page')) || 1;
      var selected = pageNumber === activePage;
      tab.id = 'calibration-report-tab-' + pageNumber;
      tab.setAttribute('aria-controls', 'calibration-report-page-' + pageNumber);
      tab.setAttribute('aria-selected', selected ? 'true' : 'false');
      tab.setAttribute('tabindex', selected ? '0' : '-1');
      tab.classList.toggle('is-active', selected);
    });
  }
  function handleTabKeydown(event){
    var tab = event.currentTarget || event.target;
    var current = Number(tab && tab.getAttribute('data-cr-page')) || activePage;
    var next = 0;
    if(event.key === 'ArrowRight' || event.key === 'ArrowDown') next = current === 3 ? 1 : current + 1;
    if(event.key === 'ArrowLeft' || event.key === 'ArrowUp') next = current === 1 ? 3 : current - 1;
    if(event.key === 'Home') next = 1;
    if(event.key === 'End') next = 3;
    if(!next) return;
    if(typeof event.preventDefault === 'function') event.preventDefault();
    setEditorPage(next);
    var nextTab = q('#calibration-report-tab-' + next);
    if(nextTab) nextTab.focus();
  }
  function fieldElement(path){ return qa('[data-cr-field]').find(function(element){ return element.getAttribute('data-cr-field') === path; }) || null; }

  function ensureLegacyEquipmentOption(value){
    var select = q('#calibration-report-equipment-name'); if(!select) return;
    if(typeof select.appendChild !== 'function') return;
    var current = String(value || '').trim();
    var legacy = select.querySelector?.('option[data-cr-legacy="true"]');
    if(legacy) legacy.remove();
    if(current && CERTIFICATE_EQUIPMENT_NAMES.indexOf(current) < 0){
      legacy = document.createElement('option'); legacy.value = current; legacy.textContent = 'Legacy value (select a catalog name): ' + current; legacy.disabled = true; legacy.setAttribute('data-cr-legacy','true'); select.appendChild(legacy);
    }
  }
  function renderModelMatch(){
    var element = q('#calibration-report-model-match'); if(!element) return;
    var match = certificateModelMatch(state?.machine?.model);
    element.className = 'calibration-report-model-match';
    if(match.status === 'exact' || match.status === 'accepted'){
      element.classList.add('is-accepted');
      element.innerHTML = '<span>Certificate Model: <strong>' + escapeHtml(match.value) + '</strong></span>' + (match.status === 'accepted' ? '<small>Closest catalog match accepted automatically.</small>' : '<small>Exact catalog match.</small>');
      return;
    }
    if(match.status === 'catalog_unavailable'){
      element.classList.add('is-warning');
      element.textContent = 'The Calibration Certificate catalog is unavailable or invalid. Reload Create TSR before final save.';
      return;
    }
    if(match.status === 'empty'){
      element.classList.add('is-empty'); element.textContent = 'Enter a model to match the certificate catalog.'; return;
    }
    element.classList.add('is-warning');
    var suggestionButtons = (match.suggestions || []).map(function(model){ return '<button type="button" class="calibration-report-model-suggestion" data-cr-model-suggestion="' + escapeHtml(model) + '">' + escapeHtml(model) + '</button>'; }).join('');
    element.innerHTML = '<span>Select an exact catalog model before final save.</span><small>Closest suggestions:</small><div class="calibration-report-model-suggestions">' + suggestionButtons + '</div>';
    qa('[data-cr-model-suggestion]').forEach(function(button){ button.addEventListener('click', function(){ var input = q('#calibration-report-model'); if(input){ input.value = button.getAttribute('data-cr-model-suggestion') || ''; input.dispatchEvent(new Event('input', { bubbles:true })); input.focus(); } }); });
  }

  function applyDomFromState(){
    if(!editorBuilt) return;
    ensureLegacyEquipmentOption(state?.machine?.modality);
    qa('[data-cr-field]').forEach(function(element){ element.value = String(getPath(state, element.getAttribute('data-cr-field')) || ''); });
    qa('[data-cr-check]').forEach(function(element){ var parts = String(element.getAttribute('data-cr-check')).split(':'); var list = parts[0] === 'mechanical' ? state.mechanical_checks : state.generator_checks; element.value = String(list[Number(parts[1])]?.result || ''); });
    qa('[data-cr-focal-spot]').forEach(function(element){ var key = String(element.getAttribute('data-cr-focal-spot')); element.checked = state.focal_spots?.[key] !== false; });
    qa('[data-cr-focal-size]').forEach(function(element){ var key = String(element.getAttribute('data-cr-focal-size')); element.value = String(state.focal_sizes?.[key] || ''); });
    qa('[data-cr-focal-group]').forEach(function(group){ var key = String(group.getAttribute('data-cr-focal-group')); var selected = state.focal_spots?.[key] !== false; group.classList.toggle('is-disabled', !selected); group.querySelectorAll?.('[data-cr-exposure]').forEach(function(element){ element.disabled = !selected; }); var size = group.querySelector?.('[data-cr-focal-size]'); if(size) size.disabled = !selected; });
    qa('[data-cr-exposure]').forEach(function(element){ var parts = String(element.getAttribute('data-cr-exposure')).split(':'); element.value = String(state.exposure?.[parts[0]]?.[Number(parts[1])]?.[EXPOSURE_KEYS[Number(parts[2])]] || ''); });
    qa('[data-cr-performance]').forEach(function(element){ element.value = String(state.performance_results[Number(element.getAttribute('data-cr-performance'))] || ''); });
    drawSignature();
    updateSignatureStatus();
    renderCertificateControls();
    renderModelMatch();
  }

  function onEditorInput(event){
    var element = event.target;
    if(element.matches('[data-cr-field]')) setPath(state, element.getAttribute('data-cr-field'), element.value);
    if(element.matches('[data-cr-check]')){ var check = String(element.getAttribute('data-cr-check')).split(':'); var list = check[0] === 'mechanical' ? state.mechanical_checks : state.generator_checks; if(list[Number(check[1])]) list[Number(check[1])].result = element.value; }
    if(element.matches('[data-cr-focal-spot]')){ var focalSpot = String(element.getAttribute('data-cr-focal-spot')); state.focal_spots[focalSpot] = !!element.checked; }
    if(element.matches('[data-cr-focal-size]')){ var focalSize = String(element.getAttribute('data-cr-focal-size')); state.focal_sizes[focalSize] = element.value; }
    if(element.matches('[data-cr-exposure]')){ var exposure = String(element.getAttribute('data-cr-exposure')).split(':'); if(state.exposure?.[exposure[0]]?.[Number(exposure[1])]) state.exposure[exposure[0]][Number(exposure[1])][EXPOSURE_KEYS[Number(exposure[2])]] = element.value; }
    if(element.matches('[data-cr-performance]')) state.performance_results[Number(element.getAttribute('data-cr-performance'))] = element.value;
    if(element.matches('[data-cr-field="machine.model"]')) syncCertificateModel(state);
    if(element.matches('[data-cr-field="machine.modality"]')) syncCertificateModel(state);
    state.status = 'draft'; state.updated_at = new Date().toISOString(); invalidateGenerated(); updateSignatureStatus(); renderCertificateControls(); renderCard(); syncAutoDocument(); scheduleDraftSave();
    renderModelMatch();
  }

  function normalizeCertificateBsid(value){ return String(value === undefined || value === null ? '' : value).replace(/[\r\n]/g,'').trim().slice(0,40); }
  function formatCertificateDate(value){
    var match = String(value || '').trim().match(/^(\d{4})[-/](\d{2})[-/](\d{2})/);
    return match ? match[1] + '/' + match[2] + '/' + match[3] : '';
  }
  function formatCertificateNumberDate(value){
    var match = String(value || '').trim().match(/^(\d{4})[-/](\d{2})[-/](\d{2})/);
    return match ? match[1] + '-' + match[2] + match[3] : '';
  }
  function certificateNumber(report){
    var date = formatCertificateNumberDate(report?.calibration?.machine_calibration_date);
    var bsid = normalizeCertificateBsid(report?.certificate?.bsid);
    return date && bsid ? [date, bsid].join('-') : '';
  }
  function certificateFieldValues(payload, report){
    var date = formatCertificateDate(report?.calibration?.machine_calibration_date);
    var nextDate = formatCertificateDate(report?.calibration?.next_calibration_date);
    var tsrNumber = String(payload?.['tsr-number'] || payload?.tsr_number || '').trim();
    var values = {
      'Textfield': certificateNumber(report),
      'Text1': String(report?.machine?.modality || '').trim(),
      'Text2': String(report?.certificate?.equipment_model || '').trim(),
      'Text3': String(report?.machine?.serial_number || '').trim(),
      'Text4': date,
      'Text5': nextDate,
      'Text6': String(report?.facility?.name || '').trim(),
      'Textfield-0': tsrNumber
    };
    var missing = [];
    [['Textfield','Certificate No.'],['Text1','Equipment Name'],['Text2','Equipment Model'],['Text3','System ID'],['Text4','Calibration Date'],['Text5','Next Calibration Date'],['Text6','Installed At'],['Textfield-0','TSR No.']].forEach(function(item){ if(!String(values[item[0]] || '').trim()) missing.push(item[1]); });
    return { values:values, missing:missing };
  }
  var CERTIFICATE_FIELD_WIDTHS = { Textfield:333.473, Text1:333.472, Text2:334.741, Text3:333.895, Text4:334.740, Text5:332.627, Text6:336.008, 'Textfield-0':335.163 };
  var CERTIFICATE_DATA_MAX_SIZE = 11;
  var CERTIFICATE_DATA_MIN_SIZE = 8.5;
  var CERTIFICATE_DATA_PADDING = 6;
  var CERTIFICATE_FIELD_LABELS = { Textfield:'Certificate No.', Text1:'Equipment Name', Text2:'Equipment Model', Text3:'System ID', Text4:'Calibration Date', Text5:'Next Calibration Date', Text6:'Installed At', 'Textfield-0':'TSR No.' };
  function certificateDataFontSize(values, font){
    var required = Object.keys(CERTIFICATE_FIELD_WIDTHS).map(function(name){ return { name:name, value:String(values?.[name] || ''), width:CERTIFICATE_FIELD_WIDTHS[name] - CERTIFICATE_DATA_PADDING }; });
    var size = CERTIFICATE_DATA_MAX_SIZE;
    required.forEach(function(item){ if(!item.value) return; var measured = font.widthOfTextAtSize(item.value, CERTIFICATE_DATA_MAX_SIZE); if(measured > item.width) size = Math.min(size, CERTIFICATE_DATA_MAX_SIZE * item.width / measured); });
    size = Math.min(CERTIFICATE_DATA_MAX_SIZE, Math.floor(size * 10) / 10);
    while(size >= CERTIFICATE_DATA_MIN_SIZE){ if(required.every(function(item){ return !item.value || font.widthOfTextAtSize(item.value, size) <= item.width + 0.01; })) return Number(size.toFixed(1)); size = Number((size - 0.1).toFixed(1)); }
    var offenders = required.filter(function(item){ return item.value && font.widthOfTextAtSize(item.value, CERTIFICATE_DATA_MIN_SIZE) > item.width + 0.01; }).map(function(item){ return CERTIFICATE_FIELD_LABELS[item.name]; });
    throw certificateError('calibration_certificate_value_fit', 'Calibration Certificate value cannot fit at ' + CERTIFICATE_DATA_MIN_SIZE + ' points: ' + (offenders.join(', ') || 'a mapped field') + '.');
  }
  function renderCertificateControls(){
    var input = q('#calibration-report-bsid');
    var preview = q('#calibration-report-certificate-number');
    if(input){ var bsid = normalizeCertificateBsid(state?.certificate?.bsid); if(input.value !== bsid) input.value = bsid; input.readOnly = true; input.setAttribute('aria-readonly','true'); }
    if(preview) preview.textContent = certificateNumber(state) || 'Incomplete certificate number';
  }

  function setupSignatureCanvas(){
    var canvas = q('#cr-signature-pad');
    if(!canvas) return;
    var context = canvas.getContext('2d');
    context.fillStyle = '#ffffff'; context.fillRect(0, 0, canvas.width, canvas.height); context.lineWidth = 4; context.lineCap = 'round'; context.lineJoin = 'round'; context.strokeStyle = '#111827';
    function finish(){
      if(!signatureDrawing) return;
      signatureDrawing = false; state.signature.image = canvas.toDataURL('image/png'); state.status = 'draft'; state.updated_at = new Date().toISOString(); invalidateGenerated(); updateSignatureStatus(); renderCard(); syncAutoDocument(); scheduleDraftSave();
    }
    canvas.addEventListener('pointerdown', function(event){ signatureDrawing = true; canvas.setPointerCapture?.(event.pointerId); var point = signaturePoint(canvas, event); context.beginPath(); context.moveTo(point.x, point.y); });
    canvas.addEventListener('pointermove', function(event){ if(!signatureDrawing) return; var point = signaturePoint(canvas, event); context.lineTo(point.x, point.y); context.stroke(); });
    ['pointerup','pointercancel','lostpointercapture'].forEach(function(name){ canvas.addEventListener(name, finish); });
  }
  function signaturePoint(canvas, event){ var rect = canvas.getBoundingClientRect(); return { x:(event.clientX - rect.left) * canvas.width / rect.width, y:(event.clientY - rect.top) * canvas.height / rect.height }; }
  function drawSignature(){
    var canvas = q('#cr-signature-pad'); if(!canvas) return;
    var context = canvas.getContext('2d'); context.clearRect(0,0,canvas.width,canvas.height); context.fillStyle = '#ffffff'; context.fillRect(0, 0, canvas.width, canvas.height);
    if(!state.signature.image) return;
    var image = new Image(); image.onload = function(){ context.drawImage(image, 0, 0, canvas.width, canvas.height); }; image.src = state.signature.image;
  }
  function clearSignature(){ state.signature.image = ''; state.status = 'draft'; state.updated_at = new Date().toISOString(); invalidateGenerated(); drawSignature(); updateSignatureStatus(); renderCard(); scheduleDraftSave(); }
  function updateSignatureStatus(){ var element = q('#cr-signature-status'); if(element) element.textContent = state.signature.image ? 'Calibration signature saved.' : 'No calibration signature saved.'; }

  function hasGeneratedMetadata(report){ return !!(report && report.generated && report.generated.attachment_id && report.generated.blob_id && report.generated.fingerprint && String(report.generated.fingerprint) === fingerprint(report)); }
  function reportReadyForAutoDocument(){ return isActive(state) && validateForFinalSave({ calibration_report:state }).ok && hasGeneratedMetadata(state) && generatedBlobState === 'available'; }
  function generatedReportBlobId(value){ var id = String(value || '').trim(); return id.indexOf('calibration-report-') === 0 ? id : ''; }
  function uniqueGeneratedBlobIds(values){
    var seen = {}; return (values || []).map(generatedReportBlobId).filter(function(id){ if(!id || seen[id]) return false; seen[id] = true; return true; });
  }
  function reportBlobIdsForCleanup(report){
    var generated = report?.generated || {}; var pending = report?.generated_cleanup?.blob_ids || [];
    return uniqueGeneratedBlobIds([generated.blob_id].concat(Array.isArray(pending) ? pending : []));
  }
  async function cleanupGeneratedBlobIds(blobIds){
    var pending = uniqueGeneratedBlobIds(blobIds);
    if(!pending.length || typeof window.deleteOfflineTSRBlobRecord !== 'function') return pending;
    var failed = [];
    for(var index = 0; index < pending.length; index += 1){
      try{ await window.deleteOfflineTSRBlobRecord(pending[index]); }catch(error){ failed.push(pending[index]); }
    }
    return failed;
  }
  function invalidateGenerated(){ state.generated_cleanup = { blob_ids:reportBlobIdsForCleanup(state) }; state.generated = { fingerprint:'', attachment_id:'', blob_id:'', filename:'', size:0 }; generatedBlobState = 'none'; }
  function reportDocuments(){ var value = String(q('#tsr-documents')?.value || ''); return value.split(',').map(function(item){ return item.trim(); }).filter(Boolean); }
  function syncAutoDocument(){
    var readyForDocument = reportReadyForAutoDocument(); var hasChip = reportDocuments().some(function(item){ return item.toLowerCase() === 'calibration report'; });
    if(readyForDocument && !hasChip && typeof window.addTSRDocument === 'function'){ state.auto_document = true; window.addTSRDocument('Calibration Report'); }
    else if(!readyForDocument && state.auto_document && hasChip && typeof window.removeTSRDocument === 'function'){ window.removeTSRDocument('Calibration Report'); state.auto_document = false; }
  }
  function refreshGeneratedBlobState(){
    var blobId = hasGeneratedMetadata(state) ? String(state.generated.blob_id) : '';
    if(!blobId){ generatedBlobState = 'none'; renderCard(); syncAutoDocument(); return; }
    generatedBlobState = 'checking'; renderCard();
    if(typeof window.loadOfflineTSRBlobRecord !== 'function'){ generatedBlobState = 'missing'; renderCard(); syncAutoDocument(); return; }
    Promise.resolve().then(function(){ return window.loadOfflineTSRBlobRecord(blobId); }).then(function(record){
      if(String(state.generated?.blob_id || '') !== blobId) return;
      generatedBlobState = record?.blob ? 'available' : 'missing'; renderCard(); syncAutoDocument();
    }).catch(function(){
      if(String(state.generated?.blob_id || '') !== blobId) return;
      generatedBlobState = 'missing'; renderCard(); syncAutoDocument();
    });
  }
  function scheduleDraftSave(){ clearTimeout(saveTimer); saveTimer = setTimeout(function(){ if(isActive(state) && typeof window.saveStandaloneTSRDraft === 'function') window.saveStandaloneTSRDraft(true).catch(function(err){ console.warn('[Calibration Report] Autosave failed', err); }); }, 500); }

  function autofill(schedule){
    var tsr = currentTSRData(); var contact = schedule?.client_contact || {};
    var mappings = [
      ['facility.name', schedule?.client_name], ['facility.address', schedule?.client_address],
      ['facility.telephone', tsr['tsr-contact-no'] || contact.phone || contact.telephone], ['facility.email', tsr['tsr-email-add'] || contact.email],
      ['facility.location', tsr['tsr-department'] || schedule?.department], ['machine.model', schedule?.product_name || tsr['tsr-equipment-model']],
      ['machine.serial_number', schedule?.product_id || tsr['tsr-serial-no']], ['calibration.machine_calibration_date', schedule?.date_iso || tsr['tsr-service-date']],
      ['calibration.engineer_name', schedule?.serviced_by || tsr['tsr-serviced-by']], ['certificate.bsid', schedule?.product_bsid]
    ];
    var applied = state.auto_fill.fields.slice();
    mappings.forEach(function(pair){ var value = String(pair[1] || '').trim(); if(!value) return; var existing = String(getPath(state, pair[0]) || '').trim(); if(pair[0] === 'certificate.bsid' || !existing){ setPath(state, pair[0], normalizeCertificateBsid(value)); if(!applied.includes(pair[0])) applied.push(pair[0]); } });
    state.auto_fill = { applied:true, fields:applied };
  }
  function createReport(){ if(!isActive(state)){ state = blankState(); state.status = 'draft'; autofill(currentSchedule()); } syncAutoDocument(); ensureEditor(); applyDomFromState(); renderCard(); open(); }
  function dialogFocusableElements(){
    var overlay = q('#calibration-report-overlay');
    if(!overlay || typeof overlay.querySelectorAll !== 'function') return [];
    var selector = 'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])';
    return Array.prototype.slice.call(overlay.querySelectorAll(selector)).filter(function(element){
      return !element.disabled && !element.hidden && element.getAttribute('tabindex') !== '-1' && element.getAttribute('aria-hidden') !== 'true' && !(element.classList && element.classList.contains('d-none')) && typeof element.getClientRects === 'function' && element.getClientRects().length > 0;
    });
  }
  function focusDialog(){
    var elements = dialogFocusableElements();
    var target = elements[0] || q('#calibration-report-close');
    if(target) target.focus();
  }
  function handleDialogKeydown(event){
    var overlay = q('#calibration-report-overlay');
    if(!overlay || !overlay.classList.contains('is-open')) return;
    if(event.key === 'Escape'){
      if(typeof event.preventDefault === 'function') event.preventDefault();
      close();
      return;
    }
    if(event.key !== 'Tab') return;
    var elements = dialogFocusableElements();
    if(!elements.length){
      if(typeof event.preventDefault === 'function') event.preventDefault();
      return;
    }
    var current = document.activeElement;
    var index = elements.indexOf(current);
    if(event.shiftKey && (index <= 0 || index < 0)){
      if(typeof event.preventDefault === 'function') event.preventDefault();
      elements[elements.length - 1].focus();
    }else if(!event.shiftKey && (index === elements.length - 1 || index < 0)){
      if(typeof event.preventDefault === 'function') event.preventDefault();
      elements[0].focus();
    }
  }
  function open(){
    ensureEditor();
    var overlay = q('#calibration-report-overlay');
    if(!overlay) return;
    if(!overlay.classList.contains('is-open')) returnFocusElement = q('#calibration-report-create-btn') || returnFocusElement;
    overlay.classList.add('is-open');
    overlay.removeAttribute('inert');
    overlay.setAttribute('aria-hidden','false');
    setEditorPage(activePage);
    var workspace = q('.calibration-report-workspace');
    if(workspace) workspace.scrollTop = overlayScrollTop;
    focusDialog();
  }
  function close(){
    var overlay = q('#calibration-report-overlay');
    if(!overlay) return;
    var workspace = q('.calibration-report-workspace');
    if(workspace) overlayScrollTop = Number(workspace.scrollTop || 0);
    overlay.classList.remove('is-open');
    overlay.setAttribute('aria-hidden','true');
    overlay.setAttribute('inert','');
    var target = returnFocusElement || q('#calibration-report-create-btn');
    if(target) target.focus();
  }
  function reset(options){ var removeAutoDocument = !!(state.auto_document && options?.removeAutoDocument); var cleanupIds = reportBlobIdsForCleanup(state); state = blankState(); state.generated_cleanup = { blob_ids:cleanupIds }; generatedBlobState = 'none'; if(removeAutoDocument && typeof window.removeTSRDocument === 'function') window.removeTSRDocument('Calibration Report'); close(); renderCard(); }
  function apply(payload){ state = payload && payload.status !== 'not_started' ? normalizeState(payload) : blankState(); generatedBlobState = hasGeneratedMetadata(state) ? 'checking' : 'none'; ensureEditor(); applyDomFromState(); syncAutoDocument(); renderCard(); refreshGeneratedBlobState(); }
  function onScheduleApplied(schedule){ if(!isActive(state)) return; if(!state.auto_fill.applied){ autofill(schedule); applyDomFromState(); invalidateGenerated(); renderCard(); scheduleDraftSave(); } }
  function clearForScheduleChange(){ if(isActive(state)) reset({ removeAutoDocument:true }); }
  function collect(){ if(!isActive(state)) return null; syncAutoDocument(); return normalizeState(state); }

  function missingFields(report){
    var missing = [];
    var required = [['facility.name','Facility Name'],['facility.address','Address'],['machine.manufacturer','Manufacturer'],['machine.modality','Equipment Name'],['machine.model','Model'],['machine.serial_number','Serial Number'],['calibration.machine_calibration_date','Date of Machine Calibration'],['calibration.next_calibration_date','Next Calibration Date'],['calibration.test_tool_manufacturer','Test Tool Manufacturer'],['calibration.test_tool_model','Test Tool Model'],['calibration.test_tool_serial','Test Tool Serial Number'],['calibration.test_tool_calibration_date','Test Tool Calibration Date'],['calibration.engineer_name','Service Engineer Name']];
    required.forEach(function(item){ if(!String(getPath(report,item[0]) || '').trim()) missing.push({ path:item[0], label:item[1] }); });
    if(!String(report.signature.image || '').trim()) missing.push({ path:'signature.image', label:'Calibration Signature' });
    report.mechanical_checks.forEach(function(item,index){ if(!String(item.result || '').trim()) missing.push({ path:'mechanical_checks.' + index + '.result', label:item.label + ' result' }); });
    report.generator_checks.forEach(function(item,index){ if(!String(item.result || '').trim()) missing.push({ path:'generator_checks.' + index + '.result', label:item.label + ' result' }); });
    var selectedSpots = ['small','large'].filter(function(key){ return report.focal_spots?.[key] !== false; });
    if(!selectedSpots.length) missing.push({ path:'focal_spots.small', label:'At least one focal spot' });
    selectedSpots.forEach(function(key){
      if(!String(report.focal_sizes?.[key] || '').trim()) missing.push({ path:'focal_sizes.' + key, label:(key === 'small' ? 'Small' : 'Large') + ' focal size' });
      var hasRow = report.exposure[key].some(function(row){ return Object.keys(row).some(function(field){ return String(row[field] || '').trim(); }); });
      if(!hasRow) missing.push({ path:'exposure.' + key + '.0.nominal_kvp', label:(key === 'small' ? 'Small' : 'Large') + ' focal spot measurements' });
    });
    report.performance_results.forEach(function(result,index){ if(!String(result || '').trim()) missing.push({ path:'performance_results.' + index, label:'Performance criterion ' + (index + 1) + ' result' }); });
    return missing;
  }
  function validateForFinalSave(payload){
    var report = payload?.calibration_report ? normalizeState(payload.calibration_report) : state; if(!isActive(report)) return { ok:true, missing:[] };
    var fit = exactFitViolations(report);
    if(fit.length){ return { ok:false, missing:fit.map(function(item){ return { path:item.path, label:item.label }; }), fit:fit, message:fit[0].message + (fit.length > 1 ? ' Fix the marked fields before generating the DOCX.' : '') }; }
    var missing = missingFields(report); if(missing.length) return { ok:false, missing:missing, message:'Complete the Calibration Report or remove it before saving: ' + missing.slice(0,4).map(function(item){ return item.label; }).join(', ') + (missing.length > 4 ? ', and more.' : '.') };
    if(!CERTIFICATE_CATALOG_AVAILABLE){
      return { ok:false, missing:[{ path:'machine.modality', label:'Calibration Certificate catalog' }], message:'The Calibration Certificate catalog is unavailable or invalid. Reload Create TSR before saving the final report.' };
    }
    if(CERTIFICATE_EQUIPMENT_NAMES.indexOf(String(report.machine?.modality || '').trim()) < 0){
      return { ok:false, missing:[{ path:'machine.modality', label:'Approved Equipment Name' }], message:'Select an approved Equipment Name before saving the final report.' };
    }
    var match = certificateModelMatch(report.machine?.model);
    if(match.status !== 'exact' && match.status !== 'accepted'){
      return { ok:false, missing:[{ path:'machine.model', label:'Exact catalog Equipment Model' }], match:match, message:'Select an exact catalog Equipment Model before saving the final report.' + (match.suggestions?.length ? ' Closest suggestions: ' + match.suggestions.join(', ') + '.' : '') };
    }
    return { ok:true, missing:[], match:match };
  }
  function focusMissing(missing){
    var first = missing?.[0]; if(!first) return; open(); if(first.path.indexOf('mechanical_checks') === 0 || first.path.indexOf('generator_checks') === 0 || first.path.indexOf('calibration.') === 0) setEditorPage(2); else if(first.path.indexOf('exposure') === 0 || first.path.indexOf('performance_results') === 0) setEditorPage(3); else setEditorPage(1);
    setTimeout(function(){ var element = first.path.indexOf('mechanical_checks') === 0 ? q('[data-cr-check="mechanical:' + first.path.split('.')[1] + '"]') : (first.path.indexOf('generator_checks') === 0 ? q('[data-cr-check="generator:' + first.path.split('.')[1] + '"]') : fieldElement(first.path)); if(!element && first.path.indexOf('exposure') === 0){ var parts = first.path.split('.'); element = q('[data-cr-exposure="' + parts[1] + ':' + parts[2] + ':0"]'); } if(!element && first.path.indexOf('performance_results') === 0) element = q('[data-cr-performance="' + first.path.split('.')[1] + '"]'); element?.focus(); element?.scrollIntoView({ behavior:'smooth', block:'center' }); }, 50);
  }

  function stableText(value){ return JSON.stringify(value, function(key, current){ if(['status','updated_at','auto_fill','generated','generated_cleanup','auto_document','certificate','certificate_approval'].includes(key)) return undefined; return current; }); }
  function hashText(value){ var hash = 2166136261; for(var index = 0; index < value.length; index += 1){ hash ^= value.charCodeAt(index); hash = Math.imul(hash, 16777619); } return ('00000000' + (hash >>> 0).toString(16)).slice(-8); }
  function fingerprint(report){ return hashText(stableText(report)); }
  function filenameFor(payload, report){
    var client = String(report.facility.name || payload?.['tsr-customer-name'] || 'Client').trim(); var model = String(report.machine.model || payload?.['tsr-equipment-model'] || 'Model').trim(); var serial = String(report.machine.serial_number || payload?.['tsr-serial-no'] || 'Serial').trim(); var date = String(report.calibration.machine_calibration_date || payload?.['tsr-service-date'] || '').replace(/[^0-9]/g,'');
    if(date.length !== 8){ var now = new Date(); date = String(now.getMonth()+1).padStart(2,'0') + String(now.getDate()).padStart(2,'0') + String(now.getFullYear()); } else if(/^\d{8}$/.test(date)) date = date.slice(4,6) + date.slice(6,8) + date.slice(0,4);
    function safe(value){ return String(value).replace(/[<>:"/\\|?*]+/g,'_').replace(/\s+/g,' ').trim().slice(0,80) || 'Unknown'; }
    return 'NCS_CALIBRATION_REPORT_Shimadzu_' + safe(client) + '_' + safe(model) + '(' + safe(serial) + ')_' + date + '.docx';
  }

  function dataUrlBytes(dataUrl){
    var parts = String(dataUrl || '').split(','); if(parts.length < 2) return new Uint8Array();
    var binary = atob(parts[1].replace(/\s/g,'')); var bytes = new Uint8Array(binary.length);
    for(var index = 0; index < binary.length; index += 1) bytes[index] = binary.charCodeAt(index);
    return bytes;
  }
  function xmlEscape(value){ return String(value === undefined || value === null ? '' : value).replace(/[\u0000-\u0008\u000B\u000C\u000E-\u001F]/g,'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&apos;'); }
  function xmlUnescape(value){ return String(value || '').replace(/&quot;/g,'"').replace(/&apos;/g,"'").replace(/&lt;/g,'<').replace(/&gt;/g,'>').replace(/&amp;/g,'&'); }
  function normalizedDocxText(value){ return String(value === undefined || value === null ? '' : value).replace(/[\u0000-\u0008\u000B\u000C\u000E-\u001F]/g,''); }
  function singleLineDocxText(value){ return normalizedDocxText(value).replace(/[\r\n\t]+/g,' ').replace(/\s+/g,' ').trim(); }
  function directXmlBlocks(xml, tag){
    var blocks = []; var depth = 0; var start = -1; var matcher = new RegExp('<w:' + tag + '\\b[^>]*>|<\\/w:' + tag + '>','g'); var match;
    while((match = matcher.exec(xml))){
      var token = match[0];
      if(token.indexOf('</') === 0){
        if(depth === 1 && start >= 0) blocks.push({ start:start, end:matcher.lastIndex, xml:xml.slice(start, matcher.lastIndex) });
        depth = Math.max(0, depth - 1);
      }else if(/\/\s*>$/.test(token)){
        if(depth === 0) blocks.push({ start:match.index, end:matcher.lastIndex, xml:token });
      }else{
        if(depth === 0) start = match.index;
        depth += 1;
      }
    }
    return blocks;
  }
  function templateSlotError(detail){ var error = new Error('The supplied Calibration Report template is missing an expected slot: ' + detail); error.code = 'calibration_report_template_slot_missing'; return error; }
  function relationshipTarget(relsXml, relId, relType){
    var matcher = /<Relationship\b[^>]*\/>/g; var match;
    while((match = matcher.exec(relsXml))){
      var tag = match[0]; var id = tag.match(/\bId="([^"]+)"/); var type = tag.match(/\bType="([^"]+)"/); var target = tag.match(/\bTarget="([^"]+)"/);
      if(id && type && target && id[1] === relId && type[1] === relType) return target[1];
    }
    return '';
  }
  function templatePartPath(target){ var normalized = String(target || '').replace(/^\/+/, '').replace(/^\.\//, ''); return normalized.indexOf('word/') === 0 ? normalized : 'word/' + normalized; }
  function validateTemplateFurniture(zip, documentXml, relsXml){
    var footerIds = []; var headerIds = [];
    documentXml.replace(/<w:footerReference\b[^>]*\br:id="([^"]+)"/g, function(_, id){ footerIds.push(id); return _; });
    documentXml.replace(/<w:headerReference\b[^>]*\br:id="([^"]+)"/g, function(_, id){ headerIds.push(id); return _; });
    if(!footerIds.length) throw templateSlotError('source footer references');
    footerIds.concat(headerIds).forEach(function(relId){
      var relType = footerIds.indexOf(relId) >= 0 ? 'http://schemas.openxmlformats.org/officeDocument/2006/relationships/footer' : 'http://schemas.openxmlformats.org/officeDocument/2006/relationships/header';
      var target = relationshipTarget(relsXml, relId, relType); if(!target || !zip.file(templatePartPath(target))) throw templateSlotError('source ' + (relType.indexOf('/footer') >= 0 ? 'footer' : 'header') + ' relationship ' + relId);
    });
  }
  function patchTableCell(documentXml, tableIndex, rowIndex, cellIndex, mutator){
    var tables = directXmlBlocks(documentXml, 'tbl'); if(!tables[tableIndex]) throw templateSlotError('table ' + tableIndex);
    var table = tables[tableIndex]; var rows = directXmlBlocks(table.xml, 'tr'); if(!rows[rowIndex]) throw templateSlotError('table ' + tableIndex + ', row ' + rowIndex);
    var row = rows[rowIndex]; var cells = directXmlBlocks(row.xml, 'tc'); if(!cells[cellIndex]) throw templateSlotError('table ' + tableIndex + ', row ' + rowIndex + ', cell ' + cellIndex);
    var cell = cells[cellIndex]; var replacement = mutator(cell.xml); if(typeof replacement !== 'string') throw templateSlotError('table ' + tableIndex + ', row ' + rowIndex + ', cell ' + cellIndex);
    var rowXml = row.xml.slice(0, cell.start) + replacement + row.xml.slice(cell.end);
    var tableXml = table.xml.slice(0, row.start) + rowXml + table.xml.slice(row.end);
    return documentXml.slice(0, table.start) + tableXml + documentXml.slice(table.end);
  }
  function cellText(cellXml){ return xmlUnescape(cellXml.replace(/<[^>]+>/g,'')).replace(/\s+/g,' ').trim(); }
  function firstRunProperties(paragraphXml){
    var runs = directXmlBlocks(paragraphXml, 'r');
    if(runs.length){ var runProperties = directXmlBlocks(runs[0].xml, 'rPr'); if(runProperties.length) return runProperties[0].xml; }
    var paragraphProperties = directXmlBlocks(paragraphXml, 'pPr');
    if(paragraphProperties.length){ var inherited = directXmlBlocks(paragraphProperties[0].xml, 'rPr'); if(inherited.length) return inherited[0].xml; }
    return '';
  }
  function removeParagraphRuns(paragraphXml){
    var runs = directXmlBlocks(paragraphXml, 'r').slice().reverse(); runs.forEach(function(run){ paragraphXml = paragraphXml.slice(0, run.start) + paragraphXml.slice(run.end); });
    return paragraphXml.replace(/<w:proofErr\b[^>]*\/>/g,'');
  }
  function textRuns(value, runProperties){
    var lines = normalizedDocxText(value).replace(/\r\n?/g,'\n').split('\n');
    return lines.map(function(line, index){ return (index ? '<w:br/>' : '') + '<w:r>' + (runProperties || '') + '<w:t xml:space="preserve">' + xmlEscape(line) + '</w:t></w:r>'; }).join('');
  }
  function replaceFirstParagraph(cellXml, appendXml){
    var paragraphs = directXmlBlocks(cellXml, 'p'); if(!paragraphs.length) throw templateSlotError('cell paragraph');
    var paragraph = paragraphs[0]; var cleanParagraph = removeParagraphRuns(paragraph.xml); var endTag = '</w:p>';
    if(cleanParagraph.slice(-endTag.length) !== endTag) throw templateSlotError('cell paragraph end');
    var replacement = cleanParagraph.slice(0, -endTag.length) + appendXml + endTag;
    return cellXml.slice(0, paragraph.start) + replacement + cellXml.slice(paragraph.end);
  }
  function setParagraphAlignment(paragraphXml, alignment){
    if(!alignment) return paragraphXml;
    var alignmentXml = '<w:jc w:val="' + xmlEscape(alignment) + '"/>';
    var paragraphProperties = directXmlBlocks(paragraphXml, 'pPr');
    if(paragraphProperties.length){
      var properties = paragraphProperties[0]; var propertiesXml = properties.xml; var existing = directXmlBlocks(propertiesXml, 'jc');
      if(existing.length){
        propertiesXml = propertiesXml.slice(0, existing[0].start) + alignmentXml + propertiesXml.slice(existing[0].end);
      } else {
        var propertiesEnd = '</w:pPr>'; if(propertiesXml.slice(-propertiesEnd.length) !== propertiesEnd) throw templateSlotError('cell paragraph properties end');
        propertiesXml = propertiesXml.slice(0, -propertiesEnd.length) + alignmentXml + propertiesEnd;
      }
      return paragraphXml.slice(0, properties.start) + propertiesXml + paragraphXml.slice(properties.end);
    }
    var openingEnd = paragraphXml.indexOf('>'); if(openingEnd < 0) throw templateSlotError('cell paragraph start');
    return paragraphXml.slice(0, openingEnd + 1) + '<w:pPr>' + alignmentXml + '</w:pPr>' + paragraphXml.slice(openingEnd + 1);
  }
  function appendTextToCell(cellXml, value, alignment){
    if(cellText(cellXml)) throw templateSlotError('expected blank text cell');
    var paragraphs = directXmlBlocks(cellXml, 'p'); if(!paragraphs.length) throw templateSlotError('blank text cell paragraph');
    if(alignment){
      var paragraph = paragraphs[0]; var alignedParagraph = setParagraphAlignment(paragraph.xml, alignment);
      cellXml = cellXml.slice(0, paragraph.start) + alignedParagraph + cellXml.slice(paragraph.end);
      paragraphs = directXmlBlocks(cellXml, 'p');
    }
    return replaceFirstParagraph(cellXml, textRuns(value, firstRunProperties(paragraphs[0].xml)));
  }
  function compactPageThreeGap(documentXml){
    var tables = directXmlBlocks(documentXml, 'tbl'); if(tables.length < 4) throw templateSlotError('page 3 performance table');
    // With both focal tables present, preserve the supplied two-paragraph gap
    // before Large and compact only the three-paragraph gap before Performance
    // Criteria. When one focal table has been removed, its surrounding gaps
    // merge; keep one natural spacer between the surviving table and criteria.
    var focalIndex = tables.length === 5 ? 3 : 2;
    var gap = documentXml.slice(tables[focalIndex].end, tables[focalIndex + 1].start); var paragraphs = directXmlBlocks(gap, 'p');
    if(paragraphs.length <= 1) return documentXml;
    var keptParagraph = paragraphs[paragraphs.length - 1].xml;
    return documentXml.slice(0, tables[focalIndex].end) + keptParagraph + documentXml.slice(tables[focalIndex + 1].start);
  }
  function removeDirectTable(documentXml, tableIndex){
    var tables = directXmlBlocks(documentXml, 'tbl');
    if(!tables[tableIndex]) throw templateSlotError('table ' + tableIndex);
    var table = tables[tableIndex];
    return documentXml.slice(0, table.start) + documentXml.slice(table.end);
  }
  function textBlocks(xml){ return directXmlBlocks(xml, 't'); }
  function replaceResultLine(cellXml, value){
    var nodes = textBlocks(cellXml); var resultIndex = -1; var resultText = '';
    nodes.some(function(node, index){ var text = xmlUnescape(node.xml.replace(/^<w:t\b[^>]*>/,'').replace(/<\/w:t>$/,'')); if(text.indexOf('RESULT:') >= 0){ resultIndex = index; resultText = text; return true; } return false; });
    if(resultIndex < 0) throw templateSlotError('result line');
    var node = nodes[resultIndex]; var openEnd = node.xml.indexOf('>'); var labelIndex = resultText.indexOf('RESULT:'); var replacementText = resultText.slice(0, labelIndex) + 'RESULT: ' + singleLineDocxText(value);
    var replacementNode = node.xml.slice(0, openEnd + 1) + xmlEscape(replacementText) + '</w:t>';
    cellXml = cellXml.slice(0, node.start) + replacementNode + cellXml.slice(node.end);
    var updatedNodes = textBlocks(cellXml); var removed = [];
    updatedNodes.forEach(function(updated, index){
      if(index <= resultIndex) return;
      var text = xmlUnescape(updated.xml.replace(/^<w:t\b[^>]*>/,'').replace(/<\/w:t>$/,''));
      if(/^\s*_+\s*$/.test(text)) removed.push(updated);
    });
    removed.reverse().forEach(function(item){ cellXml = cellXml.slice(0, item.start) + cellXml.slice(item.end); });
    return cellXml;
  }
  function replaceFocalSizeLine(cellXml, value){
    var nodes = textBlocks(cellXml); var labelIndex = -1;
    nodes.some(function(node, index){ var text = xmlUnescape(node.xml.replace(/^<w:t\b[^>]*>/,'').replace(/<\/w:t>$/,'')); if(text.indexOf('FOCAL SIZE:') >= 0){ labelIndex = index; return true; } return false; });
    if(labelIndex < 0 || !nodes[labelIndex + 1]) throw templateSlotError('focal size line');
    var valueNodes = nodes.slice(labelIndex + 1);
    valueNodes.slice().reverse().forEach(function(node){
      var openEnd = node.xml.indexOf('>');
      var text = node === valueNodes[0] && String(value || '').trim() ? ' ' + singleLineDocxText(value) : '';
      var replacement = node.xml.slice(0, openEnd + 1) + xmlEscape(text) + '</w:t>';
      cellXml = cellXml.slice(0, node.start) + replacement + cellXml.slice(node.end);
    });
    return cellXml;
  }
  function signatureDrawingRun(relId, runProperties){
    var cx = 2400000; var cy = 500000;
    return '<w:r>' + (runProperties || '') + '<w:drawing><wp:inline distT="0" distB="0" distL="0" distR="0"><wp:extent cx="' + cx + '" cy="' + cy + '"/><wp:effectExtent l="0" t="0" r="0" b="0"/><wp:docPr id="2000000001" name="Calibration signature"/><wp:cNvGraphicFramePr><a:graphicFrameLocks xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" noChangeAspect="1"/></wp:cNvGraphicFramePr><a:graphic xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture"><pic:pic xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture"><pic:nvPicPr><pic:cNvPr id="2000000001" name="Calibration signature"/><pic:cNvPicPr/></pic:nvPicPr><pic:blipFill><a:blip r:embed="' + relId + '"/><a:stretch><a:fillRect/></a:stretch></pic:blipFill><pic:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="' + cx + '" cy="' + cy + '"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr></pic:pic></a:graphicData></a:graphic></wp:inline></w:drawing></w:r>';
  }
  function fillSignatureCell(cellXml, relId){
    if(cellText(cellXml)) throw templateSlotError('signature cell is not blank');
    var paragraphs = directXmlBlocks(cellXml, 'p'); if(!paragraphs.length) throw templateSlotError('signature cell paragraph');
    return replaceFirstParagraph(cellXml, signatureDrawingRun(relId, firstRunProperties(paragraphs[0].xml)));
  }
  function addImageRelationship(relsXml){
    var existing = relsXml.match(/<Relationship\b[^>]*Target="media\/calibration-signature\.png"[^>]*\/>/);
    if(existing){ var existingId = existing[0].match(/\bId="([^"]+)"/); return { xml:relsXml, id:existingId ? existingId[1] : 'rId1' }; }
    var maximum = 0; var matcher = /\bId="rId(\d+)"/g; var match; while((match = matcher.exec(relsXml))) maximum = Math.max(maximum, Number(match[1]));
    var id = 'rId' + (maximum + 1); var relationship = '<Relationship Id="' + id + '" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="media/calibration-signature.png"/>';
    var close = relsXml.lastIndexOf('</Relationships>'); if(close < 0) throw templateSlotError('document relationships');
    return { xml:relsXml.slice(0, close) + relationship + relsXml.slice(close), id:id };
  }
  function addImageContentType(contentTypesXml){
    if(/PartName="\/word\/media\/calibration-signature\.png"/.test(contentTypesXml)) return contentTypesXml;
    var close = contentTypesXml.lastIndexOf('</Types>'); if(close < 0) throw templateSlotError('content types');
    return contentTypesXml.slice(0, close) + '<Override PartName="/word/media/calibration-signature.png" ContentType="image/png"/>' + contentTypesXml.slice(close);
  }
  async function buildDocx(payload, report, filename){
    var JSZip = window.JSZip;
    if(!JSZip?.loadAsync) throw new Error('The local Calibration Report DOCX runtime is unavailable. Reload the page once, then try again.');
    if(!CONFIG.templateUrl) throw new Error('The local Calibration Report DOCX template is unavailable.');
    var response = await fetch(CONFIG.templateUrl, { cache:'force-cache', credentials:'same-origin' }); if(!response.ok) throw new Error('The local Calibration Report DOCX template could not be loaded.');
    var zip = await JSZip.loadAsync(await response.arrayBuffer()); var documentFile = zip.file('word/document.xml'); if(!documentFile) throw templateSlotError('word/document.xml');
    var documentXml = await documentFile.async('string'); var relsFile = zip.file('word/_rels/document.xml.rels'); var contentTypesFile = zip.file('[Content_Types].xml'); if(!relsFile || !contentTypesFile) throw templateSlotError('signature package relationships'); var documentRels = await relsFile.async('string'); validateTemplateFurniture(zip, documentXml, documentRels); if(directXmlBlocks(documentXml, 'tbl').length !== 5) throw templateSlotError('five source tables');
    var pageOneFields = [['facility.name',0,1,1],['facility.address',0,2,1],['facility.telephone',0,3,1],['facility.email',0,4,1],['facility.location',0,5,1],['machine.manufacturer',0,7,1],['machine.modality',0,8,1],['machine.model',0,9,1],['machine.serial_number',0,10,1],['machine.console_model',0,12,1],['machine.console_serial',0,12,2],['machine.tube1_model',0,14,1],['machine.tube1_serial',0,14,2],['machine.tube2_model',0,16,1],['machine.tube2_serial',0,16,2],['machine.installation_date',0,17,1],['technical.max_tube_current_ma',0,19,1],['technical.max_tube_voltage_kv',0,20,1],['technical.tube_current_mas_range',0,21,1],['technical.tube_voltage_kvp_range',0,22,1],['technical.exposure_time_range',0,23,1],['technical.max_rated_power_kw',0,24,1],['technical.power_supply',0,25,1],['technical.total_inherent_filtration',0,26,1]];
    pageOneFields.forEach(function(field){ var value = getPath(report, field[0]); if(!String(value || '').trim()) return; documentXml = patchTableCell(documentXml, field[1], field[2], field[3], function(cell){ return appendTextToCell(cell, value); }); });
    [[0,1,1,report.mechanical_checks[0]?.result],[0,3,1,report.generator_checks[0]?.result],[0,4,1,report.generator_checks[1]?.result],[0,5,1,report.generator_checks[2]?.result],[0,6,1,report.generator_checks[3]?.result]].forEach(function(item){ documentXml = patchTableCell(documentXml, 1, item[1], item[2], function(cell){ return replaceResultLine(cell, item[3]); }); });
    [['calibration.machine_calibration_date',8],['calibration.next_calibration_date',9],['calibration.test_tool_manufacturer',10],['calibration.test_tool_model',11],['calibration.test_tool_serial',12],['calibration.test_tool_calibration_date',13]].forEach(function(field){ var value = getPath(report, field[0]); if(!String(value || '').trim()) return; documentXml = patchTableCell(documentXml, 1, field[1], 1, function(cell){ return appendTextToCell(cell, value); }); });
    [['small',2],['large',3]].forEach(function(table){
      var key = table[0]; var selected = report.focal_spots?.[key] !== false; var rows = report.exposure[key] || [];
      if(selected) documentXml = patchTableCell(documentXml, table[1], 1, 0, function(cell){ return replaceFocalSizeLine(cell, report.focal_sizes?.[key]); });
      if(!selected) return;
      rows.forEach(function(row, rowIndex){ EXPOSURE_KEYS.forEach(function(field, columnIndex){ var value = row[field]; if(!String(value || '').trim()) return; documentXml = patchTableCell(documentXml, table[1], rowIndex + 4, columnIndex, function(cell){ return appendTextToCell(cell, value, 'center'); }); }); });
    });
    report.performance_results.forEach(function(value, index){ documentXml = patchTableCell(documentXml, 4, index + 1, 1, function(cell){ return appendTextToCell(cell, value); }); });
    // Remove unselected focal tables after all source-indexed writes are done.
    // Descending order keeps the original table indexes valid.
    if(report.focal_spots?.large === false) documentXml = removeDirectTable(documentXml, 3);
    if(report.focal_spots?.small === false) documentXml = removeDirectTable(documentXml, 2);
    documentXml = compactPageThreeGap(documentXml);
    var relationshipInfo = addImageRelationship(documentRels); documentXml = patchTableCell(documentXml, 1, 14, 1, function(cell){ return fillSignatureCell(cell, relationshipInfo.id); });
    zip.file('word/document.xml', documentXml); zip.file('word/_rels/document.xml.rels', relationshipInfo.xml); zip.file('[Content_Types].xml', addImageContentType(await contentTypesFile.async('string'))); zip.file('word/media/calibration-signature.png', dataUrlBytes(report.signature.image), { binary:true });
    var bytes = await zip.generateAsync({ type:'blob', compression:'STORE' }); return { blob:new Blob([bytes], { type:DOCX_MIME }), filename:filename };
  }
  function missingGeneratedBlobError(){ var error = new Error('The stored Calibration Report DOCX is missing from this device. Click Save Final Report to create a new final attachment.'); error.code = 'calibration_report_blob_missing'; return error; }
  function notFinalizedError(){ var error = new Error('Save Final Report before saving or synchronizing this TSR. Generate Sample DOCX is for review only.'); error.code = 'calibration_report_not_finalized'; return error; }
  function downloadBlob(blob, filename){
    var url = URL.createObjectURL(blob); var link = document.createElement('a'); link.href = url; link.download = filename; document.body.appendChild(link); link.click(); link.remove(); setTimeout(function(){ URL.revokeObjectURL(url); }, 1500);
  }

  async function preparePayload(payload, ownerId, options){
    var next = Object.assign({}, payload || {}); var report = next.calibration_report ? normalizeState(next.calibration_report) : (isActive(state) ? normalizeState(state) : blankState()); if(!isActive(report)) return next;
    report = normalizeReportFitValues(report);
    var validation = validateForFinalSave({ calibration_report:report }); if(!validation.ok){ var validationError = new Error(validation.message); validationError.code = validation.fit?.length ? 'calibration_report_exact_fit' : 'calibration_report_incomplete'; validationError.missing = validation.missing; validationError.fit = validation.fit || []; throw validationError; }
    var opts = options || {}; var fp = fingerprint(report); var filename = filenameFor(next, report); var blobId = 'calibration-report-' + fp; var existingId = String(report.generated?.blob_id || '').trim(); var existingFingerprint = String(report.generated?.fingerprint || '').trim(); var existingMatches = !!existingId && existingFingerprint === fp; var supersededBlobIds = reportBlobIdsForCleanup(report).filter(function(id){ return id !== blobId; }); var record = null;
    if(!existingMatches && !opts.regenerate && !opts.finalize) throw notFinalizedError();
    if(existingMatches && typeof window.loadOfflineTSRBlobRecord === 'function') record = await window.loadOfflineTSRBlobRecord(existingId);
    if(existingMatches && !record?.blob && !opts.regenerate){ generatedBlobState = 'missing'; renderCard(); syncAutoDocument(); throw missingGeneratedBlobError(); }
    var blob = record?.blob && existingMatches && !opts.regenerate ? record.blob : null;
    if(!blob){
      blob = (await buildDocx(next, report, filename)).blob;
      if(typeof window.saveOfflineTSRBlobRecord !== 'function') throw new Error('Durable browser storage is unavailable for the Calibration Report DOCX.');
      // Write new bytes before swapping the report metadata and attachment reference.
      await window.saveOfflineTSRBlobRecord({ id:blobId, owner_id:ownerId || 'calibration-report', owner_type:'generated_calibration_report', name:filename, type:DOCX_MIME, size:blob.size || 0, blob:blob, source:'generated_calibration_report' });
    }else blobId = existingId;
    generatedBlobState = 'available';
    report.generated_cleanup = { blob_ids:[] };
    report.generated = { fingerprint:fp, attachment_id:'calibration-report-' + fp, blob_id:blobId, filename:filename, size:Number(blob.size || 0) }; report.updated_at = new Date().toISOString(); next.calibration_report = report;
    var attachments = Array.isArray(next.attachments) ? next.attachments.filter(function(item){ return String(item?.source || '') !== 'generated_calibration_report'; }) : [];
    attachments.push({ id:report.generated.attachment_id, name:filename, filename:filename, type:DOCX_MIME, size:report.generated.size, blob_id:blobId, source:'generated_calibration_report', report_fingerprint:fp }); next.attachments = attachments;
    state = report; renderCard(); syncAutoDocument();
    var cleanupFailures = await cleanupGeneratedBlobIds(supersededBlobIds);
    if(cleanupFailures.length){ report.generated_cleanup = { blob_ids:cleanupFailures }; state.generated_cleanup = report.generated_cleanup; console.warn('[Calibration Report] Previous generated Blob cleanup remains pending', cleanupFailures); }
    return next;
  }
  function attachmentFromPayload(payload){ var report = payload?.calibration_report ? normalizeState(payload.calibration_report) : state; if(!isActive(report) || !report.generated?.attachment_id || !report.generated?.blob_id) return null; return { id:report.generated.attachment_id, name:report.generated.filename, filename:report.generated.filename, type:DOCX_MIME, size:Number(report.generated.size || 0), blob_id:report.generated.blob_id, source:'generated_calibration_report', report_fingerprint:report.generated.fingerprint }; }
  async function resolveAttachmentBlob(attachment){ if(String(attachment?.source || '') !== 'generated_calibration_report') return null; if(attachment.blob instanceof Blob) return attachment.blob; if(attachment.blob_id && typeof window.loadOfflineTSRBlobRecord === 'function'){ var record = await window.loadOfflineTSRBlobRecord(attachment.blob_id); if(record?.blob){ if(String(state.generated?.blob_id || '') === String(attachment.blob_id)) generatedBlobState = 'available'; return record.blob; } } if(String(state.generated?.blob_id || '') === String(attachment?.blob_id || '')){ generatedBlobState = 'missing'; renderCard(); syncAutoDocument(); } return null; }

  function certificateError(code, message){ var error = new Error(message); error.code = code; return error; }
  function certificateFilename(number){
    var safe = String(number || '').replace(/[<>:"/\\|?*\u0000-\u001f]+/g,'_').replace(/\s+/g,' ').trim().slice(0,120);
    return safe ? 'SAMPLE_Calibration_Certificate_' + safe + '.pdf' : 'SAMPLE_Calibration_Certificate.pdf';
  }
  function decodeCertificateTemplateBytes(){
    var data = CONFIG.certificateTemplateData;
    if(!data || typeof data !== 'object' || typeof data.base64 !== 'string' || !data.base64.trim()) throw certificateError('calibration_certificate_template_missing', 'The embedded Calibration Certificate template is unavailable.');
    var encoded = data.base64.replace(/\s+/g,'');
    if(!/^[A-Za-z0-9+/]*={0,2}$/.test(encoded) || encoded.length % 4 !== 0) throw certificateError('calibration_certificate_template_corrupt', 'The embedded Calibration Certificate template data is corrupt. Reload Create TSR, then try again.');
    var binary;
    try{ binary = atob(encoded); }catch(error){ throw certificateError('calibration_certificate_template_corrupt', 'The embedded Calibration Certificate template data is corrupt. Reload Create TSR, then try again.'); }
    var bytes = new Uint8Array(binary.length);
    for(var index = 0; index < binary.length; index += 1) bytes[index] = binary.charCodeAt(index);
    var header = bytes.length >= 5 ? String.fromCharCode(bytes[0], bytes[1], bytes[2], bytes[3], bytes[4]) : '';
    if(Number(data.byteLength) !== bytes.byteLength || bytes.byteLength < 32 || header !== '%PDF-') throw certificateError('calibration_certificate_template_corrupt', 'The embedded Calibration Certificate template data is corrupt. Reload Create TSR, then try again.');
    return bytes;
  }
  async function loadCertificateDocument(){
    var bytes = decodeCertificateTemplateBytes();
    try{ return await window.PDFLib.PDFDocument.load(bytes); }
    catch(error){ throw certificateError('calibration_certificate_template_invalid', 'The embedded Calibration Certificate template could not be read. Reload Create TSR, then try again.'); }
  }
  async function buildCertificatePdf(payload, report){
    if(!CERTIFICATE_CATALOG_AVAILABLE) throw certificateError('calibration_certificate_catalog_unavailable', 'The Calibration Certificate catalog is unavailable or invalid. Reload Create TSR, then try again.');
    if(!window.PDFLib || typeof window.PDFLib.PDFDocument?.load !== 'function') throw certificateError('calibration_certificate_runtime_missing', 'The local Calibration Certificate PDF runtime is unavailable. Reload Create TSR, then try again.');
    var document = await loadCertificateDocument();
    var form;
    try{ form = document.getForm(); }catch(error){ throw certificateError('calibration_certificate_template_fields', 'The Calibration Certificate template has no readable AcroForm fields.'); }
    var expected = ['Textfield','Text1','Text2','Text3','Text4','Text5','Text6','Textfield-0','Rodito Aretano Jr'];
    var available = [];
    try{ available = form.getFields().map(function(field){ return field.getName(); }); }catch(error){ available = []; }
    var missing = expected.filter(function(name){ return available.indexOf(name) < 0; });
    if(missing.length) throw certificateError('calibration_certificate_template_fields', 'The Calibration Certificate template is missing expected field(s): ' + missing.join(', ') + '.');
    var fieldData = certificateFieldValues(payload, report);
    var helvetica = await document.embedFont(window.PDFLib.StandardFonts.Helvetica);
    var dataSize = certificateDataFontSize(fieldData.values, helvetica);
    Object.keys(fieldData.values).forEach(function(name){ var field = form.getTextField(name); if(field.acroField && typeof field.acroField.setDefaultAppearance === 'function') field.acroField.setDefaultAppearance('/Helv 10 Tf 0 g'); field.setFontSize(dataSize); field.setText(fieldData.values[name]); });
    // Blank the legacy identity widget. Its fixed page text is absent from
    // the runtime-v2 asset, so no opaque rectangle is needed.
    form.getTextField('Rodito Aretano Jr').setText('');
    form.updateFieldAppearances(helvetica);
    form.flatten();
    if(document.catalog && typeof document.catalog.delete === 'function' && window.PDFLib.PDFName?.of) document.catalog.delete(window.PDFLib.PDFName.of('AcroForm'));
    var bytes = await document.save();
    return { blob:new Blob([bytes], { type:'application/pdf' }), filename:certificateFilename(fieldData.values.Textfield), missing:fieldData.missing, dataSize:dataSize };
  }
  async function generateCertificateSample(){
    try{
      var payload = currentTSRData(); var report = payload?.calibration_report ? normalizeState(payload.calibration_report) : normalizeState(state);
      var built = await buildCertificatePdf(payload, report); downloadBlob(built.blob, built.filename);
      showStatus('Sample Calibration Certificate PDF downloaded. It is not attached to the TSR.', 'success');
      if(built.missing.length) showStatus('Sample Calibration Certificate PDF downloaded. It is not attached. Some values are still missing: ' + built.missing.slice(0,4).join(', ') + (built.missing.length > 4 ? ', and more.' : '.'), 'warning');
      return built;
    }catch(error){ console.error('[Calibration Report] Sample Calibration Certificate generation failed', error); showStatus(error?.message || 'Calibration Certificate sample PDF could not be generated.', 'danger'); return null; }
  }

  async function generateSample(){
    try{
      var payload = currentTSRData(); var report = payload?.calibration_report ? normalizeState(payload.calibration_report) : normalizeState(state); report = normalizeReportFitValues(report);
      var fit = exactFitViolations(report);
      if(fit.length){ var fitError = new Error(fit[0].message + (fit.length > 1 ? ' Fix the marked fields before generating the DOCX.' : '')); fitError.code = 'calibration_report_exact_fit'; fitError.missing = fit.map(function(item){ return { path:item.path, label:item.label }; }); throw fitError; }
      var missing = missingFields(report);
      var filename = 'SAMPLE_' + filenameFor(payload, report); var built = await buildDocx(payload, report, filename); downloadBlob(built.blob, filename); showStatus('Sample Calibration Report DOCX downloaded. It is not attached to the TSR.', 'success');
      if(missing.length){ showStatus('Sample Calibration Report DOCX downloaded. It is not attached. Some required fields are still missing: ' + missing.slice(0,4).map(function(item){ return item.label; }).join(', ') + (missing.length > 4 ? ', and more.' : '.'), 'warning'); }
    }catch(err){ if(err?.code === 'calibration_report_incomplete' || err?.code === 'calibration_report_exact_fit'){ focusMissing(err.missing); showStatus(err.message,'danger'); } else { console.error('[Calibration Report] Sample DOCX generation failed',err); showStatus(err?.message || 'Calibration Report sample DOCX could not be generated.','danger'); } }
  }
  async function saveFinalReport(){
    try{
      var ready = await preparePayload(currentTSRData(), 'calibration-final', { regenerate:true, finalize:true });
      state.certificate_approval = Object.assign({}, state.certificate_approval || {}, { status: String(state.certificate?.bsid || '').trim() ? 'queued' : 'not_ready', error: '' });
      var persisted = typeof window.saveStandaloneTSRDraft === 'function' ? await window.saveStandaloneTSRDraft(true) : null;
      var persistenceSource = String(persisted?.source || '').toLowerCase();
      if(!persisted || persisted.skipped || persisted.failed || persistenceSource === 'none') throw new Error('Calibration Report final attachment was created locally, but the TSR draft was not saved. Try Save Final Report again.');
      var durableIndexedDB = persistenceSource === 'offline_tsr_page' || persistenceSource === 'indexeddb';
      if(!durableIndexedDB || persisted.attachments_not_durable){ var storageError = new Error('Calibration Report final attachment was created, but it was not saved durably in IndexedDB. Keep this editor open and try Save Final Report again when durable browser storage is available.'); storageError.code = 'calibration_report_attachment_not_durable'; throw storageError; }
      showStatus('Final Calibration Report saved and attached to the TSR draft. The certificate will queue after TSR sync.', 'success'); renderCard(); close();
    }catch(err){ if(err?.code === 'calibration_report_incomplete' || err?.code === 'calibration_report_exact_fit'){ focusMissing(err.missing); showStatus(err.message,'danger'); } else { console.error('[Calibration Report] Final save failed',err); showStatus(err?.message || 'Final Calibration Report could not be saved. Try again.','danger'); } }
  }
  async function download(){
    try{
      var payload = currentTSRData(); var report = payload?.calibration_report ? normalizeState(payload.calibration_report) : normalizeState(state); var attachment = attachmentFromPayload({ calibration_report:report });
      if(!attachment || !hasGeneratedMetadata(report)){ throw notFinalizedError(); }
      var blob = await resolveAttachmentBlob(attachment); if(!blob){ generatedBlobState = 'missing'; renderCard(); syncAutoDocument(); throw missingGeneratedBlobError(); }
      downloadBlob(blob, attachment.filename || report.generated.filename || 'Calibration_Report.docx'); showStatus('Final Calibration Report DOCX downloaded.', 'success');
    }catch(err){ if(err?.code === 'calibration_report_incomplete' || err?.code === 'calibration_report_exact_fit'){ focusMissing(err.missing); showStatus(err.message,'danger'); } else showStatus(err?.message || 'Save Final Report before downloading the final DOCX.','danger'); }
  }

  function renderCard(){
    var status = q('#calibration-report-status'); var summary = q('#calibration-report-summary'); var createButton = q('#calibration-report-create-btn'); var entryLabel = q('#calibration-report-entry-label'); var toolbarGenerate = q('#calibration-report-generate'); var toolbarGenerateLabel = q('#calibration-report-generate-label'); var toolbarFinal = q('#calibration-report-final-save'); var toolbarDownload = q('#calibration-report-download'); var toolbarClear = q('#calibration-report-clear'); var toolbarRemove = q('#calibration-report-toolbar-remove'); var note = q('#calibration-report-attachment-note'); var filename = q('#calibration-report-filename'); var capacity = q('#calibration-report-capacity');
    var active = isActive(state); var validation = active ? validateForFinalSave({ calibration_report:state }) : { ok:false, missing:[] }; var capacityInfo = typeof window.getTSRAttachmentCapacity === 'function' ? window.getTSRAttachmentCapacity({ calibration_report:state }) : null; var overCapacity = !!(capacityInfo && capacityInfo.total > capacityInfo.max); var hasGenerated = hasGeneratedMetadata(state); var ready = active && validation.ok && !overCapacity; var downloadReady = reportReadyForAutoDocument();
    var cardLabel = !active ? 'Create Calibration Report' : (downloadReady ? 'Open Calibration Report' : 'Continue Calibration Report');
    if(status){ status.textContent = !active ? 'Not Started' : (downloadReady ? 'Final Saved' : 'Draft'); status.className = 'calibration-report-status ' + (!active ? 'muted' : (downloadReady ? 'ready' : 'draft')); }
    if(summary) summary.textContent = !active ? 'Create an optional Calibration Report using the supplied Word form. It remains separate from the main TSR PDF.' : (hasGenerated && generatedBlobState === 'missing' ? 'The final DOCX is missing from this device. Save Final Report again before downloading or saving the TSR.' : (ready ? (downloadReady ? 'Final report saved and attached to this TSR draft.' : 'Complete. Generate a sample for review or save the final report to attach it.') : 'Incomplete report or attachment capacity issue. Finish the marked fields, save the final report, or remove the report before saving.'));
    if(entryLabel) entryLabel.textContent = cardLabel; if(createButton) createButton.setAttribute('aria-label', cardLabel);
    if(toolbarGenerateLabel) toolbarGenerateLabel.textContent = 'Generate Sample DOCX';
    if(toolbarGenerate) toolbarGenerate.classList.toggle('d-none', !active); if(toolbarFinal) toolbarFinal.classList.toggle('d-none', !active); if(toolbarDownload) toolbarDownload.classList.toggle('d-none', !downloadReady); if(toolbarClear) toolbarClear.classList.toggle('d-none', !active); if(toolbarRemove) toolbarRemove.classList.toggle('d-none', !active);
    if(filename) filename.textContent = active && state.generated?.filename ? state.generated.filename : 'No DOCX generated yet.';
    if(capacity){ if(!capacityInfo) capacity.textContent = 'Supporting attachment capacity is checked when the TSR is saved.'; else if(overCapacity) capacity.textContent = `${capacityInfo.total} of ${capacityInfo.max} supporting attachments selected. Remove an ordinary attachment before attaching this report; files will not be truncated.`; else capacity.textContent = `${capacityInfo.total} of ${capacityInfo.max} supporting attachment slots used${active ? ' including this report' : ''}.`; capacity.classList.toggle('is-over', overCapacity); }
    var cert = state.certificate_approval || {};
    var certStatusKey = String(cert.status || '').trim().toLowerCase().replace(/\s+/g, '_');
    var certStatus = 'Certificate queued until TSR sync.';
    if(!String(state.certificate?.bsid || '').trim()) certStatus = 'Certificate not ready: update Product Inventory with a BSID.';
    else if(certStatusKey === 'returned') certStatus = 'Certificate returned for correction: ' + (cert.remarks || 'See Approval Center.');
    else if(certStatusKey === 'approved') certStatus = 'Certificate approved by ' + (cert.approver_name || 'approver') + (cert.approved_at ? ' on ' + cert.approved_at : '') + '.';
    else if(certStatusKey === 'pending') certStatus = 'Certificate pending approval.';
    else if(certStatusKey === 'awaiting_route' || certStatusKey === 'awaiting_approver_assignment') certStatus = 'Certificate awaiting approver assignment.';
    else if(certStatusKey === 'error' || certStatusKey === 'retryable') certStatus = 'Certificate submission failed; retry after TSR sync.';
    if(note) note.textContent = (downloadReady ? 'Auto-managed document chip: Calibration Report · source: generated_calibration_report. ' : 'Sample downloads are not attached. Save Final Report to create the TSR attachment. ') + certStatus;
  }
  function setApprovalStatus(approval, statusLabel){
    if(!approval || typeof approval !== 'object') return;
    var rawStatus = String(statusLabel || approval.status || '').trim().toLowerCase();
    var status = rawStatus === 'awaiting approver assignment' ? 'awaiting_route' : rawStatus.replace(/\s+/g, '_');
    if(!['pending','approved','returned','superseded','awaiting_route','error','retryable'].includes(status)) return;
    state.certificate_approval = Object.assign({}, state.certificate_approval || {}, {
      status: status,
      submission_id: approval.submission_id || state.certificate_approval?.submission_id || '',
      revision_no: Number(approval.revision_no || state.certificate_approval?.revision_no || 0),
      remarks: approval.return_remarks || approval.remarks || '',
      approver_name: approval.approver_name || '',
      approver_title: approval.approver_title || '',
      approved_at: approval.approved_at || '',
      signed_url: approval.signed_url || '',
      error: approval.error || ''
    });
    renderCard();
  }
  async function saveReportDraft(){
    if(typeof window.saveStandaloneTSRDraft !== 'function') return;
    try{
      var result = await window.saveStandaloneTSRDraft(true);
      if(!result || result.skipped || result.failed || String(result.source || '').toLowerCase() === 'none'){
        showStatus('Calibration Report draft could not be saved on this device.','danger');
        return;
      }
      showStatus('Calibration Report draft saved with the TSR draft.', 'success');
    }catch(err){ showStatus('Calibration Report draft could not be saved on this device.','danger'); }
  }
  async function clearForm(){
    var confirmed = typeof window.offlineTSRConfirm === 'function' ? await window.offlineTSRConfirm({ title:'Clear Calibration Report form?', message:'Clear only the Calibration Report values and generated file. The ordinary TSR, signatures, documents, and manual attachments will remain unchanged.', confirmText:'Clear Form', cancelText:'Keep Report', tone:'warning', icon:'eraser' }) : false;
    if(!confirmed) return;
    var cleanupIds = reportBlobIdsForCleanup(state); var hadAutoDocument = !!state.auto_document;
    state = blankState(); state.status = 'draft'; autofill(currentSchedule()); activePage = 1; generatedBlobState = 'none';
    if(hadAutoDocument && typeof window.removeTSRDocument === 'function') window.removeTSRDocument('Calibration Report');
    ensureEditor(); applyDomFromState(); renderCard(); syncAutoDocument(); open();
    var cleanupFailures = await cleanupGeneratedBlobIds(cleanupIds);
    state.generated_cleanup = { blob_ids:cleanupFailures };
    applyDomFromState(); renderCard(); syncAutoDocument();
    var persisted = typeof window.saveStandaloneTSRDraft === 'function' ? await window.saveStandaloneTSRDraft(true).catch(function(){ return null; }) : null;
    if(!persisted || persisted.skipped || persisted.failed || String(persisted.source || '').toLowerCase() === 'none') showStatus('Calibration Report was cleared, but the cleared draft could not be saved on this device.','danger');
    else if(cleanupFailures.length) showStatus('Calibration Report cleared, but old generated-file cleanup remains pending on this device.','danger');
    else showStatus('Calibration Report form cleared. The ordinary TSR remains unchanged.','info');
  }
  async function removeReport(){
    var confirmed = typeof window.offlineTSRConfirm === 'function' ? await window.offlineTSRConfirm({ title:'Remove Calibration Report?', message:'Remove this optional Calibration Report from the TSR draft? The ordinary TSR will remain unchanged.', confirmText:'Remove Report', cancelText:'Keep Report', tone:'danger', icon:'file-circle-minus' }) : false;
    if(!confirmed) return;
    var cleanupIds = reportBlobIdsForCleanup(state);
    reset({ removeAutoDocument:true });
    var cleanupFailures = await cleanupGeneratedBlobIds(cleanupIds);
    state.generated_cleanup = { blob_ids:cleanupFailures };
    renderCard(); syncAutoDocument();
    if(typeof window.saveStandaloneTSRDraft === 'function') await window.saveStandaloneTSRDraft(true).catch(function(){});
    if(cleanupFailures.length) showStatus('Calibration Report removed, but generated DOCX cleanup remains pending on this device.', 'danger');
    else showStatus('Calibration Report removed. The ordinary TSR remains unchanged.', 'info');
  }
  function ensureEditor(){ if(!editorBuilt) buildEditor(); }

  window.calibrationReport = { collect:collect, apply:apply, setApprovalStatus:setApprovalStatus, getApprovalStatus:function(){ return clone(state.certificate_approval || {}); }, reset:reset, create:createReport, open:open, close:close, generate:generateSample, generateSample:generateSample, generateCertificateSample:generateCertificateSample, saveFinalReport:saveFinalReport, download:download, saveDraft:saveReportDraft, clearForm:clearForm, remove:removeReport, onScheduleApplied:onScheduleApplied, clearForScheduleChange:clearForScheduleChange, validateForFinalSave:validateForFinalSave, focusMissing:focusMissing, preparePayload:preparePayload, getAttachment:attachmentFromPayload, resolveAttachmentBlob:resolveAttachmentBlob, getCertificateNumber:function(report){ return certificateNumber(normalizeState(report || state)); }, getCertificateFields:function(payload, report){ return certificateFieldValues(payload || currentTSRData(), normalizeState(report || state)); }, getCertificateModelMatch:certificateModelMatch, normalizeCertificateModel:normalizeCertificateModel, getCertificateCatalog:function(){ return { equipment_names:CERTIFICATE_EQUIPMENT_NAMES.slice(), models:CERTIFICATE_MODELS.slice() }; }, getSource:function(){ return clone(SOURCE); }, getExactFitRules:function(){ return clone(EXACT_FIT_CAPACITIES); } };
  document.addEventListener('DOMContentLoaded', function(){ ensureEditor(); renderCard(); q('#calibration-report-close')?.addEventListener('click', close); q('#calibration-report-save')?.addEventListener('click', saveReportDraft); q('#calibration-report-generate')?.addEventListener('click', generateSample); q('#calibration-report-certificate-generate')?.addEventListener('click', generateCertificateSample); q('#calibration-report-final-save')?.addEventListener('click', saveFinalReport); q('#calibration-report-download')?.addEventListener('click', download); q('#calibration-report-clear')?.addEventListener('click', clearForm); q('#calibration-report-create-btn')?.addEventListener('click', createReport); q('#calibration-report-toolbar-remove')?.addEventListener('click', removeReport); document.addEventListener('keydown', handleDialogKeydown); });
})();

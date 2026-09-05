"""Focused contracts for Create TSR notifications and explicit navigation."""

import json
import pathlib
import re
import subprocess
import tempfile
import unittest

from tests.sw_cache_version import assert_cache_version_at_least


ROOT = pathlib.Path(__file__).resolve().parents[1]
NODE = pathlib.Path(r'C:\Users\Jonamar\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe')


class TsrNotificationSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.template = (ROOT / 'templates' / 'offline_tsr.html').read_text(encoding='utf-8')
        cls.calibration = (ROOT / 'static' / 'js' / 'app-calibration-report.js').read_text(encoding='utf-8')
        cls.app_source = (ROOT / 'app.py').read_text(encoding='utf-8')

    def test_page_and_dialog_notification_hosts_exist(self):
        for marker in (
            'id="offline-tsr-notifications"',
            'id="offline-tsr-dialog-notifications"',
            'id="schedule-picker-modal-notifications"',
            'id="tsr-preview-notifications"',
            'id="signature-modal-notifications"',
        ):
            self.assertIn(marker, self.template)
        self.assertNotIn('id="standalone-tsr-status"', self.template)

    def test_status_and_recovery_do_not_scroll_the_document(self):
        status = self.template.split('function showTSRStatus(', 1)[1].split('function copyStandaloneTSRText', 1)[0]
        recovery = self.template.split('function showTSRFinalSaveRecovery(', 1)[1].split('async function finishStandaloneTSRFinalSave', 1)[0]
        self.assertIn('offline-tsr-notification', self.template)
        self.assertNotIn('scrollIntoView', status)
        self.assertNotIn('scrollIntoView', recovery)
        self.assertIn('Download PDF now', recovery)

    def test_notifications_are_persistent_or_timed_by_tone_and_action(self):
        status = self.template.split('function showTSRStatus(', 1)[1].split('function copyStandaloneTSRText', 1)[0]
        notification = self.template.split('function renderTSRNotification(', 1)[1].split('function showTSRStatus', 1)[0]
        for marker in ('mouseenter', 'mouseleave', 'focusin', 'focusout', 'replaceKey', 'action'):
            self.assertIn(marker, notification + status, marker)
        self.assertIn('8000', self.template)
        self.assertIn('aria-live="polite"', self.template)

    def test_required_navigation_is_explicit_and_immediate(self):
        core = self.template.split('function focusTSRCoreDetail(', 1)[1].split('async function validateTSRFinalSaveRequirements', 1)[0]
        recommended = self.template.split('function focusTSRRecommendedDetail(', 1)[1].split('async function confirmTSRRecommendedDetailsBeforeSave', 1)[0]
        validation = self.template.split('async function validateTSRFinalSaveRequirements(', 1)[1].split('const TSR_RECOMMENDED_DETAIL_CHECKS', 1)[0]
        recommendation = self.template.split('async function confirmTSRRecommendedDetailsBeforeSave(', 1)[1].split('async function saveSignatureFromModal', 1)[0]
        for helper in (core, recommended):
            self.assertIn('explicit', helper)
            self.assertIn("behavior:'auto'", helper)
            self.assertIn('preventScroll:true', helper)
            self.assertNotIn("behavior:'smooth'", helper)
        self.assertNotIn('focusTSRCoreDetail(missingCoreDetails[0]);', validation)
        self.assertIn('Go to field', validation)
        self.assertNotIn('focusTSRRecommendedDetail(missing[0]);', recommendation)
        self.assertIn('Review Details', recommendation)
        self.assertIn("escapeValue:'dismiss'", recommendation)
        self.assertIn("backdropValue:'dismiss'", recommendation)

    def test_signature_validation_offers_explicit_navigation(self):
        validation = self.template.split('async function validateTSRFinalSaveRequirements(', 1)[1].split('const TSR_RECOMMENDED_DETAIL_CHECKS', 1)[0]
        self.assertIn('Go to signature', validation)
        self.assertNotIn('signatureButton?.focus({ preventScroll:true });', validation)

    def test_calibration_review_navigation_is_explicit_and_not_smooth(self):
        focus = self.calibration.split('function focusMissing(', 1)[1].split('function stableText', 1)[0]
        self.assertIn('explicit', focus)
        self.assertIn("behavior:'auto'", focus)
        self.assertIn('preventScroll:true', focus)
        self.assertNotIn("behavior:'smooth'", focus)
        for marker in ('Review calibration report', 'focusMissing(err.missing, { explicit:true })'):
            self.assertIn(marker, self.calibration)

    def test_service_worker_and_release_entry_are_bumped(self):
        assert_cache_version_at_least(self, 128, self.app_source)
        self.assertIn('medical-service-pwa-offline-navigation-v128-tsr-notifications', self.app_source)
        manifest = json.loads((ROOT / 'static' / 'changelog' / 'releases.json').read_text(encoding='utf-8'))
        matches = [item for release in manifest['releases'] for item in release.get('items', [])
                   if item.get('item_key') == '2026-09-05-tsr-notifications-everyone']
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]['category'], 'Create TSR')


class TsrNotificationBehaviorTests(unittest.TestCase):
    """Execute the notification helpers from the template in a small DOM harness."""

    def test_actual_notification_helpers_keep_position_and_actions(self):
        if not NODE.exists():
            self.skipTest(f'Node runtime unavailable: {NODE}')
        script = r'''
const fs = require('fs');
const vm = require('vm');
const source = fs.readFileSync('templates/offline_tsr.html', 'utf8');
function extractFunction(name) {
  const marker = 'function ' + name + '(';
  const start = source.indexOf(marker);
  if (start < 0) throw new Error('missing function ' + name);
  const brace = source.indexOf('){', start) + 1;
  let depth = 0;
  for (let i = brace; i < source.length; i += 1) {
    if (source[i] === '{') depth += 1;
    if (source[i] === '}') { depth -= 1; if (!depth) return source.slice(start, i + 1); }
  }
  throw new Error('unclosed function ' + name);
}
class ClassList {
  constructor() { this.values = new Set(); }
  add(...items) { items.forEach(item => this.values.add(item)); }
  remove(...items) { items.forEach(item => this.values.delete(item)); }
  toggle(item, force) { if (force === undefined ? !this.values.has(item) : force) this.add(item); else this.remove(item); }
  contains(item) { return this.values.has(item); }
}
class Element {
  constructor(id) { this.id = id || ''; this.children = []; this.parentElement = null; this.dataset = {}; this.attributes = {}; this.classList = new ClassList(); this.listeners = {}; this.textContent = ''; this.innerHTML = ''; this.style = {}; this.focused = false; this.scrollCalls = 0; }
  appendChild(child) { this.children.push(child); child.parentElement = this; return child; }
  remove() { if (this.parentElement) this.parentElement.children = this.parentElement.children.filter(item => item !== this); }
  contains(node) { if (node === this) return true; return this.children.some(child => child.contains(node)); }
  closest() { return this; }
  setAttribute(name, value) { this.attributes[name] = String(value); }
  getAttribute(name) { return this.attributes[name] || null; }
  addEventListener(name, handler) { (this.listeners[name] ||= []).push(handler); }
  dispatch(name, event = {}) { (this.listeners[name] || []).forEach(handler => handler(event)); }
  focus() { this.focused = true; document.activeElement = this; }
  scrollIntoView() { this.scrollCalls += 1; throw new Error('notification helper scrolled'); }
  querySelectorAll(selector) {
    const output = [];
    const visit = node => { node.children.forEach(child => { if (selector === 'button' && child.tagName === 'BUTTON') output.push(child); if (selector === '[data-tsr-notification]' && child.dataset.tsrNotification) output.push(child); visit(child); }); };
    visit(this); return output;
  }
}
const globalHost = new Element('offline-tsr-notifications');
const notificationHost = new Element('signature-modal-notifications');
const nodes = { 'offline-tsr-notifications': globalHost, 'signature-modal-notifications': notificationHost };
const timers = [];
const fakeSetTimeout = (callback, delay) => { const timer = { callback, delay, cancelled:false }; timers.push(timer); return timer; };
const fakeClearTimeout = timer => { if (timer) timer.cancelled = true; };
const context = {
  console,
  Date,
  setTimeout: fakeSetTimeout,
  clearTimeout: fakeClearTimeout,
  requestAnimationFrame: callback => callback(),
  document: {
    activeElement: null,
    createElement: tag => { const element = new Element(); element.tagName = String(tag || '').toUpperCase(); return element; },
    getElementById: id => nodes[id] || null,
    querySelector: () => null,
    querySelectorAll: () => [],
  },
};
context.window = context;
global.document = context.document;
vm.createContext(context);
vm.runInContext(extractFunction('escapeHTML'), context);
vm.runInContext('const TSR_NOTIFICATION_DISMISS_MS = 8000;', context);
for (const name of ['getTSRNotificationHost','findTSRNotification','removeTSRNotification','renderTSRNotification','showTSRStatus']) vm.runInContext(extractFunction(name), context);
context.showTSRStatus('Saved draft', 'success');
if (globalHost.children.length !== 1) throw new Error('success notification was not rendered');
const first = globalHost.children[0];
const firstTimer = timers.at(-1);
if (firstTimer?.delay !== 8000) throw new Error('success notification did not schedule the eight-second dismissal');
if (first.scrollCalls || context.document.activeElement) throw new Error('notification changed page position or focus');
const hasText = (node, needle) => node.textContent.includes(needle) || node.children.some(child => hasText(child, needle));
if (first.dataset.tsrNotification !== 'true' || !hasText(first, 'Saved draft')) throw new Error('notification content missing');
context.showTSRStatus('Saved draft', 'success');
if (globalHost.children.length !== 1) throw new Error('duplicate notification was not coalesced');
const timerCountBeforeRecovery = timers.length;
context.showTSRStatus('Could not save', 'danger', { action: { label:'Download PDF now', onClick:()=>{} }, key:'recovery' });
if (globalHost.children.length !== 2) throw new Error('recovery notification was not preserved');
const recovery = globalHost.children[1];
if (!recovery.querySelectorAll('button').length) throw new Error('recovery action or dismiss button missing');
if (timers.length !== timerCountBeforeRecovery) throw new Error('persistent recovery unexpectedly scheduled a timer');
context.showTSRStatus('Modal error', 'danger');
if (globalHost.children.length !== 3) throw new Error('modal test used the wrong host in the harness');
// The helper must route to an active modal host when one exists.
context.document.querySelector = selector => selector === '.modal.show [data-tsr-notification-host]' ? notificationHost : null;
context.showTSRStatus('Signature error', 'danger');
if (notificationHost.children.length !== 1 || !hasText(notificationHost.children[0], 'Signature error')) throw new Error('modal notification was not routed locally');
context.showTSRStatus('Auto dismiss', 'info', { key:'auto-dismiss' });
const auto = notificationHost.children.find(item => item.dataset.tsrNotificationKey === 'auto-dismiss');
const autoTimer = timers.at(-1);
auto.dispatch('mouseenter');
if (!autoTimer.cancelled) throw new Error('hover did not pause the notification timer');
auto.dispatch('mouseleave');
const resumedTimer = timers.at(-1);
if (resumedTimer === autoTimer || resumedTimer.cancelled) throw new Error('hover did not resume the notification timer');
auto.dispatch('focusin');
const closeButton = auto.querySelectorAll('button')[0];
auto.dispatch('focusout', { relatedTarget: closeButton });
if (!resumedTimer.cancelled || timers.at(-1) !== resumedTimer) throw new Error('keyboard focus moved within notification without pausing');
auto.dispatch('focusout', { relatedTarget: null });
const keyboardTimer = timers.at(-1);
if (keyboardTimer === resumedTimer || keyboardTimer.cancelled) throw new Error('keyboard focus did not resume notification timer');
keyboardTimer.callback();
if (notificationHost.children.includes(auto)) throw new Error('notification did not dismiss after its timer');
const target = new Element('field');
target.closest = () => target;
target.scrollIntoView = () => { target.scrollCalls += 1; };
context.document.querySelector = selector => selector === '#field' ? target : null;
vm.runInContext(extractFunction('focusTSRCoreDetail'), context);
vm.runInContext(extractFunction('focusTSRRecommendedDetail'), context);
context.focusTSRCoreDetail({ selector:'#field' });
if (target.scrollCalls !== 0 || target.focused) throw new Error('core validation navigated without an explicit action');
context.focusTSRCoreDetail({ selector:'#field' }, { explicit:true });
if (target.scrollCalls !== 1 || !target.focused) throw new Error('explicit core navigation did not jump and focus');
target.focused = false;
context.focusTSRRecommendedDetail({ selector:'#field' });
if (target.scrollCalls !== 1 || target.focused) throw new Error('recommended validation navigated without an explicit action');
context.focusTSRRecommendedDetail({ selector:'#field' }, { explicit:true });
if (target.scrollCalls !== 2 || !target.focused) throw new Error('explicit recommended navigation did not jump and focus');
console.log('notification behavior ok');
'''
        with tempfile.NamedTemporaryFile('w', suffix='.cjs', delete=False, encoding='utf-8') as handle:
            handle.write(script)
            script_path = pathlib.Path(handle.name)
        try:
            result = subprocess.run([str(NODE), str(script_path)], cwd=ROOT, capture_output=True, text=True, timeout=30)
        finally:
            script_path.unlink(missing_ok=True)
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        self.assertIn('notification behavior ok', result.stdout)


if __name__ == '__main__':
    unittest.main()

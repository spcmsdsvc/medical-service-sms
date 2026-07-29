/* Extracted from the inline <script> block in templates/changelog.html.
   The one template-injected constant now reads window.__changelogConfig, set
   inline by the template before this file loads. */

const changelogIsAdmin = (window.__changelogConfig || {}).isAdmin === true;
let changelogAdminMode = false;
let changelogReleases = [];

function changelogEscape(value){
    return String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
}

function changelogDate(value){
    if(!value) return {main:'Update', year:''};
    const date = new Date(`${value}T00:00:00`);
    return {
        main: date.toLocaleDateString(undefined, {month:'short', day:'numeric'}),
        year: date.toLocaleDateString(undefined, {weekday:'long', year:'numeric'})
    };
}

function showChangelogStatus(message, type='success'){
    const box = document.getElementById('changelog-status');
    if(!box) return;
    box.textContent = message || '';
    box.className = `changelog-status${message ? ' show' : ''}${message ? ' ' + type : ''}`;
}

function groupChangelogItems(items){
    return (items || []).reduce((groups, item) => {
        const category = item.category || 'General';
        if(!groups[category]) groups[category] = [];
        groups[category].push(item);
        return groups;
    }, {});
}

function renderChangelog(){
    const list = document.getElementById('changelog-list');
    if(!list) return;
    const unreadCount = changelogReleases.filter(release => release.is_unread).length;
    const acknowledgeAllButton = document.getElementById('changelog-acknowledge-all');
    if(acknowledgeAllButton){
        acknowledgeAllButton.hidden = unreadCount === 0 || changelogAdminMode;
        const label = acknowledgeAllButton.querySelector('span');
        if(label) label.textContent = unreadCount > 0 ? `Acknowledge All (${unreadCount})` : 'Acknowledge All';
    }
    if(!changelogReleases.length){
        list.innerHTML = '<div class="changelog-empty"><i class="fa-solid fa-circle-check me-2"></i>No published updates are available for your account.</div>';
        return;
    }
    list.innerHTML = changelogReleases.map(release => {
        const date = changelogDate(release.release_date);
        const groups = groupChangelogItems(release.items || []);
        const categories = Object.entries(groups).map(([category, items]) => `
            <section>
                <h3 class="changelog-category-title">${changelogEscape(category)}</h3>
                <ul class="changelog-items">
                    ${items.map(item => `
                        <li class="changelog-item">
                            <i class="fa-solid fa-circle-check changelog-item-icon"></i>
                            <span>${changelogEscape(item.description)}</span>
                            ${item.admin_edited && !item.is_inapp ? '<span class="changelog-flag changelog-flag-edited" title="Edited in the app, so releases.json no longer updates it">edited in app</span>' : ''}
                            ${(item.branches || []).length ? `<span class="changelog-flag">${(item.branches || []).map(changelogEscape).join(', ')}</span>` : ''}
                            ${item.is_minor ? '<span class="changelog-flag">minor</span>' : ''}
                            <span class="changelog-audiences changelog-admin-control">
                                ${(item.audiences || []).map(audience => `<span class="changelog-audience">${changelogEscape(audience)}</span>`).join('')}
                                <button type="button" class="changelog-btn" style="min-height:30px;padding:3px 8px;" onclick="openChangelogItemEditor(${Number(item.id)})"><i class="fa-solid fa-pen"></i></button>
                            </span>
                        </li>
                    `).join('')}
                </ul>
            </section>
        `).join('');
        return `
            <article class="changelog-release ${release.is_unread ? 'unread' : ''} ${release.is_published ? '' : 'unpublished'}">
                <div class="changelog-release-head">
                    <div class="changelog-date">${changelogEscape(date.main)}<span>${changelogEscape(date.year)}</span></div>
                    <div>
                        <h2 class="changelog-release-title">${changelogEscape(release.title)}</h2>
                        <p class="changelog-summary">${changelogEscape(release.summary)}</p>
                    </div>
                    <div class="changelog-release-actions">
                        ${release.is_unread ? '<span class="changelog-unread-pill"><i class="fa-solid fa-circle"></i>New</span>' : ''}
                        ${!release.is_published ? '<span class="changelog-hidden-pill">Hidden</span>' : ''}
                        ${release.is_scheduled ? `<span class="changelog-flag changelog-flag-scheduled" title="Scheduled">scheduled ${changelogEscape((release.publish_at || '').replace('T', ' ').slice(0, 16))}</span>` : ''}
                        ${release.is_inapp ? '<span class="changelog-flag">in-app</span>' : ''}
                        ${release.is_unread ? `<button type="button" class="changelog-btn changelog-btn-primary" onclick="acknowledgeChangelog(${Number(release.id)})"><i class="fa-solid fa-check"></i>Got It</button>` : ''}
                        <button type="button" class="changelog-btn changelog-admin-control" onclick="openChangelogReleaseEditor(${Number(release.id)})"><i class="fa-solid fa-pen"></i>Edit</button>
                    </div>
                </div>
                <div class="changelog-body">${categories || '<div class="changelog-empty">No visible items in this release.</div>'}</div>
            </article>
        `;
    }).join('');
}

let changelogPage = 1;
let changelogTotalPages = 1;

function changelogQueryString(){
    const params = new URLSearchParams();
    if(changelogAdminMode) params.set('admin', '1');
    params.set('page', String(changelogPage));

    const search = (document.getElementById('changelog-search-input') || {}).value || '';
    if(search.trim()) params.set('search', search.trim());

    const category = (document.getElementById('changelog-category-filter') || {}).value || '';
    if(category) params.set('category', category);

    const previewRole = (document.getElementById('changelog-preview-role') || {}).value || '';
    if(previewRole) params.set('preview_role', previewRole);

    return params.toString();
}

function renderChangelogCategories(categories){
    const select = document.getElementById('changelog-category-filter');
    if(!select) return;
    const current = select.value;
    select.innerHTML = '<option value="">All categories</option>'
        + (categories || []).map(c => `<option value="${changelogEscape(c)}">${changelogEscape(c)}</option>`).join('');
    if(current) select.value = current;
}

function renderChangelogPagination(data){
    const nav = document.getElementById('changelog-pagination');
    if(!nav) return;
    changelogTotalPages = Number(data.total_pages || 1);
    nav.hidden = changelogTotalPages <= 1;

    const label = document.getElementById('changelog-page-label');
    if(label) label.textContent = `Page ${data.page} of ${changelogTotalPages} · ${data.count} release${data.count === 1 ? '' : 's'}`;

    const prev = document.getElementById('changelog-prev');
    const next = document.getElementById('changelog-next');
    if(prev) prev.disabled = Number(data.page) <= 1;
    if(next) next.disabled = Number(data.page) >= changelogTotalPages;
}

function changeChangelogPage(delta){
    const target = changelogPage + delta;
    if(target < 1 || target > changelogTotalPages) return;
    changelogPage = target;
    loadChangelog();
    const shell = document.querySelector('.changelog-shell');
    if(shell) shell.scrollIntoView({block: 'start', behavior: 'smooth'});
}

async function loadChangelog(){
    const list = document.getElementById('changelog-list');
    if(list) list.innerHTML = '<div class="changelog-empty"><i class="fa-solid fa-circle-notch fa-spin me-2"></i>Loading updates...</div>';
    try{
        const response = await fetch(`/api/changelog/releases?${changelogQueryString()}`, {credentials:'same-origin', cache:'no-store', headers:{Accept:'application/json'}});
        const data = await response.json();
        if(!response.ok || !data.success) throw new Error(data.error || 'Unable to load updates.');
        changelogReleases = data.releases || [];
        changelogPage = Number(data.page || 1);
        renderChangelogCategories(data.categories);
        renderChangelog();
        renderChangelogPagination(data);
        showChangelogStatus(data.preview_role ? `Previewing as ${data.preview_role}.` : '');
    }catch(error){
        if(list) list.innerHTML = `<div class="changelog-empty">${changelogEscape(error.message || 'Unable to load updates.')}</div>`;
    }
}

// Filters reset to page 1, otherwise a narrow result set can land on an empty page.
function applyChangelogFilters(){
    changelogPage = 1;
    loadChangelog();
}

document.addEventListener('DOMContentLoaded', function(){
    const search = document.getElementById('changelog-search-input');
    if(search){
        let timer;
        search.addEventListener('input', function(){
            clearTimeout(timer);
            timer = setTimeout(applyChangelogFilters, 250);
        });
    }
    ['changelog-category-filter', 'changelog-preview-role'].forEach(id => {
        const el = document.getElementById(id);
        if(el) el.addEventListener('change', applyChangelogFilters);
    });
});

async function acknowledgeChangelog(releaseId){
    try{
        const response = await fetch(`/api/changelog/releases/${encodeURIComponent(releaseId)}/acknowledge`, {
            method:'POST', credentials:'same-origin', cache:'no-store',
            headers:{'Content-Type':'application/json','Accept':'application/json','X-CSRFToken':getCSRFToken()}, body:'{}'
        });
        const data = await response.json();
        if(!response.ok || !data.success) throw new Error(data.error || 'Unable to acknowledge update.');
        await loadChangelog();
        if(typeof window.refreshGlobalChangelogBadge === 'function') window.refreshGlobalChangelogBadge();
        showChangelogStatus('Update acknowledged.', 'success');
    }catch(error){ showChangelogStatus(error.message || 'Unable to acknowledge update.', 'error'); }
}

async function acknowledgeAllChangelog(){
    const button = document.getElementById('changelog-acknowledge-all');
    if(!button || button.disabled) return;
    const originalContent = button.innerHTML;
    button.disabled = true;
    button.innerHTML = '<i class="fa-solid fa-circle-notch fa-spin"></i><span>Acknowledging...</span>';
    try{
        const response = await fetch('/api/changelog/releases/acknowledge-all', {
            method:'POST', credentials:'same-origin', cache:'no-store',
            headers:{'Content-Type':'application/json','Accept':'application/json','X-CSRFToken':getCSRFToken()}, body:'{}'
        });
        const data = await response.json();
        if(!response.ok || !data.success) throw new Error(data.error || 'Unable to acknowledge updates.');
        await loadChangelog();
        if(typeof window.refreshGlobalChangelogBadge === 'function') await window.refreshGlobalChangelogBadge();
        showChangelogStatus(data.message || 'All updates acknowledged.', 'success');
    }catch(error){
        showChangelogStatus(error.message || 'Unable to acknowledge updates.', 'error');
    }finally{
        button.disabled = false;
        if(!button.hidden) button.innerHTML = originalContent;
    }
}

function toggleChangelogAdminMode(){
    if(!changelogIsAdmin) return;
    changelogAdminMode = !changelogAdminMode;
    document.body.classList.toggle('changelog-admin-mode', changelogAdminMode);
    const button = document.getElementById('changelog-admin-toggle');
    if(button) button.innerHTML = changelogAdminMode ? '<i class="fa-solid fa-eye"></i>Exit Manage Mode' : '<i class="fa-solid fa-pen-to-square"></i>Manage Updates';
    loadChangelog();
}

function findChangelogItem(itemId){
    for(const release of changelogReleases){
        const item = (release.items || []).find(entry => Number(entry.id) === Number(itemId));
        if(item) return item;
    }
    return null;
}

function openChangelogReleaseEditor(releaseId){
    const release = changelogReleases.find(entry => Number(entry.id) === Number(releaseId));
    if(!release) return;
    document.getElementById('changelog-edit-type').value = 'release';
    document.getElementById('changelog-edit-id').value = release.id;
    document.getElementById('changelog-edit-title').textContent = 'Edit Daily Release';
    document.getElementById('changelog-release-fields').style.display = '';
    document.getElementById('changelog-item-fields').style.display = 'none';
    document.getElementById('changelog-release-title-input').value = release.title || '';
    document.getElementById('changelog-release-summary-input').value = release.summary || '';
    document.getElementById('changelog-published-input').checked = !!release.is_published;
    setChangelogEditorActions({canDelete: !!release.is_inapp, canRevert: false});
    bootstrap.Modal.getOrCreateInstance(document.getElementById('changelogEditModal')).show();
}

function openChangelogItemEditor(itemId){
    const item = findChangelogItem(itemId);
    if(!item) return;
    document.getElementById('changelog-edit-type').value = 'item';
    document.getElementById('changelog-edit-id').value = item.id;
    document.getElementById('changelog-edit-title').textContent = 'Edit Update Item';
    document.getElementById('changelog-release-fields').style.display = 'none';
    document.getElementById('changelog-item-fields').style.display = '';
    document.getElementById('changelog-item-category-input').value = item.category || '';
    document.getElementById('changelog-item-description-input').value = item.description || '';
    document.querySelectorAll('.changelog-audience-check').forEach(input => { input.checked = (item.audiences || []).includes(input.value); });
    document.getElementById('changelog-published-input').checked = !!item.is_published;

    // Delete only applies to entries written in the app; manifest items must be changed
    // in releases.json. Revert only applies where a manifest version was recorded.
    setChangelogEditorActions({canDelete: !!item.is_inapp, canRevert: !!item.can_revert});
    bootstrap.Modal.getOrCreateInstance(document.getElementById('changelogEditModal')).show();
}

function setChangelogEditorActions({canDelete = false, canRevert = false} = {}){
    const deleteBtn = document.getElementById('changelog-delete-btn');
    const revertBtn = document.getElementById('changelog-revert-btn');
    if(deleteBtn) deleteBtn.hidden = !canDelete;
    if(revertBtn) revertBtn.hidden = !canRevert;
}

async function saveChangelogEdit(){
    const type = document.getElementById('changelog-edit-type').value;
    const id = document.getElementById('changelog-edit-id').value;
    const payload = type === 'release' ? {
        title: document.getElementById('changelog-release-title-input').value,
        summary: document.getElementById('changelog-release-summary-input').value,
        is_published: document.getElementById('changelog-published-input').checked
    } : {
        category: document.getElementById('changelog-item-category-input').value,
        description: document.getElementById('changelog-item-description-input').value,
        audiences: Array.from(document.querySelectorAll('.changelog-audience-check:checked')).map(input => input.value),
        is_published: document.getElementById('changelog-published-input').checked
    };
    const button = document.getElementById('changelog-save-edit-btn');
    button.disabled = true;
    try{
        const response = await fetch(`/api/changelog/admin/${type === 'release' ? 'releases' : 'items'}/${encodeURIComponent(id)}`, {
            method:'PUT', credentials:'same-origin', cache:'no-store',
            headers:{'Content-Type':'application/json','Accept':'application/json','X-CSRFToken':getCSRFToken()},
            body:JSON.stringify(payload)
        });
        const data = await response.json();
        if(!response.ok || !data.success) throw new Error(data.error || 'Unable to save update.');
        bootstrap.Modal.getInstance(document.getElementById('changelogEditModal'))?.hide();
        await loadChangelog();
        if(typeof window.refreshGlobalChangelogBadge === 'function') window.refreshGlobalChangelogBadge();
        showChangelogStatus('Changelog updated.', 'success');
    }catch(error){ showChangelogStatus(error.message || 'Unable to save update.', 'error'); }
    finally{ button.disabled = false; }
}

document.addEventListener('DOMContentLoaded', loadChangelog);

// --- IN-APP AUTHORING -------------------------------------------------------
// The admin API used to be PUT-only, so nothing could be announced without a deploy.

let changelogComposeModal = null;

function openChangelogComposer(){
    if(!changelogIsAdmin) return;
    const modalEl = document.getElementById('changelogComposeModal');
    if(!modalEl || typeof bootstrap === 'undefined') return;

    ['changelog-compose-title', 'changelog-compose-description',
     'changelog-compose-category', 'changelog-compose-schedule'].forEach(id => {
        const el = document.getElementById(id);
        if(el) el.value = '';
    });
    document.querySelectorAll('.changelog-compose-branch').forEach(cb => { cb.checked = false; });
    const minor = document.getElementById('changelog-compose-minor');
    if(minor) minor.checked = false;

    changelogComposeModal = changelogComposeModal || new bootstrap.Modal(modalEl);
    changelogComposeModal.show();
}

async function submitChangelogComposer(){
    const title = (document.getElementById('changelog-compose-title') || {}).value || '';
    const description = (document.getElementById('changelog-compose-description') || {}).value || '';
    if(!title.trim()){ showChangelogStatus('A title is required.', 'error'); return; }
    if(!description.trim()){ showChangelogStatus('Describe what changed.', 'error'); return; }

    const audiences = Array.from(document.querySelectorAll('.changelog-compose-audience:checked')).map(cb => cb.value);
    if(!audiences.length){ showChangelogStatus('Select at least one audience.', 'error'); return; }

    const branches = Array.from(document.querySelectorAll('.changelog-compose-branch:checked')).map(cb => cb.value);
    const schedule = (document.getElementById('changelog-compose-schedule') || {}).value || '';
    const category = (document.getElementById('changelog-compose-category') || {}).value || '';
    const isMinor = !!(document.getElementById('changelog-compose-minor') || {}).checked;

    try{
        const releaseResponse = await fetch('/api/changelog/admin/releases', {
            method:'POST', credentials:'same-origin',
            headers:{'Content-Type':'application/json','Accept':'application/json','X-CSRFToken':getCSRFToken()},
            body: JSON.stringify({title: title.trim(), summary: '', publish_at: schedule})
        });
        const releaseData = await releaseResponse.json();
        if(!releaseResponse.ok || !releaseData.success) throw new Error(releaseData.error || 'Unable to create the update.');

        const releaseId = releaseData.release.id;
        const itemResponse = await fetch(`/api/changelog/admin/releases/${releaseId}/items`, {
            method:'POST', credentials:'same-origin',
            headers:{'Content-Type':'application/json','Accept':'application/json','X-CSRFToken':getCSRFToken()},
            body: JSON.stringify({
                description: description.trim(),
                category: category.trim() || 'General',
                audiences: audiences,
                branches: branches,
                is_minor: isMinor
            })
        });
        const itemData = await itemResponse.json();
        if(!itemResponse.ok || !itemData.success) throw new Error(itemData.error || 'Update created but the detail could not be added.');

        if(changelogComposeModal) changelogComposeModal.hide();
        changelogPage = 1;
        await loadChangelog();
        if(typeof window.refreshGlobalChangelogBadge === 'function') window.refreshGlobalChangelogBadge();
        showChangelogStatus(schedule ? 'Update scheduled.' : 'Update published.', 'success');
    }catch(error){
        showChangelogStatus(error.message || 'Unable to publish the update.', 'error');
    }
}

async function deleteChangelogEntry(){
    const type = (document.getElementById('changelog-edit-type') || {}).value || '';
    const id = (document.getElementById('changelog-edit-id') || {}).value || '';
    if(!type || !id) return;
    if(!window.confirm('Delete this update? This cannot be undone.')) return;

    const url = type === 'release'
        ? `/api/changelog/admin/releases/${encodeURIComponent(id)}`
        : `/api/changelog/admin/items/${encodeURIComponent(id)}`;
    try{
        const response = await fetch(url, {
            method:'DELETE', credentials:'same-origin',
            headers:{'Accept':'application/json','X-CSRFToken':getCSRFToken()}
        });
        const data = await response.json();
        if(!response.ok || !data.success) throw new Error(data.error || 'Unable to delete.');
        const modalEl = document.getElementById('changelogEditModal');
        if(modalEl && typeof bootstrap !== 'undefined'){
            const instance = bootstrap.Modal.getInstance(modalEl);
            if(instance) instance.hide();
        }
        await loadChangelog();
        if(typeof window.refreshGlobalChangelogBadge === 'function') window.refreshGlobalChangelogBadge();
        showChangelogStatus('Update deleted.', 'success');
    }catch(error){ showChangelogStatus(error.message || 'Unable to delete.', 'error'); }
}

async function revertChangelogItem(){
    const id = (document.getElementById('changelog-edit-id') || {}).value || '';
    if(!id) return;
    if(!window.confirm('Restore this update to the wording in releases.json?')) return;
    try{
        const response = await fetch(`/api/changelog/admin/items/${encodeURIComponent(id)}/revert`, {
            method:'POST', credentials:'same-origin',
            headers:{'Accept':'application/json','X-CSRFToken':getCSRFToken()}
        });
        const data = await response.json();
        if(!response.ok || !data.success) throw new Error(data.error || 'Unable to revert.');
        const modalEl = document.getElementById('changelogEditModal');
        if(modalEl && typeof bootstrap !== 'undefined'){
            const instance = bootstrap.Modal.getInstance(modalEl);
            if(instance) instance.hide();
        }
        await loadChangelog();
        showChangelogStatus('Restored to the manifest version.', 'success');
    }catch(error){ showChangelogStatus(error.message || 'Unable to revert.', 'error'); }
}

/* ---------------------------------------------------------------------------
   EMAIL DIGEST
   Preview reaches no mail provider by design. Sending is gated server-side by
   CHANGELOG_DIGEST_ENABLED; the buttons here mirror that state but are not the
   guard - the server refuses with 409 regardless of what this UI allows.
--------------------------------------------------------------------------- */

let changelogDigestModal = null;
let changelogDigestState = {
    sendingEnabled:false, groups:[], testEmail:'', itemCount:0,
    audienceCount:0, missingEmail:[], selectable:[], selectedIds:null
};

function openChangelogDigest(){
    const modalEl = document.getElementById('changelogDigestModal');
    if(!modalEl || typeof bootstrap === 'undefined') return;
    changelogDigestModal = changelogDigestModal || new bootstrap.Modal(modalEl);
    // A fresh selection each time: carrying one over would silently change what a
    // later send contains.
    changelogDigestState.selectedIds = null;
    changelogDigestModal.show();
    refreshChangelogDigestPreview();
}

function changelogDigestMode(){
    const select = document.getElementById('changelog-digest-mode');
    return select ? select.value : 'audience';
}

function updateChangelogDigestMode(){
    const row = document.getElementById('changelog-digest-group-row');
    if(row) row.hidden = changelogDigestMode() !== 'group';
    // Re-render the recipient line too, or it keeps describing the audience while the
    // send would actually go to a group - misleading exactly where it matters most.
    renderChangelogDigestRecipients();
    setChangelogDigestButtons();
}

function selectedChangelogDigestItemIds(){
    // null means "not chosen yet", which the server reads as everything this
    // audience can see. An empty array means the admin deliberately chose nothing.
    if(changelogDigestState.selectedIds === null) return null;
    return changelogDigestState.selectedIds.slice();
}

function renderChangelogDigestPicker(){
    const host = document.getElementById('changelog-digest-picker');
    if(!host) return;

    const items = changelogDigestState.selectable || [];
    if(!items.length){
        host.innerHTML = '<p class="changelog-hint mb-0">Nothing is available for this audience and branch.</p>';
        return;
    }

    const chosen = changelogDigestState.selectedIds;
    const groups = [];
    items.forEach(function(item){
        let group = groups.find(g => g.title === item.release_title && g.date === item.release_date);
        if(!group){
            group = { title:item.release_title, date:item.release_date, items:[] };
            groups.push(group);
        }
        group.items.push(item);
    });

    host.innerHTML = '';
    groups.forEach(function(group){
        const wrapper = document.createElement('div');
        wrapper.className = 'changelog-digest-picker-group';

        const heading = document.createElement('div');
        heading.className = 'changelog-digest-picker-title';
        heading.textContent = group.date + ' - ' + group.title;
        wrapper.appendChild(heading);

        group.items.forEach(function(item){
            const label = document.createElement('label');
            label.className = 'changelog-digest-picker-item';

            const box = document.createElement('input');
            box.type = 'checkbox';
            box.value = String(item.id);
            box.checked = chosen === null || chosen.indexOf(item.id) !== -1;
            box.addEventListener('change', onChangelogDigestItemToggled);

            const text = document.createElement('span');
            text.textContent = item.category + ': ' + item.description;

            label.appendChild(box);
            label.appendChild(text);
            wrapper.appendChild(label);
        });

        host.appendChild(wrapper);
    });
}

function currentChangelogDigestCheckedIds(){
    const host = document.getElementById('changelog-digest-picker');
    if(!host) return [];
    return [...host.querySelectorAll('input[type="checkbox"]')]
        .filter(box => box.checked)
        .map(box => parseInt(box.value, 10))
        .filter(value => !isNaN(value));
}

function onChangelogDigestItemToggled(){
    changelogDigestState.selectedIds = currentChangelogDigestCheckedIds();
    refreshChangelogDigestPreview({ keepSelection:true });
}

function setAllChangelogDigestItems(checked){
    changelogDigestState.selectedIds = checked
        ? (changelogDigestState.selectable || []).map(item => item.id)
        : [];
    refreshChangelogDigestPreview({ keepSelection:true });
}

function selectedChangelogDigestGroup(){
    const groupSelect = document.getElementById('changelog-digest-group');
    const key = groupSelect ? groupSelect.value : '';
    return changelogDigestState.groups.find(group => group.key === key) || null;
}

function setChangelogDigestButtons(){
    const testBtn = document.getElementById('changelog-digest-test-btn');
    const sendBtn = document.getElementById('changelog-digest-send-btn');
    const hasContent = changelogDigestState.itemCount > 0;
    const enabled = changelogDigestState.sendingEnabled;

    let hasRecipients;
    if(changelogDigestMode() === 'group'){
        const selected = selectedChangelogDigestGroup();
        hasRecipients = !!(selected && selected.active_count);
    }else{
        hasRecipients = changelogDigestState.audienceCount > 0;
    }

    if(testBtn) testBtn.disabled = !enabled || !hasContent || !changelogDigestState.testEmail;
    if(sendBtn) sendBtn.disabled = !enabled || !hasContent || !hasRecipients;
}

function renderChangelogDigestRecipients(){
    const box = document.getElementById('changelog-digest-recipients');
    if(!box) return;

    if(changelogDigestMode() === 'group'){
        box.textContent = 'Sending to the selected recipient group.';
        box.className = 'changelog-digest-recipients';
        return;
    }

    const count = changelogDigestState.audienceCount;
    const missing = changelogDigestState.missingEmail || [];
    const audience = (document.getElementById('changelog-digest-audience') || {}).value || 'everyone';

    let text = count
        ? 'This will email ' + count + ' account' + (count === 1 ? '' : 's') + ' in the ' + audience + ' audience.'
        : 'No account in the ' + audience + ' audience has an email address on file.';
    if(missing.length){
        text += ' ' + missing.length + ' account' + (missing.length === 1 ? '' : 's') +
                ' skipped for having no email: ' + missing.slice(0, 6).join(', ') +
                (missing.length > 6 ? ', ...' : '') + '.';
    }

    box.textContent = text;
    box.className = 'changelog-digest-recipients' +
        (count ? '' : ' changelog-digest-recipients-empty') +
        (missing.length ? ' changelog-digest-recipients-warn' : '');
}

function updateChangelogDigestGroupHint(){
    const hint = document.getElementById('changelog-digest-group-hint');
    const selected = selectedChangelogDigestGroup();
    if(hint){
        if(!selected) hint.textContent = ' ';
        else if(!selected.active_count) hint.textContent = 'No active recipients - add them in Settings.';
        else hint.textContent = selected.active_count + ' active recipient' + (selected.active_count === 1 ? '' : 's') + '.';
    }
    setChangelogDigestButtons();
}

async function refreshChangelogDigestPreview(options){
    const keepSelection = !!(options && options.keepSelection);
    const summary = document.getElementById('changelog-digest-summary');
    const preview = document.getElementById('changelog-digest-preview');
    const audience = (document.getElementById('changelog-digest-audience') || {}).value || 'everyone';
    const branch = (document.getElementById('changelog-digest-branch') || {}).value || '';

    // Changing audience or branch changes what is even available, so a selection made
    // against the previous list would be meaningless. Start fresh unless a checkbox
    // was what triggered this.
    if(!keepSelection) changelogDigestState.selectedIds = null;

    if(summary) summary.innerHTML = '<i class="fa-solid fa-circle-notch fa-spin me-2"></i>Rendering preview...';
    if(preview) preview.innerHTML = '';

    try{
        let query = 'audience=' + encodeURIComponent(audience) + '&branch=' + encodeURIComponent(branch);
        const chosen = selectedChangelogDigestItemIds();
        if(chosen !== null) query += '&item_ids=' + encodeURIComponent(chosen.join(','));

        const response = await fetch('/api/changelog/admin/digest/preview?' + query, {
            credentials:'same-origin', headers:{'Accept':'application/json'}
        });
        const data = await response.json();
        if(!response.ok || !data.success) throw new Error(data.error || 'Unable to render the preview.');

        const digest = data.digest || {};
        changelogDigestState.sendingEnabled = !!data.sending_enabled;
        changelogDigestState.groups = data.recipient_groups || [];
        changelogDigestState.testEmail = data.test_email || '';
        changelogDigestState.itemCount = digest.item_count || 0;
        changelogDigestState.selectable = data.selectable_items || [];
        changelogDigestState.audienceCount = data.audience_recipient_count || 0;
        changelogDigestState.missingEmail = data.audience_missing_email || [];

        const banner = document.getElementById('changelog-digest-disabled');
        if(banner) banner.hidden = changelogDigestState.sendingEnabled;

        const groupSelect = document.getElementById('changelog-digest-group');
        if(groupSelect && !groupSelect.options.length){
            changelogDigestState.groups.forEach(function(group){
                const option = document.createElement('option');
                option.value = group.key;
                option.textContent = group.label;
                groupSelect.appendChild(option);
            });
            if(data.default_group) groupSelect.value = data.default_group;
        }

        const target = document.getElementById('changelog-digest-test-target');
        if(target){
            target.textContent = changelogDigestState.testEmail
                ? 'Test goes only to ' + changelogDigestState.testEmail
                : 'No email address on file for your account, so a test cannot be sent.';
        }

        if(summary){
            summary.textContent = digest.item_count
                ? digest.release_count + ' release' + (digest.release_count === 1 ? '' : 's') +
                  ', ' + digest.item_count + ' update' + (digest.item_count === 1 ? '' : 's') +
                  ' - subject: ' + digest.subject
                : 'Nothing to send for this audience and branch.';
        }
        if(preview) preview.innerHTML = digest.html || '<p class="changelog-hint">Nothing to preview.</p>';

        renderChangelogDigestPicker();
        renderChangelogDigestRecipients();
        updateChangelogDigestGroupHint();
    }catch(error){
        if(summary) summary.textContent = error.message || 'Unable to render the preview.';
        changelogDigestState.itemCount = 0;
        setChangelogDigestButtons();
    }
}

async function sendChangelogDigest(testOnly){
    const audience = (document.getElementById('changelog-digest-audience') || {}).value || 'everyone';
    const branch = (document.getElementById('changelog-digest-branch') || {}).value || '';
    const groupSelect = document.getElementById('changelog-digest-group');
    const groupKey = groupSelect ? groupSelect.value : '';
    const mode = changelogDigestMode();
    const updates = changelogDigestState.itemCount;
    const plural = n => n === 1 ? '' : 's';

    if(testOnly){
        if(!window.confirm(
            'Send a test digest to ' + changelogDigestState.testEmail + ' only?\n\n' +
            updates + ' update' + plural(updates) + ' included.'
        )) return;
    }else{
        let who;
        if(mode === 'group'){
            const selected = selectedChangelogDigestGroup();
            const count = selected ? selected.active_count : 0;
            who = count + ' recipient' + plural(count) + ' in "' + (selected ? selected.label : groupKey) + '"';
        }else{
            const count = changelogDigestState.audienceCount;
            who = count + ' account' + plural(count) + ' in the ' + audience + ' audience';
        }
        if(!window.confirm(
            'Send this digest to ' + who + '?\n\n' +
            updates + ' update' + plural(updates) + ' included.\n\n' +
            'This sends real email and cannot be undone.'
        )) return;
    }

    const testBtn = document.getElementById('changelog-digest-test-btn');
    const sendBtn = document.getElementById('changelog-digest-send-btn');
    if(testBtn) testBtn.disabled = true;
    if(sendBtn) sendBtn.disabled = true;

    try{
        const response = await fetch('/api/changelog/admin/digest/send', {
            method:'POST', credentials:'same-origin',
            headers:{'Content-Type':'application/json','Accept':'application/json','X-CSRFToken':getCSRFToken()},
            body: JSON.stringify({
                audience: audience,
                branch: branch,
                recipient_mode: mode,
                recipient_group: mode === 'group' ? groupKey : '',
                item_ids: selectedChangelogDigestItemIds(),
                test_only: !!testOnly
            })
        });
        const data = await response.json();
        if(!response.ok || !data.success) throw new Error(data.error || data.message || 'The digest was not sent.');
        showChangelogStatus(
            testOnly
                ? 'Test digest sent to ' + changelogDigestState.testEmail + '.'
                : 'Digest sent to ' + data.recipients + ' recipient' + plural(data.recipients) +
                  ' (' + data.item_count + ' update' + plural(data.item_count) + ').',
            'success'
        );
    }catch(error){
        showChangelogStatus(error.message || 'The digest was not sent.', 'error');
    }finally{
        setChangelogDigestButtons();
    }
}

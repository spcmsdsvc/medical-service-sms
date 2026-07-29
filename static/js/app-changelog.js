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

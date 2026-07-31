/* Offline schedule creation for field engineers.

   An engineer with no signal adds a schedule from the timeline exactly as they would online.
   It is held in IndexedDB and replayed when signal returns, carrying a creation token so a
   retry cannot create the schedule twice.

   This mirrors the offline TSR queue in templates/offline_tsr.html deliberately: same store
   layout, same retriable-versus-fatal split, same health ping. Two offline systems that look
   alike are easier to reason about than two that were each invented separately.

   No template syntax lives in this file; the timeline passes what it needs in. */
(function () {
    'use strict';

    var DB_NAME = 'medical_service_offline_schedule_db';
    var DB_VERSION = 1;
    var STORES = { queue: 'queue', attachments: 'attachments', reference: 'reference' };

    var PING_URL = '/offline_tsr_sync_ping';
    var SUBMIT_URL = '/add_shift';

    var changeHandlers = [];
    var syncInFlight = null;

    function isSupported() {
        return typeof window !== 'undefined' && 'indexedDB' in window;
    }

    function openDatabase() {
        return new Promise(function (resolve, reject) {
            if (!isSupported()) {
                reject(new Error('This browser cannot store schedules offline.'));
                return;
            }

            var request = indexedDB.open(DB_NAME, DB_VERSION);
            request.onupgradeneeded = function (event) {
                var db = event.target.result;
                if (!db.objectStoreNames.contains(STORES.queue)) {
                    var queue = db.createObjectStore(STORES.queue, { keyPath: 'id' });
                    queue.createIndex('state', 'state', { unique: false });
                    queue.createIndex('queuedAt', 'queuedAt', { unique: false });
                }
                if (!db.objectStoreNames.contains(STORES.attachments)) {
                    var attachments = db.createObjectStore(STORES.attachments, { keyPath: 'id' });
                    attachments.createIndex('ownerId', 'ownerId', { unique: false });
                }
                if (!db.objectStoreNames.contains(STORES.reference)) {
                    db.createObjectStore(STORES.reference, { keyPath: 'key' });
                }
            };
            request.onsuccess = function () { resolve(request.result); };
            request.onerror = function () { reject(request.error || new Error('IndexedDB unavailable.')); };
        });
    }

    function withStore(storeName, mode, worker) {
        return openDatabase().then(function (db) {
            return new Promise(function (resolve, reject) {
                var transaction = db.transaction(storeName, mode);
                var store = transaction.objectStore(storeName);
                var result;
                try {
                    result = worker(store);
                } catch (err) {
                    reject(err);
                    return;
                }
                transaction.oncomplete = function () { resolve(result && result.value !== undefined ? result.value : result); };
                transaction.onerror = function () { reject(transaction.error); };
                transaction.onabort = function () { reject(transaction.error); };
            });
        });
    }

    function requestValue(request) {
        var box = { value: undefined };
        request.onsuccess = function () { box.value = request.result; };
        return box;
    }

    function notifyChanged() {
        changeHandlers.forEach(function (handler) {
            try { handler(); } catch (err) { console.warn('[OfflineSchedule] change handler failed', err); }
        });
    }

    /* ---------------------------------------------------------------------
       Reference data.

       masterClients and masterProducts were fetched fresh on every timeline load and never
       stored, so offline the client and product autocompletes came up empty. That was the
       one thing genuinely blocking the full form from working in the field.
       --------------------------------------------------------------------- */

    function cacheReference(key, rows) {
        // Each list is cached under its own key so a page that only loads one of them cannot
        // blank the others. Engineers matter as much as clients and products here: the mobile
        // Add Schedule button calls loadEngineerList() before opening the form, so without a
        // cached copy the form cannot open at all with no signal.
        if (!isSupported()) return Promise.resolve(false);
        if (!Array.isArray(rows) || !rows.length) {
            // Never overwrite a good cache with an empty one -- a failed fetch would
            // otherwise wipe the device's only copy.
            return Promise.resolve(false);
        }
        return withStore(STORES.reference, 'readwrite', function (store) {
            store.put({ key: key, savedAt: new Date().toISOString(), rows: rows });
        }).then(function () { return true; }).catch(function (err) {
            console.warn('[OfflineSchedule] Unable to cache ' + key, err);
            return false;
        });
    }

    function getCachedList(key) {
        if (!isSupported()) return Promise.resolve([]);
        return withStore(STORES.reference, 'readonly', function (store) {
            return requestValue(store.get(key));
        }).then(function (row) {
            return (row && Array.isArray(row.rows)) ? row.rows : [];
        }).catch(function (err) {
            console.warn('[OfflineSchedule] Unable to read cached ' + key, err);
            return [];
        });
    }

    function getCachedReference() {
        return Promise.all([
            getCachedList('clients'),
            getCachedList('products'),
            getCachedList('engineers')
        ]).then(function (rows) {
            return { clients: rows[0], products: rows[1], engineers: rows[2] };
        });
    }

    /* ---------------------------------------------------------------------
       Conflict pre-check against the cached timeline snapshot.

       Advisory only. The snapshot is as old as the last time this device was online, so the
       server stays the authority -- this exists to catch the obvious clash while the
       engineer can still change it, not to promise there is none.
       --------------------------------------------------------------------- */

    function readSnapshotMaps() {
        var keys = ['timelineOfflineSnapshots', 'medicalServiceTimelineOfflineSnapshotMapV1'];
        var snapshots = [];
        keys.forEach(function (key) {
            try {
                var parsed = JSON.parse(localStorage.getItem(key) || '{}');
                if (parsed && typeof parsed === 'object') {
                    Object.keys(parsed).forEach(function (mapKey) { snapshots.push(parsed[mapKey]); });
                }
            } catch (err) { /* a corrupt snapshot must not block adding a schedule */ }
        });
        ['timelineOfflineSnapshot', 'medicalServiceTimelineOfflineSnapshotV1'].forEach(function (key) {
            try {
                var single = JSON.parse(localStorage.getItem(key) || 'null');
                if (single) snapshots.push(single);
            } catch (err) { /* ignore */ }
        });
        return snapshots;
    }

    function overlaps(startA, endA, startB, endB) {
        if (!startA || !endA || !startB || !endB) return false;
        return startA < endB && endA > startB;
    }

    function findCachedConflict(request) {
        var engineerIds = (request.engineerIds || []).map(String);
        var dates = request.dates || [];
        var startTime = request.startTime || '';
        var endTime = request.endTime || '';
        if (!engineerIds.length || !dates.length || !startTime || !endTime) return null;

        var snapshots = readSnapshotMaps();
        var newestAt = '';

        for (var s = 0; s < snapshots.length; s += 1) {
            var snapshot = snapshots[s];
            var data = (snapshot && snapshot.data) || snapshot;
            if (!data || !data.schedule) continue;
            if (snapshot && snapshot.savedAt && snapshot.savedAt > newestAt) newestAt = snapshot.savedAt;

            for (var e = 0; e < engineerIds.length; e += 1) {
                var dayMap = data.schedule[engineerIds[e]];
                if (!dayMap) continue;

                for (var d = 0; d < dates.length; d += 1) {
                    var rows = dayMap[dates[d]] || [];
                    for (var r = 0; r < rows.length; r += 1) {
                        var row = rows[r];
                        if (!row) continue;
                        if (overlaps(startTime, endTime, row.time_start, row.time_end)) {
                            return {
                                engineerId: engineerIds[e],
                                date: dates[d],
                                time: (row.time_start || '') + ' - ' + (row.time_end || ''),
                                task: row.task || '',
                                clientName: row.client_name || '',
                                snapshotSavedAt: (snapshot && snapshot.savedAt) || ''
                            };
                        }
                    }
                }
            }
        }
        return null;
    }

    function snapshotAgeLabel() {
        var newest = '';
        readSnapshotMaps().forEach(function (snapshot) {
            if (snapshot && snapshot.savedAt && snapshot.savedAt > newest) newest = snapshot.savedAt;
        });
        if (!newest) return '';
        var saved = new Date(newest);
        if (isNaN(saved.getTime())) return '';
        var hours = Math.floor((Date.now() - saved.getTime()) / 3600000);
        if (hours < 1) return 'less than an hour old';
        if (hours < 24) return hours + ' hour' + (hours === 1 ? '' : 's') + ' old';
        var days = Math.floor(hours / 24);
        return days + ' day' + (days === 1 ? '' : 's') + ' old';
    }

    /* ---------------------------------------------------------------------
       Queue.
       --------------------------------------------------------------------- */

    function createToken() {
        // The server requires 16-100 characters of [A-Za-z0-9._:-].
        var random = '';
        try {
            if (window.crypto && typeof window.crypto.randomUUID === 'function') {
                random = window.crypto.randomUUID().replace(/-/g, '');
            }
        } catch (err) { /* fall through */ }
        if (!random) {
            random = String(Date.now()) + '-' + Math.random().toString(36).slice(2) +
                Math.random().toString(36).slice(2);
        }
        return ('sched-' + random).replace(/[^A-Za-z0-9._:-]/g, '').slice(0, 100);
    }

    function serializeFormData(formData) {
        var fields = [];
        var files = [];
        formData.forEach(function (value, key) {
            if (typeof File !== 'undefined' && value instanceof File) {
                files.push({ key: key, name: value.name || 'attachment', type: value.type || '', blob: value });
            } else if (typeof Blob !== 'undefined' && value instanceof Blob) {
                files.push({ key: key, name: 'attachment', type: value.type || '', blob: value });
            } else {
                fields.push([key, String(value)]);
            }
        });
        return { fields: fields, files: files };
    }

    function enqueue(formData, summary) {
        if (!isSupported()) {
            return Promise.reject(new Error('This browser cannot store schedules offline.'));
        }

        var serialized = serializeFormData(formData);
        var token = createToken();
        var id = token;

        // The token travels with the payload so every retry carries the same one.
        serialized.fields = serialized.fields.filter(function (pair) { return pair[0] !== 'creation_token'; });
        serialized.fields.push(['creation_token', token]);

        var item = {
            id: id,
            creationToken: token,
            state: 'queued',
            queuedAt: new Date().toISOString(),
            attempts: 0,
            lastError: '',
            summary: summary || {},
            fields: serialized.fields,
            attachmentCount: serialized.files.length
        };

        return withStore(STORES.queue, 'readwrite', function (store) {
            store.put(item);
        }).then(function () {
            if (!serialized.files.length) return null;
            return withStore(STORES.attachments, 'readwrite', function (store) {
                serialized.files.forEach(function (file, index) {
                    store.put({
                        id: id + '::' + index,
                        ownerId: id,
                        key: file.key,
                        name: file.name,
                        type: file.type,
                        blob: file.blob
                    });
                });
            });
        }).then(function () {
            notifyChanged();
            return item;
        });
    }

    function list() {
        if (!isSupported()) return Promise.resolve([]);
        return withStore(STORES.queue, 'readonly', function (store) {
            return requestValue(store.getAll());
        }).then(function (rows) {
            return (rows || []).sort(function (a, b) {
                return String(a.queuedAt).localeCompare(String(b.queuedAt));
            });
        }).catch(function () { return []; });
    }

    function attachmentsFor(ownerId) {
        return withStore(STORES.attachments, 'readonly', function (store) {
            return requestValue(store.index('ownerId').getAll(ownerId));
        }).catch(function () { return []; });
    }

    function discard(id) {
        return withStore(STORES.queue, 'readwrite', function (store) {
            store.delete(id);
        }).then(function () {
            return attachmentsFor(id);
        }).then(function (rows) {
            if (!rows || !rows.length) return null;
            return withStore(STORES.attachments, 'readwrite', function (store) {
                rows.forEach(function (row) { store.delete(row.id); });
            });
        }).then(function () {
            notifyChanged();
            return true;
        });
    }

    function updateItem(id, changes) {
        return withStore(STORES.queue, 'readwrite', function (store) {
            var getRequest = store.get(id);
            getRequest.onsuccess = function () {
                var current = getRequest.result;
                if (!current) return;
                Object.keys(changes).forEach(function (key) { current[key] = changes[key]; });
                store.put(current);
            };
        }).then(function () { notifyChanged(); });
    }

    function rebuildFormData(item, attachments) {
        var formData = new FormData();
        (item.fields || []).forEach(function (pair) { formData.append(pair[0], pair[1]); });
        (attachments || []).forEach(function (row) {
            try {
                formData.append(row.key, new File([row.blob], row.name || 'attachment',
                    { type: row.type || 'application/octet-stream' }));
            } catch (err) {
                formData.append(row.key, row.blob, row.name || 'attachment');
            }
        });
        return formData;
    }

    /* ---------------------------------------------------------------------
       Sync.

       Retriable means try again unchanged. Fatal means stop and show the engineer, because
       retrying will never succeed on its own -- a conflict is the case that matters, and it
       must not spin forever against a schedule someone else already booked.
       --------------------------------------------------------------------- */

    function classifyResponse(status) {
        if (status === 409) return 'conflict';
        if (status === 400 || status === 403) return 'rejected';
        if (status === 401) return 'session';
        if (status >= 500) return 'retriable';
        return 'retriable';
    }

    function syncQueue(options) {
        var settings = options || {};

        if (syncInFlight) return syncInFlight;

        syncInFlight = (function () {
            var outcome = { synced: 0, parked: 0, remaining: 0, message: '' };

            return list().then(function (items) {
                var pending = items.filter(function (item) { return item.state !== 'conflict' && item.state !== 'rejected'; });
                if (!pending.length) {
                    outcome.remaining = items.length;
                    outcome.message = items.length ? 'Queued schedules need your attention.' : 'Nothing queued.';
                    return outcome;
                }

                if (!navigator.onLine) {
                    outcome.remaining = items.length;
                    outcome.message = 'Still offline. Queued schedules will sync automatically.';
                    return outcome;
                }

                return fetch(PING_URL + '?_=' + Date.now(), { credentials: 'same-origin', cache: 'no-store' })
                    .then(function (response) {
                        if (response.redirected || response.status === 401 || response.status === 403) {
                            throw new Error('Your session expired. Sign in again and the queued schedules will resume safely.');
                        }
                        if (!response.ok) throw new Error('The server did not confirm the connection.');
                        return response.json().catch(function () { return {}; });
                    })
                    .then(function (ping) {
                        var token = (ping && ping.csrf_token) || '';
                        return pending.reduce(function (chain, item) {
                            return chain.then(function () { return sendOne(item, token, outcome); });
                        }, Promise.resolve());
                    })
                    .then(function () {
                        return list();
                    })
                    .then(function (after) {
                        outcome.remaining = after.length;
                        if (!outcome.message) {
                            var parts = [];
                            if (outcome.synced) {
                                parts.push('Synced ' + outcome.synced + ' schedule' + (outcome.synced === 1 ? '' : 's') + '.');
                            }
                            if (outcome.parked) {
                                // Saying "nothing to sync" while quietly parking a rejected
                                // schedule is how a lost day in the field goes unnoticed.
                                parts.push(outcome.parked + ' need' + (outcome.parked === 1 ? 's' : '') + ' your attention.');
                            }
                            outcome.message = parts.length ? parts.join(' ') : 'Nothing to sync.';
                        }
                        return outcome;
                    })
                    .catch(function (error) {
                        outcome.message = error.message || 'Sync could not complete.';
                        return list().then(function (after) {
                            outcome.remaining = after.length;
                            return outcome;
                        });
                    });
            });
        })().then(function (result) {
            syncInFlight = null;
            notifyChanged();
            if (!settings.silent && typeof settings.onDone === 'function') settings.onDone(result);
            return result;
        }).catch(function (error) {
            syncInFlight = null;
            notifyChanged();
            throw error;
        });

        return syncInFlight;
    }

    function sendOne(item, csrfToken, outcome) {
        return attachmentsFor(item.id).then(function (attachments) {
            var body = rebuildFormData(item, attachments);
            var headers = {};
            if (csrfToken) headers['X-CSRFToken'] = csrfToken;

            return fetch(SUBMIT_URL, {
                method: 'POST',
                credentials: 'same-origin',
                headers: headers,
                body: body
            }).then(function (response) {
                if (response.ok) {
                    outcome.synced += 1;
                    return discard(item.id);
                }

                return response.json().catch(function () { return {}; }).then(function (payload) {
                    var kind = classifyResponse(response.status);
                    var message = (payload && payload.message) || 'The server refused this schedule.';

                    if (kind === 'conflict' || kind === 'rejected') {
                        outcome.parked += 1;
                        return updateItem(item.id, {
                            state: kind === 'conflict' ? 'conflict' : 'rejected',
                            lastError: message,
                            conflict: (payload && payload.conflict) || null,
                            attempts: (item.attempts || 0) + 1
                        });
                    }

                    if (kind === 'session') {
                        throw new Error('Your session expired. Sign in again and the queued schedules will resume safely.');
                    }

                    return updateItem(item.id, {
                        lastError: message,
                        attempts: (item.attempts || 0) + 1
                    });
                });
            }).catch(function (error) {
                if (/session expired/i.test(error.message || '')) throw error;
                // Network failure: leave it queued exactly as it is.
                return updateItem(item.id, {
                    lastError: 'Connection failed. This schedule is still queued.',
                    attempts: (item.attempts || 0) + 1
                });
            });
        });
    }

    function onChange(handler) {
        if (typeof handler === 'function') changeHandlers.push(handler);
    }

    window.addEventListener('online', function () {
        syncQueue({ silent: true }).catch(function () { /* reported through the panel */ });
    });

    window.offlineSchedule = {
        isSupported: isSupported,
        cacheReference: cacheReference,
        getCachedList: getCachedList,
        getCachedReference: getCachedReference,
        findCachedConflict: findCachedConflict,
        snapshotAgeLabel: snapshotAgeLabel,
        enqueue: enqueue,
        list: list,
        discard: discard,
        sync: syncQueue,
        onChange: onChange
    };
})();

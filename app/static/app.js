import {Recorder, base64} from './media.js';
import {initExperience, confirmAction} from './experience.js';
const $ = id => document.getElementById(id);
const state = {csrf: '', status: null, page: '', draft: null, items: [], selected: null, read: null, serial: 0, writing: false, pendingWrite: null, camera: null, cameraSerial: 0, audioURL: null, manual: false, reviewing: false};
const recorder = new Recorder(); let recording = false, startingRecording = false;
function say(message = '', error = false) { $('notice').textContent = message; $('notice').classList.toggle('error', error); }
function node(tag, text, cls) { const element = document.createElement(tag); if (text !== undefined) element.textContent = text; if (cls) element.className = cls; return element; }
function date(value) { if (!value) return 'Date unknown'; const d = new Date(value); return Number.isNaN(d.getTime()) ? 'Date unknown' : d.toLocaleString(undefined, {dateStyle: 'medium', timeStyle: 'short'}); }
function errorMessage(e) { if (e.name === 'TypeError' || e.name === 'SyntaxError') return 'The local service did not return a complete result. For a save, retry the same details; otherwise check that the server is running.'; return e.status === 409 ? `${e.message} Reload the record and review it again before confirming.` : e.message; }
async function api(path, {method = 'GET', body, signal, raw = false, keepalive = false, renewed = false} = {}) {
  const headers = {}; if (method !== 'GET') headers['X-CSRF-Token'] = state.csrf;
  if (body !== undefined) headers['Content-Type'] = raw ? body.type : 'application/json';
  let response;
  try { response = await fetch(path, {method, headers, body: body === undefined ? undefined : raw ? body : JSON.stringify(body), signal, keepalive, credentials: 'same-origin'}); }
  catch (error) { if (error.name !== 'AbortError') $('connection-state').textContent = 'Disconnected. Start the local service and try again.'; throw error; }
  if (response.ok && $('connection-state').textContent.startsWith('Disconnected.')) $('connection-state').textContent = 'Connected to this computer.';
  const result = await response.json();
  if (!response.ok && !renewed && path !== '/api/session' && (response.status === 401 || result.error?.code === 'csrf_denied')) { const session = await api('/api/session'); state.csrf = session.csrf_token; return api(path, {method, body, signal, raw, keepalive, renewed:true}); }
  if (!response.ok) { const error = new Error(result.error?.message || 'The local service could not complete this request.'); error.status = response.status; error.code = result.error?.code; throw error; }
  return result;
}
function speechReady() { return !!(state.status?.speech?.provider_enabled && state.status?.speech?.artifacts_present); }
async function refreshStatus() {
  state.status = await api('/api/status'); const enabled = speechReady();
  $('record').disabled = !enabled; $('record').title = enabled ? 'Record a question, then review' : 'Local speech is off; type your question';
  $('speak-reply').disabled = !enabled; if (!enabled) $('speak-reply').checked = false;
  $('speech-state').textContent = enabled ? 'Local speech is ready to try. Review every transcript before sending.' : state.status.speech?.provider_enabled ? 'Speech files are unavailable. You can still type a question.' : 'Local speech is off for this session. You can still type a question.';
  $('connection-state').textContent = `Connected to this computer. ${state.status.item_count} saved ${state.status.item_count === 1 ? 'memory' : 'memories'}.`;
}
function revokeAudio() { if (state.audioURL) URL.revokeObjectURL(state.audioURL); state.audioURL = null; $('answer').querySelectorAll('audio').forEach(a => { a.pause(); a.removeAttribute('src'); a.load(); }); }
async function cancelRead() { state.serial++; const work = state.read; state.read = null; work?.controller.abort(); if (work?.id) api(`/api/requests/${work.id}/cancel`, {method: 'POST'}).catch(() => {}); await recorder.cancel(); recording = startingRecording = false; $('stop-record').hidden = true; $('record').hidden = false; $('ask').disabled = false; $('ask').hidden = false; $('cancel-talk').hidden = true; revokeAudio(); }
async function read(path, body) { const serial = ++state.serial, controller = new AbortController(); const id = body?.request_id; state.read = {controller, id}; try { const value = await api(path, {method: body ? 'POST' : 'GET', body, signal: controller.signal}); if (serial !== state.serial) return null; return value; } finally { if (serial === state.serial) state.read = null; } }
function lockWrites(locked) { state.writing = locked; document.body.classList.toggle('busy-write', locked); document.querySelectorAll('#capture button,#capture input,#capture select,#detail button,#detail input').forEach(e => e.disabled = locked || (!!state.pendingWrite && e.tagName !== 'BUTTON')); $('save-memory').disabled = locked || !$('confirm-save').checked; }
// A failed transport retains the exact payload and idempotency key in memory.
async function write(path, fields, method = 'POST') {
  if (state.writing) return null;
  const fingerprint = JSON.stringify({path, method, fields});
  if (state.pendingWrite && fingerprint !== state.pendingWrite.fingerprint) throw new Error('The previous save has an uncertain result. Retry those same details first, or reload and inspect Saved before making another change.');
  const work = state.pendingWrite || {path, method, fingerprint, body: {...fields, confirmed: true, write_epoch: state.status.write_epoch, idempotency_key: crypto.randomUUID()}};
  state.pendingWrite = work; lockWrites(true);
  try { const result = await api(path, {method, body: work.body}); state.pendingWrite = null; chatReset(); return result; }
  catch (error) { if (error.status && error.status < 500) state.pendingWrite = null; throw error; }
  finally { lockWrites(false); }
}
function sourceLabel(observation) { if (observation?.provenance === 'user_report') return 'Your update'; if (observation?.provenance === 'photo_confirmed') return observation.photo?.source === 'camera' ? 'Confirmed camera photo' : 'Confirmed imported photo'; return 'Source unknown'; }
function evidence(item, detail = false) {
  const card = node('article', undefined, 'card'), current = item.current_observation;
  if (current?.photo?.available) { const img = node('img'); img.src = current.photo.url; img.alt = `Saved photo of ${item.personal_name}`; img.loading = 'lazy'; img.onerror = () => { img.replaceWith(node('span', 'Photo unavailable', 'meta')); }; card.append(img); }
  card.append(node(detail ? 'h2' : 'h3', item.personal_name));
  card.append(node('p', item.location ? `${item.location_label}: ${item.location}` : 'Location unknown', 'record-place'));
  card.append(node('p', `${date(current?.confirmed_at)}`, 'meta'));
  if (item.distinguishing_note) card.append(node('p', item.distinguishing_note, 'meta'));
  card.append(node('p', `${sourceLabel(current)}. ${item.freshness === 'needs_recheck' ? 'Needs a recheck. ' : ''}Not a live location.`, 'meta evidence-date'));
  if (current?.photo && detail) card.append(node('p', `Photo date: ${date(current.photo.captured_at)}. Saved ${date(current.photo.recorded_at)}.`, 'meta'));
  if (!detail) { const button = node('button', 'Review record'); button.type = 'button'; button.onclick = () => showDetail(item.id); card.append(button); }
  return card;
}
function renderRecall(result) {
  const area = $('answer'); area.replaceChildren(); const recall = result.recall || result; const knownUnknown = recall.kind === 'unknown' && recall.items?.length > 0;
  area.append(node('p', 'Nook', 'response-label'));
  area.append(node('h2', recall.kind === 'clarify' ? 'Which item did you mean?' : recall.kind === 'unknown' ? (knownUnknown ? 'The item is saved. Its location is unknown.' : 'No matching memory yet.') : 'Here is your last record.'));
  if (knownUnknown) area.append(node('p', 'Review the history for past clues, or update the record when you find it.', 'muted'));
  if (recall.kind === 'unknown' && !knownUnknown) area.append(node('p', 'Try the name or alias you saved. An unsaved item cannot be located from these records.', 'muted'));
  if (recall.kind === 'clarify') area.append(node('p', 'More than one record matches. Review the names and evidence before choosing.', 'muted'));
  const cards = node('div', undefined, 'cards'); (recall.items || []).forEach(item => cards.append(evidence(item))); area.append(cards);
  if (result.reply_text) area.append(node('p', result.reply_text));
  const speech = result.speech;
  if (speech?.audio_base64) { const bytes = Uint8Array.from(atob(speech.audio_base64), c => c.charCodeAt(0)); state.audioURL = URL.createObjectURL(new Blob([bytes], {type: speech.content_type || 'audio/wav'})); const audio = node('audio'); audio.controls = true; audio.src = state.audioURL; audio.setAttribute('aria-label', 'Play spoken reply'); area.append(audio); }
  else if ($('speak-reply').checked) { $('speak-reply').checked = false; area.append(node('p', 'A spoken reply was unavailable. Your written result is shown above. Typing is ready for your next question.', 'hint')); }
}
function chatReset() { $('answer').replaceChildren(); $('user-question').hidden = true; $('chat-welcome').hidden = false; }
async function ask(event) {
  event.preventDefault(); if ($('ask').disabled) return;
  const utterance = $('utterance').value.trim().replace(/\s+/g, ' '); if (!utterance) return;
  await cancelRead(); $('chat-welcome').hidden = true; $('user-question').textContent = utterance; $('user-question').hidden = false;
  $('ask').disabled = true; $('ask').hidden = true; $('cancel-talk').hidden = false;
  $('answer').replaceChildren(node('p', 'Looking through your memories…', 'thinking')); say();
  try {
    const spoken = $('speak-reply').checked;
    const result = await read(spoken ? '/api/speech/turns' : '/api/recall', spoken ? {request_id: crypto.randomUUID(), utterance, transcript_confirmed: true} : {request_id: crypto.randomUUID(), query: utterance, use_inference: false});
    if (result) { renderRecall(result); $('utterance').value = ''; say(); }
  } catch (e) { if (e.name !== 'AbortError') { $('speak-reply').checked = false; $('answer').replaceChildren(node('h2', "Couldn't reach your memories."), node('p', !e.status ? 'The local service is unavailable. Start it on this computer, then try your question again.' : errorMessage(e), 'muted')); const retry = node('button', 'Try question again', 'secondary'); retry.onclick = () => { $('utterance').value = utterance; $('talk-form').requestSubmit(); }; $('answer').append(retry); } }
  finally { if (!state.read) { $('ask').disabled = false; $('ask').hidden = false; $('cancel-talk').hidden = true; if (state.page === 'talk' && !$('detail').open && $('onboarding').hidden) $('utterance').focus({preventScroll:true}); } }
}
async function stopRecording() { if (!recording) return; recording = false; $('stop-record').hidden = true; $('record').hidden = false; $('record').disabled = true; $('ask').disabled = true; try { const serial = state.serial; const bytes = await recorder.stop(); if (serial !== state.serial) return; say('Transcribing locally. You will review the words before asking.'); const result = await read('/api/speech/transcribe', {request_id: crypto.randomUUID(), audio: {content_type: 'audio/wav', data_base64: base64(bytes)}, language_hint: 'auto'}); if (result) { $('utterance').value = result.transcript; $('utterance').focus(); say('Review and edit the transcript, then choose Send question.'); } } catch (e) { if (e.name !== 'AbortError') say(errorMessage(e), true); } finally { $('record').disabled = !speechReady(); $('ask').disabled = false; if (!state.read) $('cancel-talk').hidden = true; } }
$('record').onclick = async () => { if (startingRecording || recording) return; await cancelRead(); startingRecording = true; $('record').disabled = true; $('cancel-talk').hidden = false; say('Waiting for microphone permission. You can cancel or type instead.'); try { const started = await recorder.start(stopRecording); if (!started) return; startingRecording = false; recording = true; $('record').hidden = true; $('stop-record').hidden = false; $('ask').disabled = true; say('Recording · up to 10 seconds. Choose Stop & review when you finish.'); } catch (e) { say(`Microphone unavailable: ${e.message} You can type instead.`, true); } finally { startingRecording = false; $('record').disabled = !speechReady(); if (!recording && !state.read) $('cancel-talk').hidden = true; } };
$('stop-record').onclick = stopRecording;
$('cancel-talk').onclick = async () => { await cancelRead(); $('utterance').value = ''; $('answer').replaceChildren(node('p', 'Stopped. Your question was not saved.', 'muted')); say(); };
$('talk-form').onsubmit = ask;
$('utterance').addEventListener('keydown', event => { if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) { event.preventDefault(); if (!$('ask').disabled) $('talk-form').requestSubmit(); } });
document.querySelectorAll('[data-question]').forEach(button => button.onclick = () => { $('utterance').value = button.dataset.question; $('utterance').focus(); });
function stopCamera() { state.cameraSerial++; state.camera?.getTracks().forEach(t => t.stop()); state.camera = null; $('camera').srcObject = null; $('camera-area').hidden = true; $('camera-start').disabled = false; }
$('camera-start').onclick = async () => { if (state.writing) return; stopCamera(); const serial = state.cameraSerial; $('camera-start').disabled = true; say('Waiting for camera permission. Only the frame you choose will be uploaded.'); try { const stream = await navigator.mediaDevices.getUserMedia({video: {facingMode: 'environment'}, audio: false}); if (serial !== state.cameraSerial) { stream.getTracks().forEach(t => t.stop()); return; } state.camera = stream; $('camera').srcObject = stream; $('camera-area').hidden = false; await $('camera').play(); say('Camera is on. Choose one frame or close the camera.'); } catch (e) { stopCamera(); say(`Camera unavailable: ${e.message} Choose a photo file instead.`, true); } };
$('camera-stop').onclick = () => { stopCamera(); say('Camera closed.'); };
$('take-photo').onclick = async () => { const serial = state.cameraSerial; const video = $('camera'); if (!video.videoWidth) return say('Camera is not ready yet.', true); const canvas = document.createElement('canvas'); const scale = Math.min(1, 2048 / Math.max(video.videoWidth, video.videoHeight)); canvas.width = video.videoWidth * scale; canvas.height = video.videoHeight * scale; canvas.getContext('2d').drawImage(video, 0, 0, canvas.width, canvas.height); const blob = await new Promise(resolve => canvas.toBlob(resolve, 'image/jpeg', .9)); if (serial !== state.cameraSerial) return; stopCamera(); if (blob) await upload(blob, 'camera'); };
function captureStage(stage) { document.querySelectorAll('[data-stage]').forEach(el => { if (el.dataset.stage === stage) el.setAttribute('aria-current', 'step'); else el.removeAttribute('aria-current'); }); }
function resetCapture() { state.draft = null; state.manual = false; state.reviewing = false; sessionStorage.removeItem('pendingCapture'); $('draft').hidden = true; $('review').hidden = true; $('capture-start').hidden = false; $('draft-photo').removeAttribute('src'); $('capture-form').reset(); $('item-name').readOnly = false; $('photo-file').value = ''; $('confirm-save').checked = false; $('save-memory').disabled = true; $('save-error').textContent = ''; captureStage('choose'); }
async function discard() { if (state.draft) await api(`/api/captures/${state.draft.id}`, {method:'DELETE'}); resetCapture(); }
$('manual-start').onclick = () => { if (state.writing || state.pendingWrite) return; state.manual = true; $('capture-start').hidden = true; $('draft').hidden = false; $('draft-figure').hidden = true; $('identity-field').hidden = true; $('current-option').hidden = true; $('identity').replaceChildren(new Option('A new item', 'new')); $('capture-form').reset(); $('item-name').readOnly = false; captureStage('details'); $('item-name').focus(); };

async function upload(blob, source) { if (state.writing) return; stopCamera(); if (blob.size > 10 * 1024 * 1024) return say('Choose a photo smaller than 10 MB.', true); lockWrites(true); try { await discard(); say('Preparing your photo for review…'); const draft = await api(`/api/captures?source=${source}`, {method: 'POST', body: blob, raw: true}); state.draft = draft; sessionStorage.setItem('pendingCapture', draft.id); $('draft-photo').src = draft.photo_url; $('draft-source').textContent = `${source === 'camera' ? 'Camera frame' : 'Imported photo'} · Photo date: ${date(draft.captured_at)} · Recorded ${date(draft.recorded_at)}`; const result = await api('/api/items?limit=50'); state.items = result.items; while (state.items.length < result.total) { const next = await api(`/api/items?limit=50&offset=${state.items.length}`); if (!next.items.length) break; state.items.push(...next.items); } $('identity').replaceChildren(new Option('A new item', 'new')); state.items.forEach(item => $('identity').add(new Option(item.personal_name, item.id))); $('draft').hidden = false; $('draft-figure').hidden = false; $('identity-field').hidden = false; $('current-option').hidden = false; $('capture-start').hidden = true; captureStage('details'); say('Photo ready. No item has been saved.'); } catch (e) { say(errorMessage(e), true); } finally { lockWrites(false); } }
$('photo-file').onchange = () => { const file = $('photo-file').files[0]; if (file) upload(file, 'import'); };
$('identity').onchange = () => { const item = state.items.find(i => i.id === $('identity').value); $('item-name').value = item?.personal_name || ''; $('item-name').readOnly = !!item; $('confirm-save').checked = false; };
$('discard').onclick = async () => { if (state.writing || state.pendingWrite) return say('Resolve the pending save before discarding this photo.', true); try { await discard(); say('Photo discarded.'); } catch (e) { say(errorMessage(e), true); } };
$('capture-form').onsubmit = event => {
  event.preventDefault(); if (state.writing || (!state.draft && !state.manual)) return;
  const name = $('item-name').value.trim(), location = $('item-location').value.trim();
  if (!name || !location) return say('Add an item name and a place before reviewing.', true);
  say(); state.reviewing = true; $('draft').hidden = true; $('review').hidden = false; $('confirm-save').checked = false; $('save-memory').disabled = true;
  const summary = $('review-summary'); summary.replaceChildren();
  if (state.draft) { const photo = node('img'); photo.src = state.draft.photo_url; photo.alt = `Photo to save for ${name}`; summary.append(photo); }
  summary.append(node('h3', name), node('p', location), node('p', $('make-current').checked || state.manual ? 'Will become the last recorded place.' : 'History only. The current place will stay unchanged.', 'meta'));
  captureStage('review'); $('main').scrollTop = 0; $('review-title').focus({preventScroll:true});
};
$('confirm-save').onchange = () => { $('save-memory').disabled = !$('confirm-save').checked || state.writing; };
$('back-to-details').onclick = () => { if (state.writing || state.pendingWrite) return say('Retry the pending save before editing its details.', true); state.reviewing = false; $('review').hidden = true; $('draft').hidden = false; $('save-error').textContent = ''; captureStage('details'); };
$('save-memory').onclick = async () => {
  if (state.writing || (!state.draft && !state.manual) || !$('confirm-save').checked) return;
  const existing = state.items.find(i => i.id === $('identity').value);
  const row = existing ? {identity:'existing', item_id:existing.id, expected_revision:existing.revision, personal_name:existing.personal_name} : {identity:'new', personal_name:$('item-name').value.trim()};
  $('save-error').textContent = '';
  try {
    const result = state.manual
      ? await write('/api/items', {personal_name:$('item-name').value.trim(), location:$('item-location').value.trim()})
      : await write(`/api/captures/${state.draft.id}/commit`, {rows:[row], location:$('item-location').value.trim(), make_current:$('make-current').checked});
    if (!result) return;
    resetCapture(); say('Memory saved. A little less to keep in your head.');
    await refreshStatus(); location.hash = 'saved';
  } catch(e) { $('save-error').textContent = errorMessage(e); }
};

async function loadSaved(more = false) {
  const offset = more ? $('saved-list').querySelectorAll('.card').length : 0;
  try {
    if (!more) { $('saved-list').replaceChildren(node('div', undefined, 'skeleton'), node('div', undefined, 'skeleton')); $('saved-list').setAttribute('aria-busy','true'); }
    const result = await read(`/api/items?limit=20&offset=${offset}${$('search').value.trim() ? '&query=' + encodeURIComponent($('search').value.trim()) : ''}`);
    if (!result) return;
    if (!more) $('saved-list').replaceChildren();
    $('saved-count').textContent = `${result.total} ${result.total === 1 ? 'memory' : 'memories'}${$('search').value.trim() ? ' found' : ', a little less to remember'}.`;
    if (!result.total) { const empty = node('div', undefined, 'empty'); empty.append(node('h2', $('search').value.trim() ? 'No memories by that name.' : 'Your next little discovery starts here.'), node('p', $('search').value.trim() ? 'Try another name or alias.' : 'Save a photo or write down an item and its place. Nook will keep the clue for later.')); if (!$('search').value.trim()) { const add = node('a', 'Save your first memory'); add.href = '#capture'; empty.append(add); } $('saved-list').append(empty); }
    result.items.forEach(item => $('saved-list').append(evidence(item))); $('load-more').hidden = offset + result.items.length >= result.total;
  } catch(e) { if (e.name !== 'AbortError') { if (!more) $('saved-list').replaceChildren(); say(errorMessage(e), true); const retry = node('button','Try loading memories again'); retry.onclick = () => loadSaved(); $('saved-list').append(retry); } }
  finally { $('saved-list').removeAttribute('aria-busy'); }
}

$('search-form').onsubmit = event => { event.preventDefault(); cancelRead().then(() => loadSaved()); };
$('load-more').onclick = () => { $('load-more').disabled = true; loadSaved(true).finally(() => $('load-more').disabled = false); };
async function showDetail(id) { try { await cancelRead(); const item = await read(`/api/items/${id}`); if (!item) return; state.selected = item; const area = $('detail-content'); area.replaceChildren(); const title = node('h1', item.personal_name); title.id = 'detail-title'; title.tabIndex = -1; area.append(title, evidence(item, true));
  const form = node('form'); const label = node('label', 'Update the last recorded place'); label.htmlFor = 'new-location'; const input = node('input'); input.id = 'new-location'; input.maxLength = 240; input.required = true; input.placeholder = 'Where you last saw it'; const hint = node('p', 'Your update will be dated and kept in the history. The old photo stays historical.', 'hint'); const save = node('button', 'Confirm location update', 'primary'); save.type = 'submit'; const unknown = node('button', 'Mark moved / unknown'); unknown.type = 'button'; form.append(label, input, hint, save, unknown); area.append(form);
  async function update(location) { try { const result = await write(`/api/items/${item.id}/observations`, {expected_revision: item.revision, location}); if (result) { say('Record updated. Previous evidence remains in history.'); await refreshStatus(); await showDetail(item.id); if (state.page === 'saved') await loadSaved(); } } catch (e) { detailError(errorMessage(e)); } }
  form.onsubmit = e => { e.preventDefault(); update(input.value.trim()); }; unknown.onclick = async () => { if (await confirmAction({title:'Not where you left it?', message:`Mark the current location of “${item.personal_name}” as unknown. Its history will stay available.`, action:'Mark location unknown', cancel:'Keep current place'})) update(null); };
  const metadata = node('details'); metadata.append(node('summary', 'Edit name and aliases'));
  const metadataForm = node('form', undefined, 'detail-name-form');
  function field(id, labelText, value, maxLength) { const label = node('label', labelText); label.htmlFor = id; const input = node('input'); input.id = id; input.value = value; input.maxLength = maxLength; metadataForm.append(label, input); return input; }
  const nameInput = field('edit-name', 'Item name', item.personal_name, 80); nameInput.required = true;
  const aliasesInput = field('edit-aliases', 'Other names, separated by commas', (item.aliases || []).join(', '), 800);
  const noteInput = field('edit-note', 'A detail to help you recognize it', item.distinguishing_note || '', 240);
  const saveDetails = node('button', 'Save item details', 'primary'); saveDetails.type = 'submit'; metadataForm.append(saveDetails);
  metadataForm.onsubmit = async event => { event.preventDefault(); try { const aliases = aliasesInput.value.split(',').map(v => v.trim()).filter(Boolean); const result = await write(`/api/items/${item.id}`, {expected_revision:item.revision, personal_name:nameInput.value.trim(), aliases, distinguishing_note:noteInput.value.trim()}, 'PATCH'); if (result) { await refreshStatus(); await showDetail(item.id); if (state.page === 'saved') await loadSaved(); say('Memory details updated.'); } } catch(e) { detailError(errorMessage(e)); } };
  metadata.append(metadataForm); area.append(metadata);
  const history = node('div', undefined, 'history'); history.append(node('h2', 'Recorded history')); item.observations.forEach(observation => { const section = node('section'); section.append(node('p', `${observation.location || 'Location unknown'} · ${date(observation.confirmed_at)}`), node('p', `${sourceLabel(observation)} · Historical evidence; does not verify current location.`, 'hint')); if (observation.photo?.available) { const img = node('img'); img.src = observation.photo.url; img.alt = `Historical photo for ${item.personal_name}`; img.loading = 'lazy'; section.append(img); } history.append(section); }); area.append(history);
  const remove = node('button', 'Delete this memory', 'danger'); remove.type = 'button'; remove.onclick = async () => { try { if (!(state.pendingWrite?.path === `/api/items/${item.id}` && state.pendingWrite.method === 'DELETE')) await api(`/api/items/${item.id}/deletion-preview`); if (!await confirmAction({title:'Let this memory go?', message:`Delete “${item.personal_name}” and its history? This cannot be undone. Photos shared with other memories will stay.`, action:'Delete memory'})) return; const result = await write(`/api/items/${item.id}`, {expected_revision: item.revision, evidence_scope: 'unreferenced'}, 'DELETE'); if (result) { $('detail').close(); state.selected = null; await refreshStatus(); await loadSaved(); say('Memory deleted. Photos used by other memories are retained.'); } } catch (e) { detailError(errorMessage(e)); } }; area.append(remove); if (!$('detail').open) $('detail').showModal(); else title.focus({preventScroll:true});
  } catch (e) { if (e.name !== 'AbortError') say(errorMessage(e), true); } }
function detailError(message) { let notice = $('detail-error'); if (!notice) { notice = node('p', undefined, 'notice error'); notice.id = 'detail-error'; notice.setAttribute('role', 'alert'); $('detail-content').prepend(notice); } notice.textContent = message; }
$('close-detail').onclick = () => { if (state.pendingWrite) return detailError('Retry the pending change before closing, or reload and inspect Saved to resolve its outcome.'); if (!state.writing) $('detail').close(); };
$('detail').addEventListener('cancel', event => { if (state.writing || state.pendingWrite) event.preventDefault(); });
$('detail').addEventListener('keydown', event => { if (event.key !== 'Tab') return; const controls = [...$('detail').querySelectorAll('button,input,select,textarea,a[href],summary')].filter(e => !e.disabled && e.offsetParent !== null); if (!controls.length) { event.preventDefault(); return; } const first = controls[0], last = controls.at(-1); if (event.shiftKey && (document.activeElement === first || document.activeElement === $('detail'))) { event.preventDefault(); last.focus(); } else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); } });
async function navigate() { const target = ['talk', 'capture', 'saved'].includes(location.hash.slice(1)) ? location.hash.slice(1) : 'talk'; if (state.writing || state.pendingWrite) { history.replaceState(null, '', `#${state.page || 'talk'}`); say('Finish or retry the pending save before leaving this screen.', true); return; } if (state.page === target) return; if (state.draft || state.manual) { if (!await confirmAction({title:'Leave this memory unfinished?', message:'Your unsaved details and photo will be discarded.', action:'Discard and leave', cancel:'Keep editing'})) { history.replaceState(null, '', '#capture'); return; } try { await discard(); } catch (e) { history.replaceState(null, '', '#capture'); return say('The draft could not be discarded. Stay here and retry Discard photo.', true); } } const mediaWasActive = recording || startingRecording || !!state.camera; await cancelRead(); stopCamera(); if (mediaWasActive) say('Recording and camera stopped. No conversation was saved.'); else if (target !== 'saved') say(); $('detail').close(); $('utterance').value = ''; chatReset(); state.page = target; for (const page of ['talk', 'capture', 'saved']) $(page).hidden = page !== target; document.querySelectorAll('nav a').forEach(a => a.toggleAttribute('aria-current', false)); document.querySelector(`nav a[data-page="${target}"]`).setAttribute('aria-current', 'page'); if (target === 'saved') await loadSaved(); $('main').scrollTop = 0; if ($('onboarding').hidden) $('main').focus({preventScroll: true}); }
addEventListener('hashchange', navigate);
addEventListener('beforeunload', event => { if (state.writing || state.pendingWrite) { event.preventDefault(); event.returnValue = ''; } });
addEventListener('pagehide', () => { recorder.cancel(); stopCamera(); revokeAudio(); if (state.read?.id) api(`/api/requests/${state.read.id}/cancel`, {method: 'POST', keepalive: true}).catch(() => {}); });
document.addEventListener('visibilitychange', () => { if (document.hidden) { const active = recording || startingRecording || !!state.camera || !!state.read; cancelRead(); stopCamera(); if (active) say('Paused because you left this tab. Start again when you are ready.'); } });
async function start() { try { const session = await api('/api/session'); state.csrf = session.csrf_token; await refreshStatus(); const abandoned = sessionStorage.getItem('pendingCapture'); if (abandoned && /^[0-9a-f-]{36}$/.test(abandoned)) { try { await api(`/api/captures/${abandoned}`, {method: 'DELETE'}); sessionStorage.removeItem('pendingCapture'); say('The unfinished photo from your previous visit was discarded.'); } catch (e) { if (e.status === 404) sessionStorage.removeItem('pendingCapture'); else throw e; } } await navigate(); } catch (e) { $('connection-state').textContent = 'Disconnected. Start the local service and reload.'; say(`Cannot connect to your local memories. ${errorMessage(e)} Reload to try again.`, true); } }
initExperience({canReplay: () => { if (state.writing || state.pendingWrite || state.draft || state.manual) { $('connection-state').textContent = 'Finish or discard your current memory before replaying the introduction.'; return false; } return true; }, beforeReplay: async () => { await cancelRead(); stopCamera(); }});
start();

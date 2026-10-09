import {Recorder, base64} from './media.js';
import {initExperience, confirmAction} from './experience.js';
import {initPlaces} from './places.js';
import {parseMemoryPrompt} from './memory-prompt.js';
const $ = id => document.getElementById(id);
const state = {chatContext: null, proposal: null, csrf: '', status: null, page: '', draft: null, items: [], selected: null, read: null, serial: 0, writing: false, pendingWrite: null, camera: null, cameraSerial: 0, audioURL: null};
const recorder = new Recorder(); let recording = false, startingRecording = false;
function say(message = '', error = false) { $('notice').textContent = message; $('notice').classList.toggle('error', error); }
function node(tag, text, cls) { const element = document.createElement(tag); if (text !== undefined) element.textContent = text; if (cls) element.className = cls; return element; }
function date(value) { if (!value) return 'Date unknown'; const d = new Date(value); return Number.isNaN(d.getTime()) ? 'Date unknown' : d.toLocaleString(undefined, {dateStyle: 'medium', timeStyle: 'short'}); }
function errorMessage(e) { if (e.name === 'TypeError' || e.name === 'SyntaxError') return 'The local service did not return a complete result. For a save, retry the same details; otherwise check that the server is running.'; return e.status === 409 ? `${e.message} Reload the record and review it again before confirming.` : e.message; }
async function api(path, {method = 'GET', body, signal, raw = false, keepalive = false, renewed = false, timeoutMs = 35000, deadline = Date.now() + timeoutMs} = {}) {
  const headers = {}; if (method !== 'GET') headers['X-CSRF-Token'] = state.csrf;
  if (body !== undefined) headers['Content-Type'] = raw ? body.type : 'application/json';
  const controller = new AbortController(); let timedOut = false;
  const cancelled = () => controller.abort();
  if (signal?.aborted) cancelled(); else signal?.addEventListener('abort', cancelled, {once:true});
  const timer = setTimeout(() => { timedOut = true; controller.abort(); }, Math.max(1, deadline - Date.now()));
  try {
    const response = await fetch(path, {method, headers, body: body === undefined ? undefined : raw ? body : JSON.stringify(body), signal:controller.signal, keepalive, credentials:'same-origin'});
    const result = await response.json();
    if (response.ok && $('connection-state').textContent.startsWith('Disconnected.')) $('connection-state').textContent = 'Connected to this computer.';
    if (!response.ok && !renewed && path !== '/api/session' && (response.status === 401 || result.error?.code === 'csrf_denied')) {
      const session = await api('/api/session', {signal, deadline}); state.csrf = session.csrf_token;
      return await api(path, {method, body, signal, raw, keepalive, renewed:true, deadline});
    }
    if (!response.ok) { const error = new Error(result.error?.message || 'The local service could not complete this request.'); error.status = response.status; error.code = result.error?.code; throw error; }
    return result;
  } catch (error) {
    if (timedOut && !signal?.aborted) { const timeout = new Error('The local service took too long to reply. You can try again.'); timeout.code = 'request_timeout'; throw timeout; }
    if (error.name !== 'AbortError' && !error.status) $('connection-state').textContent = 'Disconnected. Start the local service and try again.';
    throw error;
  } finally { clearTimeout(timer); signal?.removeEventListener('abort', cancelled); }
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
async function cancelRead() { if (state.proposal && !state.pendingWrite) { const id = state.proposal.proposal_id; state.proposal = null; api(`/api/actions/${id}`, {method:'DELETE'}).catch(() => {}); } state.serial++; const work = state.read; state.read = null; work?.controller.abort(); if (work?.id) api(`/api/requests/${work.id}/cancel`, {method: 'POST'}).catch(() => {}); await recorder.cancel(); recording = startingRecording = false; $('stop-record').hidden = true; $('record').hidden = false; $('ask').disabled = false; $('ask').hidden = false; $('cancel-talk').hidden = true; revokeAudio(); }
async function read(path, body) { const serial = ++state.serial, controller = new AbortController(); const id = body?.request_id; state.read = {controller, id}; try { const value = await api(path, {method: body ? 'POST' : 'GET', body, signal: controller.signal, timeoutMs:path === '/api/chat' ? (state.status?.chat?.enabled ? 35000 : 10000) : path === '/api/actions/preview' ? 10000 : 35000}); if (serial !== state.serial) return null; return value; } finally { if (serial === state.serial) state.read = null; } }
function lockWrites(locked) {
  state.writing = locked; document.body.classList.toggle('busy-write', locked);
  document.querySelectorAll('#capture button,#capture input,#capture select,#capture textarea,#detail button,#detail input,#delete-data-form button,#delete-data-form input,#answer button,#talk-form textarea').forEach(e => {
    e.disabled = locked || (!!state.pendingWrite && (e.closest('#capture') ? e.id !== 'send-memory' : e.tagName !== 'BUTTON'));
  });
  $('ask').disabled = locked || !!state.pendingWrite; $('record').disabled = locked || !!state.pendingWrite || !speechReady();
  $('add-photo-item').disabled = locked || !!state.pendingWrite || $('extra-items').children.length >= 4;
  $('item-location').disabled = locked || !!state.pendingWrite || (!state.draft && $('manual-unknown').checked);
  $('send-memory').textContent = locked ? 'Saving…' : state.pendingWrite ? 'Retry save ↑' : 'Send ↑';
}
// A failed transport retains the exact payload and idempotency key in memory.
async function write(path, fields, method = 'POST', identity = {}) {
  if (state.writing) return null;
  const fingerprint = JSON.stringify({path, method, fields, identity});
  if (state.pendingWrite && fingerprint !== state.pendingWrite.fingerprint) throw new Error('The previous save has an uncertain result. Retry those same details first, or reload and inspect Saved before making another change.');
  const work = state.pendingWrite || {path, method, fingerprint, body: {...fields, confirmed: true, write_epoch: state.status.write_epoch, idempotency_key: crypto.randomUUID(), ...identity}};
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
  if (item.category) card.append(node('p',`Category: ${item.category}`,'meta'));
  if (current?.review_after) card.append(node('p',`Recheck after ${date(current.review_after)}`,'meta'));
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
function renderChat(result) {
  state.chatContext = result.context_id || null;
  if (result.kind === 'generated') {
    $('answer').replaceChildren(node('p','Nook · generated reply','response-label'), node('p',result.reply_text), node('p','This is general conversation, not a saved personal record. Recent context expires after five minutes.','hint'));
    const reset = node('button','Start a new conversation','secondary'); reset.type='button'; reset.onclick=()=>{ chatReset(); $('utterance').value=''; $('utterance').focus(); }; $('answer').append(reset);
    return;
  }
  if (['greeting','help','unsupported'].includes(result.kind)) {
    $('answer').replaceChildren(node('p','Nook','response-label'), node('p',result.reply_text));
    if (result.kind !== 'greeting') { const remember=node('a','Open Remember'); remember.href='#capture'; $('answer').append(remember); }
  } else renderRecall(result);
}
function clearChatContext() { const id=state.chatContext; state.chatContext=null; if(id) api('/api/chat',{method:'DELETE',body:{request_id:crypto.randomUUID(),context_id:id}}).catch(()=>{}); }
function chatReset() { clearChatContext(); state.proposal = null; $('answer').replaceChildren(); $('user-question').hidden = true; $('chat-welcome').hidden = false; }
function renderProposal(result) {
  const area = $('answer'); area.replaceChildren(node('p','Nook','response-label'));
  if (result.kind !== 'proposal') {
    area.append(node('h2',result.kind === 'clarify' ? 'Choose a unique record first.' : 'No change proposed.'), node('p',result.reason));
    for (const item of result.items || []) area.append(node('p',`${item.personal_name} · ${item.location || 'Location unknown'}`));
    area.append(node('p','Supported commands use quoted names:', 'hint'));
    for (const example of result.examples || []) area.append(node('p',example,'hint'));
    return;
  }
  state.proposal = result;
  area.append(node('h2','Review this change'),node('p','Only your approval saves this record change. This is a bounded command, not general chat.','hint'));
  const table=node('table'); const head=node('tr'); ['Field','Before','After'].forEach(t=>head.append(node('th',t)));table.append(head);
  const value = v => v === null || v === undefined ? 'None' : Array.isArray(v) ? (v.join(', ') || 'None') : String(v);
  for (const [key,label] of [['personal_name','Name'],['location','Last recorded location'],['category','Category'],['aliases','Aliases'],['distinguishing_note','Note']]) {
    const row=node('tr');row.append(node('th',label),node('td',result.before ? value(result.before[key]) : 'New record'),node('td',value(result.after[key])));table.append(row);
  }
  area.append(table,node('p',result.effect,'hint'));
  const approve=node('button','Approve this change');approve.id='approve-proposal';
  const cancel=node('button','Cancel proposal','secondary');cancel.id='cancel-proposal';
  const feedback=node('p','','hint');feedback.setAttribute('role','status');
  approve.onclick=async()=>{if(state.writing)return;try {const saved=await write(`/api/actions/${result.proposal_id}/approve`,{},'POST',{idempotency_key:result.idempotency_key,write_epoch:result.write_epoch});if(!saved)return;area.replaceChildren(node('h2','Change saved.'),...saved.items.map(i=>evidence(i)));await refreshStatus();}catch(e){feedback.textContent=errorMessage(e);approve.textContent=state.pendingWrite?'Retry approval':'Approval unavailable';approve.disabled=!state.pendingWrite;cancel.disabled=!!state.pendingWrite;}};
  cancel.onclick=async()=>{if(state.writing||state.pendingWrite)return;await cancelRead();area.replaceChildren(node('p','Proposal cancelled. No record change was requested.'));};
  area.append(approve,cancel,feedback);
}
async function ask(event) {
  event.preventDefault(); if ($('ask').disabled || state.writing) return; if(state.pendingWrite) {say('Retry the pending approval or save before sending another request.',true);return;}
  const utterance = $('utterance').value.trim().replace(/\s+/g, ' ');
  if (!utterance) { await cancelRead(); $('chat-welcome').hidden=true; $('user-question').hidden=true; $('answer').replaceChildren(node('p','Nook','response-label'),node('h2','What would you like to find?'),node('p','Type a message or an item name, such as “Where are my keys?”.')); $('utterance').focus(); return; }
  await cancelRead(); $('chat-welcome').hidden = true; $('user-question').textContent = utterance; $('user-question').hidden = false;
  $('ask').disabled = true; $('ask').hidden = true; $('cancel-talk').hidden = false;
  $('answer').replaceChildren(node('p', state.status?.chat?.enabled ? 'Preparing your reply…' : 'Looking through your memories…', 'thinking')); say();
  try {
    if (/^(remember|move|rename|categorize|mark)\b/i.test(utterance)) { const result = await read('/api/actions/preview',{utterance}); if(result) {renderProposal(result);$('utterance').value='';} return; }
    const spoken = $('speak-reply').checked;
    const result = await read(spoken ? '/api/speech/turns' : '/api/chat', spoken ? {request_id: crypto.randomUUID(), utterance, transcript_confirmed: true} : {request_id: crypto.randomUUID(), query: utterance, ...(state.chatContext ? {context_id:state.chatContext} : {})});
    if (result) { renderChat(result); $('utterance').value = ''; say(); }
  } catch (e) { if (e.name !== 'AbortError') { clearChatContext(); $('speak-reply').checked = false; $('answer').replaceChildren(node('h2', e.code === 'request_timeout' ? 'That took too long.' : "Couldn't reach your memories."), node('p', e.code === 'request_timeout' ? e.message : !e.status ? 'The local service is unavailable. Start it on this computer, then try your question again.' : errorMessage(e), 'muted')); const retry = node('button', 'Try question again', 'secondary'); retry.onclick = () => { $('utterance').value = utterance; $('talk-form').requestSubmit(); }; $('answer').append(retry); } }
  finally { if (!state.read) { $('ask').disabled = false; $('ask').hidden = false; $('cancel-talk').hidden = true; if (state.page === 'talk' && !$('detail').open && $('onboarding').hidden) $('utterance').focus({preventScroll:true}); } }
}
async function stopRecording() { if (!recording) return; recording = false; $('stop-record').hidden = true; $('record').hidden = false; $('record').disabled = true; $('ask').disabled = true; try { const serial = state.serial; const bytes = await recorder.stop(); if (serial !== state.serial) return; say('Transcribing locally. You will review the words before asking.'); const result = await read('/api/speech/transcribe', {request_id: crypto.randomUUID(), audio: {content_type: 'audio/wav', data_base64: base64(bytes)}, language_hint: 'auto'}); if (result) { $('utterance').value = result.transcript; $('utterance').focus(); say('Review and edit the transcript, then choose Send question.'); } } catch (e) { if (e.name !== 'AbortError') say(errorMessage(e), true); } finally { $('record').disabled = !speechReady(); $('ask').disabled = false; if (!state.read) $('cancel-talk').hidden = true; } }
$('record').onclick = async () => { if (startingRecording || recording || state.writing || state.pendingWrite) return; await cancelRead(); startingRecording = true; $('record').disabled = true; $('cancel-talk').hidden = false; say('Waiting for microphone permission. You can cancel or type instead.'); try { const started = await recorder.start(stopRecording); if (!started) return; startingRecording = false; recording = true; $('record').hidden = true; $('stop-record').hidden = false; $('ask').disabled = true; say('Recording · up to 10 seconds. Choose Stop & review when you finish.'); } catch (e) { say(`Microphone unavailable: ${e.message} You can type instead.`, true); } finally { startingRecording = false; $('record').disabled = !speechReady(); if (!recording && !state.read) $('cancel-talk').hidden = true; } };
$('stop-record').onclick = stopRecording;
$('cancel-talk').onclick = async () => { await cancelRead(); clearChatContext(); $('utterance').value = ''; $('answer').replaceChildren(node('p', 'Stopped. Your question was not saved.', 'muted')); say(); };
$('talk-form').onsubmit = ask;
$('utterance').addEventListener('keydown', event => { if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) { event.preventDefault(); if (!$('ask').disabled) $('talk-form').requestSubmit(); } });
document.querySelectorAll('[data-question]').forEach(button => button.onclick = () => { $('utterance').value = button.dataset.question; $('utterance').focus(); });
function stopCamera() { state.cameraSerial++; state.camera?.getTracks().forEach(t => t.stop()); state.camera = null; $('camera').srcObject = null; $('camera-area').hidden = true; $('camera-start').disabled = false; }
$('camera-start').onclick = async () => { if (state.writing || state.pendingWrite) return; stopCamera(); const serial = state.cameraSerial; $('camera-start').disabled = true; say('Waiting for camera permission. Only the frame you choose will be uploaded.'); try { const stream = await navigator.mediaDevices.getUserMedia({video: {facingMode: 'environment'}, audio: false}); if (serial !== state.cameraSerial) { stream.getTracks().forEach(t => t.stop()); return; } state.camera = stream; $('camera').srcObject = stream; $('camera-area').hidden = false; await $('camera').play(); say('Camera is on. Choose one frame or close the camera.'); } catch (e) { stopCamera(); say(`Camera unavailable: ${e.message} Choose a photo file instead.`, true); } };
$('camera-stop').onclick = () => { stopCamera(); say('Camera closed.'); };
$('take-photo').onclick = async () => { const serial = state.cameraSerial; const video = $('camera'); if (!video.videoWidth) return say('Camera is not ready yet.', true); const canvas = document.createElement('canvas'); const scale = Math.min(1, 2048 / Math.max(video.videoWidth, video.videoHeight)); canvas.width = video.videoWidth * scale; canvas.height = video.videoHeight * scale; canvas.getContext('2d').drawImage(video, 0, 0, canvas.width, canvas.height); const blob = await new Promise(resolve => canvas.toBlob(resolve, 'image/jpeg', .9)); if (serial !== state.cameraSerial) return; stopCamera(); if (blob) await upload(blob, 'camera'); };
function hasCaptureInput() { return !!(state.draft || $('memory-prompt').value.trim() || $('item-name').value.trim() || $('item-location').value.trim()); }
function resetCapture() {
  state.draft = null; sessionStorage.removeItem('pendingCapture'); $('extra-items').replaceChildren(); $('photo-extras').hidden = true; $('photo-extras').open = false; $('manual-unknown-option').hidden = false; $('item-location').disabled = false; $('add-photo-item').disabled = false;
  $('remember-form').reset(); $('photo-attachment').hidden = true; $('draft-photo').removeAttribute('src');
  $('item-name').readOnly = false; $('identity').replaceChildren(new Option('A new item','new'));
  $('identity-field').hidden = true; $('current-option').hidden = true; $('memory-details').open = false;
  $('remember-success').hidden = true; $('remember-error').textContent = ''; $('memory-preview').hidden = true;
  $('discard').hidden = true; $('send-memory').textContent = 'Send ↑';
}
async function discard() { if (state.draft) await api(`/api/captures/${state.draft.id}`, {method:'DELETE'}); resetCapture(); }
function updateMemoryPreview() {
  const name = $('item-name').value.trim(), place = $('item-location').value.trim();
  $('memory-preview').hidden = !name || (!place && !(!$('manual-unknown-option').hidden && $('manual-unknown').checked));
  $('preview-name').textContent = name + ($('extra-items').children.length ? ` + ${$('extra-items').children.length} additional reviewed item(s)` : ''); $('preview-location').textContent = !state.draft && $('manual-unknown').checked ? 'Location unknown' : place;
  $('discard').hidden = !hasCaptureInput();
}
$('memory-prompt').oninput = () => {
  const parsed = parseMemoryPrompt($('memory-prompt').value);
  const existing = state.items.find(item => item.id === $('identity').value);
  $('item-name').value = existing?.personal_name || parsed.name; $('item-location').value = parsed.location;
  $('remember-error').textContent = ''; $('remember-success').hidden = true; updateMemoryPreview();
};
for (const id of ['item-name','item-location']) $(id).oninput = () => { $('remember-error').textContent = ''; $('remember-success').hidden = true; updateMemoryPreview(); };
$('edit-memory-details').onclick = () => { $('memory-details').open = true; $('item-name').focus(); };
$('choose-photo').onclick = () => { if (!state.writing && !state.pendingWrite) $('photo-file').click(); };
async function upload(blob, source) {
  if (state.writing || state.pendingWrite) return;
  stopCamera();
  if (blob.size > 10 * 1024 * 1024) { $('remember-error').textContent = 'Choose a photo smaller than 10 MB.'; return; }
  if (!['image/jpeg','image/png','image/webp'].includes(blob.type)) { $('remember-error').textContent = 'Choose a JPEG, PNG or WebP photo.'; return; }
  lockWrites(true); $('send-memory').textContent = 'Attaching…'; $('remember-error').textContent = ''; $('remember-success').hidden = true;
  try {
    if (state.draft) { await api(`/api/captures/${state.draft.id}`, {method:'DELETE'}); state.draft = null; $('extra-items').replaceChildren(); $('photo-extras').hidden = true; $('manual-unknown-option').hidden = false; sessionStorage.removeItem('pendingCapture'); $('photo-attachment').hidden = true; }
    const draft = await api(`/api/captures?source=${source}`, {method:'POST', body:blob, raw:true});
    state.draft = draft; $('photo-extras').hidden = false; $('manual-unknown-option').hidden = true; $('manual-unknown').checked = false; sessionStorage.setItem('pendingCapture',draft.id);
    $('draft-photo').src = draft.photo_url; $('draft-source').textContent = source === 'camera' ? 'Camera frame · ready to send' : 'Ready to send';
    $('photo-attachment').hidden = false; $('current-option').hidden = false;
    // Linking an existing item is optional. Listing failure must not lose an attached photo.
    try {
      const result = await api('/api/items?limit=50'); state.items = result.items;
      while (state.items.length < result.total) { const next = await api(`/api/items?limit=50&offset=${state.items.length}`); if (!next.items.length) break; state.items.push(...next.items); }
      const chosen = $('identity').value;
      $('identity').replaceChildren(new Option('A new item','new')); state.items.forEach(item => $('identity').add(new Option(item.personal_name,item.id)));
      $('identity').value = state.items.some(item => item.id === chosen) ? chosen : 'new'; $('identity-field').hidden = !state.items.length;
    } catch { $('identity-field').hidden = true; $('identity').value = 'new'; $('item-name').readOnly = false; }
    say('Photo attached. Add your message, then Send to save.');
  } catch(e) { $('remember-error').textContent = errorMessage(e); }
  finally { lockWrites(false); updateMemoryPreview(); }
}
$('photo-file').onchange = () => { const file = $('photo-file').files[0]; if (file) upload(file,'import'); $('photo-file').value = ''; };
$('identity').onchange = () => { const item = state.items.find(i => i.id === $('identity').value); $('item-name').value = item?.personal_name || parseMemoryPrompt($('memory-prompt').value).name; $('item-name').readOnly = !!item; updateMemoryPreview(); };
$('remove-photo').onclick = async () => {
  if (state.writing || state.pendingWrite) return;
  lockWrites(true);
  try { if (state.draft) await api(`/api/captures/${state.draft.id}`,{method:'DELETE'}); state.draft = null; $('extra-items').replaceChildren(); $('photo-extras').hidden = true; $('manual-unknown-option').hidden = false; sessionStorage.removeItem('pendingCapture'); $('photo-attachment').hidden = true; $('draft-photo').removeAttribute('src'); $('identity').value = 'new'; $('item-name').readOnly = false; $('identity-field').hidden = true; $('current-option').hidden = true; say('Photo removed. Your message is still here.'); }
  catch(e) { $('remember-error').textContent = errorMessage(e); }
  finally { lockWrites(false); updateMemoryPreview(); }
};
$('discard').onclick = async () => {
  if (state.writing || state.pendingWrite) return say('Retry the pending save before discarding this memory.',true);
  lockWrites(true); try { await discard(); say('Draft discarded.'); } catch(e) { $('remember-error').textContent = errorMessage(e); } finally { lockWrites(false); }
};
$('manual-unknown').onchange = () => { $('item-location').disabled = $('manual-unknown').checked; updateMemoryPreview(); };
function manualLocation() { return !state.draft && $('manual-unknown').checked ? null : $('item-location').value.trim(); }
function recheckDays(input) { const value = input.value.trim(); if (!value) return null; const days = Number(value); if (!Number.isInteger(days) || days < 1 || days > 3650) throw new Error('Choose a whole number of days from 1 to 3650.'); return days; }
function photoRegion(container) { const values = ['x','y','w','h'].map(k => container.querySelector('.region-' + k).value.trim()); if (values.every(v => !v)) return null; if (values.some(v => !v)) throw new Error('Fill all four photo-area values or leave them all empty.'); const [x,y,w,h] = values.map(Number); if (![x,y,w,h].every(Number.isFinite) || x < 0 || y < 0 || w <= 0 || h <= 0 || x + w > 100 || y + h > 100) throw new Error('The highlighted area must fit inside the photo.'); return {x:x/100,y:y/100,w:w/100,h:h/100}; }
function rowFrom(identity, name, region) { const item = state.items.find(i => i.id === identity); if (!name.trim()) throw new Error('Name every item before reviewing.'); return item ? {identity:'existing',item_id:item.id,expected_revision:item.revision,personal_name:item.personal_name,region} : {identity:'new',personal_name:name.trim(),region}; }
function reviewedRows() { const rows = [rowFrom($('identity').value,$('item-name').value,photoRegion($('first-region')))]; $('extra-items').querySelectorAll('.extra-item').forEach(group => rows.push(rowFrom(group.querySelector('select').value,group.querySelector('.extra-name').value,photoRegion(group)))); const ids=rows.filter(r=>r.identity==='existing').map(r=>r.item_id); if (new Set(ids).size !== ids.length) throw new Error('Choose each existing item only once in this photo.'); if (rows.length > 5) throw new Error('A photo supports up to five reviewed items.'); return rows; }
$('add-photo-item').onclick = () => { if (!state.draft || state.writing || state.pendingWrite || $('extra-items').children.length >= 4) return; const group=node('fieldset',undefined,'extra-item'); group.append(node('legend','Another item in this photo')); const identity=node('select'); identity.setAttribute('aria-label','Save additional item to'); identity.add(new Option('A new item','new')); state.items.forEach(item=>identity.add(new Option(item.personal_name,item.id))); const name=node('input'); name.className='extra-name'; name.maxLength=80; name.required=true; name.setAttribute('aria-label','Additional item name'); name.placeholder='Item name'; identity.onchange=()=>{const item=state.items.find(i=>i.id===identity.value);name.value=item?.personal_name||'';name.readOnly=!!item;};group.append(identity,name); const details=node('details');details.append(node('summary','Optional area inside the photo')); for(const [key,labelText] of [['x','Left'],['y','Top'],['w','Width'],['h','Height']]) {const label=node('label',labelText+' (%)'),input=node('input');input.type='number';input.step='0.1';input.min=['w','h'].includes(key)?'0.1':'0';input.max='100';input.className='region-'+key;label.append(input);details.append(label);} const remove=node('button','Remove this extra item','text-button');remove.type='button';remove.onclick=()=>{if(state.pendingWrite||state.writing)return;group.remove();$('add-photo-item').disabled=false;updateMemoryPreview();};group.append(details,remove);$('extra-items').append(group);$('add-photo-item').disabled=$('extra-items').children.length>=4;name.oninput=updateMemoryPreview;updateMemoryPreview();name.focus(); };

$('remember-form').onsubmit = async event => {
  event.preventDefault(); if (state.writing) return;
  const name = $('item-name').value.trim(), place = $('item-location').value.trim();
  if (!name || (!place && !(!state.draft && $('manual-unknown').checked))) {
    $('remember-error').textContent = !name && !place ? 'Add the item and its place below so I can remember them correctly.' : !name ? 'What is the item called? Add its name below.' : 'Where did you leave it? Add its place below.';
    $('memory-details').open = true; (!name ? $('item-name') : $('item-location')).focus(); return;
  }
  if (!state.status) { $('remember-error').textContent = 'Connect to the local service and reload before saving.'; return; }
  $('remember-error').textContent = ''; stopCamera();
  const existing = state.items.find(item => item.id === $('identity').value);
  const note = $('memory-prompt').value.trim().replace(/\s+/g,' ');
  let rows, days; try { rows = state.draft ? reviewedRows() : null; days = recheckDays($('review-days')); if(rows && !existing) rows[0].distinguishing_note = note; } catch(e) { $('remember-error').textContent=e.message; $('memory-details').open=true; return; }
  let result;
  try {
    // Tapping Send explicitly confirms the visible message, photo and parsed details.
    result = state.draft
      ? await write(`/api/captures/${state.draft.id}/commit`, {rows, location:place, review_after_days:days, make_current:$('make-current').checked})
      : await write('/api/items', {personal_name:name, location:manualLocation(), distinguishing_note:note, review_after_days:days});
  } catch(e) { $('remember-error').textContent = errorMessage(e); return; }
  if (!result) return;
  const saved = result.items[0]; resetCapture(); say();
  $('remember-success-copy').textContent = `${saved.personal_name}${result.items.length > 1 ? ` + ${result.items.length-1} more` : ''} · ${saved.location || 'Location unknown'}`;
  $('remember-success').hidden = false; $('view-saved-memory').onclick = () => showDetail(saved.id);
  $('memory-prompt').focus({preventScroll:true}); $('main').scrollTop = 0;
  // Saving already succeeded: a failed status refresh must never invite a duplicate save.
  try { await refreshStatus(); } catch { say('Memory saved. The connection status could not refresh.'); }
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
  const form = node('form'); const label = node('label', 'Update the last recorded place'); label.htmlFor = 'new-location'; const input = node('input'); input.id = 'new-location'; input.maxLength = 240; input.required = true; input.placeholder = 'Where you last saw it'; const daysLabel = node('label','Recheck after (optional days)'); daysLabel.htmlFor='new-review-days'; const daysInput=node('input');daysInput.id='new-review-days';daysInput.type='number';daysInput.min='1';daysInput.max='3650';daysInput.step='1'; const hint = node('p', 'Your update will be dated and kept in the history. The old photo stays historical.', 'hint'); const save = node('button', 'Confirm location update', 'primary'); save.type = 'submit'; const unknown = node('button', 'Mark moved / unknown'); unknown.type = 'button'; form.append(label, input, daysLabel, daysInput, hint, save, unknown); area.append(form);
  async function update(location) { try { const result = await write(`/api/items/${item.id}/observations`, {expected_revision: item.revision, location, review_after_days:recheckDays(daysInput)}); if (result) { say('Record updated. Previous evidence remains in history.'); await refreshStatus(); await showDetail(item.id); if (state.page === 'saved') await loadSaved(); } } catch (e) { detailError(errorMessage(e)); } }
  form.onsubmit = e => { e.preventDefault(); update(input.value.trim()); }; unknown.onclick = async () => { if (await confirmAction({title:'Not where you left it?', message:`Mark the current location of “${item.personal_name}” as unknown. Its history will stay available.`, action:'Mark location unknown', cancel:'Keep current place'})) update(null); };
  const metadata = node('details'); metadata.append(node('summary', 'Edit name and aliases'));
  const metadataForm = node('form', undefined, 'detail-name-form');
  function field(id, labelText, value, maxLength) { const label = node('label', labelText); label.htmlFor = id; const input = node('input'); input.id = id; input.value = value; input.maxLength = maxLength; metadataForm.append(label, input); return input; }
  const nameInput = field('edit-name', 'Item name', item.personal_name, 80); nameInput.required = true;
  const aliasesInput = field('edit-aliases', 'Other names, separated by commas', (item.aliases || []).join(', '), 800);
  const noteInput = field('edit-note', 'A detail to help you recognize it', item.distinguishing_note || '', 240);
  const categoryInput = field('edit-category','Category (optional)',item.category || '',80);
  const saveDetails = node('button', 'Save item details', 'primary'); saveDetails.type = 'submit'; metadataForm.append(saveDetails);
  metadataForm.onsubmit = async event => { event.preventDefault(); try { const aliases = aliasesInput.value.split(',').map(v => v.trim()).filter(Boolean); const result = await write(`/api/items/${item.id}`, {expected_revision:item.revision, personal_name:nameInput.value.trim(), aliases, distinguishing_note:noteInput.value.trim(), category:categoryInput.value.trim()||null}, 'PATCH'); if (result) { await refreshStatus(); await showDetail(item.id); if (state.page === 'saved') await loadSaved(); say('Memory details updated.'); } } catch(e) { detailError(errorMessage(e)); } };
  metadata.append(metadataForm); area.append(metadata);
  const history = node('div', undefined, 'history'); history.append(node('h2', 'Recorded history')); item.observations.forEach(observation => { const section = node('section'); section.append(node('p', `${observation.location || 'Location unknown'} · ${date(observation.confirmed_at)}`), node('p', `${sourceLabel(observation)} · Historical evidence; does not verify current location.`, 'hint')); if (observation.photo?.available) { const img = node('img'); img.src = observation.photo.url; img.alt = `Historical photo for ${item.personal_name}`; img.loading = 'lazy'; section.append(img); } history.append(section); }); area.append(history);
  const remove = node('button', 'Delete this memory', 'danger'); remove.type = 'button'; remove.onclick = async () => { try { if (!(state.pendingWrite?.path === `/api/items/${item.id}` && state.pendingWrite.method === 'DELETE')) await api(`/api/items/${item.id}/deletion-preview`); if (!await confirmAction({title:'Let this memory go?', message:`Delete “${item.personal_name}” and its history? This cannot be undone. Photos shared with other memories will stay.`, action:'Delete memory'})) return; const result = await write(`/api/items/${item.id}`, {expected_revision: item.revision, evidence_scope: 'unreferenced'}, 'DELETE'); if (result) { $('detail').close(); state.selected = null; await refreshStatus(); await loadSaved(); say('Memory deleted. Photos used by other memories are retained.'); } } catch (e) { detailError(errorMessage(e)); } }; area.append(remove); if (!$('detail').open) $('detail').showModal(); else title.focus({preventScroll:true});
  } catch (e) { if (e.name !== 'AbortError') say(errorMessage(e), true); } }
function detailError(message) { let notice = $('detail-error'); if (!notice) { notice = node('p', undefined, 'notice error'); notice.id = 'detail-error'; notice.setAttribute('role', 'alert'); $('detail-content').prepend(notice); } notice.textContent = message; }
$('close-detail').onclick = () => { if (state.pendingWrite) return detailError('Retry the pending change before closing, or reload and inspect Saved to resolve its outcome.'); if (!state.writing) $('detail').close(); };
$('detail').addEventListener('cancel', event => { if (state.writing || state.pendingWrite) event.preventDefault(); });
$('detail').addEventListener('keydown', event => { if (event.key !== 'Tab') return; const controls = [...$('detail').querySelectorAll('button,input,select,textarea,a[href],summary')].filter(e => !e.disabled && e.offsetParent !== null); if (!controls.length) { event.preventDefault(); return; } const first = controls[0], last = controls.at(-1); if (event.shiftKey && (document.activeElement === first || document.activeElement === $('detail'))) { event.preventDefault(); last.focus(); } else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); } });
async function navigate() { const target = ['talk', 'capture', 'saved'].includes(location.hash.slice(1)) ? location.hash.slice(1) : 'talk'; if (state.writing || state.pendingWrite) { history.replaceState(null, '', `#${state.page || 'talk'}`); say('Finish or retry the pending save before leaving this screen.', true); return; } if (state.page === target) return; if (hasCaptureInput()) { if (!await confirmAction({title:'Leave this memory unfinished?', message:'Your unsaved details and photo will be discarded.', action:'Discard and leave', cancel:'Keep editing'})) { history.replaceState(null, '', '#capture'); return; } try { await discard(); } catch (e) { history.replaceState(null, '', '#capture'); return say('The draft could not be discarded. Stay here and retry Discard photo.', true); } } const mediaWasActive = recording || startingRecording || !!state.camera; await cancelRead(); stopCamera(); if (mediaWasActive) say('Recording and camera stopped. No conversation was saved.'); else if (target !== 'saved') say(); $('detail').close(); $('utterance').value = ''; chatReset(); state.page = target; for (const page of ['talk', 'capture', 'saved']) $(page).hidden = page !== target; document.querySelectorAll('nav a').forEach(a => a.toggleAttribute('aria-current', false)); document.querySelector(`nav a[data-page="${target}"]`).setAttribute('aria-current', 'page'); if (target === 'saved') await loadSaved(); $('main').scrollTop = 0; if ($('onboarding').hidden) $('main').focus({preventScroll: true}); }
addEventListener('hashchange', navigate);
addEventListener('beforeunload', event => { if (state.writing || state.pendingWrite || hasCaptureInput()) { event.preventDefault(); event.returnValue = ''; } });
addEventListener('pagehide', () => { recorder.cancel(); stopCamera(); revokeAudio(); if (state.read?.id) api(`/api/requests/${state.read.id}/cancel`, {method: 'POST', keepalive: true}).catch(() => {}); });
document.addEventListener('visibilitychange', () => { if (document.hidden) { const active = recording || startingRecording || !!state.camera || !!state.read; cancelRead(); stopCamera(); if (active) say('Paused because you left this tab. Start again when you are ready.'); } });
async function start() { try { const session = await api('/api/session'); state.csrf = session.csrf_token; await refreshStatus(); const abandoned = sessionStorage.getItem('pendingCapture'); if (abandoned && /^[0-9a-f-]{36}$/.test(abandoned)) { try { await api(`/api/captures/${abandoned}`, {method: 'DELETE'}); sessionStorage.removeItem('pendingCapture'); say('The unfinished photo from your previous visit was discarded.'); } catch (e) { if (e.status === 404) sessionStorage.removeItem('pendingCapture'); else throw e; } } await navigate(); } catch (e) { $('connection-state').textContent = 'Disconnected. Start the local service and reload.'; say(`Cannot connect to your local memories. ${errorMessage(e)} Reload to try again.`, true); } }
$('delete-data-form').onsubmit = async event => { event.preventDefault(); const error=$('delete-data-error'); error.textContent=''; if(state.writing)return; if(state.pendingWrite && state.pendingWrite.path!=='/api/data') {error.textContent='Resolve the pending memory change before deleting all data.';return;} if($('delete-data-phrase').value!=='DELETE ALL LOCAL DATA') {error.textContent='Type the exact confirmation phrase.';return;} try { if(!state.pendingWrite) await refreshStatus(); const generation=state.pendingWrite?.body.expected_generation ?? state.status.generation; if(!await confirmAction({title:'Delete every local memory?',message:'All saved items, history, photos, unfinished drafts and local places cache will be removed. This cannot be undone.',action:'Delete all local data',cancel:'Keep my data'}))return; const result=await write('/api/data',{confirmation:'DELETE ALL LOCAL DATA',expected_generation:generation},'DELETE'); if(!result)return; await cancelRead();stopCamera();resetCapture();state.items=[];state.selected=null;$('detail').close();$('delete-data-phrase').value='';$('search').value='';await refreshStatus();$('settings').close();if(state.page==='saved')await loadSaved();else location.hash='saved';say('All local memories and cached places deleted. Model files remain installed.'); } catch(e) {error.textContent=errorMessage(e);} };
initExperience({canCloseSettings: () => { if(state.pendingWrite?.path==='/api/data'||state.writing) {$('delete-data-error').textContent='Retry the pending deletion before closing, or reload and inspect Saved to resolve its outcome.';return false;}return true;}, canReplay: () => { if (state.writing || state.pendingWrite || hasCaptureInput()) { $('connection-state').textContent = 'Finish or discard your current memory before replaying the introduction.'; return false; } return true; }, beforeReplay: async () => { await cancelRead(); stopCamera(); }});
initPlaces({api, canOpen: () => { if(state.writing||state.pendingWrite) {say('Resolve the pending memory change first.',true);return false;}return true;}, beforeOpen: async () => {await cancelRead();stopCamera();}});
start();

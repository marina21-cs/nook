const $ = id => document.getElementById(id);
function preference(key, value) { try { if (value === undefined) return localStorage.getItem(key); localStorage.setItem(key, value); } catch { /* Preferences are optional; blocked storage never prevents use. */ } }
export function initExperience({canReplay, beforeReplay, canCloseSettings}) {
  const appearance = preference('nook.appearance') || 'system';
  function theme(value) { if (value === 'system') delete document.documentElement.dataset.theme; else document.documentElement.dataset.theme = value; }
  $('appearance').value = appearance; theme(appearance);
  $('appearance').onchange = () => { theme($('appearance').value); preference('nook.appearance', $('appearance').value); };
  const reduceMotion = matchMedia('(prefers-reduced-motion: reduce)');
  let timers = [], leaving = false, step = -1;
  let name = (preference('nook.profileName') || '').slice(0,40);
  const screens = ['setup-profile','setup-introduction','setup-ready'];
  const titles = ['setup-title','setup-intro-title','setup-ready-title'];
  const mascot = document.querySelector('.welcome-character .mascot').cloneNode(true);
  mascot.querySelector('linearGradient').id = 'rello-setup';
  mascot.querySelector('path').setAttribute('fill','url(#rello-setup)');
  $('setup-character').append(mascot);
  function personalize() {
    $('talk-title').replaceChildren(document.createTextNode(name ? `Hey, ${name}.` : "Hey, I'm Nook."), document.createElement('br'), document.createTextNode('What are we finding?'));
    $('profile-summary').textContent = name ? `${name}’s space in Nook.` : 'Your space in Nook.';
  }
  personalize();
  $('reduce-motion').checked = preference('nook.reduceMotion') === '1';
  function motionPreference() { if ($('reduce-motion').checked) document.documentElement.dataset.motion = 'reduce'; else delete document.documentElement.dataset.motion; }
  motionPreference();
  const motionReduced = () => reduceMotion.matches || $('reduce-motion').checked;
  $('reduce-motion').onchange = () => { preference('nook.reduceMotion', $('reduce-motion').checked ? '1' : '0'); motionPreference(); };
  function clearSequence() { timers.forEach(clearTimeout); timers = []; }
  function highlight(index) { document.querySelectorAll('.intro-words span').forEach((word,i) => word.classList.toggle('lit', i === index)); }
  function showStep(index) {
    clearSequence(); step = index;
    $('intro-opening').hidden = index !== -1; $('setup').hidden = index === -1;
    $('onboarding').classList.toggle('setup-active', index !== -1);
    $('onboarding').setAttribute('aria-labelledby', index === -1 ? 'onboard-title' : titles[index]);
    $('onboarding').classList.remove('intro-running','intro-leaving');
    if (index === -1) {
      void $('onboarding').offsetWidth; $('onboarding').classList.add('intro-running');
      if (motionReduced()) highlight(10);
      else { highlight(0); for (let i=1;i<11;i++) timers.push(setTimeout(()=>highlight(i),220+i*280)); }
      $('onboard-title').focus({preventScroll:true}); return;
    }
    screens.forEach((id,i) => $(id).hidden = i !== index);
    document.querySelectorAll('.setup-progress span').forEach((el,i) => el.classList.toggle('complete', i <= index));
    $('setup').scrollTop = 0;
    $('setup-next').textContent = index === 2 ? 'Save my first memory →' : 'Continue →';
    $('setup-skip').textContent = index === 2 ? 'Explore first' : 'Skip setup';
    const draftName = $('profile-name').value.trim();
    $('setup-ready-title').textContent = draftName ? `You're all set, ${draftName}.` : 'Your nook is ready.';
    $(titles[index]).focus({preventScroll:true});
  }
  function show(start = -1) {
    leaving = false; $('app-shell').classList.remove('intro-arrival');
    $('app-shell').inert = true; $('onboarding').hidden = false; $('profile-name').value = name;
    showStep(start);
  }
  function complete(destination, saveProfile) {
    if (leaving) return; leaving = true; clearSequence();
    if (saveProfile) { name = $('profile-name').value.trim().replace(/\s+/g,' ').slice(0,40); preference('nook.profileName',name); personalize(); }
    preference('nook.onboarded','1'); preference('nook.setupVersion','2'); location.hash = destination;
    const reveal = () => { $('onboarding').hidden = true; $('app-shell').inert = false; $('app-shell').classList.add('intro-arrival'); $('main').focus({preventScroll:true}); };
    if (motionReduced()) reveal(); else { $('onboarding').classList.add('intro-leaving'); timers.push(setTimeout(reveal,240)); }
  }
  $('onboard-next').onclick = () => showStep(0);
  $('setup-form').onsubmit = event => { event.preventDefault(); if (!leaving) { if (step < 2) showStep(step+1); else complete('capture',true); } };
  $('setup-back').onclick = () => { if (!leaving) showStep(step-1); };
  $('setup-skip').onclick = () => complete('talk',step === 2);
  reduceMotion.addEventListener('change', () => { if (motionReduced() && !$('onboarding').hidden) { clearSequence(); highlight(10); if (leaving) { $('onboarding').hidden = true; $('app-shell').inert = false; $('main').focus({preventScroll:true}); } } });
  $('open-settings').onclick = () => $('settings').showModal(); $('close-settings').onclick = () => { if (!canCloseSettings || canCloseSettings()) $('settings').close(); };
  $('settings').addEventListener('cancel', event => { if (canCloseSettings && !canCloseSettings()) event.preventDefault(); });
  async function replay(start) { if (!canReplay()) return; await beforeReplay(); $('settings').close(); show(start); }
  $('replay-onboarding').onclick = () => replay(-1); $('edit-profile').onclick = () => replay(0);
  $('onboarding').addEventListener('keydown', event => {
    if (event.key !== 'Tab') return;
    const controls = [...$('onboarding').querySelectorAll('button,input')].filter(el => !el.disabled && el.getClientRects().length);
    const first = controls[0], last = controls.at(-1);
    if (event.shiftKey && (document.activeElement === first || !controls.includes(document.activeElement))) { event.preventDefault(); last?.focus(); }
    else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
  });
  if (preference('nook.setupVersion') !== '2') show();
}
export function confirmAction({title, message, action, cancel = 'Keep memory'}) {
  const dialog = $('confirmation');
  if (dialog.open) return Promise.resolve(false);
  $('confirmation-title').textContent = title; $('confirmation-copy').textContent = message;
  $('confirm-action').textContent = action; $('decline-action').textContent = cancel;
  return new Promise(resolve => {
    let approved = false;
    const finish = () => { dialog.removeEventListener('close', finish); resolve(approved); };
    $('confirm-action').onclick = () => { approved = true; dialog.close(); };
    $('decline-action').onclick = () => dialog.close();
    dialog.addEventListener('close', finish); dialog.showModal(); $('decline-action').focus();
  });
}

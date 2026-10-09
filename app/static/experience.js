const $ = id => document.getElementById(id);
function preference(key, value) { try { if (value === undefined) return localStorage.getItem(key); localStorage.setItem(key, value); } catch { /* Preferences are optional; blocked storage never prevents use. */ } }
export function initExperience({canReplay, beforeReplay}) {
  const appearance = preference('nook.appearance') || 'system';
  function theme(value) { if (value === 'system') delete document.documentElement.dataset.theme; else document.documentElement.dataset.theme = value; }
  $('appearance').value = appearance; theme(appearance);
  $('appearance').onchange = () => { theme($('appearance').value); preference('nook.appearance', $('appearance').value); };
  const reduceMotion = matchMedia('(prefers-reduced-motion: reduce)');
  let timers = [], leaving = false;
  $('reduce-motion').checked = preference('nook.reduceMotion') === '1';
  function motionPreference() { if ($('reduce-motion').checked) document.documentElement.dataset.motion = 'reduce'; else delete document.documentElement.dataset.motion; }
  motionPreference();
  const motionReduced = () => reduceMotion.matches || $('reduce-motion').checked;
  $('reduce-motion').onchange = () => { preference('nook.reduceMotion', $('reduce-motion').checked ? '1' : '0'); motionPreference(); }; 
  function clearSequence() { timers.forEach(clearTimeout); timers = []; }
  function highlight(index) { document.querySelectorAll('.intro-words span').forEach((word,i) => word.classList.toggle('lit', i === index)); }
  function show() {
    clearSequence(); leaving = false; $('app-shell').classList.remove('intro-arrival');
    $('app-shell').inert = true; $('onboarding').hidden = false;
    $('onboarding').classList.remove('intro-running','intro-leaving');
    void $('onboarding').offsetWidth; $('onboarding').classList.add('intro-running');
    if (motionReduced()) highlight(10);
    else { highlight(0); for (let i=1;i<11;i++) timers.push(setTimeout(()=>highlight(i),220+i*280)); }
    $('onboard-title').focus({preventScroll:true});
  }
  function complete() {
    if (leaving) return; leaving = true; clearSequence(); preference('nook.onboarded','1');
    location.hash = 'talk';
    const reveal = () => {
      $('onboarding').hidden = true; $('app-shell').inert = false;
      $('app-shell').classList.add('intro-arrival'); $('main').focus({preventScroll:true});
    };
    if (motionReduced()) reveal();
    else { $('onboarding').classList.add('intro-leaving'); timers.push(setTimeout(reveal,240)); }
  }
  $('onboard-next').onclick = complete;
  reduceMotion.addEventListener('change', () => { if (motionReduced() && !$('onboarding').hidden) { clearSequence(); highlight(10); if (leaving) { $('onboarding').hidden = true; $('app-shell').inert = false; $('main').focus({preventScroll:true}); } } });
  $('open-settings').onclick = () => $('settings').showModal();
  $('close-settings').onclick = () => $('settings').close();
  $('replay-onboarding').onclick = async () => { if (!canReplay()) return; await beforeReplay(); $('settings').close(); show(); };
  $('onboarding').addEventListener('keydown', event => {
    if (event.key === 'Tab') { event.preventDefault(); $('onboard-next').focus(); }
  });
  if (preference('nook.onboarded') !== '1') show();
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

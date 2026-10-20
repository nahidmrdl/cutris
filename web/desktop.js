'use strict';

function applyBranding(info = {}) {
  const name = typeof info.name === 'string' && info.name.trim() ? info.name.trim() : $('appName').textContent;
  document.title = `${name} · Background Remover`;
  $('appName').textContent = name;
  $('aboutAppName').textContent = name;
  $('footerAppName').textContent = name;
  $('appBrandLink').setAttribute('aria-label', `${name} home`);
  if (info.version != null) $('appVersion').textContent = String(info.version);
}

function applyModelAvailability(models) {
  state.models = models;
  for (const option of $('quality').options) option.disabled = !models[option.value];
  if (!models[$('quality').value]) {
    const available = [...$('quality').options].find(option => !option.disabled);
    if (available) $('quality').value = available.value;
  }
  renderQueue();
}

function syncDesktopState() {
  const bridge = window.pywebview?.api;
  if (!bridge) return;
  const processing = ['queued', 'running', 'pausing'].includes(state.job?.status);
  bridge.document_state(state.dirty, processing).catch(() => {});
}

function connectDesktop() {
  $('modelsButton').hidden = false;
  $('savedWorkButton').hidden = false;
  syncDesktopState();
}
window.addEventListener('pywebviewready', connectDesktop);
if (window.pywebview?.api) connectDesktop();

$('modelsButton').onclick = safely(async () => {
  $('modelsButton').disabled = true;
  notice('AI model setup is open in a separate window.');
  try {
    const result = await window.pywebview.api.setup_models();
    if (result.models) applyModelAvailability(result.models);
    notice(result.message || (result.ok ? 'AI models are ready. Processing stays offline.' : 'Model setup was cancelled. Previously installed models are still available.'));
  } finally { $('modelsButton').disabled = false; }
});
$('savedWorkButton').onclick = safely(async () => { await window.pywebview.api.open_saved_work(); });
$('aboutButton').onclick = safely(async () => {
  const info = await api('/about');
  applyBranding(info);
  $('licenseNotices').textContent = info.notices;
  $('aboutDialog').showModal();
});
$('closeAbout').onclick = () => $('aboutDialog').close();
setInterval(syncDesktopState, 1000);
$('quality').addEventListener('change', renderQueue);

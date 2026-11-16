(() => {
  const panel = document.getElementById('archiveProgress');
  const message = document.getElementById('archiveMessage');
  const bar = document.getElementById('archiveBar');
  const cancel = document.getElementById('archiveCancel');
  const download = document.getElementById('archiveDownload');
  let job = null, timer = null, starting = false;
  const size = bytes => `${(bytes / 1024 ** 2).toFixed(1)} MiB`;
  async function poll() {
    try {
      const response = await fetch(`/api/exports/${job}`, {cache:'no-store'});
      const state = await response.json();
      if (!state.ok) throw new Error(state.error);
      bar.value = state.percent;
      if (state.state === 'compressing') {
        message.textContent = `Compressing ${state.percent}% · ${size(state.processed)} / ${size(state.total)} · ${state.files_done}/${state.files_total} files · ${Math.round(state.elapsed_s)} s — ${state.file}`;
        timer = setTimeout(poll, 1000);
        return;
      }
      cancel.classList.add('hidden');
      writeLocalSetting('dosecam_archive_job', '');
      if (state.state === 'ready') {
        message.textContent = `ZIP ready: ${size(state.size)}. Download starting. Use Download ZIP to retry.`;
        download.href = `/api/exports/${job}/download`;
        download.classList.remove('hidden');
        download.click();
      } else {
        message.textContent = state.error || 'Compression cancelled';
      }
      job = null;
    } catch (err) {
      message.textContent = `Could not check compression: ${err.message}. Refresh to resume checking.`;
      cancel.classList.add('hidden');
      job = null;
    }
  }
  window.prepareArchive = async (scope, path, format='raw_zip', rotation=180) => {
    panel.classList.remove('hidden');
    if (job || starting) { panel.scrollIntoView({block:'nearest'}); return; }
    starting = true;
    clearTimeout(timer);
    message.textContent = 'Starting compression…';
    bar.value = 0;
    download.classList.add('hidden');
    cancel.classList.add('hidden');
    try {
      const response = await fetch('/api/exports', {method:'POST', headers:{'Content-Type':'application/json'},
        body:JSON.stringify({scope,path,format,rotation})});
      const state = await response.json();
      if (!state.ok) throw new Error(state.error);
      job = state.id;
      writeLocalSetting('dosecam_archive_job', job);
      cancel.classList.remove('hidden');
      panel.scrollIntoView({block:'nearest'});
      poll();
    } catch (err) { message.textContent = err.message; }
    finally { starting = false; }
  };
  cancel.addEventListener('click', async () => {
    if (!job) return;
    try {
      const response = await fetch(`/api/exports/${job}/cancel`, {method:'POST'});
      if (!response.ok) throw new Error('Cancel failed');
      message.textContent = 'Cancelling compression…';
    } catch (err) { message.textContent = err.message; }
  });
  job = readLocalSetting('dosecam_archive_job');
  if (job) { panel.classList.remove('hidden'); poll(); }
})();

(() => {
  const el = id => document.getElementById(`wifi_${id}`);
  let loaded = false;
  let pending = false;
  let lastMode = 'off';
  async function refresh() {
    try {
      const response = await fetch('/api/wifi');
      const state = await response.json();
      if (!state.ok) throw new Error(state.error);
      lastMode = state.mode;
      for (const mode of ['ap', 'client']) {
        el(`${mode}_enabled`).checked = state.mode === mode;
        if (!loaded) el(`${mode}_ssid`).value = state.profiles[mode].ssid;
      }
      if (!loaded) el('ap_ip').value = state.profiles.ap.ip;
      loaded = true;
      pending = state.busy;
      const address = state.address.split('/')[0];
      el('status').textContent = `${state.message || 'Wi-Fi status'} — ${state.mode === 'ap' ? 'Hosting hotspot' : state.mode === 'client' ? 'Joined network' : 'Wi-Fi inactive'}${address ? ' · ' + address : ''}`;
      el('url').classList.toggle('hidden', !address);
      if (address) {
        el('url').href = `http://${address}/`;
        el('url').textContent = `Camera page: http://${address}/`;
      }
      for (const id of ['ap_enabled', 'client_enabled', 'ap_apply', 'client_apply']) el(id).disabled = state.busy;
    } catch (err) {
      el('status').textContent = `Wi-Fi status unavailable: ${err.message}. If you changed Wi-Fi, reconnect your phone and reopen the camera page.`;
    }
    if (pending) setTimeout(refresh, 2000);
  }
  async function apply(mode) {
    const data = {mode};
    if (mode !== 'off') {
      data.ssid = el(`${mode}_ssid`).value;
      data.password = el(`${mode}_password`).value;
      if (mode === 'ap') data.ip = el('ap_ip').value.trim();
    }
    el('status').textContent = 'Applying Wi-Fi settings…';
    try {
      const response = await fetch('/api/wifi', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(data)});
      const state = await response.json();
      if (!state.ok) throw new Error(state.error);
      if (mode !== 'off') el(`${mode}_password`).value = '';
      pending = true;
      for (const id of ['ap_enabled', 'client_enabled', 'ap_apply', 'client_apply']) el(id).disabled = true;
      el('status').textContent = state.message;
      setTimeout(refresh, 2000);
    } catch (err) {
      el('status').textContent = err.message;
      for (const m of ['ap', 'client']) el(`${m}_enabled`).checked = lastMode === m;
    }
  }
  for (const mode of ['ap', 'client']) {
    el(`${mode}_enabled`).addEventListener('change', () => apply(el(`${mode}_enabled`).checked ? mode : 'off'));
    el(`${mode}_apply`).addEventListener('click', () => apply(mode));
  }
  el('refresh').addEventListener('click', () => { pending = false; refresh(); });
  refresh();
})();

(() => {
  const HOT = 85;

  const finite = value => {
    if (value === null || value === undefined || value === '') return null;
    const number = Number(value);
    return Number.isFinite(number) ? number : null;
  };
  const clamp = value => Math.max(0, Math.min(100, value));
  const byId = id => document.getElementById(id);
  const setText = (id, value) => {
    const element = byId(id);
    if (element && element.textContent !== value) element.textContent = value;
  };
  const memoryPercent = memory => {
    const usage = finite(memory.usage);
    if (usage !== null) return usage;
    const used = finite(memory.used), total = finite(memory.total);
    return used !== null && total ? (used / total) * 100 : null;
  };
  const percent = value => (value === null ? '--%' : `${Math.round(clamp(value))}%`);
  const degrees = value => (value === null ? '--°' : `${Math.round(value)}°`);
  const clockOf = snapshot => {
    const timestamp = finite(snapshot.timestamp);
    return timestamp === null ? new Date() : new Date(timestamp * 1000);
  };

  const rate = value => (value === null ? '--' : value >= 100 ? value.toFixed(0) : value.toFixed(1));
  // Snap the bar to whole 12 px segments, like a text-mode meter.
  const setBar = (name, value) => {
    const bar = byId(`${name}-bar`);
    const fill = bar && bar.querySelector('.fill');
    if (!fill) return;
    const segments = value === null ? 0 : Math.round(clamp(value) / 100 * 16);
    fill.style.width = `${segments * 12 - (segments ? 4 : 0)}px`;
    bar.classList.toggle('hot', value !== null && value >= HOT);
  };

  window.TuringTheme = {
    update(snapshot) {
      const data = snapshot.data || {};
      const cpu = data.cpu || {}, gpu = data.gpu || {}, network = data.network || {};
      const now = clockOf(snapshot);
      setText('time', now.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit', hour12: false }));
      const date = now.toLocaleDateString('pt-BR', { weekday: 'short', day: '2-digit', month: 'short', year: 'numeric' });
      setText('date', date.replace(/\./g, '').replace(/ de /g, ' ').replace(/,/g, '').toUpperCase());
      const values = { cpu: finite(cpu.usage), gpu: finite(gpu.usage), ram: memoryPercent(data.memory || {}) };
      for (const [name, value] of Object.entries(values)) {
        setBar(name, value);
        setText(`${name}-val`, percent(value));
        byId(`${name}-val`)?.classList.toggle('hot', value !== null && value >= HOT);
      }
      const cpuTemp = finite(cpu.temperature), gpuTemp = finite(gpu.temperature);
      setText('temps', `TEMP CPU ${degrees(cpuTemp)} GPU ${degrees(gpuTemp)}`);
      byId('temps')?.classList.toggle('hot', Math.max(cpuTemp ?? 0, gpuTemp ?? 0) >= HOT);
      setText('net', `NET DL ${rate(finite(network.download))} UL ${rate(finite(network.upload))} MB/S`);
    }
  };
})();

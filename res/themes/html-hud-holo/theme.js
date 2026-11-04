(() => {
  const WARN = 70, HOT = 85;
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
  const rate = value => (value === null ? '--' : value >= 100 ? value.toFixed(0) : value.toFixed(1));

  window.TuringTheme = {
    update(snapshot) {
      const data = snapshot.data || {};
      const cpu = data.cpu || {}, gpu = data.gpu || {}, memory = data.memory || {}, network = data.network || {};
      const usage = finite(cpu.usage);
      const segments = document.querySelectorAll('#cpu-meter .seg');
      const lit = usage === null ? 0 : Math.round((clamp(usage) / 100) * segments.length);
      segments.forEach((segment, index) => {
        const percent = ((index + 1) / segments.length) * 100;
        segment.classList.toggle('on', index < lit);
        segment.classList.toggle('warn', percent > WARN && percent <= HOT);
        segment.classList.toggle('hot', percent > HOT);
      });
      setText('cpu-val', usage === null ? '--' : String(Math.round(clamp(usage))));
      byId('cpu-val')?.classList.toggle('hot-text', usage !== null && usage >= HOT);
      const temperature = finite(cpu.temperature);
      setText('cpu-temp', temperature === null ? 'T --°C' : `T ${Math.round(temperature)}°C`);

      const gpuUsage = finite(gpu.usage), gpuTemp = finite(gpu.temperature);
      setText('gpu-val', gpuUsage === null ? '--%' : `${Math.round(clamp(gpuUsage))}%`);
      setText('gpu-temp', gpuTemp === null ? '--°C' : `${Math.round(gpuTemp)}°C`);
      const ram = memoryPercent(memory), used = finite(memory.used);
      setText('ram-val', ram === null ? '--%' : `${Math.round(clamp(ram))}%`);
      setText('ram-used', used === null ? '-- GB' : `${used.toFixed(1)} GB`);
      setText('net', `DL ${rate(finite(network.download))} · UL ${rate(finite(network.upload))}`);

      const timestamp = finite(snapshot.timestamp);
      const now = timestamp === null ? new Date() : new Date(timestamp * 1000);
      setText('time', now.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit', hour12: false }));
    }
  };
})();

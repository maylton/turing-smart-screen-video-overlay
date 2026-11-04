(() => {
  const HOT = 80;

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

  // Liquid level: 0 °C at the bottom of the glass, 100 °C at the top.
  const setLevel = celsius => {
    const level = document.querySelector('#tank .level');
    if (!level) return;
    const fraction = celsius === null ? 0 : clamp(celsius) / 100;
    level.setAttribute('transform', `translate(0 ${(238 - fraction * 232).toFixed(1)})`);
    byId('tank').classList.toggle('hot', celsius !== null && celsius >= HOT);
  };

  window.TuringTheme = {
    update(snapshot) {
      const data = snapshot.data || {};
      const cpu = data.cpu || {}, gpu = data.gpu || {};
      const now = clockOf(snapshot);
      setText('time', now.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit', hour12: false }));
      setText('date', now.toLocaleDateString('pt-BR', { weekday: 'short', day: '2-digit', month: 'short' }).replace(/\./g, '').toUpperCase());
      const cpuTemp = finite(cpu.temperature), gpuTemp = finite(gpu.temperature);
      setLevel(cpuTemp);
      setText('cpu-temp', degrees(cpuTemp));
      byId('cpu-temp')?.classList.toggle('hot', cpuTemp !== null && cpuTemp >= HOT);
      setText('cpu-sub', `CPU ${percent(finite(cpu.usage))}`);
      setText('gpu-val', percent(finite(gpu.usage)));
      setText('ram-val', percent(memoryPercent(data.memory || {})));
      setText('gpu-temp', degrees(gpuTemp));
      byId('gpu-temp')?.classList.toggle('hot', gpuTemp !== null && gpuTemp >= HOT);
    }
  };
})();

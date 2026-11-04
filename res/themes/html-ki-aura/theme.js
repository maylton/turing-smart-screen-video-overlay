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

  window.TuringTheme = {
    update(snapshot) {
      const data = snapshot.data || {};
      const cpu = data.cpu || {}, gpu = data.gpu || {};
      const now = clockOf(snapshot);
      setText('time', now.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit', hour12: false }));
      setText('date', now.toLocaleDateString('pt-BR', { weekday: 'short', day: '2-digit', month: 'short' }).replace(/\./g, '').replace(/,/g, '').replace(/ de /g, ' ').toUpperCase());
      const cpuUsage = finite(cpu.usage), gpuUsage = finite(gpu.usage);
      const cpuTemp = finite(cpu.temperature), gpuTemp = finite(gpu.temperature);
      // Power level: CPU and GPU load together, 0 to 10 000.
      const known = [cpuUsage, gpuUsage].filter(value => value !== null);
      const load = known.length ? known.reduce((sum, value) => sum + clamp(value), 0) / known.length : null;
      setText('power', load === null ? '----' : Math.round(load * 100).toLocaleString('pt-BR'));
      const arc = document.querySelector('#power-arc .fill');
      if (arc) {
        const length = Number(arc.dataset.length);
        arc.style.strokeDashoffset = String(length * (1 - Math.max(0.01, (load ?? 0) / 100)));
      }
      const hot = load !== null && load >= HOT;
      byId('power')?.classList.toggle('hot', hot);
      byId('power-arc')?.classList.toggle('hot', hot);
      setText('cpu-val', percent(cpuUsage));
      setText('gpu-val', percent(gpuUsage));
      setText('cpu-temp', degrees(cpuTemp));
      setText('gpu-temp', degrees(gpuTemp));
      byId('cpu-temp')?.classList.toggle('hot', cpuTemp !== null && cpuTemp >= HOT);
      byId('gpu-temp')?.classList.toggle('hot', gpuTemp !== null && gpuTemp >= HOT);
    }
  };
})();

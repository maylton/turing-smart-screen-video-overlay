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

  const rotate = (element, degrees, cx = 240, cy = 240) => element?.setAttribute('transform', `rotate(${degrees.toFixed(1)} ${cx} ${cy})`);
  const setNeedle = (name, value) => {
    const needle = document.querySelector(`.needle-${name}`);
    if (!needle) return;
    rotate(needle, -150 + (value === null ? 0 : clamp(value)) * 3, Number(needle.dataset.cx), Number(needle.dataset.cy));
  };

  window.TuringTheme = {
    update(snapshot) {
      const data = snapshot.data || {};
      const cpu = data.cpu || {}, gpu = data.gpu || {};
      const now = clockOf(snapshot);
      const minutes = now.getMinutes(), hours = now.getHours() % 12;
      rotate(document.querySelector('.hand-hour'), (hours + minutes / 60) * 30);
      rotate(document.querySelector('.hand-minute'), minutes * 6);
      setText('date', now.toLocaleDateString('pt-BR', { weekday: 'short', day: '2-digit', month: 'short' }).replace(/\./g, '').replace(/,/g, '').replace(/ de /g, ' ').toUpperCase());
      const values = { cpu: finite(cpu.usage), gpu: finite(gpu.usage), ram: memoryPercent(data.memory || {}) };
      for (const [name, value] of Object.entries(values)) {
        setNeedle(name, value);
        setText(`${name}-val`, percent(value));
        byId(`${name}-val`)?.classList.toggle('hot', value !== null && value >= HOT);
      }
      const temp = finite(cpu.temperature);
      setText('cpu-temp', temp === null ? '--°C' : `${Math.round(temp)}°C`);
      byId('cpu-temp')?.classList.toggle('hot', temp !== null && temp >= HOT);
    }
  };
})();

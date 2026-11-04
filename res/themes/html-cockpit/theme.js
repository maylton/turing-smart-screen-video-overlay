(() => {
  // 0-100 % spans 270 degrees, from -135 (7:30) to +135 (4:30).
  const angle = percent => -135 + 2.7 * percent;
  const finite = value => {
    if (value === null || value === undefined || value === '') return null;
    const number = Number(value);
    return Number.isFinite(number) ? number : null;
  };
  const clamp = value => Math.max(0, Math.min(100, value));
  const setText = (id, value) => {
    const element = document.getElementById(id);
    if (element && element.textContent !== value) element.textContent = value;
  };
  const setNeedle = (name, percent) => {
    const needle = document.querySelector(`.needle-${name}`);
    if (!needle) return;
    const { cx, cy } = needle.dataset;
    needle.setAttribute('transform', `rotate(${angle(percent === null ? 0 : clamp(percent)).toFixed(1)} ${cx} ${cy})`);
  };
  const memoryPercent = memory => {
    const usage = finite(memory.usage);
    if (usage !== null) return usage;
    const used = finite(memory.used), total = finite(memory.total);
    return used !== null && total ? (used / total) * 100 : null;
  };

  window.TuringTheme = {
    update(snapshot) {
      const data = snapshot.data || {};
      const cpu = data.cpu || {};
      const usage = finite(cpu.usage);
      const temperature = finite(cpu.temperature);
      setNeedle('cpu', usage);
      setNeedle('gpu', finite((data.gpu || {}).usage));
      setNeedle('ram', memoryPercent(data.memory || {}));
      setText('cpu-val', usage === null ? '--%' : `${Math.round(clamp(usage))}%`);
      setText('cpu-temp', temperature === null ? '--°C' : `${Math.round(temperature)}°C`);
      const timestamp = finite(snapshot.timestamp);
      const now = timestamp === null ? new Date() : new Date(timestamp * 1000);
      setText('time', now.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit', hour12: false }));
    }
  };
})();

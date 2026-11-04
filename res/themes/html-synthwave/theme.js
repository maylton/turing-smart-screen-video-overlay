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
  const degrees = value => (value === null ? '--°' : `${Math.round(value)}°`);

  window.TuringTheme = {
    update(snapshot) {
      const data = snapshot.data || {};
      const timestamp = finite(snapshot.timestamp);
      const now = timestamp === null ? new Date() : new Date(timestamp * 1000);
      setText('time', now.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit', hour12: false }));
      setText('date', now.toLocaleDateString('pt-BR', { weekday: 'short', day: '2-digit', month: 'short' }).replace(/\./g, '').toUpperCase());
      const values = { cpu: finite((data.cpu || {}).usage), gpu: finite((data.gpu || {}).usage), ram: memoryPercent(data.memory || {}) };
      for (const [name, value] of Object.entries(values)) {
        setText(`${name}-val`, value === null ? '--%' : `${Math.round(clamp(value))}%`);
        byId(`${name}-val`)?.classList.toggle('hot', value !== null && value >= HOT);
      }
      setText('temps', `CPU ${degrees(finite((data.cpu || {}).temperature))} · GPU ${degrees(finite((data.gpu || {}).temperature))}`);
    }
  };
})();

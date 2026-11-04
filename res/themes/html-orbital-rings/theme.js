(() => {
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
  const setArc = (name, percent) => {
    const arc = document.querySelector(`.arc-${name}`);
    if (!arc) return;
    const circumference = Number(arc.dataset.circumference);
    // A tiny visible start keeps the round cap for 0 %.
    const fraction = percent === null ? 0 : Math.max(0.004, clamp(percent) / 100);
    arc.style.strokeDashoffset = String(circumference * (1 - fraction));
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
      const timestamp = finite(snapshot.timestamp);
      const now = timestamp === null ? new Date() : new Date(timestamp * 1000);
      setText('time', now.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit', hour12: false }));
      const date = now.toLocaleDateString('pt-BR', { weekday: 'short', day: 'numeric', month: 'short' }).replace(/\./g, '');
      setText('date', date.charAt(0).toUpperCase() + date.slice(1));
      const values = {
        cpu: finite((data.cpu || {}).usage),
        gpu: finite((data.gpu || {}).usage),
        ram: memoryPercent(data.memory || {}),
      };
      for (const [name, value] of Object.entries(values)) {
        setArc(name, value);
        setText(`${name}-val`, value === null ? '--%' : `${Math.round(clamp(value))}%`);
      }
    }
  };
})();

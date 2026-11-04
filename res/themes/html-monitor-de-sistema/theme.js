(() => {
  // Thresholds of the original mock: orange from 70 %, red from 85 %.
  const WARN = 70;
  const HOT = 85;

  const finite = value => {
    if (value === null || value === undefined || value === '') return null;
    const number = Number(value);
    return Number.isFinite(number) ? number : null;
  };
  const clamp = value => Math.max(0, Math.min(100, value));
  const byId = id => document.getElementById(id);
  const setText = (element, value) => {
    if (element && element.textContent !== value) element.textContent = value;
  };
  const level = percent => (percent >= HOT ? 'hot' : percent >= WARN ? 'warn' : '');

  const setLevel = (element, percent) => {
    if (!element) return;
    const current = percent === null ? '' : level(percent);
    element.classList.toggle('warn', current === 'warn');
    element.classList.toggle('hot', current === 'hot');
  };

  const updateMetric = (name, usage, temperature) => {
    const percent = usage === null ? null : clamp(usage);
    const usageElement = byId(`${name}-usage`);
    setText(usageElement, percent === null ? '--%' : `${Math.round(percent)}%`);
    setLevel(usageElement, percent);

    const fill = byId(`${name}-bar`)?.querySelector('.fill');
    if (fill) {
      fill.style.width = `${percent === null ? 0 : percent}%`;
      setLevel(fill, percent);
    }

    if (temperature !== undefined) {
      const value = byId(`${name}-temp`)?.querySelector('.temp-value');
      setText(value, temperature === null ? '--' : String(Math.round(temperature)));
    }
  };

  const timeText = date =>
    date.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit', hour12: false });

  const dateText = date => {
    const text = date
      .toLocaleDateString('pt-BR', { weekday: 'long', day: 'numeric', month: 'short' })
      .replace('.', '');
    return text.charAt(0).toUpperCase() + text.slice(1);
  };

  window.TuringTheme = {
    update(snapshot) {
      const data = snapshot.data || {};
      const cpu = data.cpu || {};
      const gpu = data.gpu || {};
      const memory = data.memory || {};

      const timestamp = finite(snapshot.timestamp);
      const now = timestamp === null ? new Date() : new Date(timestamp * 1000);
      setText(byId('time'), timeText(now));
      setText(byId('date'), dateText(now));

      updateMetric('cpu', finite(cpu.usage), finite(cpu.temperature));
      updateMetric('gpu', finite(gpu.usage), finite(gpu.temperature));

      const used = finite(memory.used);
      const total = finite(memory.total);
      let usage = finite(memory.usage);
      if (usage === null && used !== null && total) usage = (used / total) * 100;
      updateMetric('ram', usage);
      const amount = byId('ram-amount');
      setText(amount?.querySelector('.ram-used'), used === null ? '--' : used.toFixed(1));
      setText(amount?.querySelector('.ram-total'), total === null ? '/-- GB' : `/${Math.round(total)} GB`);
    }
  };
})();

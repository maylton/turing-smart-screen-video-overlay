(() => {
  const CELLS = 16;
  // Same thresholds as the original mock.
  const CPU_HOT = 75;
  const GPU_HOT = 80;

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
  const percentText = value =>
    value === null ? '--%' : `${String(Math.round(clamp(value))).padStart(2, '0')}%`;
  const temperatureText = value => (value === null ? '--°C' : `${Math.round(value)}°C`);

  const setBar = (id, percent) => {
    const filled = percent === null ? 0 : Math.round((clamp(percent) / 100) * CELLS);
    const cells = byId(id)?.children || [];
    for (let index = 0; index < cells.length; index += 1)
      cells[index].classList.toggle('on', index < filled);
  };

  window.TuringTheme = {
    update(snapshot) {
      const data = snapshot.data || {};
      const cpu = data.cpu || {};
      const gpu = data.gpu || {};
      const memory = data.memory || {};

      const timestamp = finite(snapshot.timestamp);
      const now = timestamp === null ? new Date() : new Date(timestamp * 1000);
      setText(
        'sys-time',
        `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}`
      );

      const cpuUsage = finite(cpu.usage);
      const cpuTemperature = finite(cpu.temperature);
      setText('cpu-val', percentText(cpuUsage));
      setText('cpu-temp', temperatureText(cpuTemperature));
      setBar('cpu-bar', cpuUsage);

      const gpuUsage = finite(gpu.usage);
      const gpuTemperature = finite(gpu.temperature);
      setText('gpu-val', percentText(gpuUsage));
      setText('gpu-temp', temperatureText(gpuTemperature));
      setBar('gpu-bar', gpuUsage);

      const used = finite(memory.used);
      const total = finite(memory.total);
      let ramUsage = finite(memory.usage);
      if (ramUsage === null && used !== null && total) ramUsage = (used / total) * 100;
      setText('ram-val', percentText(ramUsage));
      setText('ram-gb', used === null ? '--G' : `${used.toFixed(1)}G`);
      setBar('ram-bar', ramUsage);

      const hot =
        (cpuTemperature !== null && cpuTemperature > CPU_HOT) ||
        (gpuTemperature !== null && gpuTemperature > GPU_HOT);
      setText('status-msg', hot ? 'ALERTA: AQUECIMENTO' : 'DIGI-SOUL: ESTAVEL');
      // Overlay captures do not run CSS animations; blink on the snapshot clock.
      const second = Math.floor(timestamp === null ? Date.now() / 1000 : timestamp);
      byId('status-msg')?.classList.toggle('status-hidden', hot && second % 2 === 1);
    }
  };
})();

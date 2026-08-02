(() => {
  const finite = (...values) => {
    for (const value of values) {
      if (value === null || value === undefined || value === '') continue;
      const number = Number(value);
      if (Number.isFinite(number)) return number;
    }
    return null;
  };

  const text = (id, value) => {
    const element = document.getElementById(id);
    if (element) element.textContent = value;
  };

  const clockText = (snapshot, system) => {
    const supplied = String(system.time || '').trim();
    if (supplied) return supplied.slice(0, 5);
    const timestamp = finite(snapshot.timestamp);
    const date = timestamp === null ? new Date() : new Date(timestamp * 1000);
    return date.toLocaleTimeString('pt-BR', {
      hour: '2-digit',
      minute: '2-digit',
      hour12: false
    });
  };

  window.TuringTheme = {
    update(snapshot) {
      const data = snapshot.data || {};
      const cpu = data.cpu || {};
      const gpu = data.gpu || {};
      const memory = data.memory || {};
      const system = data.system || {};
      const cpuTemperature = finite(cpu.temperature);
      const gpuUsage = finite(gpu.usage);
      const memoryUsed = finite(memory.used);

      text('time-display', clockText(snapshot, system));
      text(
        'cpu-value',
        cpuTemperature === null ? '--°C' : `${Math.round(cpuTemperature)}°C`
      );
      text(
        'gpu-value',
        gpuUsage === null ? '--%' : `${Math.round(Math.max(0, Math.min(100, gpuUsage)))}%`
      );
      text(
        'ram-value',
        memoryUsed === null ? '-- GB' : `${memoryUsed.toFixed(1)} GB`
      );
    }
  };
})();

(() => {
  const clampPercent = value => {
    if (value === null || value === undefined || value === '') return null;
    const number = Number(value);
    return Number.isFinite(number) ? Math.max(0, Math.min(100, number)) : null;
  };

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

  const setBar = (id, value) => {
    const element = document.getElementById(id);
    if (element) element.style.width = value === null ? '0%' : `${value}%`;
  };

  const showTemperature = (id, value) => {
    text(id, value === null ? '--' : String(Math.round(value)));
  };

  const setFanPaused = paused => {
    if (document.documentElement.dataset.turingRenderMode === 'overlay') return;
    const fanIcon = document.getElementById('fan-icon');
    if (fanIcon) fanIcon.classList.toggle('paused', paused);
  };

  const updatePrimaryTemperature = (cpu, cooling) => {
    const liquid = finite(
      cooling.liquidTemperature,
      cooling.liquidTemp,
      cooling.coolantTemperature
    );
    const cpuTemperature = finite(cpu.temperature);

    if (liquid !== null) {
      text('liquid-label', 'LIQUID');
      text('liquid-temp', liquid.toFixed(1));
      text('liquid-status', 'COOLANT SENSOR');
      return;
    }

    text('liquid-label', 'CPU TEMP');
    text('liquid-temp', cpuTemperature === null ? '--' : String(Math.round(cpuTemperature)));
    text('liquid-status', 'FALLBACK');
  };

  const updateCoolingSpeed = (gpu, cooling) => {
    const pumpRpm = finite(cooling.pumpRpm, cooling.pumpRPM, cooling.rpm);
    const gpuFan = finite(gpu.fan);

    if (pumpRpm !== null) {
      text('cooling-label', 'PUMP');
      text('pump-value', String(Math.round(pumpRpm)));
      text('pump-unit', 'RPM');
      setFanPaused(false);
      return;
    }

    if (gpuFan !== null) {
      text('cooling-label', 'GPU FAN');
      text('pump-value', String(Math.round(gpuFan)));
      text('pump-unit', '%');
      setFanPaused(false);
      return;
    }

    text('cooling-label', 'COOLING');
    text('pump-value', '--');
    text('pump-unit', '');
    setFanPaused(true);
  };

  window.TuringTheme = {
    update(snapshot) {
      const data = snapshot.data || {};
      const cpu = data.cpu || {};
      const gpu = data.gpu || {};
      const memory = data.memory || {};
      const cooling = data.cooling || {};

      const cpuUsage = clampPercent(cpu.usage);
      const gpuUsage = clampPercent(gpu.usage);
      const cpuTemperature = finite(cpu.temperature);
      const gpuTemperature = finite(gpu.temperature);
      const memoryUsed = finite(memory.used);
      const memoryTotal = finite(memory.total);

      text('cpu-load', cpuUsage === null ? '--%' : `${Math.round(cpuUsage)}%`);
      showTemperature('cpu-temp', cpuTemperature);
      setBar('cpu-bar', cpuUsage);

      text('gpu-load', gpuUsage === null ? '--%' : `${Math.round(gpuUsage)}%`);
      showTemperature('gpu-temp', gpuTemperature);
      setBar('gpu-bar', gpuUsage);

      if (memoryUsed !== null && memoryTotal !== null) {
        text('ram-usage', `${memoryUsed.toFixed(1)} / ${memoryTotal.toFixed(0)} GB`);
      } else if (memoryUsed !== null) {
        text('ram-usage', `${memoryUsed.toFixed(1)} GB`);
      } else {
        text('ram-usage', '-- GB');
      }

      updatePrimaryTemperature(cpu, cooling);
      updateCoolingSpeed(gpu, cooling);
    }
  };
})();

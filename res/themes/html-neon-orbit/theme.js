(() => {
  const root = document.documentElement;

  const finite = (...values) => {
    for (const value of values) {
      if (value === null || value === undefined || value === '') continue;
      const number = Number(value);
      if (Number.isFinite(number)) return number;
    }
    return null;
  };

  const percent = value => {
    const number = finite(value);
    return number === null ? null : Math.max(0, Math.min(100, number));
  };

  const text = (id, value) => {
    const element = document.getElementById(id);
    if (element) element.textContent = value;
  };

  const setPercent = (name, value) => {
    root.style.setProperty(name, value === null ? '0' : value.toFixed(1));
  };

  const temperature = (id, value) => {
    text(id, value === null ? '--' : String(Math.round(value)));
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
      const disk = data.disk || {};
      const network = data.network || {};
      const cooling = data.cooling || {};
      const system = data.system || {};

      const cpuLoad = percent(cpu.usage);
      const gpuLoad = percent(gpu.usage);
      const ramLoad = percent(memory.usage);
      const diskLoad = percent(disk.usage);
      const ramUsed = finite(memory.used);
      const ramTotal = finite(memory.total);
      const download = finite(network.download);
      const pumpRpm = finite(
        cooling.pumpRpm,
        cooling.pumpRPM,
        cooling.rpm
      );
      const gpuFan = percent(gpu.fan);

      setPercent('--cpu', cpuLoad);
      setPercent('--gpu', gpuLoad);
      setPercent('--ram', ramLoad);
      setPercent('--disk', diskLoad);

      temperature('cpu-temp', finite(cpu.temperature));
      text('cpu-load', cpuLoad === null ? '--%' : `${Math.round(cpuLoad)}%`);
      temperature('gpu-temp', finite(gpu.temperature));
      text('gpu-load', gpuLoad === null ? '--%' : `${Math.round(gpuLoad)}%`);

      text('ram-used', ramUsed === null ? '--' : ramUsed.toFixed(1));
      text('ram-total', ramTotal === null ? '--' : ramTotal.toFixed(0));
      text('ram-load', ramLoad === null ? '--%' : `${Math.round(ramLoad)}%`);
      text('disk-load', diskLoad === null ? '--' : String(Math.round(diskLoad)));
      text('net-down', download === null ? '--' : download.toFixed(1));
      text('clock', clockText(snapshot, system));

      if (pumpRpm !== null) {
        text('cooling-label', 'Pump');
        text('fan-value', String(Math.round(pumpRpm)));
        text('fan-unit', 'RPM');
      } else if (gpuFan !== null) {
        text('cooling-label', 'GPU fan');
        text('fan-value', String(Math.round(gpuFan)));
        text('fan-unit', '%');
      } else {
        text('cooling-label', 'Cooling');
        text('fan-value', '--');
        text('fan-unit', '');
      }
    }
  };
})();

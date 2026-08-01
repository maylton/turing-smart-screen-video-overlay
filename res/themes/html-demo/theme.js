(() => {
  const clamp = value => Math.max(0, Math.min(100, Number(value) || 0));
  const text = (id, value) => { document.getElementById(id).textContent = value; };

  window.TuringTheme = {
    update(snapshot) {
      const data = snapshot.data || {};
      const cpu = data.cpu || {};
      const gpu = data.gpu || {};
      const memory = data.memory || {};
      const network = data.network || {};
      const system = data.system || {};

      const cpuUsage = clamp(cpu.usage);
      const gpuUsage = clamp(gpu.usage);
      const ramUsage = clamp(memory.usage);

      document.documentElement.style.setProperty('--cpu', `${cpuUsage * 3.6}deg`);
      document.documentElement.style.setProperty('--gpu', `${gpuUsage}%`);
      document.documentElement.style.setProperty('--ram', `${ramUsage}%`);

      text('clock', system.time || '--:--:--');
      text('cpu-value', `${Math.round(cpuUsage)}%`);
      text('cpu-temp', `${Math.round(Number(cpu.temperature) || 0)}°C`);
      text('cpu-frequency', `${Number(cpu.frequency || 0).toFixed(2)} GHz`);
      text('gpu-value', `${Math.round(gpuUsage)}%`);
      text('gpu-meta', `${Math.round(Number(gpu.temperature) || 0)}°C · ${Number(gpu.vramUsed || 0).toFixed(1)} / ${Number(gpu.vramTotal || 0).toFixed(0)} GB`);
      text('ram-value', `${Math.round(ramUsage)}%`);
      text('ram-meta', `${Number(memory.used || 0).toFixed(1)} / ${Number(memory.total || 0).toFixed(0)} GB`);
      text('download', Number(network.download || 0).toFixed(1));
      text('upload', Number(network.upload || 0).toFixed(1));
      text('sequence', `FRAME ${String(snapshot.sequence || 0).padStart(3, '0')}`);
    }
  };
})();

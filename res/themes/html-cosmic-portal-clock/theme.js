(() => {
  const ptWeekday = new Intl.DateTimeFormat('pt-BR', { weekday: 'long' });
  const ptDate = new Intl.DateTimeFormat('pt-BR', { day: '2-digit', month: 'short' });
  let lastSnapshotTime = null;
  let receivedAt = null;

  const setText = (id, value) => {
    const element = document.getElementById(id);
    if (element) element.textContent = value;
  };

  const finiteNumber = value => {
    if (value === null || value === undefined || value === '') return null;
    const number = Number(value);
    return Number.isFinite(number) ? number : null;
  };

  const snapshotDate = () => {
    if (lastSnapshotTime === null || receivedAt === null) return new Date();
    return new Date(lastSnapshotTime + (Date.now() - receivedAt));
  };

  const renderClock = () => {
    const date = snapshotDate();
    const hours = String(date.getHours()).padStart(2, '0');
    const minutes = String(date.getMinutes()).padStart(2, '0');
    const seconds = String(date.getSeconds()).padStart(2, '0');
    const weekday = ptWeekday.format(date).replace('-feira', '').toUpperCase();
    const calendarDate = ptDate.format(date).replace('.', '').toUpperCase();

    setText('clock-hours', `${hours}:${minutes}`);
    setText('clock-seconds', seconds);
    setText('weekday', weekday);
    setText('calendar-date', calendarDate);
  };

  const renderTemperature = value => {
    const card = document.getElementById('cpu-card');
    const temperature = finiteNumber(value);

    if (card) {
      card.classList.toggle('is-unavailable', temperature === null);
      card.classList.toggle('is-warm', temperature !== null && temperature >= 70 && temperature < 85);
      card.classList.toggle('is-hot', temperature !== null && temperature >= 85);
    }
    setText('cpu-temperature', temperature === null ? '--' : String(Math.round(temperature)));
  };

  window.TuringTheme = {
    update(snapshot) {
      const timestamp = finiteNumber(snapshot && snapshot.timestamp);
      if (timestamp !== null) {
        lastSnapshotTime = timestamp * 1000;
        receivedAt = Date.now();
      }
      const data = (snapshot && snapshot.data) || {};
      const cpu = data.cpu || {};
      renderTemperature(cpu.temperature);
      renderClock();
    }
  };

  renderClock();
  renderTemperature(null);
  window.setInterval(renderClock, 1000);
})();

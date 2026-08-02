(() => {
  if (window.__turingGeneratedWidgetsInstalled) return;
  window.__turingGeneratedWidgetsInstalled = true;

  const valueAt = (snapshot, path) => {
    if (path === '$timestamp') return snapshot.timestamp;
    let value = snapshot.data || {};
    for (const part of String(path || '').split('.')) {
      if (value === null || value === undefined) return null;
      value = value[part];
    }
    return value;
  };
  const finite = value => {
    if (value === null || value === undefined || value === '') return null;
    const number = Number(value);
    return Number.isFinite(number) ? number : null;
  };
  const cssNumber = value => {
    const number = Number.parseFloat(String(value ?? ''));
    return Number.isFinite(number) ? number : null;
  };
  const positionInViewport = (element, targetX, targetY) => {
    if (!element) return;
    const x = finite(targetX);
    const y = finite(targetY);
    if (x === null || y === null) return;
    element.style.setProperty('--turing-editor-x', `${x}px`, 'important');
    element.style.setProperty('--turing-editor-y', `${y}px`, 'important');
    element.style.setProperty('left', `${x}px`, 'important');
    element.style.setProperty('top', `${y}px`, 'important');
    // A transformed ancestor becomes the containing block even for fixed
    // descendants. Correct its viewport offset without changing the theme's
    // surrounding layout.
    for (let attempt = 0; attempt < 3; attempt += 1) {
      const rect = element.getBoundingClientRect();
      const dx = x - rect.left;
      const dy = y - rect.top;
      if (Math.abs(dx) < 0.1 && Math.abs(dy) < 0.1) break;
      const style = getComputedStyle(element);
      const left = cssNumber(style.left) || 0;
      const top = cssNumber(style.top) || 0;
      element.style.setProperty('left', `${left + dx}px`, 'important');
      element.style.setProperty('top', `${top + dy}px`, 'important');
    }
  };
  const normalizeLayout = () => {
    document.querySelectorAll('[data-turing-overlay]').forEach(element => {
      const style = getComputedStyle(element);
      const x = cssNumber(style.getPropertyValue('--turing-editor-x'));
      const y = cssNumber(style.getPropertyValue('--turing-editor-y'));
      if (x !== null && y !== null) positionInViewport(element, x, y);
    });
  };
  window.__turingPositionEditorElement = positionInViewport;
  window.__turingNormalizeEditorLayout = normalizeLayout;
  const formatted = (value, format, snapshot) => {
    const number = finite(value);
    if (format === 'temperature') return number === null ? '--°C' : `${Math.round(number)}°C`;
    if (format === 'percent') return number === null ? '--%' : `${Math.round(Math.max(0, Math.min(100, number)))}%`;
    if (format === 'gigabytes') return number === null ? '-- GB' : `${number.toFixed(1)} GB`;
    if (format === 'megabytes') return number === null ? '-- M' : `${Math.round(number)} M`;
    if (format === 'gigahertz') return number === null ? '-- GHz' : `${number.toFixed(2)} GHz`;
    if (format === 'gigahertz-from-megahertz') return number === null ? '-- GHz' : `${(number / 1000).toFixed(2)} GHz`;
    if (format === 'megabytes-per-second') return number === null ? '-- MB/s' : `${number.toFixed(1)} MB/s`;
    if (format === 'integer') return number === null ? '--' : String(Math.round(number));
    if (format === 'decimal') return number === null ? '--' : number.toFixed(2);
    if (format === 'fps') return number === null ? '-- FPS' : `${Math.round(number)} FPS`;
    if (format === 'bytes') {
      if (number === null) return '--';
      const units = ['B', 'KB', 'MB', 'GB', 'TB'];
      let amount = Math.max(0, number);
      let unit = 0;
      while (amount >= 1024 && unit < units.length - 1) {
        amount /= 1024;
        unit += 1;
      }
      return `${amount.toFixed(unit === 0 ? 0 : 1)} ${units[unit]}`;
    }
    if (format === 'duration') {
      if (number === null) return '--:--:--';
      const seconds = Math.max(0, Math.round(number));
      const hours = Math.floor(seconds / 3600);
      const minutes = Math.floor((seconds % 3600) / 60);
      const remainder = seconds % 60;
      return `${hours}:${String(minutes).padStart(2, '0')}:${String(remainder).padStart(2, '0')}`;
    }
    if (format === 'load') return number === null ? '--' : number.toFixed(2);
    if (format === 'time') {
      const supplied = String(value || '').trim();
      if (supplied) return supplied.slice(0, 5);
      const date = new Date((finite(snapshot.timestamp) || Date.now() / 1000) * 1000);
      return date.toLocaleTimeString('pt-BR', {hour: '2-digit', minute: '2-digit', hour12: false});
    }
    if (format === 'date') {
      const date = new Date((number || Date.now() / 1000) * 1000);
      return date.toLocaleDateString('pt-BR');
    }
    const text = String(value === null || value === undefined ? '' : value).trim();
    return text || '--';
  };
  const updateGenerated = snapshot => {
    document.querySelectorAll('[data-turing-generated-widget]').forEach(element => {
      const value = valueAt(snapshot, element.dataset.turingBinding);
      if (element.dataset.turingKind === 'bar') {
        const number = finite(value);
        const percentage = number === null ? 0 : Math.max(0, Math.min(100, number));
        let fill = element.querySelector('[data-turing-bar-fill]');
        if (!fill) {
          fill = document.createElement('div');
          fill.setAttribute('data-turing-bar-fill', '');
          fill.setAttribute('aria-hidden', 'true');
          element.replaceChildren(fill);
        }
        fill.style.setProperty('width', `${percentage}%`, 'important');
        if (number === null) {
          element.removeAttribute('aria-valuenow');
          element.setAttribute('aria-valuetext', 'indisponível');
        } else {
          element.setAttribute('aria-valuenow', String(Math.round(percentage)));
          element.removeAttribute('aria-valuetext');
        }
        return;
      }
      element.textContent = formatted(value, element.dataset.turingFormat, snapshot);
    });
  };
  window.__turingUpdateGeneratedWidgets = updateGenerated;

  window.TuringTheme = window.TuringTheme || {};
  const originalUpdate = typeof window.TuringTheme.update === 'function'
    ? window.TuringTheme.update.bind(window.TuringTheme)
    : null;
  window.TuringTheme.update = snapshot => {
    if (originalUpdate) originalUpdate(snapshot);
    normalizeLayout();
    updateGenerated(snapshot || {});
  };
  normalizeLayout();
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', normalizeLayout, {once: true});
  }
})();

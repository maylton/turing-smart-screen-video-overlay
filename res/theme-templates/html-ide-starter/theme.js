/*
 * Author-owned JavaScript example.
 *
 * The renderer calls window.TuringTheme.update(snapshot). Do not poll sensors,
 * read files, or use fetch here: values already arrive in the safe snapshot.
 */
(() => {
  'use strict';

  /** Return a nested value from snapshot.data using a dotted binding path. */
  const valueAt = (snapshot, binding) => {
    let value = snapshot?.data ?? {};
    for (const part of String(binding).split('.')) {
      if (value === null || value === undefined) return null;
      value = value[part];
    }
    return value ?? null;
  };

  /** Replace text safely. textContent prevents sensor values becoming HTML. */
  const setText = (elementId, value, fallback = '--') => {
    const element = document.getElementById(elementId);
    if (!element) return;
    const text = String(value ?? '').trim();
    element.textContent = text || fallback;
  };

  /**
   * Optional custom update hook. The generated widget runtime calls this first
   * and then updates every generatedWidget from overlays.json.
   */
  const update = snapshot => {
    const hostname = valueAt(snapshot, 'system.hostname');
    setText('custom-status', hostname ? `HOST: ${hostname}` : null, 'HOST: --');
  };

  // Expose exactly one stable bridge object to the application renderer.
  window.TuringTheme = {update};
})();

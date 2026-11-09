(() => {
  const panel = document.querySelector('.exterior-view');
  if (!panel) return;
  const button = panel.querySelector('.exterior-load');
  const status = panel.querySelector('.exterior-status');
  const host = panel.querySelector('.exterior-map');
  let timer;
  let failed = false;
  function fail() {
    failed = true;
    clearTimeout(timer);
    status.textContent = panel.dataset.error;
    host.hidden = true;
    // A provider, network or browser error is not evidence of missing coverage.
  }
  button.addEventListener('click', () => {
    button.disabled = true;
    status.textContent = panel.dataset.loading;
    timer = setTimeout(fail, 30000);
    window.gm_authFailure = fail;
    window.heritageMapsReady = async () => {
      try {
        const { Map3DElement } = await google.maps.importLibrary('maps3d');
        const map = new Map3DElement({
          center: { lat: Number(panel.dataset.lat), lng: Number(panel.dataset.lng), altitude: 0 },
          range: 600, tilt: 65, heading: 0, mode: 'HYBRID'
        });
        map.addEventListener('gmp-error', fail);
        map.addEventListener('gmp-steadychange', (event) => {
          if (!event.isSteady || failed) return;
          clearTimeout(timer);
          status.textContent = panel.dataset.loaded;
        });
        if (failed) return;
        host.replaceChildren(map);
        host.hidden = false;
      } catch (_) { fail(); }
    };
    const url = new URL('https://maps.googleapis.com/maps/api/js');
    url.search = new URLSearchParams({key: panel.dataset.key, loading: 'async',
      libraries: 'maps3d', callback: 'heritageMapsReady',
      language: panel.dataset.lang === 'zh' ? 'zh-CN' : panel.dataset.lang});
    const script = document.createElement('script');
    script.src = url.toString();
    script.async = true;
    script.onerror = fail;
    document.head.append(script);
  }, { once: true });
})();

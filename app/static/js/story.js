(() => {
  const root = document.querySelector('[data-story]');
  if (!root) return;
  const chapters = [...root.querySelectorAll('[data-chapter]')];
  if (!chapters.length) return;
  const labels = JSON.parse(document.getElementById('story-labels').textContent);
  const next = root.querySelector('[data-next]');
  const prev = root.querySelector('[data-prev]');
  const listen = root.querySelector('[data-listen]');
  let index = 0;
  let speaking = false;
  const stop = () => {
    if ('speechSynthesis' in window) speechSynthesis.cancel();
    speaking = false;
    listen.textContent = labels.listen;
  };
  function show(value, focus = true) {
    stop();
    index = value;
    chapters.forEach((chapter, i) => { chapter.hidden = i !== index; });
    root.querySelectorAll('[data-progress]').forEach((bar, i) => bar.classList.toggle('read', i <= index));
    root.querySelector('[data-counter]').textContent = `${labels.chapter} ${index + 1} / ${chapters.length}`;
    prev.disabled = index === 0;
    next.textContent = index === chapters.length - 1 ? labels.restart + ' ↺' : labels.next + ' →';
    root.querySelector('[data-story-end]').hidden = index !== chapters.length - 1;
    if (focus) chapters[index].querySelector('h2').focus({preventScroll: true});
  }
  root.querySelectorAll('[data-story-controls]').forEach(el => { el.hidden = false; });
  next.addEventListener('click', () => show((index + 1) % chapters.length));
  prev.addEventListener('click', () => show(Math.max(0, index - 1)));
  root.addEventListener('keydown', event => {
    if (event.target.closest('input, textarea, select') || event.altKey || event.ctrlKey || event.metaKey) return;
    if (event.key === 'ArrowRight' || event.key === 'ArrowLeft') {
      event.preventDefault();
      show(Math.min(chapters.length - 1, Math.max(0, index + (event.key === 'ArrowRight' ? 1 : -1))));
    }
  });
  if (!('speechSynthesis' in window)) listen.hidden = true;
  listen.addEventListener('click', () => {
    if (speaking) return stop();
    const card = chapters[index];
    const utterance = new SpeechSynthesisUtterance(card.querySelector('h2').textContent + '. ' + card.querySelector('.chapter-text').textContent);
    utterance.lang = {en: 'en-US', ru: 'ru-RU', zh: 'zh-CN'}[root.dataset.lang];
    utterance.onend = utterance.onerror = stop;
    speaking = true;
    listen.textContent = labels.stop;
    speechSynthesis.speak(utterance);
  });
  root.querySelector('[data-share]').addEventListener('click', async () => {
    const url = new URL(location.href);
    url.searchParams.set('lang', root.dataset.lang);
    const status = root.querySelector('[data-share-status]');
    try { await navigator.clipboard.writeText(url.href); status.textContent = labels.copied; }
    catch { status.textContent = labels.copy_error; }
  });
  window.addEventListener('pagehide', stop);
  show(0, false);
})();

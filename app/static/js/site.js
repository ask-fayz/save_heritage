// Reading-page controls. No 3D viewer or conversational assistant.
(() => {
  const decades = document.querySelector('[data-decades]');
  if (decades) decades.addEventListener('click', event => {
    const button = event.target.closest('button[data-decade]');
    if (!button) return;
    decades.querySelectorAll('button').forEach(b => b.setAttribute('aria-pressed', String(b === button)));
    document.querySelectorAll('.timeline > li').forEach(li => {
      li.hidden = button.dataset.decade !== 'all' && li.dataset.decade !== button.dataset.decade;
    });
  });
})();

(() => {
  'use strict';
  const menu = document.querySelector('.menu-toggle');
  const sidebar = document.querySelector('.sidebar');
  if (menu && sidebar) menu.addEventListener('click', () => {
    const expanded = menu.getAttribute('aria-expanded') !== 'true';
    menu.setAttribute('aria-expanded', String(expanded));
    sidebar.classList.toggle('is-open', expanded);
  });
  const search = document.querySelector('.search');
  const results = document.getElementById('search-results');
  if (search && results) search.addEventListener('submit', event => {
    event.preventDefault();
    const query = search.elements.query.value.trim();
    results.replaceChildren();
    if (!query) { results.hidden = true; return; }
    const words = query.toLocaleLowerCase().split(/\s+/).filter(Boolean);
    const matches = (window.MASTERY_SEARCH || []).map(entry => {
      const title = entry.title.toLocaleLowerCase();
      const text = entry.text.toLocaleLowerCase();
      const score = words.every(word => (title + ' ' + text).includes(word))
        ? words.reduce((total, word) => total + (title.includes(word) ? 6 : 1), 0) + (entry.written ? 2 : 0) : 0;
      return {entry, score};
    }).filter(match => match.score > 0).sort((a, b) => b.score - a.score);
    const heading = document.createElement('h2');
    heading.textContent = `${matches.length} result${matches.length === 1 ? '' : 's'} for “${query}”`;
    results.append(heading);
    const list = document.createElement('ol');
    matches.slice(0, 30).forEach(({entry}) => {
      const item = document.createElement('li');
      const link = document.createElement('a'); link.href = entry.url; link.textContent = entry.title;
      const state = document.createElement('span'); state.className = 'status'; state.textContent = entry.written ? entry.status : 'Planned';
      const snippet = document.createElement('p');
      const lower = entry.text.toLocaleLowerCase();
      const location = lower.indexOf(words[0]);
      const start = Math.max(0, location - 60);
      snippet.textContent = `${start ? '…' : ''}${entry.text.slice(start, start + 240)}${entry.text.length > start + 240 ? '…' : ''}`;
      item.append(link, state, snippet); list.append(item);
    });
    results.append(list);
    if (!matches.length) { const p = document.createElement('p'); p.textContent = 'Try a concept such as opportunity cost, valuation, equilibrium, or econometrics.'; results.append(p); }
    results.hidden = false; results.tabIndex = -1; results.focus();
  });
  let openedForPrint = [];
  function preparePrint() {
    if (openedForPrint.length) return;
    openedForPrint = [...document.querySelectorAll('details.solutions:not([open])')];
    openedForPrint.forEach(details => { details.open = true; });
  }
  function restorePrint() { openedForPrint.forEach(details => { details.open = false; }); openedForPrint = []; }
  window.addEventListener('beforeprint', preparePrint);
  window.addEventListener('afterprint', restorePrint);
  document.querySelectorAll('[data-print]').forEach(button => button.addEventListener('click', () => { preparePrint(); window.print(); }));
})();

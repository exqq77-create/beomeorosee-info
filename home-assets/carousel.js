const menu = document.querySelector('.menu-toggle');
const nav = document.querySelector('.nav');
menu?.addEventListener('click', () => {
  const expanded = menu.getAttribute('aria-expanded') === 'true';
  menu.setAttribute('aria-expanded', String(!expanded));
  nav?.classList.toggle('open', !expanded);
});
document.addEventListener('keydown', event => {
  if (event.key === 'Escape' && menu?.getAttribute('aria-expanded') === 'true') {
    menu.setAttribute('aria-expanded', 'false');
    nav?.classList.remove('open');
    menu.focus();
  }
});

const track = document.querySelector('#main-carousel');
if (track) {
  const cards = [...track.querySelectorAll('[data-carousel-card]')];
  const previous = document.querySelector('[data-carousel-direction="-1"]');
  const next = document.querySelector('[data-carousel-direction="1"]');
  const status = document.querySelector('.carousel-status');
  let frame = 0;
  let offsets = [];
  let maxScroll = 0;
  const current = () => {
    const left = track.scrollLeft;
    return offsets.reduce((best, offset, i) => Math.abs(offset - left) < Math.abs(offsets[best] - left) ? i : best, 0);
  };
  const update = () => {
    const first = track.scrollLeft <= 2;
    const last = track.scrollLeft >= maxScroll - 2;
    if (previous && previous.disabled !== first) previous.disabled = first;
    if (next && next.disabled !== last) next.disabled = last;
    const label = `${maxScroll > 2 && last ? cards.length : current() + 1} / ${cards.length}`;
    if (status && status.textContent !== label) status.textContent = label;
    frame = 0;
  };
  const measure = () => {
    const left = track.getBoundingClientRect().left;
    const scroll = track.scrollLeft;
    offsets = cards.map(card => card.getBoundingClientRect().left - left + scroll);
    maxScroll = Math.max(0, track.scrollWidth - track.clientWidth);
    update();
  };
  const go = index => {
    const target = offsets[Math.max(0, Math.min(cards.length - 1, index))];
    track.scrollTo({left: Math.min(maxScroll, target), behavior: matchMedia('(prefers-reduced-motion:reduce)').matches ? 'auto' : 'smooth'});
  };
  previous?.addEventListener('click', () => go(current() - 1));
  next?.addEventListener('click', () => go(current() + 1));
  track.addEventListener('keydown', event => {
    if (event.target !== track || maxScroll <= 2) return;
    const destinations = {ArrowLeft: current() - 1, ArrowRight: current() + 1, Home: 0, End: cards.length - 1};
    if (Object.hasOwn(destinations, event.key)) {
      event.preventDefault();
      go(destinations[event.key]);
    }
  });
  track.addEventListener('scroll', () => { if (!frame) frame = requestAnimationFrame(update); }, {passive: true});
  let resizeFrame = 0;
  window.addEventListener('resize', () => {
    if (!resizeFrame) resizeFrame = requestAnimationFrame(() => { resizeFrame = 0; measure(); });
  });
  measure();
}

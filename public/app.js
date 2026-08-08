const toc = document.querySelector('nav');
const marks = [...document.querySelectorAll('article > section[id]')];
const links = marks.map(section => toc.querySelector(`a[href="#${section.id}"]`));
let current = -1;

const atEnd = () =>
  innerHeight + scrollY >= document.documentElement.scrollHeight - 2;

const locate = () => {
  if (atEnd()) return marks.length - 1;
  const line = toc.getBoundingClientRect().bottom + 1;
  let found = -1;
  marks.forEach((section, i) => {
    if (section.getBoundingClientRect().top <= line) found = i;
  });
  return found;
};

const keepInView = link => {
  const bar = toc.getBoundingClientRect();
  const box = link.getBoundingClientRect();
  const pad = 24;
  if (box.left < bar.left + pad) toc.scrollLeft += box.left - bar.left - pad;
  else if (box.right > bar.right - pad) toc.scrollLeft += box.right - bar.right + pad;
};

const sync = () => {
  const next = locate();
  if (next === current) return;
  if (links[current]) links[current].removeAttribute('aria-current');
  current = next;
  if (links[current]) {
    links[current].setAttribute('aria-current', 'location');
    keepInView(links[current]);
  }
};

let queued = false;
const onScroll = () => {
  if (queued) return;
  queued = true;
  requestAnimationFrame(() => { queued = false; sync(); });
};

addEventListener('scroll', onScroll, { passive: true });
addEventListener('resize', onScroll);
sync();

document.querySelectorAll('.clip').forEach(clip => {
  const button = document.createElement('button');
  button.type = 'button';
  button.className = 'morebtn';
  button.textContent = 'Show more';
  button.setAttribute('aria-expanded', 'false');
  clip.append(button);
  clip.setAttribute('data-clip', '');

  button.addEventListener('click', () => {
    const open = clip.toggleAttribute('data-open');
    button.textContent = open ? 'Show less' : 'Show more';
    button.setAttribute('aria-expanded', String(open));
    if (!open) clip.scrollIntoView({ block: 'nearest' });
  });
});

document.querySelectorAll('[data-copy]').forEach(button => {
  const source = button.closest('.copyhead').nextElementSibling.querySelector('pre');
  button.addEventListener('click', async () => {
    try {
      await navigator.clipboard.writeText(source.textContent);
      button.textContent = 'Copied';
    } catch {
      button.textContent = 'Press ⌘C';
      getSelection().selectAllChildren(source);
    }
    setTimeout(() => { button.textContent = 'Copy'; }, 2000);
  });
});

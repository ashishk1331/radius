const toc = document.querySelector('nav');

const tidy = path => path.replace(/\/+$/, '') || '/';

const keepInView = link => {
  const bar = toc.getBoundingClientRect();
  const box = link.getBoundingClientRect();
  const pad = 24;
  if (box.left < bar.left + pad) toc.scrollLeft += box.left - bar.left - pad;
  else if (box.right > bar.right - pad) toc.scrollLeft += box.right - bar.right + pad;
};

const here = tidy(location.pathname);
const active = [...toc.querySelectorAll('a')].find(
  link => tidy(new URL(link.href).pathname) === here
);

if (active) {
  active.setAttribute('aria-current', 'page');
  keepInView(active);
}

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

const copies = (source, button) => {
  let revert;
  return async () => {
    try {
      await navigator.clipboard.writeText(source.textContent);
      button.textContent = 'Copied';
    } catch {
      button.textContent = 'Press ⌘C';
      getSelection().selectAllChildren(source);
    }
    clearTimeout(revert);
    revert = setTimeout(() => { button.textContent = 'Copy'; }, 2000);
  };
};

document.querySelectorAll('[data-copy]').forEach(button => {
  const source = button.closest('.copyhead').nextElementSibling.querySelector('pre');
  button.addEventListener('click', copies(source, button));
});

document.querySelectorAll('.panel > pre').forEach(source => {
  const panel = source.parentElement;
  if (panel.closest('.clip')) return;

  const button = document.createElement('button');
  button.type = 'button';
  button.className = 'copybtn corner';
  button.textContent = 'Copy';
  button.addEventListener('click', copies(source, button));

  panel.classList.add('snip');
  panel.append(button);
});

const header = document.querySelector('[data-header]');
const nav = document.querySelector('[data-nav]');
const navToggle = document.querySelector('[data-nav-toggle]');

const updateHeader = () => {
    header?.classList.toggle('is-scrolled', window.scrollY > 24);
};

updateHeader();
window.addEventListener('scroll', updateHeader, { passive: true });

navToggle?.addEventListener('click', () => {
    const open = nav?.classList.toggle('is-open') ?? false;
    navToggle.setAttribute('aria-expanded', String(open));
});

nav?.addEventListener('click', (event) => {
    if (event.target instanceof HTMLAnchorElement) {
        nav.classList.remove('is-open');
        navToggle?.setAttribute('aria-expanded', 'false');
    }
});

document.querySelectorAll('[data-copy]').forEach((button) => {
    button.addEventListener('click', async () => {
        const value = button.getAttribute('data-copy');
        const label = button.querySelector('[data-copy-label]');
        if (!value || !label) return;

        await navigator.clipboard.writeText(value);
        label.textContent = 'copied';
        window.setTimeout(() => { label.textContent = 'copy'; }, 1600);
    });
});

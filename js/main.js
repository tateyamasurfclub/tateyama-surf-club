// ============================================
// TATEYAMA SURF CLUB - Main JavaScript
// ============================================

document.addEventListener('DOMContentLoaded', () => {

  // --- Mobile Menu Toggle ---
  const hamburger = document.querySelector('.hamburger');
  const nav = document.querySelector('.nav');
  if (hamburger && nav) {
    hamburger.addEventListener('click', () => {
      hamburger.classList.toggle('active');
      nav.classList.toggle('active');
      document.body.style.overflow = nav.classList.contains('active') ? 'hidden' : '';
    });
    // Close menu on link click
    nav.querySelectorAll('.nav__link').forEach(link => {
      link.addEventListener('click', () => {
        hamburger.classList.remove('active');
        nav.classList.remove('active');
        document.body.style.overflow = '';
      });
    });
  }

  // --- Header scroll effect ---
  const header = document.querySelector('.header');
  if (header) {
    window.addEventListener('scroll', () => {
      header.classList.toggle('scrolled', window.scrollY > 50);
    });
  }

  // --- Scroll to top ---
  const scrollTopBtn = document.querySelector('.scroll-top');
  if (scrollTopBtn) {
    window.addEventListener('scroll', () => {
      scrollTopBtn.classList.toggle('visible', window.scrollY > 400);
    });
    scrollTopBtn.addEventListener('click', () => {
      window.scrollTo({ top: 0, behavior: 'smooth' });
    });
  }

  // --- FAQ Accordion ---
  document.querySelectorAll('.faq__question').forEach(btn => {
    btn.addEventListener('click', () => {
      const item = btn.closest('.faq__item');
      const isActive = item.classList.contains('active');
      // Close all
      document.querySelectorAll('.faq__item').forEach(i => i.classList.remove('active'));
      // Toggle clicked
      if (!isActive) item.classList.add('active');
    });
  });

  // --- Sodateru Slider ---
  const sliderImgs = document.querySelectorAll('.sodateru-slider__img');
  if (sliderImgs.length > 1) {
    let current = 0;
    setInterval(() => {
      sliderImgs[current].classList.remove('sodateru-slider__img--active');
      current = (current + 1) % sliderImgs.length;
      sliderImgs[current].classList.add('sodateru-slider__img--active');
    }, 5000);
  }

  // --- メールリンクの保険 ---
  // 「メールする」を押しても、スマホやパソコンにメールアプリが設定されていないと
  // 何も起きない（mailto: の仕様上どうにもならない）。
  // そこで押した瞬間にアドレスをコピーしておき、
  // アプリが開かなかった人でも貼り付けて送れるようにする。
  const mailLinks = document.querySelectorAll('a[href^="mailto:"]');
  if (mailLinks.length) {
    let toast;
    const showToast = (address) => {
      if (!toast) {
        toast = document.createElement('div');
        toast.className = 'copy-toast';
        toast.setAttribute('role', 'status');
        toast.setAttribute('aria-live', 'polite');
        document.body.appendChild(toast);
      }
      toast.innerHTML =
        '<strong>' + address + '</strong>' +
        '<span>メールアドレスをコピーしました。<br>' +
        'メールアプリが開かない場合は、貼り付けてお送りください。</span>';
      toast.classList.add('visible');
      clearTimeout(toast._timer);
      toast._timer = setTimeout(() => toast.classList.remove('visible'), 6000);
    };

    const copyText = (text) => {
      if (navigator.clipboard && window.isSecureContext) {
        return navigator.clipboard.writeText(text);
      }
      // 古いブラウザ向け
      const ta = document.createElement('textarea');
      ta.value = text;
      ta.setAttribute('readonly', '');
      ta.style.position = 'fixed';
      ta.style.opacity = '0';
      document.body.appendChild(ta);
      ta.select();
      try { document.execCommand('copy'); } catch (e) { /* コピー不可でも先へ進む */ }
      document.body.removeChild(ta);
      return Promise.resolve();
    };

    mailLinks.forEach(link => {
      link.addEventListener('click', () => {
        const address = link.getAttribute('href').replace(/^mailto:/, '').split('?')[0];
        copyText(address).catch(() => {}).then(() => showToast(address));
      });
    });
  }

  // --- Active nav link ---
  const currentPage = window.location.pathname.split('/').pop() || 'index.html';
  document.querySelectorAll('.nav__link').forEach(link => {
    const href = link.getAttribute('href');
    if (href === currentPage || (currentPage === '' && href === 'index.html')) {
      link.classList.add('nav__link--active');
    }
  });

});

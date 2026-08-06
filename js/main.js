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

  // --- お問い合わせフォーム ---
  // 送信先はGoogleフォーム。別ドメインのため送信結果を直接は読めないので、
  // 見えない枠(iframe)の読み込み完了をもって「送信できた」と判断する。
  const contactForm = document.getElementById('contact-form');
  const contactFrame = document.getElementById('contact-form-target');
  const contactThanks = document.getElementById('contact-thanks');
  if (contactForm && contactFrame && contactThanks) {
    const submitBtn = document.getElementById('contact-submit');

    // 他のページから contact.html?type=junior のように来たとき、
    // 「お問い合わせ種別」をあらかじめ選んでおく。
    // 選択肢の文言が変わっても壊れないよう、含まれる言葉で探す。
    const TYPE_KEYWORDS = {
      join: '入会',
      visit: '見学',
      junior: '普及部',
      event: 'イベント',
      media: '取材',
      sponsor: 'スポンサー',
      other: 'その他'
    };
    const wanted = new URLSearchParams(location.search).get('type');
    const categorySelect = document.getElementById('cf-category');
    if (wanted && categorySelect && TYPE_KEYWORDS[wanted]) {
      const keyword = TYPE_KEYWORDS[wanted];
      const hit = [...categorySelect.options]
        .find(o => o.value && o.value.indexOf(keyword) !== -1);
      if (hit) categorySelect.value = hit.value;
    }
    const againBtn = document.getElementById('contact-again');
    let sending = false;
    let timer = null;

    const finish = () => {
      clearTimeout(timer);
      sending = false;
      contactForm.hidden = true;
      contactThanks.hidden = false;
      contactThanks.scrollIntoView({ behavior: 'smooth', block: 'center' });
      contactForm.reset();
      submitBtn.disabled = false;
      submitBtn.textContent = '送信する';
    };

    contactForm.addEventListener('submit', () => {
      // 入力チェックはブラウザ標準に任せる。ここに来た時点で内容は妥当
      sending = true;
      submitBtn.disabled = true;
      submitBtn.textContent = '送信中…';
      // 通信が返らないまま固まるのを防ぐ
      clearTimeout(timer);
      timer = setTimeout(() => {
        if (!sending) return;
        sending = false;
        submitBtn.disabled = false;
        submitBtn.textContent = '送信する';
        alert('送信の確認が取れませんでした。\n'
            + 'お手数ですが jimukyoku.tateyamasc@gmail.com までメールでご連絡ください。');
      }, 15000);
    });

    contactFrame.addEventListener('load', () => {
      // ページ表示時にも1度発火するため、送信中のときだけ完了とみなす
      if (sending) finish();
    });

    if (againBtn) {
      againBtn.addEventListener('click', () => {
        contactThanks.hidden = true;
        contactForm.hidden = false;
        contactForm.scrollIntoView({ behavior: 'smooth', block: 'center' });
      });
    }
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

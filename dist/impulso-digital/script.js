/* ═══════════════════════════════════════════
   ULTRA Generated JS — Impulso Digital
   ═══════════════════════════════════════════ */
'use strict';

// ── Config (editable por ULTRA o por agentes) ──────────────────────────
const ULTRA_CONFIG = {
  clientName:  "Impulso Digital",
  niche:       "Agencia Digital",
  chatApiUrl:  null,  // Reemplazar con endpoint real: "/api/chat"
  contactUrl:  null,  // Reemplazar con endpoint real: "/api/contact"
};

// ── DOM Ready ──────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  initNav();
  initFAQ();
  initContactForm();
  initChat();
  initScrollAnimations();
});

// ── NAV ────────────────────────────────────────────────────────────────
function initNav() {
  const burger = document.querySelector('.nav__burger');
  const links  = document.querySelector('.nav__links');
  if (!burger || !links) return;

  burger.addEventListener('click', () => {
    const open = links.classList.toggle('open');
    burger.setAttribute('aria-expanded', open);
  });

  // Cerrar al hacer clic en enlace
  links.querySelectorAll('a').forEach(a => {
    a.addEventListener('click', () => {
      links.classList.remove('open');
      burger.setAttribute('aria-expanded', false);
    });
  });

  // Highlight activo
  const navLinks = links.querySelectorAll('a[href^="#"]');
  const observer = new IntersectionObserver(entries => {
    entries.forEach(e => {
      if (e.isIntersecting) {
        navLinks.forEach(l => l.removeAttribute('aria-current'));
        const id = e.target.id;
        const active = [...navLinks].find(l => l.getAttribute('href') === '#' + id);
        if (active) active.setAttribute('aria-current', 'page');
      }
    });
  }, { threshold: 0.5 });
  document.querySelectorAll('section[id]').forEach(s => observer.observe(s));
}

// ── FAQ ────────────────────────────────────────────────────────────────
function initFAQ() {
  document.querySelectorAll('.faq__question').forEach(btn => {
    btn.addEventListener('click', () => {
      const answer  = document.getElementById(btn.getAttribute('aria-controls'));
      const open    = btn.getAttribute('aria-expanded') === 'true';
      // Cerrar todas
      document.querySelectorAll('.faq__question').forEach(b => {
        b.setAttribute('aria-expanded', 'false');
        document.getElementById(b.getAttribute('aria-controls'))?.removeAttribute('hidden');
        document.getElementById(b.getAttribute('aria-controls'))?.setAttribute('hidden', '');
      });
      // Abrir si no estaba abierto
      if (!open && answer) {
        btn.setAttribute('aria-expanded', 'true');
        answer.removeAttribute('hidden');
      }
    });
  });
}

// ── CONTACT FORM (multi-step) ──────────────────────────────────────────
function initContactForm() {
  const form = document.getElementById('contact-form');
  if (!form) return;

  const steps   = form.querySelectorAll('.form__step');
  let current   = 0;

  function showStep(n) {
    steps.forEach((s, i) => {
      if (i === n) s.removeAttribute('hidden'); else s.setAttribute('hidden', '');
    });
    current = n;
  }

  form.querySelectorAll('.form__next').forEach(btn => {
    btn.addEventListener('click', () => {
      if (validateStep(steps[current])) showStep(current + 1);
    });
  });

  form.querySelectorAll('.form__prev').forEach(btn => {
    btn.addEventListener('click', () => showStep(current - 1));
  });

  form.addEventListener('submit', async e => {
    e.preventDefault();
    if (!validateStep(steps[current])) return;

    const data = Object.fromEntries(new FormData(form));
    data._meta = { client: ULTRA_CONFIG.clientName, niche: ULTRA_CONFIG.niche, ts: Date.now() };

    try {
      if (ULTRA_CONFIG.contactUrl) {
        await fetch(ULTRA_CONFIG.contactUrl, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(data)
        });
      }
    } catch (_) {/* silencioso — aún mostramos éxito */}

    showStep(2);
  });

  function validateStep(step) {
    let ok = true;
    step.querySelectorAll('[required]').forEach(field => {
      const err = field.parentElement.querySelector('.form__error');
      field.classList.remove('error');
      if (err) err.textContent = '';
      if (!field.value.trim()) {
        field.classList.add('error');
        if (err) err.textContent = 'Este campo es obligatorio.';
        ok = false;
      } else if (field.type === 'email' && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(field.value)) {
        field.classList.add('error');
        if (err) err.textContent = 'Email no válido.';
        ok = false;
      }
    });
    return ok;
  }
}

// ── CHATBOT ────────────────────────────────────────────────────────────
function initChat() {
  const toggle   = document.getElementById('chat-toggle');
  const box      = document.getElementById('chat-box');
  const closeBtn = document.getElementById('chat-close');
  const form     = document.getElementById('chat-form');
  const input    = document.getElementById('chat-input');
  const messages = document.getElementById('chat-messages');
  if (!toggle || !box) return;

  const BOT_INTRO = `¡Hola! Soy el asistente de ${ULTRA_CONFIG.clientName}. ¿En qué puedo ayudarte hoy?`;

  function openChat() {
    box.removeAttribute('hidden');
    toggle.setAttribute('aria-expanded', 'true');
    if (!messages.children.length) addMsg(BOT_INTRO, 'bot');
    input.focus();
  }
  function closeChat() {
    box.setAttribute('hidden', '');
    toggle.setAttribute('aria-expanded', 'false');
    toggle.focus();
  }

  toggle.addEventListener('click', () => box.hasAttribute('hidden') ? openChat() : closeChat());
  closeBtn?.addEventListener('click', closeChat);

  // Cerrar con Escape
  box.addEventListener('keydown', e => { if (e.key === 'Escape') closeChat(); });

  form?.addEventListener('submit', async e => {
    e.preventDefault();
    const text = input.value.trim();
    if (!text) return;
    addMsg(text, 'user');
    input.value = '';
    const typingEl = addTyping();
    const reply = await getReply(text);
    typingEl.remove();
    addMsg(reply, 'bot');
  });

  function addMsg(text, from) {
    const el = document.createElement('div');
    el.className = `chat__msg chat__msg--${from}`;
    el.textContent = text;
    messages.appendChild(el);
    messages.scrollTop = messages.scrollHeight;
    return el;
  }

  function addTyping() {
    const el = document.createElement('div');
    el.className = 'chat__typing';
    el.innerHTML = '<span></span><span></span><span></span>';
    messages.appendChild(el);
    messages.scrollTop = messages.scrollHeight;
    return el;
  }

  async function getReply(userMsg) {
    if (ULTRA_CONFIG.chatApiUrl) {
      try {
        const res = await fetch(ULTRA_CONFIG.chatApiUrl, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            message: userMsg,
            context: { client: ULTRA_CONFIG.clientName, niche: ULTRA_CONFIG.niche }
          })
        });
        if (res.ok) {
          const data = await res.json();
          return data.reply || data.message || 'Gracias por tu mensaje.';
        }
      } catch (_) {}
    }
    // Fallback local
    return localReply(userMsg);
  }

  function localReply(msg) {
    const m = msg.toLowerCase();
    if (m.includes('precio') || m.includes('coste') || m.includes('cuánto')) return 'Tenemos planes desde 49€/mes. Puedes verlos más abajo en la página o contactarnos para un presupuesto personalizado.';
    if (m.includes('hola') || m.includes('buenas')) return `¡Hola! Encantado de atenderte. ¿Tienes alguna pregunta sobre ${ULTRA_CONFIG.clientName}?`;
    if (m.includes('contacto') || m.includes('llamar') || m.includes('email')) return 'Puedes contactarnos usando el formulario de la sección "Hablemos" o escribiéndonos directamente. ¡Respondemos en menos de 24h!';
    if (m.includes('gracias')) return '¡De nada! Estamos aquí para lo que necesites.';
    return `Gracias por tu pregunta. Un miembro del equipo de ${ULTRA_CONFIG.clientName} te responderá en breve. Mientras tanto, puedes usar el formulario de contacto.`;
  }
}

// ── SCROLL ANIMATIONS ──────────────────────────────────────────────────
function initScrollAnimations() {
  if (!('IntersectionObserver' in window)) return;
  const targets = document.querySelectorAll('.feature-card, .testimonial-card, .plan-card, .method-step, .portfolio-card, .product-card');
  const obs = new IntersectionObserver((entries) => {
    entries.forEach(e => {
      if (e.isIntersecting) {
        e.target.style.opacity = '1';
        e.target.style.transform = 'translateY(0)';
        obs.unobserve(e.target);
      }
    });
  }, { threshold: 0.1 });
  targets.forEach(t => {
    t.style.opacity = '0';
    t.style.transform = 'translateY(20px)';
    t.style.transition = 'opacity .5s ease, transform .5s ease';
    obs.observe(t);
  });
}

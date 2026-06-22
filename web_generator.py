#!/usr/bin/env python3
"""
ULTRA Web Generator — Núcleo del generador de webs.
Ruta destino: /opt/ultra/web_generator.py

Pipeline:
  1. Recibe payload de evento (lead/cliente + nicho + prompt)
  2. Selecciona estrategia de nicho (componentes, paleta, copy)
  3. Renderiza HTML/CSS/JS mediante plantillas modulares
  4. Valida el output (estructura mínima, tamaño, encoding)
  5. Persiste en /opt/ultra/websites/<web_id>/
  6. Registra en websites_registry.json
  7. Publica evento web_generated en el bus
"""

import json
import os
import re
import shutil
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# ── Rutas ──────────────────────────────────────────────────────────────────
BASE_DIR        = Path("/opt/ultra")
WEBSITES_DIR    = BASE_DIR / "websites"
REGISTRY_FILE   = BASE_DIR / "websites_registry.json"
TEMPLATES_DIR   = BASE_DIR / "web_templates"

# ── Configuración de nichos ────────────────────────────────────────────────
NICHE_CONFIG = {
    "saas_b2b": {
        "label": "SaaS B2B",
        "palette": {"primary": "#2563EB", "accent": "#7C3AED", "dark": "#0F172A", "light": "#F8FAFC"},
        "hero_cta": "Solicitar demo gratuita",
        "sections": ["hero", "features", "social_proof", "pricing", "faq", "cta_bottom"],
        "tone": "profesional y directo",
        "value_props": 6,
        "testimonials": 3,
    },
    "ecommerce": {
        "label": "E-commerce",
        "palette": {"primary": "#DC2626", "accent": "#F59E0B", "dark": "#111827", "light": "#FAFAFA"},
        "hero_cta": "Comprar ahora",
        "sections": ["hero", "featured_products", "benefits", "testimonials", "newsletter"],
        "tone": "persuasivo y cercano",
        "value_props": 4,
        "testimonials": 4,
    },
    "coaching": {
        "label": "Coaching / Consultoría",
        "palette": {"primary": "#059669", "accent": "#F59E0B", "dark": "#1C1C1E", "light": "#F9FAFB"},
        "hero_cta": "Reservar sesión gratuita",
        "sections": ["hero", "about", "methodology", "testimonials", "packages", "cta_bottom"],
        "tone": "empático y transformador",
        "value_props": 4,
        "testimonials": 5,
    },
    "agencia": {
        "label": "Agencia Digital",
        "palette": {"primary": "#7C3AED", "accent": "#EC4899", "dark": "#09090B", "light": "#FAFAFA"},
        "hero_cta": "Ver nuestros proyectos",
        "sections": ["hero", "services", "portfolio", "process", "testimonials", "contact"],
        "tone": "creativo y sofisticado",
        "value_props": 5,
        "testimonials": 3,
    },
    "local_business": {
        "label": "Negocio Local",
        "palette": {"primary": "#0284C7", "accent": "#F97316", "dark": "#1E293B", "light": "#F8FAFC"},
        "hero_cta": "Llamar ahora",
        "sections": ["hero", "services", "about", "testimonials", "location", "contact"],
        "tone": "cercano y de confianza",
        "value_props": 4,
        "testimonials": 4,
    },
}
DEFAULT_NICHE = "saas_b2b"


# ── Clase principal ────────────────────────────────────────────────────────
class UltraWebGenerator:
    def __init__(self):
        WEBSITES_DIR.mkdir(parents=True, exist_ok=True)
        self._load_registry()

    def _load_registry(self):
        if REGISTRY_FILE.exists():
            with open(REGISTRY_FILE, encoding="utf-8") as f:
                self.registry = json.load(f)
        else:
            self.registry = {"websites": []}

    def _save_registry(self):
        with open(REGISTRY_FILE, "w", encoding="utf-8") as f:
            json.dump(self.registry, f, indent=2, ensure_ascii=False)

    def generate(self, payload: dict) -> dict:
        """
        Genera una web completa a partir de un payload.

        Payload esperado:
        {
            "client_name": "Acme Corp",
            "niche": "saas_b2b",          # ver NICHE_CONFIG
            "business_desc": "...",
            "tagline": "...",
            "offer": "...",
            "contact_email": "...",
            "contact_phone": "",           # opcional
            "website_url": "",             # opcional (para og:url)
            "features": ["f1", "f2"],      # lista de features/servicios
            "testimonials": [              # opcional
                {"name": "...", "role": "...", "text": "..."}
            ],
            "pricing": [                   # opcional
                {"name": "Starter", "price": "49€", "features": [...]}
            ],
            "lang": "es"                   # es | en
        }
        """
        web_id  = str(uuid.uuid4())[:12]
        niche   = payload.get("niche", DEFAULT_NICHE)
        config  = NICHE_CONFIG.get(niche, NICHE_CONFIG[DEFAULT_NICHE])
        web_dir = WEBSITES_DIR / web_id
        web_dir.mkdir(parents=True, exist_ok=True)

        ctx = self._build_context(web_id, payload, config)

        html = render_html(ctx, config)
        css  = render_css(ctx, config)
        js   = render_js(ctx, config)
        meta = self._build_meta(web_id, payload, config)

        (web_dir / "index.html").write_text(html, encoding="utf-8")
        (web_dir / "style.css").write_text(css,  encoding="utf-8")
        (web_dir / "script.js").write_text(js,   encoding="utf-8")
        (web_dir / "meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")

        # Validación estructural
        validation = validate_web_output(web_dir)

        # Registro
        record = {
            "web_id":      web_id,
            "client_name": payload.get("client_name", ""),
            "niche":       niche,
            "prompt_hash": hash(str(payload)),
            "path":        str(web_dir),
            "created_at":  datetime.now(timezone.utc).isoformat(),
            "status":      "validated" if validation["valid"] else "failed_validation",
            "validation":  validation,
        }
        self.registry["websites"].append(record)
        self._save_registry()

        return {"web_id": web_id, "path": str(web_dir), "valid": validation["valid"], "errors": validation.get("errors", [])}

    def _build_context(self, web_id: str, payload: dict, config: dict) -> dict:
        """Construye el contexto de renderizado."""
        return {
            "web_id":       web_id,
            "lang":         payload.get("lang", "es"),
            "client_name":  payload.get("client_name", "Tu Empresa"),
            "tagline":      payload.get("tagline", "Soluciones que marcan la diferencia"),
            "business_desc":payload.get("business_desc", ""),
            "offer":        payload.get("offer", ""),
            "features":     payload.get("features", ["Feature 1", "Feature 2", "Feature 3"]),
            "testimonials": payload.get("testimonials", _default_testimonials(config["testimonials"])),
            "pricing":      payload.get("pricing", []),
            "contact_email":payload.get("contact_email", "hola@empresa.com"),
            "contact_phone":payload.get("contact_phone", ""),
            "website_url":  payload.get("website_url", ""),
            "hero_cta":     config["hero_cta"],
            "palette":      config["palette"],
            "niche_label":  config["label"],
            "sections":     config["sections"],
            "year":         datetime.now().year,
        }

    def _build_meta(self, web_id: str, payload: dict, config: dict) -> dict:
        return {
            "web_id":        web_id,
            "schema_version":"1.0",
            "generated_at":  datetime.now(timezone.utc).isoformat(),
            "generator":     "ULTRA Web Generator v1.0",
            "niche":         payload.get("niche", DEFAULT_NICHE),
            "niche_label":   config["label"],
            "client_name":   payload.get("client_name", ""),
            "sections":      config["sections"],
            "palette":       config["palette"],
            "prompt_payload":payload,
        }


# ── Defaults ───────────────────────────────────────────────────────────────
def _default_testimonials(n: int) -> list:
    pool = [
        {"name": "Carlos M.", "role": "CEO, StartupX", "text": "Resultados increíbles desde el primer mes."},
        {"name": "Laura P.", "role": "Directora de Marketing", "text": "La mejor inversión que hemos hecho este año."},
        {"name": "Andrés R.", "role": "Emprendedor", "text": "Superó todas mis expectativas. 100% recomendado."},
        {"name": "Sofía T.", "role": "Responsable IT", "text": "Implementación rápida y soporte excelente."},
        {"name": "Miguel F.", "role": "CTO", "text": "Escalable, robusto y el equipo es de primera."},
    ]
    return pool[:n]


# ── Validador de output ────────────────────────────────────────────────────
def validate_web_output(web_dir: Path) -> dict:
    errors = []
    required = ["index.html", "style.css", "script.js", "meta.json"]
    for f in required:
        path = web_dir / f
        if not path.exists():
            errors.append(f"Falta {f}")
        elif path.stat().st_size < 50:
            errors.append(f"{f} demasiado pequeño ({path.stat().st_size} bytes)")

    html_path = web_dir / "index.html"
    if html_path.exists():
        content = html_path.read_text(encoding="utf-8")
        for tag in ["<!DOCTYPE html>", "<html", "<head>", "<body", "</html>"]:
            if tag not in content:
                errors.append(f"HTML: falta {tag}")
        if "<title>" not in content:
            errors.append("HTML: falta <title>")

    return {"valid": len(errors) == 0, "errors": errors, "checked_at": datetime.now(timezone.utc).isoformat()}


# ══════════════════════════════════════════════════════════════════════════
#  RENDERIZADO HTML
# ══════════════════════════════════════════════════════════════════════════
def render_html(ctx: dict, config: dict) -> str:
    sections_html = "\n".join(_render_section(s, ctx, config) for s in ctx["sections"])

    return f"""<!DOCTYPE html>
<html lang="{ctx['lang']}" data-web-id="{ctx['web_id']}">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta name="description" content="{_esc(ctx['business_desc'][:160] if ctx['business_desc'] else ctx['tagline'])}">
  <meta property="og:title" content="{_esc(ctx['client_name'])}">
  <meta property="og:description" content="{_esc(ctx['tagline'])}">
  <meta property="og:type" content="website">
  {"<meta property='og:url' content='" + ctx['website_url'] + "'>" if ctx.get('website_url') else ""}
  <title>{_esc(ctx['client_name'])} — {_esc(ctx['tagline'])}</title>
  <link rel="stylesheet" href="style.css">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
</head>
<body>

<!-- ░░ NAV ░░ -->
<header class="nav" role="banner">
  <div class="container nav__inner">
    <a href="#" class="nav__logo" aria-label="Inicio">{_esc(ctx['client_name'])}</a>
    <nav class="nav__links" aria-label="Navegación principal">
      <a href="#features">Servicios</a>
      {"<a href='#pricing'>Precios</a>" if "pricing" in ctx["sections"] else ""}
      <a href="#testimonials">Clientes</a>
      <a href="#contact">Contacto</a>
    </nav>
    <a href="#contact" class="btn btn--primary nav__cta">{_esc(ctx['hero_cta'])}</a>
    <button class="nav__burger" aria-label="Menú" aria-expanded="false" aria-controls="nav-links">
      <span></span><span></span><span></span>
    </button>
  </div>
</header>

<main id="main-content">
{sections_html}
</main>

<!-- ░░ FOOTER ░░ -->
<footer class="footer" role="contentinfo">
  <div class="container footer__inner">
    <div class="footer__brand">
      <span class="footer__logo">{_esc(ctx['client_name'])}</span>
      <p class="footer__desc">{_esc(ctx['tagline'])}</p>
    </div>
    <div class="footer__contact">
      {"<a href='mailto:" + ctx['contact_email'] + "' class='footer__link'>" + ctx['contact_email'] + "</a>" if ctx.get('contact_email') else ""}
      {"<a href='tel:" + ctx['contact_phone'] + "' class='footer__link'>" + ctx['contact_phone'] + "</a>" if ctx.get('contact_phone') else ""}
    </div>
    <p class="footer__legal">&copy; {ctx['year']} {_esc(ctx['client_name'])}. Todos los derechos reservados.</p>
  </div>
</footer>

<!-- ░░ CHATBOT WIDGET ░░ -->
<div id="ultra-chat" class="chat" aria-live="polite" aria-label="Chat de asistencia" data-niche="{ctx['niche_label']}" data-client="{_esc(ctx['client_name'])}">
  <button class="chat__toggle" id="chat-toggle" aria-expanded="false" aria-controls="chat-box" title="Abrir chat">
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
      <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
    </svg>
  </button>
  <div class="chat__box" id="chat-box" role="dialog" aria-modal="false" aria-label="Asistente virtual" hidden>
    <div class="chat__header">
      <span>Asistente de {_esc(ctx['client_name'])}</span>
      <button class="chat__close" id="chat-close" aria-label="Cerrar chat">&times;</button>
    </div>
    <div class="chat__messages" id="chat-messages" role="log" aria-live="polite"></div>
    <form class="chat__form" id="chat-form" novalidate>
      <input type="text" id="chat-input" class="chat__input" placeholder="Escribe tu pregunta..." aria-label="Mensaje" autocomplete="off" required>
      <button type="submit" class="chat__send btn btn--primary" aria-label="Enviar">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
          <line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/>
        </svg>
      </button>
    </form>
  </div>
</div>

<script src="script.js" defer></script>
</body>
</html>"""


def _render_section(section: str, ctx: dict, config: dict) -> str:
    dispatch = {
        "hero":              _section_hero,
        "features":          _section_features,
        "social_proof":      _section_social_proof,
        "pricing":           _section_pricing,
        "faq":               _section_faq,
        "cta_bottom":        _section_cta_bottom,
        "testimonials":      _section_testimonials,
        "about":             _section_about,
        "methodology":       _section_methodology,
        "packages":          _section_packages,
        "services":          _section_services,
        "portfolio":         _section_portfolio,
        "process":           _section_process,
        "contact":           _section_contact,
        "location":          _section_location,
        "newsletter":        _section_newsletter,
        "featured_products": _section_featured_products,
        "benefits":          _section_benefits,
    }
    fn = dispatch.get(section)
    return fn(ctx, config) if fn else f"<!-- Section {section} not implemented -->"


# ── Secciones ──────────────────────────────────────────────────────────────
def _section_hero(ctx, cfg):
    return f"""
<section class="hero section" id="hero" aria-labelledby="hero-title">
  <div class="container hero__inner">
    <div class="hero__content">
      <div class="hero__badge animate-fade-in">✦ {_esc(cfg['label'])}</div>
      <h1 class="hero__title animate-slide-up" id="hero-title">{_esc(ctx['tagline'])}</h1>
      <p class="hero__desc animate-fade-in">{_esc(ctx['business_desc'] or 'Descubre cómo podemos transformar tu negocio.')}</p>
      <div class="hero__actions animate-fade-in">
        <a href="#contact" class="btn btn--primary btn--lg">{_esc(ctx['hero_cta'])}</a>
        <a href="#features" class="btn btn--ghost btn--lg">Saber más</a>
      </div>
      <div class="hero__trust">
        <span class="hero__trust-item">✓ Sin compromisos</span>
        <span class="hero__trust-item">✓ Respuesta en 24h</span>
        <span class="hero__trust-item">✓ Resultados garantizados</span>
      </div>
    </div>
    <div class="hero__visual" aria-hidden="true">
      <div class="hero__card">
        <div class="hero__card-metric"><span class="metric-value">+127%</span><span class="metric-label">Crecimiento promedio</span></div>
        <div class="hero__card-metric"><span class="metric-value">98%</span><span class="metric-label">Satisfacción clientes</span></div>
        <div class="hero__card-metric"><span class="metric-value">2.4x</span><span class="metric-label">ROI medio</span></div>
      </div>
    </div>
  </div>
</section>"""


def _section_features(ctx, cfg):
    items = ""
    for i, f in enumerate(ctx["features"]):
        icon = ["⚡", "🎯", "🔒", "📊", "🚀", "💡"][i % 6]
        items += f"""
    <article class="feature-card animate-fade-in" style="--delay:{i*0.1}s">
      <div class="feature-card__icon" aria-hidden="true">{icon}</div>
      <h3 class="feature-card__title">{_esc(str(f))}</h3>
      <p class="feature-card__desc">Diseñado para maximizar tu eficiencia y resultados desde el primer día.</p>
    </article>"""
    return f"""
<section class="features section" id="features" aria-labelledby="features-title">
  <div class="container">
    <header class="section__header">
      <h2 class="section__title" id="features-title">Por qué elegirnos</h2>
      <p class="section__subtitle">Todo lo que necesitas para llevar tu negocio al siguiente nivel</p>
    </header>
    <div class="features__grid">{items}
    </div>
  </div>
</section>"""


def _section_social_proof(ctx, cfg):
    logos = ["", "", "", ""]  # placeholders
    items = "".join(f'<div class="proof__logo" aria-label="Cliente {i+1}"><span>Cliente {i+1}</span></div>' for i in range(4))
    return f"""
<section class="social-proof section--sm" aria-label="Empresas que confían en nosotros">
  <div class="container">
    <p class="proof__label">Con la confianza de líderes del sector</p>
    <div class="proof__logos">{items}</div>
  </div>
</section>"""


def _section_pricing(ctx, cfg):
    if not ctx.get("pricing"):
        plans = [
            {"name": "Starter", "price": "49€", "period": "/mes", "features": ["5 usuarios", "10 GB", "Soporte email"], "highlight": False},
            {"name": "Pro", "price": "129€", "period": "/mes", "features": ["25 usuarios", "100 GB", "Soporte prioritario", "API access"], "highlight": True},
            {"name": "Enterprise", "price": "Consultar", "period": "", "features": ["Ilimitado", "SLA dedicado", "Onboarding personalizado", "Integraciones custom"], "highlight": False},
        ]
    else:
        plans = ctx["pricing"]

    cards = ""
    for p in plans:
        hl = p.get("highlight", False)
        feats = "".join(f'<li class="plan__feature">✓ {_esc(str(f))}</li>' for f in p.get("features", []))
        cards += f"""
    <div class="plan-card {'plan-card--highlight' if hl else ''}" {'aria-label="Más popular"' if hl else ''}>
      {"<div class='plan-card__badge'>Más popular</div>" if hl else ""}
      <h3 class="plan-card__name">{_esc(str(p.get('name','')))}</h3>
      <div class="plan-card__price">
        <span class="plan-card__amount">{_esc(str(p.get('price','')))}</span>
        <span class="plan-card__period">{_esc(str(p.get('period','')))}</span>
      </div>
      <ul class="plan-card__features" aria-label="Características del plan">{feats}</ul>
      <a href="#contact" class="btn {'btn--primary' if hl else 'btn--outline'} plan-card__cta">Empezar ahora</a>
    </div>"""
    return f"""
<section class="pricing section" id="pricing" aria-labelledby="pricing-title">
  <div class="container">
    <header class="section__header">
      <h2 class="section__title" id="pricing-title">Planes y precios</h2>
      <p class="section__subtitle">Flexible y transparente. Sin costes ocultos.</p>
    </header>
    <div class="pricing__grid">{cards}
    </div>
  </div>
</section>"""


def _section_faq(ctx, cfg):
    faqs = [
        ("¿Cuánto tiempo tarda la implementación?", "La mayoría de nuestros clientes están operativos en menos de 48 horas. Nuestro equipo te guía en cada paso."),
        ("¿Ofrecéis soporte en español?", "Sí, todo nuestro soporte es en español. Disponible por email, chat y teléfono según el plan."),
        ("¿Puedo cancelar en cualquier momento?", "Por supuesto. Sin permanencias ni penalizaciones. Tu confianza es nuestra prioridad."),
        ("¿Mis datos están seguros?", "Cumplimos con RGPD y utilizamos cifrado de extremo a extremo para proteger toda tu información."),
    ]
    items = ""
    for i, (q, a) in enumerate(faqs):
        items += f"""
    <div class="faq__item" data-faq="{i}">
      <button class="faq__question" aria-expanded="false" aria-controls="faq-answer-{i}">
        {_esc(q)}
        <span class="faq__icon" aria-hidden="true">+</span>
      </button>
      <div class="faq__answer" id="faq-answer-{i}" role="region" hidden>
        <p>{_esc(a)}</p>
      </div>
    </div>"""
    return f"""
<section class="faq section" id="faq" aria-labelledby="faq-title">
  <div class="container faq__inner">
    <header class="section__header">
      <h2 class="section__title" id="faq-title">Preguntas frecuentes</h2>
    </header>
    <div class="faq__list" role="list">{items}
    </div>
  </div>
</section>"""


def _section_cta_bottom(ctx, cfg):
    return f"""
<section class="cta-bottom section" aria-labelledby="cta-title">
  <div class="container cta-bottom__inner">
    <h2 class="cta-bottom__title" id="cta-title">¿Listo para empezar?</h2>
    <p class="cta-bottom__subtitle">Únete a cientos de empresas que ya confían en nosotros.</p>
    <a href="#contact" class="btn btn--white btn--lg">{_esc(ctx['hero_cta'])}</a>
  </div>
</section>"""


def _section_testimonials(ctx, cfg):
    cards = ""
    for t in ctx["testimonials"]:
        cards += f"""
    <article class="testimonial-card">
      <div class="testimonial-card__stars" aria-label="5 estrellas">★★★★★</div>
      <blockquote class="testimonial-card__text">"{_esc(str(t.get('text','')))}"</blockquote>
      <footer class="testimonial-card__author">
        <div class="testimonial-card__avatar" aria-hidden="true">{str(t.get('name',''))[:1]}</div>
        <div>
          <cite class="testimonial-card__name">{_esc(str(t.get('name','')))}</cite>
          <span class="testimonial-card__role">{_esc(str(t.get('role','')))}</span>
        </div>
      </footer>
    </article>"""
    return f"""
<section class="testimonials section" id="testimonials" aria-labelledby="testimonials-title">
  <div class="container">
    <header class="section__header">
      <h2 class="section__title" id="testimonials-title">Lo que dicen nuestros clientes</h2>
    </header>
    <div class="testimonials__grid">{cards}
    </div>
  </div>
</section>"""


def _section_about(ctx, cfg):
    return f"""
<section class="about section" id="about" aria-labelledby="about-title">
  <div class="container about__inner">
    <div class="about__content">
      <h2 class="section__title" id="about-title">Sobre nosotros</h2>
      <p class="about__text">{_esc(ctx['business_desc'] or 'Somos un equipo apasionado dedicado a transformar negocios.')}</p>
      <p class="about__text">Con años de experiencia en el sector, hemos ayudado a cientos de clientes a alcanzar sus metas.</p>
      <a href="#contact" class="btn btn--primary">Trabajemos juntos</a>
    </div>
    <div class="about__stats" aria-label="Estadísticas">
      <div class="stat"><span class="stat__num">+500</span><span class="stat__label">Clientes satisfechos</span></div>
      <div class="stat"><span class="stat__num">8 años</span><span class="stat__label">De experiencia</span></div>
      <div class="stat"><span class="stat__num">98%</span><span class="stat__label">Tasa de retención</span></div>
    </div>
  </div>
</section>"""


def _section_methodology(ctx, cfg):
    steps = [("Diagnóstico", "Analizamos tu situación actual y objetivos específicos."),
             ("Estrategia", "Diseñamos un plan personalizado para tu negocio."),
             ("Implementación", "Ejecutamos el plan con seguimiento semanal."),
             ("Resultados", "Medimos, iteramos y escalamos los logros.")]
    items = "".join(f'<div class="method-step"><div class="method-step__num">{i+1}</div><h3>{t}</h3><p>{d}</p></div>' for i,(t,d) in enumerate(steps))
    return f"""
<section class="methodology section" id="methodology" aria-labelledby="method-title">
  <div class="container">
    <header class="section__header">
      <h2 class="section__title" id="method-title">Nuestra metodología</h2>
    </header>
    <div class="methodology__steps">{items}</div>
  </div>
</section>"""


def _section_packages(ctx, cfg):
    return _section_pricing(ctx, cfg).replace('id="pricing"', 'id="packages"').replace('id="pricing-title"', 'id="packages-title"').replace("Planes y precios", "Paquetes de trabajo")


def _section_services(ctx, cfg):
    return _section_features(ctx, cfg).replace('id="features"', 'id="services"').replace("Por qué elegirnos", "Nuestros servicios")


def _section_portfolio(ctx, cfg):
    projects = [f"Proyecto {i+1}" for i in range(3)]
    cards = "".join(f'<article class="portfolio-card"><div class="portfolio-card__img" aria-hidden="true"></div><h3 class="portfolio-card__title">{p}</h3><p>Solución personalizada para cliente del sector.</p></article>' for p in projects)
    return f"""
<section class="portfolio section" id="portfolio" aria-labelledby="portfolio-title">
  <div class="container">
    <header class="section__header">
      <h2 class="section__title" id="portfolio-title">Nuestro portfolio</h2>
    </header>
    <div class="portfolio__grid">{cards}</div>
  </div>
</section>"""


def _section_process(ctx, cfg):
    return _section_methodology(ctx, cfg).replace('id="methodology"', 'id="process"').replace("Nuestra metodología", "Cómo trabajamos")


def _section_contact(ctx, cfg):
    phone_field = f'<a href="tel:{ctx["contact_phone"]}" class="contact__phone">{ctx["contact_phone"]}</a>' if ctx.get("contact_phone") else ""
    return f"""
<section class="contact section" id="contact" aria-labelledby="contact-title">
  <div class="container contact__inner">
    <header class="section__header">
      <h2 class="section__title" id="contact-title">Hablemos</h2>
      <p class="section__subtitle">Cuéntanos tu proyecto. Respondemos en menos de 24 horas.</p>
    </header>
    <div class="contact__layout">
      <div class="contact__info">
        <a href="mailto:{ctx['contact_email']}" class="contact__email">{ctx['contact_email']}</a>
        {phone_field}
      </div>
      <form class="contact__form" id="contact-form" novalidate aria-label="Formulario de contacto">
        <div class="form__step active" data-step="1">
          <div class="form__group">
            <label for="cf-name" class="form__label">Nombre *</label>
            <input type="text" id="cf-name" name="name" class="form__input" required aria-required="true" autocomplete="name">
            <span class="form__error" aria-live="polite"></span>
          </div>
          <div class="form__group">
            <label for="cf-email" class="form__label">Email *</label>
            <input type="email" id="cf-email" name="email" class="form__input" required aria-required="true" autocomplete="email">
            <span class="form__error" aria-live="polite"></span>
          </div>
          <button type="button" class="btn btn--primary form__next">Siguiente →</button>
        </div>
        <div class="form__step" data-step="2" hidden>
          <div class="form__group">
            <label for="cf-company" class="form__label">Empresa</label>
            <input type="text" id="cf-company" name="company" class="form__input" autocomplete="organization">
          </div>
          <div class="form__group">
            <label for="cf-message" class="form__label">¿Cómo podemos ayudarte? *</label>
            <textarea id="cf-message" name="message" class="form__textarea" rows="4" required aria-required="true" placeholder="Cuéntanos tu proyecto..."></textarea>
            <span class="form__error" aria-live="polite"></span>
          </div>
          <div class="form__actions">
            <button type="button" class="btn btn--ghost form__prev">← Atrás</button>
            <button type="submit" class="btn btn--primary">Enviar mensaje</button>
          </div>
        </div>
        <div class="form__step" data-step="3" hidden>
          <div class="form__success">
            <div class="form__success-icon" aria-hidden="true">✓</div>
            <h3>¡Mensaje enviado!</h3>
            <p>Te contactaremos en menos de 24 horas.</p>
          </div>
        </div>
      </form>
    </div>
  </div>
</section>"""


def _section_location(ctx, cfg):
    return f"""
<section class="location section--sm" id="location" aria-labelledby="location-title">
  <div class="container">
    <h2 class="section__title" id="location-title">Dónde estamos</h2>
    <div class="location__map-placeholder" aria-label="Mapa de ubicación">
      <span>Mapa disponible próximamente</span>
    </div>
  </div>
</section>"""


def _section_newsletter(ctx, cfg):
    return f"""
<section class="newsletter section--sm" aria-labelledby="newsletter-title">
  <div class="container newsletter__inner">
    <h2 class="newsletter__title" id="newsletter-title">Mantente al día</h2>
    <p>Recibe novedades, ofertas y consejos directamente en tu bandeja.</p>
    <form class="newsletter__form" novalidate aria-label="Suscripción al boletín">
      <input type="email" class="form__input" placeholder="tu@email.com" aria-label="Email" required>
      <button type="submit" class="btn btn--primary">Suscribirme</button>
    </form>
  </div>
</section>"""


def _section_featured_products(ctx, cfg):
    products = ctx.get("features", ["Producto 1", "Producto 2", "Producto 3"])
    cards = "".join(f'<article class="product-card"><div class="product-card__img" aria-hidden="true"></div><h3 class="product-card__name">{_esc(str(p))}</h3><p class="product-card__price">Desde 29€</p><a href="#contact" class="btn btn--primary btn--sm">Comprar</a></article>' for p in products[:3])
    return f"""
<section class="products section" id="features" aria-labelledby="products-title">
  <div class="container">
    <header class="section__header">
      <h2 class="section__title" id="products-title">Productos destacados</h2>
    </header>
    <div class="products__grid">{cards}</div>
  </div>
</section>"""


def _section_benefits(ctx, cfg):
    benefits = ["Envío rápido", "Devolución fácil", "Pago seguro", "Atención 24/7"]
    items = "".join(f'<div class="benefit"><span class="benefit__icon" aria-hidden="true">{"✓"}</span><span>{b}</span></div>' for b in benefits)
    return f"""
<section class="benefits section--sm" aria-label="Beneficios de compra">
  <div class="container benefits__row">{items}</div>
</section>"""


def _esc(s: str) -> str:
    return (str(s)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;"))


# ══════════════════════════════════════════════════════════════════════════
#  RENDERIZADO CSS
# ══════════════════════════════════════════════════════════════════════════
def render_css(ctx: dict, config: dict) -> str:
    p = config["palette"]
    return f"""/* ═══════════════════════════════════════════
   ULTRA Generated CSS — {ctx['client_name']}
   Niche: {config['label']}
   ═══════════════════════════════════════════ */

/* ── Reset & Variables ── */
:root {{
  --primary:    {p['primary']};
  --accent:     {p['accent']};
  --dark:       {p['dark']};
  --light:      {p['light']};
  --white:      #ffffff;
  --gray-100:   #f3f4f6;
  --gray-200:   #e5e7eb;
  --gray-500:   #6b7280;
  --gray-700:   #374151;
  --radius-sm:  6px;
  --radius:     12px;
  --radius-lg:  20px;
  --shadow-sm:  0 1px 3px rgba(0,0,0,.08);
  --shadow:     0 4px 16px rgba(0,0,0,.10);
  --shadow-lg:  0 16px 40px rgba(0,0,0,.14);
  --transition: .25s cubic-bezier(.4,0,.2,1);
  --font:       'Inter', system-ui, -apple-system, sans-serif;
  --max-w:      1200px;
  --section-py: clamp(60px, 8vw, 120px);
}}
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
html{{scroll-behavior:smooth;-webkit-text-size-adjust:100%}}
body{{font-family:var(--font);color:var(--dark);background:var(--white);line-height:1.6;overflow-x:hidden}}
img{{max-width:100%;height:auto;display:block}}
a{{color:inherit;text-decoration:none}}
ul{{list-style:none}}
button{{cursor:pointer;border:none;background:none;font-family:inherit}}
input,textarea{{font-family:inherit}}

/* ── Utils ── */
.container{{max-width:var(--max-w);margin:0 auto;padding:0 clamp(16px,4vw,40px)}}
.section{{padding:var(--section-py) 0}}
.section--sm{{padding:40px 0}}
.section__header{{text-align:center;margin-bottom:clamp(40px,5vw,64px)}}
.section__title{{font-size:clamp(1.75rem,3vw,2.5rem);font-weight:800;line-height:1.2;margin-bottom:16px}}
.section__subtitle{{font-size:1.125rem;color:var(--gray-500);max-width:600px;margin:0 auto}}

/* ── Buttons ── */
.btn{{display:inline-flex;align-items:center;gap:8px;padding:12px 24px;border-radius:var(--radius-sm);font-weight:600;font-size:.9375rem;transition:var(--transition);text-decoration:none;border:2px solid transparent;white-space:nowrap}}
.btn--primary{{background:var(--primary);color:var(--white);border-color:var(--primary)}}
.btn--primary:hover{{filter:brightness(1.1);transform:translateY(-1px);box-shadow:var(--shadow)}}
.btn--ghost{{color:var(--primary);border-color:var(--primary)}}
.btn--ghost:hover{{background:var(--primary);color:var(--white)}}
.btn--outline{{border-color:var(--gray-200);color:var(--dark)}}
.btn--outline:hover{{border-color:var(--primary);color:var(--primary)}}
.btn--white{{background:var(--white);color:var(--primary)}}
.btn--white:hover{{background:var(--gray-100)}}
.btn--lg{{padding:16px 32px;font-size:1.0625rem}}
.btn--sm{{padding:8px 16px;font-size:.875rem}}

/* ── Animations ── */
@keyframes fadeIn{{from{{opacity:0}}to{{opacity:1}}}}
@keyframes slideUp{{from{{opacity:0;transform:translateY(24px)}}to{{opacity:1;transform:translateY(0)}}}}
.animate-fade-in{{animation:fadeIn .6s ease both;animation-delay:var(--delay,.1s)}}
.animate-slide-up{{animation:slideUp .7s cubic-bezier(.2,0,0,1) both;animation-delay:var(--delay,.05s)}}

/* ── NAV ── */
.nav{{position:sticky;top:0;z-index:100;background:rgba(255,255,255,.92);backdrop-filter:blur(12px);border-bottom:1px solid var(--gray-200)}}
.nav__inner{{display:flex;align-items:center;gap:24px;height:68px}}
.nav__logo{{font-weight:800;font-size:1.125rem;color:var(--primary);flex-shrink:0}}
.nav__links{{display:flex;gap:24px;margin:auto}}
.nav__links a{{font-size:.9375rem;color:var(--gray-700);transition:var(--transition)}}
.nav__links a:hover{{color:var(--primary)}}
.nav__cta{{margin-left:auto;flex-shrink:0}}
.nav__burger{{display:none;flex-direction:column;gap:5px;padding:8px;width:36px;height:36px;justify-content:center;margin-left:auto}}
.nav__burger span{{display:block;height:2px;background:var(--dark);transition:var(--transition);border-radius:2px}}
@media(max-width:768px){{
  .nav__links{{display:none;position:absolute;top:68px;left:0;right:0;flex-direction:column;background:var(--white);padding:20px;border-bottom:1px solid var(--gray-200);gap:16px}}
  .nav__links.open{{display:flex}}
  .nav__cta{{display:none}}
  .nav__burger{{display:flex}}
}}

/* ── HERO ── */
.hero{{background:linear-gradient(135deg,var(--dark) 0%,color-mix(in srgb,var(--primary) 40%,var(--dark)) 100%);color:var(--white);min-height:90vh;display:flex;align-items:center}}
.hero__inner{{display:grid;grid-template-columns:1fr 1fr;gap:60px;align-items:center;width:100%}}
.hero__badge{{display:inline-block;background:rgba(255,255,255,.12);border:1px solid rgba(255,255,255,.2);padding:6px 14px;border-radius:999px;font-size:.8125rem;font-weight:600;letter-spacing:.05em;margin-bottom:20px}}
.hero__title{{font-size:clamp(2rem,4.5vw,3.5rem);font-weight:800;line-height:1.1;margin-bottom:20px}}
.hero__desc{{font-size:1.125rem;color:rgba(255,255,255,.75);margin-bottom:32px;max-width:520px}}
.hero__actions{{display:flex;flex-wrap:wrap;gap:12px;margin-bottom:24px}}
.hero__trust{{display:flex;flex-wrap:wrap;gap:16px}}
.hero__trust-item{{font-size:.875rem;color:rgba(255,255,255,.65)}}
.hero__visual{{display:flex;justify-content:center}}
.hero__card{{background:rgba(255,255,255,.1);border:1px solid rgba(255,255,255,.15);border-radius:var(--radius-lg);padding:32px;backdrop-filter:blur(8px);display:flex;flex-direction:column;gap:24px;width:100%;max-width:320px}}
.metric-value{{display:block;font-size:2rem;font-weight:800;color:var(--white)}}
.metric-label{{font-size:.875rem;color:rgba(255,255,255,.6)}}
@media(max-width:768px){{
  .hero__inner{{grid-template-columns:1fr;text-align:center}}
  .hero__desc,.hero__actions,.hero__trust{{justify-content:center}}
  .hero__visual{{display:none}}
}}

/* ── FEATURES ── */
.features__grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:24px}}
.feature-card{{background:var(--white);border:1px solid var(--gray-200);border-radius:var(--radius);padding:28px;transition:var(--transition)}}
.feature-card:hover{{border-color:var(--primary);box-shadow:var(--shadow);transform:translateY(-2px)}}
.feature-card__icon{{font-size:2rem;margin-bottom:16px}}
.feature-card__title{{font-size:1.0625rem;font-weight:700;margin-bottom:8px}}
.feature-card__desc{{font-size:.9375rem;color:var(--gray-500);line-height:1.5}}

/* ── SOCIAL PROOF ── */
.social-proof{{background:var(--gray-100);padding:40px 0}}
.proof__label{{text-align:center;font-size:.875rem;color:var(--gray-500);font-weight:600;letter-spacing:.05em;text-transform:uppercase;margin-bottom:24px}}
.proof__logos{{display:flex;flex-wrap:wrap;gap:24px;justify-content:center;align-items:center}}
.proof__logo{{background:var(--white);border:1px solid var(--gray-200);border-radius:var(--radius-sm);padding:12px 24px;font-weight:600;color:var(--gray-500);font-size:.875rem}}

/* ── PRICING ── */
.pricing__grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:24px;align-items:start}}
.plan-card{{background:var(--white);border:2px solid var(--gray-200);border-radius:var(--radius-lg);padding:32px;position:relative;transition:var(--transition)}}
.plan-card--highlight{{border-color:var(--primary);box-shadow:var(--shadow-lg)}}
.plan-card__badge{{position:absolute;top:-12px;left:50%;transform:translateX(-50%);background:var(--primary);color:var(--white);padding:4px 16px;border-radius:999px;font-size:.75rem;font-weight:700}}
.plan-card__name{{font-size:1.125rem;font-weight:700;margin-bottom:12px}}
.plan-card__price{{display:flex;align-items:baseline;gap:4px;margin-bottom:20px}}
.plan-card__amount{{font-size:2.25rem;font-weight:800;color:var(--primary)}}
.plan-card__period{{color:var(--gray-500);font-size:.9375rem}}
.plan-card__features{{display:flex;flex-direction:column;gap:10px;margin-bottom:28px}}
.plan-card__features li{{font-size:.9375rem;color:var(--gray-700)}}
.plan-card__cta{{width:100%;justify-content:center}}

/* ── FAQ ── */
.faq__inner{{max-width:720px;margin:0 auto}}
.faq__list{{display:flex;flex-direction:column;gap:8px}}
.faq__item{{border:1px solid var(--gray-200);border-radius:var(--radius)}}
.faq__question{{width:100%;text-align:left;padding:20px 24px;font-size:1rem;font-weight:600;display:flex;justify-content:space-between;align-items:center;gap:12px;color:var(--dark);transition:var(--transition)}}
.faq__question:hover{{color:var(--primary)}}
.faq__icon{{font-size:1.25rem;transition:var(--transition);flex-shrink:0}}
.faq__question[aria-expanded=true] .faq__icon{{transform:rotate(45deg)}}
.faq__answer{{padding:0 24px 20px}}
.faq__answer p{{color:var(--gray-700);font-size:.9375rem;line-height:1.6}}

/* ── CTA BOTTOM ── */
.cta-bottom{{background:linear-gradient(135deg,var(--primary),var(--accent));color:var(--white);text-align:center}}
.cta-bottom__inner{{max-width:600px;margin:0 auto}}
.cta-bottom__title{{font-size:clamp(1.5rem,3vw,2.25rem);font-weight:800;margin-bottom:12px}}
.cta-bottom__subtitle{{font-size:1.0625rem;color:rgba(255,255,255,.8);margin-bottom:28px}}

/* ── TESTIMONIALS ── */
.testimonials__grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:24px}}
.testimonial-card{{background:var(--white);border:1px solid var(--gray-200);border-radius:var(--radius);padding:28px}}
.testimonial-card__stars{{color:#F59E0B;font-size:1rem;margin-bottom:12px}}
.testimonial-card__text{{font-size:.9375rem;color:var(--gray-700);line-height:1.6;margin-bottom:20px;font-style:italic}}
.testimonial-card__author{{display:flex;align-items:center;gap:12px}}
.testimonial-card__avatar{{width:40px;height:40px;background:var(--primary);color:var(--white);border-radius:50%;display:flex;align-items:center;justify-content:center;font-weight:700;font-size:1rem;flex-shrink:0}}
.testimonial-card__name{{display:block;font-weight:700;font-size:.9375rem}}
.testimonial-card__role{{font-size:.8125rem;color:var(--gray-500)}}

/* ── ABOUT ── */
.about__inner{{display:grid;grid-template-columns:1fr 1fr;gap:60px;align-items:center}}
.about__text{{font-size:1rem;color:var(--gray-700);line-height:1.7;margin-bottom:16px}}
.about__stats{{display:grid;grid-template-columns:1fr 1fr;gap:20px}}
.stat{{background:var(--gray-100);border-radius:var(--radius);padding:20px;text-align:center}}
.stat__num{{display:block;font-size:1.75rem;font-weight:800;color:var(--primary)}}
.stat__label{{font-size:.8125rem;color:var(--gray-500)}}
@media(max-width:768px){{.about__inner{{grid-template-columns:1fr}}}}

/* ── METHODOLOGY ── */
.methodology__steps{{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:24px}}
.method-step{{text-align:center;padding:24px}}
.method-step__num{{width:48px;height:48px;background:var(--primary);color:var(--white);border-radius:50%;display:flex;align-items:center;justify-content:center;font-weight:800;font-size:1.125rem;margin:0 auto 16px}}
.method-step h3{{font-weight:700;margin-bottom:8px}}
.method-step p{{font-size:.9375rem;color:var(--gray-500)}}

/* ── CONTACT ── */
.contact__inner{{max-width:900px;margin:0 auto}}
.contact__layout{{display:grid;grid-template-columns:1fr 2fr;gap:48px;align-items:start}}
.contact__info{{display:flex;flex-direction:column;gap:12px;padding-top:8px}}
.contact__email,.contact__phone{{display:block;color:var(--primary);font-weight:600;word-break:break-all}}
.form__group{{margin-bottom:16px}}
.form__label{{display:block;font-size:.875rem;font-weight:600;margin-bottom:6px;color:var(--gray-700)}}
.form__input,.form__textarea{{width:100%;padding:12px 16px;border:2px solid var(--gray-200);border-radius:var(--radius-sm);font-size:.9375rem;transition:var(--transition);background:var(--white)}}
.form__input:focus,.form__textarea:focus{{outline:none;border-color:var(--primary);box-shadow:0 0 0 3px color-mix(in srgb,var(--primary) 15%,transparent)}}
.form__textarea{{resize:vertical;min-height:120px}}
.form__error{{display:block;font-size:.8125rem;color:#DC2626;margin-top:4px;min-height:1em}}
.form__actions{{display:flex;gap:12px;align-items:center;flex-wrap:wrap}}
.form__success{{text-align:center;padding:32px 0}}
.form__success-icon{{width:56px;height:56px;background:color-mix(in srgb,#059669 15%,transparent);color:#059669;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:1.5rem;margin:0 auto 16px;font-weight:700}}
.form__success h3{{font-size:1.25rem;font-weight:700;margin-bottom:8px}}
@media(max-width:640px){{.contact__layout{{grid-template-columns:1fr}}}}

/* ── PORTFOLIO ── */
.portfolio__grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:24px}}
.portfolio-card{{border-radius:var(--radius);overflow:hidden;border:1px solid var(--gray-200)}}
.portfolio-card__img{{height:180px;background:linear-gradient(135deg,var(--gray-100),var(--gray-200))}}
.portfolio-card h3,.portfolio-card p{{padding:0 16px}}
.portfolio-card h3{{padding-top:16px;font-weight:700}}
.portfolio-card p{{padding-bottom:16px;font-size:.875rem;color:var(--gray-500)}}

/* ── PRODUCTS ── */
.products__grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:24px}}
.product-card{{border:1px solid var(--gray-200);border-radius:var(--radius);overflow:hidden;transition:var(--transition)}}
.product-card:hover{{box-shadow:var(--shadow);transform:translateY(-2px)}}
.product-card__img{{height:200px;background:var(--gray-100)}}
.product-card__name{{padding:16px 16px 4px;font-weight:700}}
.product-card__price{{padding:0 16px 4px;color:var(--primary);font-weight:700}}
.product-card .btn{{margin:0 16px 16px;width:calc(100% - 32px)}}

/* ── BENEFITS ── */
.benefits__row{{display:flex;flex-wrap:wrap;gap:24px;justify-content:center}}
.benefit{{display:flex;align-items:center;gap:8px;font-weight:600;font-size:.9375rem}}
.benefit__icon{{color:var(--primary)}}

/* ── NEWSLETTER ── */
.newsletter{{background:var(--gray-100)}}
.newsletter__inner{{text-align:center;max-width:480px;margin:0 auto}}
.newsletter__title{{font-size:1.5rem;font-weight:700;margin-bottom:8px}}
.newsletter__form{{display:flex;gap:8px;margin-top:20px}}
.newsletter__form .form__input{{flex:1}}

/* ── LOCATION ── */
.location__map-placeholder{{background:var(--gray-100);border-radius:var(--radius);height:200px;display:flex;align-items:center;justify-content:center;color:var(--gray-500);border:1px solid var(--gray-200)}}

/* ── FOOTER ── */
.footer{{background:var(--dark);color:rgba(255,255,255,.7);padding:48px 0}}
.footer__inner{{display:grid;grid-template-columns:1fr auto;gap:32px;align-items:start}}
.footer__logo{{display:block;font-weight:800;font-size:1.125rem;color:var(--white);margin-bottom:8px}}
.footer__desc{{font-size:.875rem;max-width:300px}}
.footer__contact{{display:flex;flex-direction:column;gap:8px;text-align:right}}
.footer__link{{color:rgba(255,255,255,.6);font-size:.875rem;transition:var(--transition)}}
.footer__link:hover{{color:var(--white)}}
.footer__legal{{grid-column:1/-1;font-size:.8125rem;color:rgba(255,255,255,.4);padding-top:24px;border-top:1px solid rgba(255,255,255,.1);margin-top:16px}}
@media(max-width:640px){{.footer__inner{{grid-template-columns:1fr}}.footer__contact{{text-align:left}}}}

/* ── CHATBOT ── */
.chat{{position:fixed;bottom:24px;right:24px;z-index:200}}
.chat__toggle{{width:56px;height:56px;background:var(--primary);color:var(--white);border-radius:50%;display:flex;align-items:center;justify-content:center;box-shadow:var(--shadow-lg);transition:var(--transition)}}
.chat__toggle:hover{{transform:scale(1.08);filter:brightness(1.1)}}
.chat__box{{position:absolute;bottom:72px;right:0;width:340px;background:var(--white);border-radius:var(--radius-lg);box-shadow:var(--shadow-lg);overflow:hidden;border:1px solid var(--gray-200)}}
.chat__header{{background:var(--primary);color:var(--white);padding:14px 16px;display:flex;justify-content:space-between;align-items:center;font-weight:600;font-size:.9375rem}}
.chat__close{{color:rgba(255,255,255,.8);font-size:1.25rem;line-height:1;padding:0 4px}}
.chat__close:hover{{color:var(--white)}}
.chat__messages{{height:280px;overflow-y:auto;padding:16px;display:flex;flex-direction:column;gap:12px}}
.chat__msg{{max-width:80%;font-size:.875rem;line-height:1.5;padding:10px 14px;border-radius:12px}}
.chat__msg--bot{{background:var(--gray-100);border-radius:4px 12px 12px 12px;align-self:flex-start}}
.chat__msg--user{{background:var(--primary);color:var(--white);border-radius:12px 12px 4px 12px;align-self:flex-end}}
.chat__form{{display:flex;gap:8px;padding:12px;border-top:1px solid var(--gray-200)}}
.chat__input{{flex:1;border:1px solid var(--gray-200);border-radius:var(--radius-sm);padding:10px 14px;font-size:.875rem}}
.chat__input:focus{{outline:none;border-color:var(--primary)}}
.chat__send{{padding:10px 14px;border-radius:var(--radius-sm);flex-shrink:0}}
.chat__typing{{display:flex;gap:4px;align-items:center;padding:10px 14px;background:var(--gray-100);border-radius:4px 12px 12px 12px;align-self:flex-start;width:fit-content}}
.chat__typing span{{width:6px;height:6px;background:var(--gray-500);border-radius:50%;animation:typing .8s ease infinite}}
.chat__typing span:nth-child(2){{animation-delay:.15s}}
.chat__typing span:nth-child(3){{animation-delay:.3s}}
@keyframes typing{{0%,80%,100%{{transform:scale(.8);opacity:.5}}40%{{transform:scale(1);opacity:1}}}}
@media(max-width:480px){{.chat__box{{width:calc(100vw - 48px)}}}}

/* ── Focus visible ── */
:focus-visible{{outline:2px solid var(--primary);outline-offset:2px}}
"""


# ══════════════════════════════════════════════════════════════════════════
#  RENDERIZADO JS
# ══════════════════════════════════════════════════════════════════════════
def render_js(ctx: dict, config: dict) -> str:
    client_name = ctx["client_name"].replace('"', '\\"')
    niche_label = config["label"].replace('"', '\\"')
    return f"""/* ═══════════════════════════════════════════
   ULTRA Generated JS — {client_name}
   ═══════════════════════════════════════════ */
'use strict';

// ── Config (editable por ULTRA o por agentes) ──────────────────────────
const ULTRA_CONFIG = {{
  clientName:  "{client_name}",
  niche:       "{niche_label}",
  chatApiUrl:  null,  // Reemplazar con endpoint real: "/api/chat"
  contactUrl:  null,  // Reemplazar con endpoint real: "/api/contact"
}};

// ── DOM Ready ──────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {{
  initNav();
  initFAQ();
  initContactForm();
  initChat();
  initScrollAnimations();
}});

// ── NAV ────────────────────────────────────────────────────────────────
function initNav() {{
  const burger = document.querySelector('.nav__burger');
  const links  = document.querySelector('.nav__links');
  if (!burger || !links) return;

  burger.addEventListener('click', () => {{
    const open = links.classList.toggle('open');
    burger.setAttribute('aria-expanded', open);
  }});

  // Cerrar al hacer clic en enlace
  links.querySelectorAll('a').forEach(a => {{
    a.addEventListener('click', () => {{
      links.classList.remove('open');
      burger.setAttribute('aria-expanded', false);
    }});
  }});

  // Highlight activo
  const navLinks = links.querySelectorAll('a[href^="#"]');
  const observer = new IntersectionObserver(entries => {{
    entries.forEach(e => {{
      if (e.isIntersecting) {{
        navLinks.forEach(l => l.removeAttribute('aria-current'));
        const id = e.target.id;
        const active = [...navLinks].find(l => l.getAttribute('href') === '#' + id);
        if (active) active.setAttribute('aria-current', 'page');
      }}
    }});
  }}, {{ threshold: 0.5 }});
  document.querySelectorAll('section[id]').forEach(s => observer.observe(s));
}}

// ── FAQ ────────────────────────────────────────────────────────────────
function initFAQ() {{
  document.querySelectorAll('.faq__question').forEach(btn => {{
    btn.addEventListener('click', () => {{
      const answer  = document.getElementById(btn.getAttribute('aria-controls'));
      const open    = btn.getAttribute('aria-expanded') === 'true';
      // Cerrar todas
      document.querySelectorAll('.faq__question').forEach(b => {{
        b.setAttribute('aria-expanded', 'false');
        document.getElementById(b.getAttribute('aria-controls'))?.removeAttribute('hidden');
        document.getElementById(b.getAttribute('aria-controls'))?.setAttribute('hidden', '');
      }});
      // Abrir si no estaba abierto
      if (!open && answer) {{
        btn.setAttribute('aria-expanded', 'true');
        answer.removeAttribute('hidden');
      }}
    }});
  }});
}}

// ── CONTACT FORM (multi-step) ──────────────────────────────────────────
function initContactForm() {{
  const form = document.getElementById('contact-form');
  if (!form) return;

  const steps   = form.querySelectorAll('.form__step');
  let current   = 0;

  function showStep(n) {{
    steps.forEach((s, i) => {{
      if (i === n) s.removeAttribute('hidden'); else s.setAttribute('hidden', '');
    }});
    current = n;
  }}

  form.querySelectorAll('.form__next').forEach(btn => {{
    btn.addEventListener('click', () => {{
      if (validateStep(steps[current])) showStep(current + 1);
    }});
  }});

  form.querySelectorAll('.form__prev').forEach(btn => {{
    btn.addEventListener('click', () => showStep(current - 1));
  }});

  form.addEventListener('submit', async e => {{
    e.preventDefault();
    if (!validateStep(steps[current])) return;

    const data = Object.fromEntries(new FormData(form));
    data._meta = {{ client: ULTRA_CONFIG.clientName, niche: ULTRA_CONFIG.niche, ts: Date.now() }};

    try {{
      if (ULTRA_CONFIG.contactUrl) {{
        await fetch(ULTRA_CONFIG.contactUrl, {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/json' }},
          body: JSON.stringify(data)
        }});
      }}
    }} catch (_) {{/* silencioso — aún mostramos éxito */}}

    showStep(2);
  }});

  function validateStep(step) {{
    let ok = true;
    step.querySelectorAll('[required]').forEach(field => {{
      const err = field.parentElement.querySelector('.form__error');
      field.classList.remove('error');
      if (err) err.textContent = '';
      if (!field.value.trim()) {{
        field.classList.add('error');
        if (err) err.textContent = 'Este campo es obligatorio.';
        ok = false;
      }} else if (field.type === 'email' && !/^[^\\s@]+@[^\\s@]+\\.[^\\s@]+$/.test(field.value)) {{
        field.classList.add('error');
        if (err) err.textContent = 'Email no válido.';
        ok = false;
      }}
    }});
    return ok;
  }}
}}

// ── CHATBOT ────────────────────────────────────────────────────────────
function initChat() {{
  const toggle   = document.getElementById('chat-toggle');
  const box      = document.getElementById('chat-box');
  const closeBtn = document.getElementById('chat-close');
  const form     = document.getElementById('chat-form');
  const input    = document.getElementById('chat-input');
  const messages = document.getElementById('chat-messages');
  if (!toggle || !box) return;

  const BOT_INTRO = `¡Hola! Soy el asistente de ${{ULTRA_CONFIG.clientName}}. ¿En qué puedo ayudarte hoy?`;

  function openChat() {{
    box.removeAttribute('hidden');
    toggle.setAttribute('aria-expanded', 'true');
    if (!messages.children.length) addMsg(BOT_INTRO, 'bot');
    input.focus();
  }}
  function closeChat() {{
    box.setAttribute('hidden', '');
    toggle.setAttribute('aria-expanded', 'false');
    toggle.focus();
  }}

  toggle.addEventListener('click', () => box.hasAttribute('hidden') ? openChat() : closeChat());
  closeBtn?.addEventListener('click', closeChat);

  // Cerrar con Escape
  box.addEventListener('keydown', e => {{ if (e.key === 'Escape') closeChat(); }});

  form?.addEventListener('submit', async e => {{
    e.preventDefault();
    const text = input.value.trim();
    if (!text) return;
    addMsg(text, 'user');
    input.value = '';
    const typingEl = addTyping();
    const reply = await getReply(text);
    typingEl.remove();
    addMsg(reply, 'bot');
  }});

  function addMsg(text, from) {{
    const el = document.createElement('div');
    el.className = `chat__msg chat__msg--${{from}}`;
    el.textContent = text;
    messages.appendChild(el);
    messages.scrollTop = messages.scrollHeight;
    return el;
  }}

  function addTyping() {{
    const el = document.createElement('div');
    el.className = 'chat__typing';
    el.innerHTML = '<span></span><span></span><span></span>';
    messages.appendChild(el);
    messages.scrollTop = messages.scrollHeight;
    return el;
  }}

  async function getReply(userMsg) {{
    if (ULTRA_CONFIG.chatApiUrl) {{
      try {{
        const res = await fetch(ULTRA_CONFIG.chatApiUrl, {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/json' }},
          body: JSON.stringify({{
            message: userMsg,
            context: {{ client: ULTRA_CONFIG.clientName, niche: ULTRA_CONFIG.niche }}
          }})
        }});
        if (res.ok) {{
          const data = await res.json();
          return data.reply || data.message || 'Gracias por tu mensaje.';
        }}
      }} catch (_) {{}}
    }}
    // Fallback local
    return localReply(userMsg);
  }}

  function localReply(msg) {{
    const m = msg.toLowerCase();
    if (m.includes('precio') || m.includes('coste') || m.includes('cuánto')) return 'Tenemos planes desde 49€/mes. Puedes verlos más abajo en la página o contactarnos para un presupuesto personalizado.';
    if (m.includes('hola') || m.includes('buenas')) return `¡Hola! Encantado de atenderte. ¿Tienes alguna pregunta sobre ${{ULTRA_CONFIG.clientName}}?`;
    if (m.includes('contacto') || m.includes('llamar') || m.includes('email')) return 'Puedes contactarnos usando el formulario de la sección "Hablemos" o escribiéndonos directamente. ¡Respondemos en menos de 24h!';
    if (m.includes('gracias')) return '¡De nada! Estamos aquí para lo que necesites.';
    return `Gracias por tu pregunta. Un miembro del equipo de ${{ULTRA_CONFIG.clientName}} te responderá en breve. Mientras tanto, puedes usar el formulario de contacto.`;
  }}
}}

// ── SCROLL ANIMATIONS ──────────────────────────────────────────────────
function initScrollAnimations() {{
  if (!('IntersectionObserver' in window)) return;
  const targets = document.querySelectorAll('.feature-card, .testimonial-card, .plan-card, .method-step, .portfolio-card, .product-card');
  const obs = new IntersectionObserver((entries) => {{
    entries.forEach(e => {{
      if (e.isIntersecting) {{
        e.target.style.opacity = '1';
        e.target.style.transform = 'translateY(0)';
        obs.unobserve(e.target);
      }}
    }});
  }}, {{ threshold: 0.1 }});
  targets.forEach(t => {{
    t.style.opacity = '0';
    t.style.transform = 'translateY(20px)';
    t.style.transition = 'opacity .5s ease, transform .5s ease';
    obs.observe(t);
  }});
}}
"""


# ── CLI de prueba ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    gen = UltraWebGenerator()

    test_cases = [
        {
            "client_name": "DataFlow SaaS",
            "niche": "saas_b2b",
            "business_desc": "Plataforma de analítica de datos en tiempo real para empresas medianas.",
            "tagline": "Toma decisiones 10x más rápido con tus datos",
            "offer": "14 días gratis, sin tarjeta de crédito",
            "contact_email": "hola@dataflow.io",
            "features": ["Dashboard en tiempo real", "Integración con 50+ fuentes", "Alertas inteligentes",
                         "Colaboración de equipo", "API REST completa", "Soporte dedicado"],
        },
        {
            "client_name": "BrillanteModa",
            "niche": "ecommerce",
            "business_desc": "Tienda online de moda sostenible y accesorios de diseño.",
            "tagline": "Moda que te define, planet-friendly",
            "offer": "Envío gratis en pedidos +50€",
            "contact_email": "hola@brillantemoda.es",
            "contact_phone": "+34 600 123 456",
            "features": ["Colecciones exclusivas", "Materiales sostenibles", "Diseño local"],
        },
        {
            "client_name": "Coaching con Propósito",
            "niche": "coaching",
            "business_desc": "Coaching ejecutivo y de vida para profesionales que quieren más.",
            "tagline": "Transforma tu carrera, transforma tu vida",
            "offer": "Primera sesión de diagnóstico gratuita",
            "contact_email": "info@coachingconproposito.es",
            "features": ["Sesiones 1:1 personalizadas", "Metodología probada", "Seguimiento continuo", "Comunidad privada"],
        },
    ]

    for tc in test_cases:
        result = gen.generate(tc)
        status = "✅" if result["valid"] else "❌"
        print(f"{status} {tc['client_name']} → {result['path']} (errors: {result['errors']})")

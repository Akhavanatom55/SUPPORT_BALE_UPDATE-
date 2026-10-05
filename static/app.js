(function () {
  'use strict';

  var root = document.documentElement;
  var body = document.body;
  var $ = function (selector, scope) { return (scope || document).querySelector(selector); };
  var $$ = function (selector, scope) { return Array.prototype.slice.call((scope || document).querySelectorAll(selector)); };
  var reduceMotion = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var finePointer = window.matchMedia && window.matchMedia('(pointer: fine)').matches;
  var allowedThemes = ['light', 'dark'];
  var allowedAccents = ['blue', 'violet', 'emerald', 'amber', 'rose'];

  function readPreference(key, allowed, fallback) {
    try {
      var value = window.localStorage.getItem(key);
      return allowed.indexOf(value) !== -1 ? value : fallback;
    } catch (_) {
      return fallback;
    }
  }

  function savePreference(key, value) {
    try { window.localStorage.setItem(key, value); } catch (_) { /* Private browsing can disable storage. */ }
  }

  var theme = allowedThemes.indexOf(root.dataset.theme) !== -1
    ? root.dataset.theme
    : readPreference('wa-support-theme', allowedThemes, 'light');
  var accent = allowedAccents.indexOf(root.dataset.accent) !== -1
    ? root.dataset.accent
    : readPreference('wa-support-accent', allowedAccents, 'blue');
  var themeButton = $('#themeToggle');
  var themeLabel = $('[data-theme-label]');
  var accentButton = $('#accentToggle');
  var accentPopover = $('#accentPopover');
  var refreshCanvasPalette = function () {};

  function syncAppearance() {
    root.dataset.theme = theme;
    root.dataset.accent = accent;
    if (themeLabel) themeLabel.textContent = theme === 'dark' ? 'حالت روشن' : 'حالت تیره';
    if (themeButton) {
      themeButton.setAttribute('aria-label', theme === 'dark' ? 'تغییر به حالت روشن' : 'تغییر به حالت تیره');
      themeButton.setAttribute('title', theme === 'dark' ? 'فعال‌کردن حالت روشن' : 'فعال‌کردن حالت تیره');
    }
    if (accentButton) accentButton.setAttribute('aria-label', 'رنگ‌بندی فعلی: ' + accent);
    $$('[data-accent-option]').forEach(function (option) {
      option.setAttribute('aria-pressed', option.dataset.accentOption === accent ? 'true' : 'false');
    });
    var themeMeta = $('#themeColorMeta');
    if (themeMeta) themeMeta.setAttribute('content', getComputedStyle(root).getPropertyValue('--page').trim());
    refreshCanvasPalette();
  }

  syncAppearance();
  if (themeButton) {
    themeButton.addEventListener('click', function () {
      theme = theme === 'dark' ? 'light' : 'dark';
      savePreference('wa-support-theme', theme);
      syncAppearance();
    });
  }
  if (accentButton && accentPopover) {
    accentButton.addEventListener('click', function () {
      var open = accentPopover.hidden;
      accentPopover.hidden = !open;
      accentButton.setAttribute('aria-expanded', open ? 'true' : 'false');
      if (open) {
        var selected = $('[data-accent-option][aria-pressed="true"]', accentPopover);
        if (selected) selected.focus({ preventScroll: true });
      }
    });
    $$('[data-accent-option]', accentPopover).forEach(function (option) {
      option.addEventListener('click', function () {
        var next = option.dataset.accentOption;
        if (allowedAccents.indexOf(next) === -1) return;
        accent = next;
        savePreference('wa-support-accent', accent);
        syncAppearance();
        accentPopover.hidden = true;
        accentButton.setAttribute('aria-expanded', 'false');
        accentButton.focus({ preventScroll: true });
      });
    });
    document.addEventListener('click', function (event) {
      if (accentPopover.hidden || event.target.closest('.accent-picker')) return;
      accentPopover.hidden = true;
      accentButton.setAttribute('aria-expanded', 'false');
    });
  }

  /* Automatically attach the CSRF token to all ordinary POST forms. */
  var csrfMeta = $('meta[name="csrf-token"]');
  var csrfToken = csrfMeta ? csrfMeta.content : '';
  $$('form').forEach(function (form) {
    if ((form.getAttribute('method') || 'get').toLowerCase() !== 'post' || form.querySelector('input[name="_csrf"]')) return;
    var hidden = document.createElement('input');
    hidden.type = 'hidden';
    hidden.name = '_csrf';
    hidden.value = csrfToken;
    form.appendChild(hidden);
  });

  /* Persian calendar date in the admin toolbar. */
  $$('[data-local-date]').forEach(function (element) {
    try {
      element.textContent = new Intl.DateTimeFormat('fa-IR', { weekday: 'short', day: 'numeric', month: 'long' }).format(new Date());
    } catch (_) {
      element.textContent = new Date().toLocaleDateString('fa-IR');
    }
  });

  /* Cursor-following ambience plus a per-control light hotspot, batched to one frame. */
  if (!reduceMotion && finePointer) {
    var pointerFrame = 0;
    var pointerX = 0;
    var pointerY = 0;
    var lightTarget = null;
    var lightX = 50;
    var lightY = 50;
    var lightTargets = '.btn, .appearance-btn, .icon-btn, .menu-trigger, .logout, .chip-btn, .accent-option, .flash .x, .stat, .feature, .panel, .sidebar nav a';
    document.addEventListener('pointermove', function (event) {
      if (event.pointerType === 'touch') return;
      pointerX = event.clientX;
      pointerY = event.clientY;
      lightTarget = event.target && event.target.closest ? event.target.closest(lightTargets) : null;
      if (lightTarget) {
        var bounds = lightTarget.getBoundingClientRect();
        lightX = Math.max(0, Math.min(100, (event.clientX - bounds.left) / Math.max(bounds.width, 1) * 100));
        lightY = Math.max(0, Math.min(100, (event.clientY - bounds.top) / Math.max(bounds.height, 1) * 100));
      }
      if (pointerFrame) return;
      pointerFrame = window.requestAnimationFrame(function () {
        root.style.setProperty('--spot-x', pointerX + 'px');
        root.style.setProperty('--spot-y', pointerY + 'px');
        if (lightTarget) {
          lightTarget.style.setProperty('--light-x', lightX.toFixed(1) + '%');
          lightTarget.style.setProperty('--light-y', lightY.toFixed(1) + '%');
        }
        body.classList.add('pointer-active');
        pointerFrame = 0;
      });
    }, { passive: true });
    document.addEventListener('pointerleave', function () { body.classList.remove('pointer-active'); });
  }

  /* Low-density ambient particles, disabled for reduced-motion preferences. */
  var canvas = $('#fx');
  if (canvas && !reduceMotion && finePointer) {
    var ctx = canvas.getContext('2d', { alpha: true });
    if (ctx) {
      var width = 0;
      var height = 0;
      var scale = Math.min(window.devicePixelRatio || 1, 1.35);
      var particles = [];
      var mouse = { x: -1000, y: -1000 };
      var lastPaint = 0;
      var palette = [];
      function resizeCanvas() {
        width = window.innerWidth;
        height = window.innerHeight;
        scale = Math.min(window.devicePixelRatio || 1, 1.35);
        canvas.width = Math.round(width * scale);
        canvas.height = Math.round(height * scale);
        ctx.setTransform(scale, 0, 0, scale, 0, 0);
        var count = Math.min(36, Math.floor(width * height / 42000));
        particles = [];
        for (var index = 0; index < count; index += 1) {
          particles.push({ x: Math.random() * width, y: Math.random() * height, vx: (Math.random() - .5) * .22, vy: (Math.random() - .5) * .22, r: Math.random() * 1.4 + .45, phase: Math.random() * 6 });
        }
      }
      refreshCanvasPalette = function () {
        palette = [getComputedStyle(root).getPropertyValue('--primary').trim() || '#456bed', '#49aeb1', '#c5a15d'];
      };
      function drawParticles(now) {
        window.requestAnimationFrame(drawParticles);
        if (document.hidden || now - lastPaint < 36) return;
        lastPaint = now;
        ctx.clearRect(0, 0, width, height);
        for (var i = 0; i < particles.length; i += 1) {
          var p = particles[i];
          p.x += p.vx;
          p.y += p.vy;
          p.phase += .018;
          if (p.x < -3 || p.x > width + 3) p.vx *= -1;
          if (p.y < -3 || p.y > height + 3) p.vy *= -1;
          var dx = p.x - mouse.x;
          var dy = p.y - mouse.y;
          var distance = Math.sqrt(dx * dx + dy * dy);
          if (distance < 110 && distance > 1) {
            p.x += dx / distance * .22;
            p.y += dy / distance * .22;
          }
          var color = palette[i % palette.length];
          ctx.beginPath();
          ctx.fillStyle = color;
          ctx.globalAlpha = .44 + Math.sin(p.phase) * .16;
          ctx.shadowBlur = 9;
          ctx.shadowColor = color;
          ctx.arc(p.x, p.y, p.r * (1 + Math.sin(p.phase) * .12), 0, Math.PI * 2);
          ctx.fill();
          ctx.shadowBlur = 0;
          for (var j = i + 1; j < particles.length; j += 1) {
            var other = particles[j];
            var separation = Math.hypot(p.x - other.x, p.y - other.y);
            if (separation < 100) {
              ctx.beginPath();
              ctx.strokeStyle = color;
              ctx.globalAlpha = (1 - separation / 100) * .12;
              ctx.lineWidth = .7;
              ctx.moveTo(p.x, p.y);
              ctx.lineTo(other.x, other.y);
              ctx.stroke();
            }
          }
        }
        ctx.globalAlpha = 1;
      }
      document.addEventListener('pointermove', function (event) {
        if (event.pointerType === 'touch') return;
        mouse.x = event.clientX;
        mouse.y = event.clientY;
      }, { passive: true });
      window.addEventListener('resize', resizeCanvas, { passive: true });
      resizeCanvas();
      refreshCanvasPalette();
      window.requestAnimationFrame(drawParticles);
    }
  }

  /* Count-up animation for dashboard numbers. */
  $$('[data-count]').forEach(function (element) {
    var target = Number(element.dataset.count) || 0;
    if (reduceMotion) { element.textContent = target.toLocaleString('fa-IR'); return; }
    var start = performance.now();
    function tick(now) {
      var progress = Math.min((now - start) / 760, 1);
      var eased = 1 - Math.pow(1 - progress, 3);
      element.textContent = Math.round(target * eased).toLocaleString('fa-IR');
      if (progress < 1) window.requestAnimationFrame(tick);
    }
    window.requestAnimationFrame(tick);
  });

  /* Subtle card tilt, only for a fine pointer and normal-motion setting. */
  if (!reduceMotion && finePointer) {
    $$('.stat, .hero-box').forEach(function (card) {
      card.addEventListener('pointermove', function (event) {
        var bounds = card.getBoundingClientRect();
        var horizontal = (event.clientX - bounds.left) / bounds.width - .5;
        var vertical = (event.clientY - bounds.top) / bounds.height - .5;
        card.style.transform = 'perspective(900px) rotateX(' + (vertical * -2.6) + 'deg) rotateY(' + (horizontal * 2.6) + 'deg) translateY(-2px)';
      });
      card.addEventListener('pointerleave', function () { card.style.transform = ''; });
    });
  }

  /* Lightweight button ripple. */
  document.addEventListener('click', function (event) {
    var button = event.target.closest('.btn');
    if (!button || event.button > 0) return;
    var bounds = button.getBoundingClientRect();
    var diameter = Math.max(bounds.width, bounds.height);
    var ripple = document.createElement('span');
    var x = event.clientX ? event.clientX - bounds.left - diameter / 2 : bounds.width / 2 - diameter / 2;
    var y = event.clientY ? event.clientY - bounds.top - diameter / 2 : bounds.height / 2 - diameter / 2;
    ripple.className = 'rip';
    ripple.style.cssText = 'width:' + diameter + 'px;height:' + diameter + 'px;left:' + x + 'px;top:' + y + 'px';
    button.appendChild(ripple);
    window.setTimeout(function () { ripple.remove(); }, 700);
  });

  /* Native dialogs and confirmation prompts. */
  document.addEventListener('click', function (event) {
    var opener = event.target.closest('[data-dialog]');
    if (opener) {
      var dialog = document.getElementById(opener.getAttribute('data-dialog'));
      if (dialog && dialog.showModal) {
        dialog.showModal();
        var firstField = dialog.querySelector('input:not([type="hidden"]), textarea');
        if (firstField) window.setTimeout(function () { firstField.focus(); }, 30);
      }
      return;
    }
    var closer = event.target.closest('[data-close]');
    if (closer) {
      var parentDialog = closer.closest('dialog');
      if (parentDialog) parentDialog.close();
      return;
    }
    if (event.target.tagName === 'DIALOG') {
      var rect = event.target.getBoundingClientRect();
      if (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom) event.target.close();
    }
  });

  var confirmBox = $('#confirmBox');
  var confirmText = $('#confirmText');
  var confirmButton = $('#confirmOk');
  var pendingAction = null;
  function askForConfirmation(message, action) {
    if (!confirmBox || !confirmBox.showModal) {
      if (window.confirm(message)) action();
      return;
    }
    pendingAction = action;
    confirmText.textContent = message;
    confirmBox.showModal();
  }
  if (confirmButton && confirmBox) {
    confirmButton.addEventListener('click', function () {
      var action = pendingAction;
      pendingAction = null;
      confirmBox.close();
      if (action) action();
    });
    confirmBox.addEventListener('close', function () { pendingAction = null; });
    document.addEventListener('submit', function (event) {
      var form = event.target;
      if (!form.hasAttribute || !form.hasAttribute('data-confirm') || form.__confirmPassed) return;
      event.preventDefault();
      var submitter = event.submitter;
      askForConfirmation(form.getAttribute('data-confirm'), function () {
        form.__confirmPassed = true;
        if (submitter && form.requestSubmit) form.requestSubmit(submitter);
        else if (form.requestSubmit) form.requestSubmit();
        else form.submit();
      });
    }, true);
    document.addEventListener('click', function (event) {
      var button = event.target.closest('button[data-confirm]');
      if (!button || !button.form || button.__confirmPassed) return;
      event.preventDefault();
      askForConfirmation(button.getAttribute('data-confirm'), function () {
        button.__confirmPassed = true;
        button.form.__confirmPassed = true;
        if (button.form.requestSubmit) button.form.requestSubmit(button);
        else button.form.submit();
      });
    });
  }

  /* Toasts auto-dismiss, with a manual close button. */
  $$('.flash').forEach(function (toast) {
    var close = function () {
      toast.classList.add('out');
      window.setTimeout(function () { toast.remove(); }, 360);
    };
    var closeButton = $('.x', toast);
    if (closeButton) closeButton.addEventListener('click', close);
    window.setTimeout(close, toast.classList.contains('error') ? 8500 : 5200);
  });

  /* Mobile navigation drawer. */
  var menuButton = $('#menuBtn');
  var scrim = $('#scrim');
  function setMenu(open) {
    body.classList.toggle('nav-open', open);
    if (menuButton) menuButton.setAttribute('aria-expanded', open ? 'true' : 'false');
  }
  if (menuButton) menuButton.addEventListener('click', function () { setMenu(!body.classList.contains('nav-open')); });
  if (scrim) scrim.addEventListener('click', function () { setMenu(false); });
  $$('.sidebar nav a').forEach(function (link) { link.addEventListener('click', function () { setMenu(false); }); });
  document.addEventListener('keydown', function (event) {
    if (event.key === 'Escape') {
      setMenu(false);
      if (accentPopover && !accentPopover.hidden) {
        accentPopover.hidden = true;
        if (accentButton) accentButton.setAttribute('aria-expanded', 'false');
      }
    }
  });

  /* Insert a saved response into the reply box without leaving the current cursor. */
  document.addEventListener('click', function (event) {
    var insertButton = event.target.closest('[data-insert-target]');
    if (!insertButton) return;
    var target = document.getElementById(insertButton.getAttribute('data-insert-target'));
    if (!target) return;
    target.value = (target.value ? target.value.replace(/\s+$/, '') + '\n\n' : '') + (insertButton.getAttribute('data-text') || '');
    target.focus();
    target.dispatchEvent(new Event('input', { bubbles: true }));
  });

  /* Live character counts for long messages. */
  $$('[data-counter]').forEach(function (field) {
    var output = $(field.getAttribute('data-counter'));
    var updateCount = function () { if (output) output.textContent = field.value.length.toLocaleString('fa-IR'); };
    field.addEventListener('input', updateCount);
    updateCount();
  });
})();

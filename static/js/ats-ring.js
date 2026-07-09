/**
 * ATS Animated Progress Ring
 *
 * Reads  data-ats-score="<0-100>"  on  .ats-ring-wrap  elements,
 * assigns the correct colour class, and animates stroke-dashoffset
 * from 0 → target on page load.
 *
 * Public API:
 *   ATSRing.update(score, wrapEl?)
 *     – pass a specific wrapper element or omit to update all rings.
 */
(function () {
  'use strict';

  /* Matches SVG: viewBox 0 0 120 120, r=48  →  C = 2π × 48 */
  var CIRCUMFERENCE = 301.593;

  function colorClass(score) {
    if (score <= 40) return 'ats-ring--red';
    if (score <= 70) return 'ats-ring--orange';
    if (score <= 85) return 'ats-ring--blue';
    return 'ats-ring--green';
  }

  function animateRing(wrap) {
    var score   = Math.max(0, Math.min(100, parseFloat(wrap.dataset.atsScore) || 0));
    var progress = wrap.querySelector('.ats-ring-progress');
    if (!progress) return;

    /* Apply colour class — replace any previous band class */
    progress.classList.remove(
      'ats-ring--red', 'ats-ring--orange', 'ats-ring--blue', 'ats-ring--green'
    );
    progress.classList.add(colorClass(score));

    /* Reset to fully hidden so re-animation always plays from 0 */
    progress.style.transition = 'none';
    progress.style.strokeDashoffset = CIRCUMFERENCE;

    /* Two rAF frames to flush the reset before starting the transition */
    requestAnimationFrame(function () {
      requestAnimationFrame(function () {
        progress.style.transition = '';
        progress.style.strokeDashoffset = CIRCUMFERENCE * (1 - score / 100);
      });
    });
  }

  function initAllRings() {
    document.querySelectorAll('.ats-ring-wrap[data-ats-score]').forEach(animateRing);
  }

  /* Fire after DOM is ready */
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initAllRings);
  } else {
    initAllRings();
  }

  /* ── Public API ──────────────────────────────────────────────── */
  window.ATSRing = {
    /**
     * Update one or all rings with a new score, then re-animate.
     * @param {number} score   – new score 0-100
     * @param {Element} [wrap] – specific .ats-ring-wrap; omit for all
     */
    update: function (score, wrap) {
      var targets = wrap
        ? [wrap]
        : Array.from(document.querySelectorAll('.ats-ring-wrap[data-ats-score]'));

      targets.forEach(function (el) {
        var clamped = Math.max(0, Math.min(100, parseInt(score, 10) || 0));
        el.dataset.atsScore = clamped;
        el.setAttribute('aria-label', 'ATS score ' + clamped + ' out of 100');

        var scoreEl = el.querySelector('.ats-ring-score');
        if (scoreEl) scoreEl.textContent = clamped;

        animateRing(el);
      });
    }
  };
})();

(function () {
  var KEY = 'orca-cookie-consent';
  var TXT = {
    de: {
      msg: 'Wir verwenden nur technisch notwendige Cookies. Externe Inhalte wie die Google-Karte werden erst nach Ihrer Zustimmung geladen und können dabei Cookies setzen.',
      accept: 'Akzeptieren', decline: 'Ablehnen', more: 'Impressum & Datenschutz',
      mapMsg: 'Zum Anzeigen der Karte ist Ihre Zustimmung erforderlich. Dabei werden Daten an Google übertragen.',
      mapBtn: 'Karte laden'
    },
    en: {
      msg: 'We only use technically necessary cookies. External content such as the Google map is loaded only after your consent and may set cookies.',
      accept: 'Accept', decline: 'Decline', more: 'Imprint & Privacy',
      mapMsg: 'Your consent is required to display the map. Data will be transferred to Google.',
      mapBtn: 'Load map'
    },
    fr: {
      msg: 'Nous utilisons uniquement des cookies techniquement nécessaires. Les contenus externes comme la carte Google ne sont chargés qu\u2019après votre consentement et peuvent déposer des cookies.',
      accept: 'Accepter', decline: 'Refuser', more: 'Mentions légales',
      mapMsg: 'Votre consentement est requis pour afficher la carte. Des données seront transmises à Google.',
      mapBtn: 'Charger la carte'
    }
  };

  function lang() {
    var h = (document.documentElement.lang || 'de').slice(0, 2);
    return TXT[h] ? h : 'de';
  }
  function get() { try { return localStorage.getItem(KEY); } catch (e) { return null; } }
  function set(v) { try { localStorage.setItem(KEY, v); } catch (e) {} }

  function activateMaps() {
    var maps = document.querySelectorAll('[data-cookie-map]');
    maps.forEach(function (el) {
      var url = el.getAttribute('data-cookie-map');
      el.innerHTML = '';
      var f = document.createElement('iframe');
      f.src = url;
      f.loading = 'lazy';
      f.setAttribute('style', 'width:100%;height:100%;border:0;filter:grayscale(15%) contrast(95%);display:block;');
      el.appendChild(f);
    });
  }

  function mapPlaceholders() {
    var t = TXT[lang()];
    document.querySelectorAll('[data-cookie-map]').forEach(function (el) {
      if (el.querySelector('iframe')) return;
      el.innerHTML =
        '<div style="width:100%;height:100%;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:16px;text-align:center;padding:24px;box-sizing:border-box;background:#e7e1d5;color:#6b6560;">' +
        '<div style="font-size:14px;line-height:1.6;max-width:360px;">' + t.mapMsg + '</div>' +
        '<button type="button" data-load-map style="padding:12px 26px;border:1px solid #1b1a17;background:transparent;font:600 11px/1 Manrope,sans-serif;letter-spacing:0.14em;text-transform:uppercase;color:#1b1a17;cursor:pointer;">' + t.mapBtn + '</button>' +
        '</div>';
      var b = el.querySelector('[data-load-map]');
      if (b) b.addEventListener('click', function () { set('accepted'); activateMaps(); });
    });
  }

  function removeBanner() {
    var b = document.getElementById('orca-cookie-banner');
    if (b) b.parentNode.removeChild(b);
  }

  function showBanner() {
    if (document.getElementById('orca-cookie-banner')) return;
    var t = TXT[lang()];
    var wrap = document.createElement('div');
    wrap.id = 'orca-cookie-banner';
    wrap.setAttribute('style',
      'position:fixed;left:0;right:0;bottom:0;z-index:9999;background:#1b1a17;color:#e9e4da;' +
      'padding:20px 24px;display:flex;align-items:center;gap:22px;flex-wrap:wrap;justify-content:center;' +
      'font-family:Manrope,sans-serif;box-shadow:0 -8px 30px rgba(0,0,0,0.25);');
    wrap.innerHTML =
      '<div style="font-size:13px;line-height:1.6;max-width:640px;flex:1 1 320px;">' + t.msg +
      ' <a href="./Legal.dc.html" style="color:#c9b89a;text-decoration:underline;">' + t.more + '</a></div>' +
      '<div style="display:flex;gap:12px;flex-shrink:0;">' +
      '<button type="button" data-decline style="padding:12px 24px;border:1px solid rgba(233,228,218,0.5);background:transparent;color:#e9e4da;font:600 11px/1 Manrope,sans-serif;letter-spacing:0.14em;text-transform:uppercase;cursor:pointer;">' + t.decline + '</button>' +
      '<button type="button" data-accept style="padding:12px 24px;border:1px solid #c9b89a;background:#c9b89a;color:#1b1a17;font:600 11px/1 Manrope,sans-serif;letter-spacing:0.14em;text-transform:uppercase;cursor:pointer;">' + t.accept + '</button>' +
      '</div>';
    document.body.appendChild(wrap);
    wrap.querySelector('[data-accept]').addEventListener('click', function () {
      set('accepted'); removeBanner(); activateMaps();
    });
    wrap.querySelector('[data-decline]').addEventListener('click', function () {
      set('declined'); removeBanner(); mapPlaceholders();
    });
  }

  function applyMapState() {
    var c = get();
    if (c === 'accepted') activateMaps();
    else mapPlaceholders();
  }

  function watchForMaps() {
    // DC content mounts asynchronously, so the map element may not exist yet.
    applyMapState();
    var obs = new MutationObserver(function () {
      var el = document.querySelector('[data-cookie-map]');
      if (el && !el.querySelector('iframe') && !el.querySelector('[data-load-map]')) {
        applyMapState();
      }
    });
    obs.observe(document.body, { childList: true, subtree: true });
  }

  function init() {
    watchForMaps();
    if (get() === null) showBanner();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();

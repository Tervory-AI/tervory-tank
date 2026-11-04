/* Internal video-shop embed. Only a Rig publishable key belongs in the browser. */
(function (global) {
  'use strict';
  global.VideoShop = {
    async mount(container, options) {
      const base = new URL(options.rigBase, document.baseURI);
      if (base.protocol !== 'https:' && base.hostname !== 'localhost') throw new Error('https_required');
      if (!/^rk_pub_[A-Za-z0-9_-]+$/.test(options.key)) throw new Error('publishable_key_required');
      const prefix = base.href.replace(/\/$/, '') + '/v1/rig';
      let destroyed = false, blobURL, session, selected, busy = false;
      const abort = new AbortController();
      const request = async (path, data, blob = false) => {
        const response = await fetch(prefix + path, {
          method: data === undefined ? 'GET' : 'POST', credentials: 'omit',
          headers: {'X-Rig-Key': options.key, ...(data === undefined ? {} : {'Content-Type': 'application/json'})},
          body: data === undefined ? undefined : JSON.stringify(data), signal: abort.signal
        });
        if (!response.ok) throw new Error('request_failed');
        return blob ? response.blob() : response.json();
      };
      const root = container.attachShadow({mode: 'open'});
      const style = document.createElement('style');
      style.textContent = ':host{display:block;color:#001840;font:inherit}video{width:100%}aside{border:1px solid #B8BFD0;padding:12px;background:#F4F6FB}button{font:inherit;margin:4px;padding:8px}button:focus-visible{outline:2px solid #001840}';
      const video = document.createElement('video');
      video.controls = true; video.playsInline = true; video.setAttribute('aria-label', options.videoLabel || 'Video');
      const panel = document.createElement('aside'); panel.setAttribute('aria-live', 'polite');
      const status = document.createElement('p'); status.setAttribute('role', 'status');
      const details = document.createElement('div');
      root.append(style, video, panel, details, status);
      const labels = {add: 'Add to cart', checkout: 'Checkout', loading: 'Loading', adding: 'Adding', added: 'Added to cart', error: 'Please try again', ...options.labels};
      const setStatus = state => { status.textContent = labels[state] || ''; container.dispatchEvent(new CustomEvent('video-shop:state', {detail: {state}})); };
      const button = (text, action) => {
        const node = document.createElement('button'); node.type = 'button'; node.textContent = text;
        node.addEventListener('click', action); return node;
      };
      const detail = async product => {
        selected = product.id; details.replaceChildren(); setStatus('loading');
        try {
          const value = await request('/products/' + encodeURIComponent(product.id));
          if (destroyed || selected !== product.id) return;
          const name = document.createElement('h3'); name.textContent = product.name;
          const price = document.createElement('p');
          price.textContent = product.price.amount + ' ' + product.price.currency;
          const picture = document.createElement('img');
          try { const source = new URL(product.image); if (source.protocol === 'https:') picture.src = source.href; } catch (_) {}
          picture.alt = product.name; picture.style.maxWidth = '160px';
          const attributes = document.createElement('p'); attributes.textContent = JSON.stringify(value.attributes || {});
          const add = button(labels.add || '', async () => {
            if (busy) return;
            busy = true; add.disabled = true; setStatus('adding');
            try {
              if (!session) session = (await request('/cart/session', {})).session;
              const cart = await request('/cart/add', {session, product_id: product.id, quantity: 1});
              container.dispatchEvent(new CustomEvent('video-shop:cart', {detail: cart})); setStatus('added');
            } catch (_) { setStatus('error'); }
            finally { busy = false; add.disabled = false; }
          });
          const checkout = button(labels.checkout || '', async () => {
            if (!session || busy) return;
            busy = true; checkout.disabled = true;
            try {
              const result = await request('/cart/checkout', {session});
              const url = new URL(result.checkout_url);
              if (url.protocol !== 'https:') throw new Error('checkout_url');
              global.location.assign(url.href);
            } catch (_) { setStatus('error'); }
            finally { busy = false; checkout.disabled = false; }
          });
          // Product detail comes from the existing Rig endpoint; render as text only.
          const description = document.createElement('p');
          description.textContent = value.product?.name || value.name || product.name;
          details.replaceChildren(name, picture, price, description, attributes, add, checkout); setStatus('ready');
        } catch (_) { setStatus('error'); }
      };
      try {
        const timeline = await request('/video-shop/videos/' + encodeURIComponent(options.videoId));
        const media = await request('/video-shop/videos/' + encodeURIComponent(options.videoId) + '/media', undefined, true);
        if (destroyed) return;
        blobURL = URL.createObjectURL(media); video.src = blobURL;
        let previous = '';
        const update = () => {
          const ids = [...new Set(timeline.moments.filter(m => m.start <= video.currentTime && video.currentTime < m.end).map(m => m.product_id))];
          const signature = JSON.stringify(ids);
          if (signature === previous) return;
          previous = signature; panel.replaceChildren();
          if (!ids.includes(selected)) { selected = undefined; details.replaceChildren(); }
          for (const id of ids) { const product = timeline.products[id]; panel.append(button(product.name, () => detail(product))); }
        };
        video.addEventListener('timeupdate', update); video.addEventListener('seeked', update); update(); setStatus('ready');
      } catch (_) { setStatus('error'); }
      return {destroy() { destroyed = true; abort.abort(); video.pause(); video.removeAttribute('src'); video.load(); if (blobURL) URL.revokeObjectURL(blobURL); root.replaceChildren(); }};
    }
  };
})(window);

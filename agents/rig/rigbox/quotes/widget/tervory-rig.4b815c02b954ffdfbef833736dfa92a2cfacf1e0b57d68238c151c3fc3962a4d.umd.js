(function(e,t){typeof exports==`object`&&typeof module<`u`?t(exports):typeof define==`function`&&define.amd?define([`exports`],t):(e=typeof globalThis<`u`?globalThis:e||self,t(e.TervoryRig={}))})(this,function(e){Object.defineProperty(e,Symbol.toStringTag,{value:`Module`});var t=Object.defineProperty,n=(e,t,n)=>()=>{if(n)throw n[0];try{return e&&(t=e(e=0)),t}catch(e){throw n=[e],e}},r=(e,n)=>{let r={};for(var i in e)t(r,i,{get:e[i],enumerable:!0});return n||t(r,Symbol.toStringTag,{value:`Module`}),r};function i(){if(typeof crypto.randomUUID==`function`)return crypto.randomUUID();let e=crypto.getRandomValues(new Uint8Array(16));e[6]=e[6]&15|64,e[8]=e[8]&63|128;let t=Array.from(e,e=>e.toString(16).padStart(2,`0`)).join(``);return`${t.slice(0,8)}-${t.slice(8,12)}-${t.slice(12,16)}-${t.slice(16,20)}-${t.slice(20)}`}var a,o=n((()=>{a=class extends Error{code;status;constructor(e,t,n){super(t),this.name=`RigError`,this.code=e,this.status=n}}})),s=r({ask:()=>h,fits:()=>l,graph:()=>m,linkQuote:()=>g,product:()=>d,quote:()=>ee,search:()=>u,setups:()=>f,swap:()=>p});function c(){throw new a(`mock_not_bundled`,`Set api-base to your Rig API.`,400)}function l(){return c()}async function u(){return c()}async function d(){return c()}async function f(){return c()}async function p(){return c()}async function m(){return c()}async function h(){return c()}async function g(){return c()}async function ee(){return c()}var te=n((()=>{o()}));o();var _=class{apiBase;key;fetchImpl;mockModule=null;constructor(e){this.apiBase=e.apiBase.replace(/\/$/,``),this.key=e.key,this.fetchImpl=e.fetchImpl??globalThis.fetch.bind(globalThis)}get usesMock(){return this.apiBase===`mock`}loadMock(){return this.mockModule??=Promise.resolve().then(()=>(te(),s)),this.mockModule}async search(e,t=12){if(this.usesMock)return(await this.loadMock()).search(e,t);let n=new URLSearchParams({q:e,limit:String(t)});return this.request(`/v1/rig/search?${n.toString()}`)}async product(e){return this.usesMock?(await this.loadMock()).product(e):this.request(`/v1/rig/products/${encodeURIComponent(e)}`)}async settledSearch(e,t){this.usesMock||await this.request(`/v1/rig/search-events`,{method:`POST`,body:JSON.stringify({event_id:e,no_results:t})})}async setups(e){return this.usesMock?(await this.loadMock()).setups(e):this.request(`/v1/rig/setups`,{method:`POST`,body:JSON.stringify({product_id:e})})}async swap(e,t,n=!1){return this.usesMock?(await this.loadMock()).swap(e,t):this.request(`/v1/rig/swap`,{method:`POST`,body:JSON.stringify({setup:v(e),role:t,commit:n})})}async graph(e){return this.usesMock?(await this.loadMock()).graph(e):this.request(`/v1/rig/graph/${encodeURIComponent(e)}`)}async ask(e){return this.usesMock?(await this.loadMock()).ask(e):this.request(`/v1/rig/ask`,{method:`POST`,body:JSON.stringify({product_id:e.product_id,...e.setup?{setup:v(e.setup)}:{},question:e.question})})}async linkQuote(e){return this.usesMock?(await this.loadMock()).linkQuote(e):this.request(`/v1/rig/link-quote`,{method:`POST`,body:JSON.stringify({url:e.url,note:e.note,...e.contact?{contact:e.contact}:{}})})}async quote(e){if(this.usesMock)return(await this.loadMock()).quote(e);let t={contact:e.contact,...e.setup?{setup:v(e.setup)}:{},...e.product_id?{product_id:e.product_id}:{}};return this.request(`/v1/rig/quote`,{method:`POST`,body:JSON.stringify(t)})}async request(e,t={}){let n=new Headers(t.headers);n.set(`Accept`,`application/json`),n.set(`X-Rig-Key`,this.key),t.body&&n.set(`Content-Type`,`application/json`);let r=await this.fetchImpl(`${this.apiBase}${e}`,{...t,headers:n});if(!r.ok){let e=null;try{e=await r.json()}catch{}throw e?.error?.code?new a(e.error.code,e.error.message,r.status):new a(`http_error`,`The request failed.`,r.status)}return await r.json()}};function v(e){return{tier:e.tier,label:e.label,parts:e.parts,total:e.total,why:e.why}}function y(e){let t=Number.isInteger(e.amount)?0:2,[n,r]=e.amount.toFixed(t).split(`.`),i=n.replace(/\B(?=(\d{3})+(?!\d))/g,` `),a=r?`${i}.${r}`:i;if(e.currency===`ZAR`)return`R ${a}`;try{return new Intl.NumberFormat(`en-US`,{style:`currency`,currency:e.currency,minimumFractionDigits:t,maximumFractionDigits:t}).format(e.amount)}catch{return`${e.currency} ${a}`}}function b(e){return typeof e.attributes.summary==`string`?e.attributes.summary:e.category}function x(e){return typeof e.attributes.detail==`string`?e.attributes.detail:b(e)}function S(e){return typeof e.attributes.match_note==`string`?e.attributes.match_note:``}function C(e){return e.map(e=>e.trim()).filter(Boolean)}var w={id:`custom-nation`,colors:{canvas:`#f2efe7`,ink:`#242722`,accent:`#ad322c`,muted:`#686b60`,faint:`#9a9c92`,line:`#e3dfd4`,lineStrong:`#d5d0c3`,card:`#ffffff`,badge:`#e8e4da`,onAccent:`#ffffff`,featured:`#242722`,featuredText:`#fcfaf4`,featuredMuted:`#b8baab`},graph:{canvas:`#121510`,raised:`#1a1d18`,text:`#fcfaf4`,muted:`#b8baab`,line:`rgba(255,255,255,0.12)`,chip:`#1a1d18`,chipOn:`#2a1a18`,glow:`rgba(31,42,34,1)`},fonts:{heading:`"Barlow Condensed", "Arial Narrow", sans-serif`,body:`Inter, "Helvetica Neue", sans-serif`,href:`https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@600&family=Inter:wght@400;500;600&display=swap`},radius:`0px`,radiusGraph:`8px`,copy:{eyebrow:`Sourced from the USA`,title:`Find it. We source it.`,placeholder:`Search a make, model or part — e.g. Staccato, Leupold Mark 5, MDT ACC`,popularLabel:`Popular:`,popular:[`Staccato`,`Leupold`,`Nightforce`,`MDT`,`TriggerTech`,`Proof Research`],steps:[{title:`Search`,body:`Every SKU from our US suppliers, as you type.`},{title:`Complete your setup`,body:`We suggest the parts that fit what you chose.`},{title:`Request a quote`,body:`One indicative price. We confirm and import it for you.`}],setupKicker:`Complete your setup`,optionWord:`option`,optionsWord:`options`,youChose:`You chose`,finePrint:`One indicative total per setup. We confirm stock, permits and the final quotation in your client space.`,missingTitle:`Not in our feeds yet? We can still get it.`,missingBody:`Paste the link to the product on any US store and we will quote it for you.`,linkPlaceholder:`https://…`,linkLabel:`Link`,requestQuote:`Request a quote`,quoteSetup:`Request a quote for this setup`,search:`Search`,complete:`Complete my setup`,quoteOnly:`Quote this only`,selected:`Selected`,explore:`Explore`,indicative:`Indicative`,setupIndicative:`Setup, indicative`,swap:`Swap`,noSwap:`No other part fits this role.`,back:`Back to setups`,askPlaceholder:`Ask a question… “Will this fit a weapon light too?”`,ask:`Ask`,whyLabel:`Why this setup`,partsFit:`all fit`,partWord:`part`,partsWord:`parts`,moreWord:`more`,fittedWord:`fitted`,showMore:`Show`,showLess:`Show fewer`,fits:`fits`,yourSetup:`Your setup`,quoteTitle:`Request a quote`,quoteName:`Name`,quoteEmail:`Email`,quotePhone:`Phone`,linkRequired:`Enter the product link.`,linkInvalid:`Enter a valid web link, starting with http:// or https://.`,nameRequired:`Enter your name.`,nameInvalid:`Use 120 characters or fewer for your name.`,emailRequired:`Enter your email address.`,emailInvalid:`Enter a valid email address, such as name@example.com.`,phoneRequired:`Enter your phone number.`,phoneInvalid:`Enter a valid phone number with 7 to 15 digits.`,quoteSend:`Send request`,quoteSent:`Request received. Reference`,quotePending:`We've got your request. The store will be in touch. Reference`,quoteNeedsPerson:`We've got your request. The store will be in touch. Reference`,graphIndicative:`indicative`,photoLabel:`Product photo (from feed)`,chosenPhotoLabel:`PHOTO`,loading:`Loading…`,noSetups:`No setups came back for this product. You can still quote it on its own.`,swappedNote:`Updated with a part that still fits.`,resultWord:`result`,resultsWord:`results`,forWord:`for`,mark:`RIG · by Tervory`,close:`Close`,notAlternative:`That part is not an alternative that fits.`,errorGeneric:`Something went wrong.`,unavailable:`That setup is no longer available.`}},T={id:`neutral`,colors:{canvas:`#f4f5f7`,ink:`#1c1e21`,accent:`#1d4e89`,muted:`#5c6370`,faint:`#8b919a`,line:`#d5d8de`,lineStrong:`#c5c9d1`,card:`#ffffff`,badge:`#e6e8ec`,onAccent:`#ffffff`,featured:`#1c1e21`,featuredText:`#f7f8fa`,featuredMuted:`#c5c9d1`},graph:{canvas:`#12141a`,raised:`#1b1e27`,text:`#f7f8fa`,muted:`#c5c9d1`,line:`rgba(255,255,255,0.14)`,chip:`#1b1e27`,chipOn:`#172033`,glow:`rgba(29,78,137,0.35)`},fonts:{heading:`Newsreader, Georgia, serif`,body:`"Source Sans 3", "Helvetica Neue", sans-serif`,href:`https://fonts.googleapis.com/css2?family=Newsreader:opsz,wght@6..72,600&family=Source+Sans+3:wght@400;500;600&display=swap`},radius:`10px`,radiusGraph:`16px`,copy:{eyebrow:`From specialist suppliers`,title:`Find it. Complete the kit.`,placeholder:`Search a make, model or part — e.g. Sony, 70-200, Peak Design`,popularLabel:`Popular:`,popular:[`Sony`,`Canon`,`Nikon`,`Peak Design`,`SmallRig`,`Godox`],steps:[{title:`Search`,body:`Every item from the suppliers, as you type.`},{title:`Complete your setup`,body:`Parts that fit what you chose.`},{title:`Request a quote`,body:`One indicative price. The shop confirms it.`}],setupKicker:`Complete your setup`,optionWord:`option`,optionsWord:`options`,youChose:`You chose`,finePrint:`One indicative total per setup. The shop confirms stock and the final quotation.`,missingTitle:`Not in the catalogue yet? We can still quote it.`,missingBody:`Paste a link to the product and your contact details, and the shop will quote it.`,linkPlaceholder:`https://…`,linkLabel:`Link`,requestQuote:`Request a quote`,quoteSetup:`Request a quote for this setup`,search:`Search`,complete:`Complete my setup`,quoteOnly:`Quote this only`,selected:`Selected`,explore:`Explore`,indicative:`Indicative`,setupIndicative:`Setup, indicative`,swap:`Swap`,noSwap:`No other part fits this role.`,back:`Back to setups`,askPlaceholder:`Ask a question… “Does this work with the rest of the kit?”`,ask:`Ask`,whyLabel:`Why this setup`,partsFit:`all fit`,partWord:`part`,partsWord:`parts`,moreWord:`more`,fittedWord:`fitted`,showMore:`Show`,showLess:`Show fewer`,fits:`fits`,yourSetup:`Your setup`,quoteTitle:`Request a quote`,quoteName:`Name`,quoteEmail:`Email`,quotePhone:`Phone`,linkRequired:`Enter the product link.`,linkInvalid:`Enter a valid web link, starting with http:// or https://.`,nameRequired:`Enter your name.`,nameInvalid:`Use 120 characters or fewer for your name.`,emailRequired:`Enter your email address.`,emailInvalid:`Enter a valid email address, such as name@example.com.`,phoneRequired:`Enter your phone number.`,phoneInvalid:`Enter a valid phone number with 7 to 15 digits.`,quoteSend:`Send request`,quoteSent:`Request received. Reference`,quotePending:`We've got your request. The store will be in touch. Reference`,quoteNeedsPerson:`We've got your request. The store will be in touch. Reference`,graphIndicative:`indicative`,photoLabel:`Photo`,chosenPhotoLabel:`Photo`,loading:`Loading…`,noSetups:`No setups came back for this product. You can still quote it on its own.`,swappedNote:`Updated with a part that still fits.`,resultWord:`result`,resultsWord:`results`,forWord:`for`,mark:`RIG · by Tervory`,close:`Close`,notAlternative:`That part is not an alternative that fits.`,errorGeneric:`Something went wrong.`,unavailable:`That setup is no longer available.`}};function E(e){if(e===`custom-nation`)return w;if(!e||e===`neutral`)return T;if(e.trim().startsWith(`{`))try{let t=JSON.parse(e);return{...T,...t,id:typeof t.id==`string`?t.id:`custom`,colors:{...T.colors,...t.colors},graph:{...T.graph,...t.graph},fonts:{...T.fonts,...t.fonts},copy:{...T.copy,...t.copy,popular:t.copy?.popular??T.copy.popular,steps:t.copy?.steps??T.copy.steps}}}catch{return T}return T}function D(e){return e.screen===`explore`?B(e):`<div class="shell">${O(e)}</div>${W(e)}`}function O(e){let t=e.screen===`home`?M(e):e.screen===`results`?N(e):e.screen===`missing`?F(e):L(e);return`${k(e,!1)}${A(e)}${ne(e,`q`)}${j(e)}${t}`}function k(e,t){let n=e.theme.copy;return`<header class="${t?`explore-header`:`header`}">
    ${t?``:`<span class="dash" aria-hidden="true"></span>`}
    ${t?``:`<p class="eyebrow">${Z(n.eyebrow)}</p>`}
    <p class="${t?`explore-mark`:`mark`}">${Z(n.mark)}</p>
  </header>`}function A(e){return`<h1 class="title">${Z(e.theme.copy.title)}</h1>`}function ne(e,t){let n=e.theme.copy;return`<form class="search" role="search">
    <label class="sr" for="${t}">${Z(n.search)}</label>
    <span class="search-icon" aria-hidden="true">⌕</span>
    <input id="${t}" type="search" name="q" autocomplete="off" enterkeyhint="search" placeholder="${Z(n.placeholder)}" value="${Z(e.query)}">
    <button class="btn btn-accent" type="submit">${Z(n.search)}</button>
  </form>`}function j(e){return e.message?`<p class="status" role="status">${Z(e.message)}</p>`:``}function M(e){let t=e.theme.copy,n=t.popular.map(e=>`<button type="button" class="chip" data-action="popular" data-q="${Z(e)}">${Z(e)}</button>`).join(``),r=t.steps.map((e,t)=>`<section class="step">
        <span class="step-no">${String(t+1).padStart(2,`0`)}</span>
        <h2>${Z(e.title)}</h2>
        <p>${Z(e.body)}</p>
      </section>`).join(``);return`<div class="popular"><span class="popular-label">${Z(t.popularLabel)}</span>${n}</div>
    <div class="steps">${r}</div>`}function N(e){let t=e.theme.copy,n=e.results.length===1?t.resultWord:t.resultsWord,r=e.results.map(t=>P(e,t)).join(``);return`<div class="meta-row">
      <strong>${e.results.length} ${Z(n)} ${Z(t.forWord)} “${Z(e.query)}”</strong>
    </div>
    <div class="cards">${r}</div>`}function P(e,t){let n=e.theme.copy,r=e.selectedId===t.id,i=r?`<button type="button" class="btn btn-selected" data-action="complete" data-id="${Z(t.id)}">${Z(n.selected)} ✓</button>`:`<button type="button" class="btn btn-ghost" data-action="complete" data-id="${Z(t.id)}">${Z(n.complete)}</button>`;return`<article class="card${r?` selected`:``}">
    ${J(t,e,`photo-lg`)}
    <div class="brand-row"><p class="brand">${Z(t.brand)}</p></div>
    <h2 class="card-name">${Z(t.name)}</h2>
    <p class="summary">${Z(b(t))}</p>
    ${q(n.indicative,t.price,``)}
    <div class="actions">
      ${i}
      <button type="button" class="btn btn-ghost" data-action="quote-product" data-id="${Z(t.id)}">${Z(n.quoteOnly)}</button>
    </div>
  </article>`}function F(e){let t=e.theme.copy,n=e.linkRequestId?Y(e.linkAck??{request_id:e.linkRequestId},e.theme):``,r=e.linkError?`<p class="status" role="status">${Z(e.linkError)}</p>`:``;return`<section class="missing">
    <h2>${Z(t.missingTitle)}</h2>
    <p class="missing-copy">${Z(t.missingBody)}</p>
    <form class="link-form" novalidate>
      ${I(e,`url`,t.linkLabel,`url`,e.linkUrl,`inputmode="url" maxlength="2048" placeholder="${Z(t.linkPlaceholder)}"`)}
      ${I(e,`name`,t.quoteName,`text`,e.linkContact?.name??``,`autocomplete="name" maxlength="120"`)}
      ${I(e,`email`,t.quoteEmail,`email`,e.linkContact?.email??``,`autocomplete="email" maxlength="254"`)}
      ${I(e,`phone`,t.quotePhone,`tel`,e.linkContact?.phone??``,`autocomplete="tel" inputmode="tel" maxlength="40"`)}
      <button class="btn btn-accent" type="submit" ${e.linkPending||e.linkRequestId?`disabled`:``}>${Z(t.requestQuote)}</button>
      ${U()}
    </form>
    ${r}${n}
  </section>`}function I(e,t,n,r,i,a){let o=e.linkErrors?.[t],s=`link-${t}`;return`<div class="note">
    <label for="${s}">${Z(n)}</label>
    <input class="field" id="${s}" name="${t}" type="${r}" required ${a}
      ${e.linkPending||e.linkRequestId?`disabled`:``}
      ${o?`aria-invalid="true" aria-describedby="${s}-error"`:``} value="${Z(i)}">
    ${o?`<p class="field-error" id="${s}-error">${Z(o)}</p>`:``}
  </div>`}function L(e){let t=e.theme.copy,n=e.product;if(!n)return``;let r=S(n),i=e.setups.map((t,n)=>R(e,t,n)).join(``),a=e.setups.length===0?`<p class="fine">${Z(t.noSetups)}</p>`:``;return`<section class="chosen">
      ${J(n,e,`photo-sm`)}
      <div class="chosen-copy">
        <p class="you-chose">${Z(t.youChose)}</p>
        <h2>${Z(n.name)} · ${Z(x(n))}</h2>
        ${r?`<p class="chosen-note">${Z(r)}</p>`:``}
      </div>
      <div class="chosen-side">
      </div>
    </section>
    ${e.setups.length?`<div class="kicker-row"><span class="kicker-bar" aria-hidden="true"></span><h2 class="kicker">${Z(t.setupKicker)} — ${e.setups.length} ${Z(e.setups.length===1?t.optionWord:t.optionsWord)}</h2><button type="button" class="text-btn explore-link" data-action="explore" data-id="${Z(n.id)}">${Z(t.explore)}</button></div>`:``}
    <div class="setups">${i}</div>
    ${a}
    ${e.setups.length?`<p class="fine">${Z(t.finePrint)}</p>`:``}`}function R(e,t,n){let r=e.theme.copy,i=!!t.badge,a=C(t.why),o=e.customizedTiers.includes(t.tier)?r.swappedNote:a[0]??``,s=t.parts.map(n=>z(e,t,n)).join(``);return`<article class="setup${i?` featured`:``}">
    <div class="setup-head">
      <span class="setup-no">${String(n+1).padStart(2,`0`)}</span>
      <h3 class="setup-name">${Z(t.tier)}</h3>
      ${t.badge?`<span class="badge-hot">${Z(t.badge)}</span>`:``}
    </div>
    <p class="label">${Z(t.label)}</p>
    ${s}
    ${o?`<p class="fit-line">✓ ${Z(o.replace(/^(?:[✓✔]\s*)+/,``))}</p>`:``}
    ${q(r.setupIndicative,t.total,`price-lg`)}
    <button type="button" class="btn btn-accent quote-wide" data-action="quote-setup" data-tier="${Z(t.tier)}">${Z(r.quoteSetup)} →</button>
  </article>`}function z(e,t,n){let r=e.theme.copy,i=n.product.id===e.selectedId,a=e.swap?.role===n.role&&e.swap.tier===t.tier,o=a?`<div class="options">${e.swap?.options.length?e.swap.options.map(e=>`<button type="button" class="option" data-action="pick-swap" data-tier="${Z(t.tier)}" data-id="${Z(e.id)}">${Z(e.name)}</button>`).join(``):`<p class="fit-line">${Z(r.noSwap)}</p>`}</div>`:``;return`<div class="part-block">
    <div class="part">
      ${J(n.product,e,`photo-xs`)}
      <div class="part-copy">
        <span class="role">${Z(n.role)}</span>
        <span class="part-name">${Z(n.product.name)}</span>
      </div>
      ${i?``:`<button type="button" class="swap-btn" data-action="swap" data-tier="${Z(t.tier)}" data-role="${Z(n.role)}" aria-expanded="${a?`true`:`false`}">${Z(r.swap)} ⇄</button>`}
    </div>
    ${o}
  </div>`}function B(e){let t=e.theme.copy,n=e.graph,r=n?.centre??e.product,i=G(e),a=(n?.branches??[]).map(n=>{let r=n.products.some(e=>i?.parts.some(t=>t.product.id===e.id)),a=e.expanded.includes(n.category),o=e.expanded.includes(`more:${n.category}`),s=o?n.products:n.products.slice(0,4),c=a?s.map(e=>`<button type="button" class="g-chip${i?.parts.some(t=>t.product.id===e.id)??!1?` on`:``}" data-action="pick-graph" data-id="${Z(e.id)}">
                <span class="swatch" aria-hidden="true"></span>
                <span class="g-copy">
                  <span class="g-name">${Z(e.name)}</span>
                  <span class="g-meta"><span class="amount">${Z(y(e.price))}</span> · ${Z(t.fits)} ✓</span>
                </span>
              </button>`).join(``):``,l=n.category.toLowerCase()===`part`?n.count===1?t.partWord:t.partsWord:n.category,u=n.count-Math.min(4,n.products.length),d=`+ ${u} ${Z(t.moreWord)} ${Z(t.fittedWord)} ${Z(l.toLowerCase())}`,f=a&&u>0?n.products.length>4?`<button type="button" class="more text-btn" data-action="branch" data-category="${Z(`more:${n.category}`)}" aria-expanded="${o}">${d}</button>`:`<span class="more">${d}</span>`:``;return`<div class="branch-row">
        <button type="button" class="branch${r?` on`:``}" data-action="branch" data-category="${Z(n.category)}" aria-expanded="${a?`true`:`false`}">
          <span class="count">${n.count}</span>
          <span class="cat">${Z(l)}</span>
        </button>
        <div class="products">${c}${f}</div>
      </div>`}).join(``),o=r?b(r):``,s=r?`<div class="centre">
        <div class="orb-wrap">
          <span class="orb-label">${Z(t.youChose)}</span>
          <span class="orb" aria-hidden="true"></span>
        </div>
        <h2>${Z(r.name)}</h2>
        <p>${o?`${Z(o)} · `:``}${Z(t.indicative)} <span class="amount">${Z(y(r.price))}</span></p>
      </div>`:``;return`<div class="shell shell-explore"><div class="explore">
    <header class="explore-header">
      <h1><button type="button" data-action="back-setup">${Z(t.title)}<span class="sr"> ${Z(t.back)}</span></button></h1>
      <form class="explore-search" role="search">
        <label class="sr" for="q">${Z(t.search)}</label>
        <span aria-hidden="true">⌕</span>
        <input id="q" type="search" name="q" autocomplete="off" value="${Z(e.query)}" placeholder="${Z(t.placeholder)}">
      </form>
      <p class="explore-mark">${Z(t.mark)}</p>
    </header>
    ${j(e)}
    <div class="explore-grid">
      <div class="graph-canvas"><svg class="connectors" aria-hidden="true"></svg>${s}
      <div class="graph">${a}</div></div>
      <div class="side">${V(e,i)}${H(e)}</div>
    </div>
  </div></div>${W(e)}`}function V(e,t){let n=e.theme.copy;if(!t)return`<aside class="panel"><p class="panel-body">${Z(n.noSetups)}</p></aside>`;let r=e.customizedTiers.includes(t.tier),i=C(t.why),a=r?n.swappedNote:i[1]??i[0]??t.label,o=r?n.swappedNote:i[2]??i[1]??i[0]??t.label,s=t.parts.map(e=>e.product.name).join(` + `),c=e.setups.map(e=>{let n=e.tier===t.tier;return`<button type="button" class="tier${n?` on`:``}" data-action="tier" data-tier="${Z(e.tier)}" aria-pressed="${n?`true`:`false`}">${Z(K(e))}</button>`}).join(``),l=t.parts.length===1?n.partWord:n.partsWord;return`<aside class="panel">
    <p class="panel-kicker">${Z(n.yourSetup)} · ${Z(t.tier)}</p>
    <h2>${Z(s)}</h2>
    <p class="panel-body">${Z(a)}</p>
    <div class="stats">
      <div class="stat"><strong>${t.parts.length}</strong><span>${Z(l)}, ${Z(n.partsFit)}</span></div>
      <div class="stat"><strong class="amount">${Z(y(t.total))}</strong><span>${Z(n.graphIndicative)}</span></div>
    </div>
    <div class="tier-row">${c}</div>
    <div class="why"><strong>✦ ${Z(n.whyLabel)}</strong><p>${Z(o)}</p></div>
    <button type="button" class="btn btn-accent quote-wide" data-action="quote-setup" data-tier="${Z(t.tier)}">${Z(n.quoteSetup)} →</button>
  </aside>`}function H(e){let t=e.theme.copy;return`${e.askAnswer?`<div class="answer" role="status"><p>${Z(e.askAnswer)}</p>${e.askCites?`<span>${Z(e.askCites)}</span>`:``}</div>`:``}<form class="ask">
    <label class="sr" for="ask-q">${Z(t.ask)}</label>
    <textarea id="ask-q" name="question" rows="2" placeholder="${Z(t.askPlaceholder)}">${Z(e.askQuestion)}</textarea>
    <button class="ask-go" type="submit" aria-label="${Z(t.ask)}">→</button>
  </form>`}function U(){return`<div data-quote-privacy hidden></div>`}function W(e){let t=e.quote;if(!t)return``;let n=e.theme.copy;return t.requestId?`<div class="backdrop">
      <div class="quote" role="dialog" aria-modal="true" aria-labelledby="quote-title">
        <h2 id="quote-title">${Z(n.quoteTitle)}</h2>
        ${Y(t.ack??{request_id:t.requestId},e.theme)}
        ${t.totalLabel?`<p class="summary">${Z(t.totalLabel)}</p>`:``}
        <button type="button" class="btn btn-accent" data-action="close-quote">${Z(n.close)}</button>
      </div>
    </div>`:`<div class="backdrop">
    <form class="quote" role="dialog" aria-modal="true" aria-labelledby="quote-title">
      <h2 id="quote-title">${Z(n.quoteTitle)}</h2>
      <p>${Z(t.title)}</p>
      ${t.totalLabel?`<p class="price-row"><span class="price-cap">${Z(e.theme.copy.indicative)}</span><span class="price">${Z(t.totalLabel)}</span></p>`:``}
      <label>${Z(n.quoteName)}
        <input class="field" id="quote-name" name="name" autocomplete="name" required ${t.pending?`disabled`:``} value="${Z(t.name)}">
      </label>
      <label>${Z(n.quoteEmail)}
        <input class="field" id="quote-email" name="email" type="email" autocomplete="email" required ${t.pending?`disabled`:``} value="${Z(t.email)}">
      </label>
      ${t.error?`<p class="status" role="status">${Z(t.error)}</p>`:``}
      <button class="btn btn-accent" type="submit" ${t.pending?`disabled`:``}>${Z(n.quoteSend)}</button>
      ${U()}
      <button type="button" class="text-btn" data-action="close-quote">${Z(n.close)}</button>
    </form>
  </div>`}function G(e){return e.setups.find(t=>t.tier===e.activeTier)??e.setups[0]??null}function K(e){return e.tier.charAt(0).toUpperCase()+e.tier.slice(1)}function q(e,t,n){return`<div class="price-row"><span class="price-cap">${Z(e)}</span><span class="price ${n}">${Z(y(t))}</span></div>`}function J(e,t,n){let r=X(e.image),i=n===`photo-sm`?t.theme.copy.chosenPhotoLabel:t.theme.copy.photoLabel;return`<div class="photo ${n}" aria-hidden="true">${r?`<img src="${Z(r)}" alt="">`:n===`photo-xs`?``:`<span>${Z(i)}</span>`}</div>`}function Y(e,t){return`<p class="ack" role="status">${Z(e.delivery===`pending`||e.delivery===`sending`?t.copy.quotePending:e.delivery===`needs_person`?t.copy.quoteNeedsPerson:t.copy.quoteSent)} ${Z(e.request_id)}.</p>`}function X(e){return/^https?:\/\//i.test(e)||e.startsWith(`data:image/`)?e:``}function Z(e){return e.replace(/[&<>"']/g,e=>{switch(e){case`&`:return`&amp;`;case`<`:return`&lt;`;case`>`:return`&gt;`;case`"`:return`&quot;`;default:return`&#39;`}})}var re=`
:host {
  all: initial;
  display: block;
  width: 100%;
  max-width: 100%;
  overflow-x: hidden;
  color: var(--rig-ink, #242722);
  background: var(--rig-canvas, #f2efe7);
  font-family: var(--rig-font-body, Inter, sans-serif);
  font-size: 16px;
  line-height: 1.4;
  box-sizing: border-box;
}
:host(.is-explore) {
  background: var(--rig-graph-canvas, #121510);
  color: var(--rig-graph-text, #fcfaf4);
}
*, *::before, *::after { box-sizing: border-box; }
button, input, textarea { font: inherit; color: inherit; }
button { cursor: pointer; }
img { max-width: 100%; display: block; }
p, h1, h2, h3 { margin: 0; }
.sr {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}
:focus-visible {
  outline: 2px solid var(--rig-accent);
  outline-offset: 2px;
}
.shell {
  width: min(1200px, 100%);
  margin: 0 auto;
  padding: 40px 48px 48px;
  display: flex;
  flex-direction: column;
  gap: 24px;
}
.shell-explore {
  width: 100%;
  max-width: none;
  margin: 0;
  padding: 0;
  gap: 0;
}
.header, .brand-row, .meta-row, .price-row, .part, .actions, .tier-row, .link-row, .popular {
  display: flex;
  align-items: center;
}
.header { gap: 12px; }
.dash { width: 28px; height: 2px; background: var(--rig-accent); flex: none; }
.eyebrow {
  margin: 0;
  color: var(--rig-muted);
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.16em;
  text-transform: uppercase;
}
.mark {
  margin-left: auto;
  color: var(--rig-faint);
  font-size: 11px;
  font-weight: 500;
}
h1.title {
  font-family: var(--rig-font-heading);
  font-weight: 600;
  font-size: 56px;
  line-height: 1;
  letter-spacing: 0;
  text-transform: uppercase;
  color: var(--rig-ink);
}
.search {
  display: flex;
  align-items: center;
  gap: 14px;
  background: var(--rig-card);
  border: 2px solid var(--rig-ink);
  border-radius: var(--rig-radius);
  padding: 8px 8px 8px 22px;
}
.search-icon { color: var(--rig-muted); font-size: 22px; line-height: 1; }
.search input {
  flex: 1;
  min-width: 0;
  border: 0;
  background: transparent;
  font-size: 18px;
  padding: 8px 0;
  outline: none;
}
.search input::placeholder { color: var(--rig-faint); }
.search:focus-within {
  outline: 2px solid var(--rig-accent);
  outline-offset: 2px;
}
.btn {
  border-radius: var(--rig-radius);
  font-size: 13px;
  font-weight: 600;
  line-height: 1;
  padding: 14px 22px;
  white-space: nowrap;
}
.btn-accent {
  background: var(--rig-accent);
  color: var(--rig-on-accent);
  border: 2px solid var(--rig-accent);
}
.btn:disabled { opacity: 0.5; cursor: default; }
.btn-ghost {
  background: transparent;
  color: var(--rig-ink);
  border: 1px solid var(--rig-ink);
}
.btn-selected {
  background: var(--rig-accent);
  color: var(--rig-on-accent);
  border: 2px solid var(--rig-accent);
}
.text-btn {
  background: none;
  border: 0;
  padding: 0;
  color: var(--rig-muted);
  font-size: 13px;
  font-weight: 600;
  text-decoration: underline;
  text-underline-offset: 3px;
}
.popular { flex-wrap: wrap; gap: 8px; }
.popular-label { color: var(--rig-muted); font-size: 12px; font-weight: 600; }
.chip {
  background: transparent;
  color: var(--rig-ink);
  border: 1px solid var(--rig-ink);
  border-radius: var(--rig-radius);
  padding: 7px 12px;
  font-size: 12px;
  font-weight: 500;
}
.steps {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 16px;
}
.step {
  border-top: 2px solid var(--rig-accent);
  padding-top: 16px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 0;
}
.step-no {
  font-family: var(--rig-font-heading);
  font-size: 24px;
  font-weight: 600;
  color: var(--rig-accent);
  line-height: 1;
}
.step h2, .kicker, .card-name, .setup-name, .panel h2, .centre h2, .missing h2, .quote h2 {
  font-family: var(--rig-font-heading);
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0;
}
.step h2 { font-size: 22px; line-height: 1.15; }
.step p, .fine, .missing-copy, .label, .summary, .fit-line { color: var(--rig-muted); }
.step p { font-size: 14px; }
.meta-row { gap: 10px; flex-wrap: wrap; }
.meta-row strong { font-size: 13px; }
.cards, .setups {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 16px;
}
.card, .setup {
  background: var(--rig-card);
  border: 2px solid transparent;
  border-radius: var(--rig-radius);
  padding: 16px 16px 18px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  min-width: 0;
}
.card.selected { border-color: var(--rig-accent); }
.photo {
  background: var(--rig-card);
  border: 1px solid var(--rig-line);
  display: flex;
  align-items: center;
  justify-content: center;
  text-align: center;
  color: var(--rig-faint);
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  overflow: hidden;
}
.photo-lg { height: 200px; width: 100%; }
.photo-sm { width: 120px; height: 80px; flex: none; }
.photo-xs { width: 64px; height: 48px; flex: none; }
.photo img { width: 100%; height: 100%; object-fit: contain; }
.brand-row { justify-content: space-between; gap: 8px; }
.brand {
  color: var(--rig-accent);
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.1em;
  text-transform: uppercase;
}
.card-name { font-size: 28px; line-height: 1; }
.summary { font-size: 13px; }
.price-row { gap: 8px; align-items: baseline; flex-wrap: wrap; }
.price-cap {
  color: var(--rig-muted);
  font-size: 10px;
  font-weight: 600;
  text-transform: uppercase;
}
.amount, .price { white-space: nowrap; }
.price {
  font-family: var(--rig-font-heading);
  font-weight: 600;
  font-size: 30px;
  line-height: 1;
}
.price-lg { font-size: 36px; }
.actions { gap: 8px; flex-wrap: wrap; }
.chosen {
  background: var(--rig-card);
  border-radius: var(--rig-radius);
  padding: 14px 16px;
  display: flex;
  gap: 20px;
  align-items: center;
}
.chosen-copy { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 4px; }
.you-chose {
  color: var(--rig-muted);
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.1em;
  text-transform: uppercase;
}
.chosen h2 {
  font-family: var(--rig-font-heading);
  font-size: 26px;
  font-weight: 600;
  text-transform: uppercase;
  line-height: 1.05;
}
.chosen-note { color: var(--rig-muted); font-size: 13px; }
.chosen-side { display: flex; flex-direction: column; align-items: flex-end; gap: 8px; }
.explore-link { margin-left: auto; font-weight: 500; flex: none; }
.kicker-row { display: flex; align-items: center; gap: 12px; }
.kicker-bar { width: 4px; height: 28px; background: var(--rig-accent); flex: none; }
.kicker { font-size: 32px; line-height: 1; }
.setup { padding: 20px 20px 22px; gap: 12px; }
.setup.featured {
  background: var(--rig-featured);
  color: var(--rig-featured-text);
}
.setup.featured .label,
.setup.featured .fit-line,
.setup.featured .price-cap,
.setup.featured .swap-btn { color: var(--rig-featured-muted); }
.setup-head { display: flex; align-items: center; gap: 8px; }
.setup-no {
  font-family: var(--rig-font-heading);
  font-size: 22px;
  font-weight: 600;
  color: var(--rig-accent);
}
.setup-name { font-size: 26px; line-height: 1; }
.setup-head .badge-hot,
.badge-hot {
  background: var(--rig-accent);
  color: var(--rig-on-accent);
  font-size: 9px;
  font-weight: 600;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  padding: 4px 7px;
  border-radius: var(--rig-radius);
}
.label { font-size: 13px; }
.part {
  gap: 10px;
  padding: 10px 0;
  border-bottom: 1px solid var(--rig-line);
}
.setup.featured .part { border-bottom-color: rgba(252, 250, 244, 0.15); }
.part-copy { flex: 1; min-width: 0; display: flex; flex-direction: column; align-items: flex-start; gap: 2px; }
.role {
  color: var(--rig-accent);
  font-size: 9px;
  font-weight: 600;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}
.part-name { font-size: 14px; font-weight: 500; }
.swap-btn {
  background: none;
  border: 0;
  color: var(--rig-muted);
  font-size: 11px;
  font-weight: 600;
  padding: 4px;
  white-space: nowrap;
}
.fit-line { font-size: 11px; }
.quote-wide { width: 100%; }
.fine { font-size: 12px; }
.options {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding-bottom: 8px;
}
.option {
  text-align: left;
  background: transparent;
  border: 1px solid var(--rig-line-strong);
  border-radius: var(--rig-radius);
  padding: 8px 10px;
  font-size: 13px;
  font-weight: 500;
}
.setup.featured .option { border-color: rgba(252, 250, 244, 0.3); color: var(--rig-featured-text); }
.missing {
  background: var(--rig-card);
  border-radius: var(--rig-radius);
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.missing h2 { font-size: 30px; line-height: 1.05; }
.missing-copy { font-size: 15px; }
.field, .link-url {
  width: 100%;
  background: var(--rig-card);
  border: 1px solid var(--rig-line-strong);
  border-radius: var(--rig-radius);
  padding: 13px 14px;
  font-size: 14px;
  outline: none;
}
.field::placeholder, .link-url::placeholder { color: var(--rig-faint); }
.field:focus,
.field:focus-visible,
.link-url:focus,
.link-url:focus-visible {
  outline: 2px solid var(--rig-accent);
  outline-offset: 2px;
}
.link-row { gap: 10px; align-items: center; }
.link-url { flex: 1; min-width: 0; }
.note { display: flex; flex-direction: column; gap: 6px; }
.note > label { font-size: 12px; font-weight: 600; color: var(--rig-muted); }
.field-error { color: var(--rig-accent); font-size: 12px; }
.field[aria-invalid="true"] { border-color: var(--rig-accent); }
.link-form { display: flex; flex-direction: column; gap: 14px; }
.link-form > .btn { align-self: flex-start; }
.status { color: var(--rig-accent); font-size: 14px; }
.ack { color: var(--rig-ink); font-size: 14px; font-weight: 600; }
.backdrop {
  position: fixed;
  inset: 0;
  background: rgba(36, 39, 34, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 16px;
  z-index: 5;
}
.quote {
  width: min(420px, 100%);
  background: var(--rig-card);
  color: var(--rig-ink);
  border-radius: var(--rig-radius);
  padding: 22px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.quote h2 { font-size: 28px; }
.quote label { display: flex; flex-direction: column; gap: 6px; font-size: 13px; font-weight: 600; }
.explore { position: relative; min-height: 640px; }
.explore-header {
  display: flex;
  align-items: center;
  gap: 16px;
  min-height: 56px;
  padding: 10px 32px;
  background: color-mix(in srgb, var(--rig-graph-canvas) 60%, transparent);
}
.explore-header h1 {
  font-family: var(--rig-font-heading);
  font-size: 22px;
  font-weight: 600;
  text-transform: uppercase;
  white-space: nowrap;
}
.explore-header h1 button { font: inherit; color: inherit; text-transform: inherit; text-align: inherit; background: none; border: 0; padding: 0; }
.explore-search {
  margin: 0 auto;
  width: min(420px, 100%);
  display: flex;
  align-items: center;
  gap: 8px;
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid var(--rig-graph-line);
  border-radius: 999px;
  padding: 6px 8px 6px 14px;
}
.explore-search input {
  flex: 1;
  min-width: 0;
  border: 0;
  background: transparent;
  color: var(--rig-graph-text);
  font-size: 14px;
  outline: none;
}
.explore-search input::placeholder { color: var(--rig-graph-muted); }
.explore-search:focus-within {
  outline: 2px solid var(--rig-accent);
  outline-offset: 2px;
}
.explore-mark { color: var(--rig-graph-muted); font-size: 11px; font-weight: 500; white-space: nowrap; }
.back {
  background: none;
  border: 0;
  color: var(--rig-graph-muted);
  font-size: 13px;
  font-weight: 600;
  padding: 0;
}
.explore-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(300px, 380px);
  gap: 16px 20px;
  padding: 28px 32px 24px;
  align-items: start;
  min-height: 720px;
}
.graph-canvas { position: relative; display: grid; grid-template-columns: minmax(150px, 220px) minmax(0, 1fr); gap: 36px; min-width: 0; align-items: center; }
.connectors { position: absolute; inset: 0; width: 100%; height: 100%; pointer-events: none; overflow: visible; }
.connectors path.on { stroke: var(--rig-accent); }
.connectors path { fill: none; stroke: var(--rig-graph-line); stroke-width: 1.5; }
.graph-canvas .centre, .graph-canvas .graph { position: relative; }
.graph { display: flex; flex-direction: column; gap: 14px; min-width: 0; }
.branch-row {
  display: grid;
  grid-template-columns: 170px minmax(0, 280px);
  gap: 28px;
  align-items: center;
}
.centre { display: flex; flex-direction: column; align-items: center; text-align: center; }
.orb-wrap { position: relative; width: 220px; height: 220px; display: grid; place-items: center; }
.orb {
  width: 84px;
  height: 84px;
  border-radius: 50%;
  background: radial-gradient(circle at 35% 35%, color-mix(in srgb, var(--rig-accent) 65%, white), var(--rig-accent) 58%, color-mix(in srgb, var(--rig-accent) 35%, black));
  box-shadow:
    0 0 0 22px color-mix(in srgb, var(--rig-accent) 28%, transparent),
    0 0 0 48px color-mix(in srgb, var(--rig-accent) 14%, transparent),
    0 0 0 78px color-mix(in srgb, var(--rig-accent) 7%, transparent),
    0 0 40px color-mix(in srgb, var(--rig-accent) 50%, transparent);
}
.orb-label {
  position: absolute;
  top: 18px;
  color: var(--rig-accent);
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}
.centre h2 { font-size: 26px; margin-top: 8px; color: var(--rig-graph-text); }
.centre p { color: var(--rig-graph-muted); font-size: 11px; }
.branches, .products { display: flex; flex-direction: column; gap: 10px; min-width: 0; }
.branch, .g-chip {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  text-align: left;
  background: var(--rig-graph-chip);
  color: var(--rig-graph-text);
  border: 1px solid var(--rig-graph-line);
  border-radius: var(--rig-radius-graph);
  padding: 6px 10px;
}
.branch.on, .g-chip.on {
  background: var(--rig-graph-chip-on);
  border-color: var(--rig-accent);
}
.branch .count {
  font-family: var(--rig-font-heading);
  font-size: 24px;
  font-weight: 600;
  line-height: 1;
  min-width: 1.4em;
}
.branch .cat {
  font-size: 9px;
  font-weight: 600;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  white-space: nowrap;
  color: var(--rig-graph-muted);
}
.swatch {
  width: 30px;
  height: 30px;
  border-radius: 4px;
  background: var(--rig-card);
  flex: none;
}
.g-copy { min-width: 0; display: flex; flex-direction: column; gap: 2px; }
.g-name { font-size: 12px; font-weight: 500; }
.g-meta { font-size: 10px; color: var(--rig-graph-muted); }
.more { color: var(--rig-graph-muted); font-size: 11px; margin: 0 0 8px; }
.side { display: flex; flex-direction: column; gap: 16px; min-height: 100%; }
.panel {
  background: color-mix(in srgb, var(--rig-graph-raised) 92%, transparent);
  border: 1px solid var(--rig-graph-line);
  border-radius: calc(var(--rig-radius-graph) + 4px);
  padding: 22px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.panel-kicker {
  color: var(--rig-accent);
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.1em;
  text-transform: uppercase;
}
.panel h2 {
  font-size: 26px;
  line-height: 1.05;
  text-transform: none;
  color: var(--rig-graph-text);
}
.panel-body { color: var(--rig-graph-muted); font-size: 13px; line-height: 1.5; }
.stats { display: grid; grid-template-columns: repeat(2, minmax(max-content, 1fr)); gap: 10px; }
.stat {
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: var(--rig-radius-graph);
  padding: 10px 12px;
}
.stat strong {
  display: block;
  font-family: var(--rig-font-heading);
  font-size: 26px;
  font-weight: 600;
  line-height: 1;
  white-space: nowrap;
}
.stat span { color: var(--rig-graph-muted); font-size: 11px; }
.tier-row { gap: 6px; flex-wrap: wrap; }
.tier {
  background: transparent;
  color: var(--rig-graph-text);
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 999px;
  padding: 7px 12px;
  font-size: 11px;
  font-weight: 600;
}
.tier.on { background: var(--rig-accent); border-color: transparent; }
.why {
  background: rgba(255, 255, 255, 0.04);
  border-radius: var(--rig-radius-graph);
  padding: 12px 14px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.why strong { font-size: 12px; }
.why p { color: var(--rig-graph-muted); font-size: 12px; }
.panel .btn { border-radius: var(--rig-radius-graph); }
.ask {
  display: flex;
  align-items: center;
  gap: 8px;
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid rgba(255, 255, 255, 0.14);
  border-radius: 999px;
  padding: 8px 8px 8px 16px;
  margin-top: auto;
}
.ask textarea {
  flex: 1;
  min-width: 0;
  border: 0;
  background: transparent;
  color: var(--rig-graph-text);
  font-size: 13px;
  line-height: 1.5;
  resize: none;
  outline: none;
}
.ask textarea::placeholder { color: var(--rig-graph-muted); }
.ask:focus-within {
  outline: 2px solid var(--rig-accent);
  outline-offset: 2px;
}
.ask-go {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  border: 0;
  background: var(--rig-accent);
  color: var(--rig-on-accent);
  font-weight: 600;
  flex: none;
}
.answer { color: var(--rig-graph-text); font-size: 13px; display: flex; flex-direction: column; gap: 4px; }
.answer span { color: var(--rig-graph-muted); font-size: 11px; }
@media (max-width: 1100px) {
  .explore-grid { grid-template-columns: 1fr; min-height: 0; padding: 16px; }
  .graph-canvas { grid-template-columns: 1fr; gap: 40px; }
  .graph { gap: 24px; }
  .branch-row { grid-template-columns: 160px minmax(0, 1fr); gap: 20px; padding-left: 12px; }
  .explore-header { flex-wrap: wrap; padding: 12px 16px; }
  .explore-header h1 { font-size: 18px; white-space: normal; }
  .explore > .status { padding: 0 16px; }
  .explore-search { order: 3; width: 100%; margin: 0; }
  .centre { padding-top: 8px; }
  .side { min-height: 0; }
  .ask { margin-top: 0; }
}
@media (max-width: 720px) {
  .shell { padding: 20px 16px 28px; gap: 18px; }
  .shell-explore { padding: 0; gap: 0; }
  h1.title { font-size: 34px; }
  .steps, .cards, .setups { grid-template-columns: 1fr; }
  .search { padding-left: 12px; gap: 8px; }
  .search input { font-size: 16px; }
  .actions { flex-direction: column; align-items: stretch; }
  .actions .btn { width: 100%; text-align: center; }
  .chosen { flex-wrap: wrap; }
  .chosen-side { flex-direction: row; align-items: center; width: 100%; justify-content: space-between; }
  .kicker { font-size: 26px; }
  .link-row { flex-direction: column; align-items: stretch; }
  .price-lg { font-size: 32px; }
  .card-name { overflow-wrap: anywhere; }
}
@media (prefers-reduced-motion: reduce) {
  * { transition: none !important; }
}
`;o();var ie=0,Q=class extends HTMLElement{static get observedAttributes(){return[`api-base`,`rig-key`,`theme`,`fonts`]}client=new _({apiBase:``,key:``});themeOverride=null;root=null;searchTimer=0;settleTimer=0;countedSearchQuery=``;pendingSearch=null;loadGen=0;pendingFocus=null;quoteOpener=null;focusOwed=!1;graphObserver=new ResizeObserver(()=>this.drawConnectors());historyKey=`__tervoryRig${++ie}`;historyViews=new Map;historyEntry=0;nextHistoryEntry=0;onPopState=e=>{let t=e.state?.[this.historyKey];typeof t==`number`&&t!==this.historyEntry&&this.restoreView(t)};query=``;screen=`home`;results=[];selectedId=null;product=null;setups=[];activeTier=null;graph=null;expanded=[];swap=null;askQuestion=``;askAnswer=null;askCites=``;askPending=!1;linkUrl=``;linkRequestId=null;linkError=null;linkErrors={};linkContact={name:``,email:``};linkAck;linkPending=!1;quote=null;quoteTarget=null;message=null;customizedTiers=[];set themeData(e){this.themeOverride=e,this.shadowRoot&&(this.applyTheme(),this.render())}connectedCallback(){if(window.addEventListener(`popstate`,this.onPopState),this.shadowRoot)return;let e=this.attachShadow({mode:`open`}),t=document.createElement(`style`);t.textContent=re,e.append(t),this.root=document.createElement(`div`),e.append(this.root),e.addEventListener(`click`,e=>this.onClick(e)),e.addEventListener(`submit`,e=>this.onSubmit(e)),e.addEventListener(`input`,e=>this.onInput(e)),e.addEventListener(`keydown`,e=>this.onKey(e)),this.syncClient(),this.applyTheme(),this.render()}disconnectedCallback(){window.removeEventListener(`popstate`,this.onPopState),window.clearTimeout(this.searchTimer),window.clearTimeout(this.settleTimer),this.graphObserver.disconnect()}attributeChangedCallback(e){this.shadowRoot&&((e===`api-base`||e===`rig-key`)&&this.syncClient(),e===`theme`&&(this.themeOverride=null),this.applyTheme(),this.render())}syncClient(){let e=this.getAttribute(`api-base`);this.client=new _({apiBase:e===null?``:e.trim(),key:this.getAttribute(`rig-key`)??``})}currentTheme(){return this.themeOverride??E(this.getAttribute(`theme`))}applyTheme(){let e=this.currentTheme(),t={"--rig-canvas":e.colors.canvas,"--rig-ink":e.colors.ink,"--rig-accent":e.colors.accent,"--rig-muted":e.colors.muted,"--rig-faint":e.colors.faint,"--rig-line":e.colors.line,"--rig-line-strong":e.colors.lineStrong,"--rig-card":e.colors.card,"--rig-badge":e.colors.badge,"--rig-on-accent":e.colors.onAccent,"--rig-featured":e.colors.featured,"--rig-featured-text":e.colors.featuredText,"--rig-featured-muted":e.colors.featuredMuted,"--rig-font-heading":e.fonts.heading,"--rig-font-body":e.fonts.body,"--rig-radius":e.radius,"--rig-radius-graph":e.radiusGraph,"--rig-graph-canvas":e.graph.canvas,"--rig-graph-raised":e.graph.raised,"--rig-graph-text":e.graph.text,"--rig-graph-muted":e.graph.muted,"--rig-graph-line":e.graph.line,"--rig-graph-chip":e.graph.chip,"--rig-graph-chip-on":e.graph.chipOn,"--rig-graph-glow":e.graph.glow};for(let[e,n]of Object.entries(t))this.style.setProperty(e,n);let n=this.getAttribute(`fonts`),r=n&&n!==`on`&&n!==`off`?n:e.fonts.href;n!==`off`&&r&&ae(r)}view(){return{theme:this.currentTheme(),query:this.query,screen:this.screen,results:this.results,selectedId:this.selectedId,product:this.product,setups:this.setups,activeTier:this.activeTier,graph:this.graph,expanded:this.expanded,swap:this.swap,askQuestion:this.askQuestion,askAnswer:this.askAnswer,askCites:this.askCites,linkUrl:this.linkUrl,linkRequestId:this.linkRequestId,linkError:this.linkError,linkErrors:this.linkErrors,linkContact:this.linkContact,linkAck:this.linkAck,linkPending:this.linkPending,quote:this.quote,message:this.message,customizedTiers:this.customizedTiers}}render(){if(!this.root)return;this.rememberView();let e=this.captureFocus(),t=this.pendingFocus;this.pendingFocus=null;let n=e!==null||t!==null||this.focusOwed;this.classList.toggle(`is-explore`,this.screen===`explore`),this.root.innerHTML=D(this.view()),this.graphObserver.disconnect();let r=this.root.querySelector(`.graph-canvas`);r&&(this.graphObserver.observe(r),this.drawConnectors());let i=this.restoreFocus(t??e);!i&&t&&e&&(i=this.restoreFocus(e)),!i&&n&&(i=this.focusFallback()),this.focusOwed=n&&!i}rememberView(){let e={screen:this.screen,query:this.query,results:this.results,selectedId:this.selectedId,product:this.product,setups:[...this.setups],activeTier:this.activeTier,graph:this.graph,expanded:[...this.expanded],customizedTiers:[...this.customizedTiers],askQuestion:this.askQuestion,askAnswer:this.askAnswer,askCites:this.askCites,linkUrl:this.linkUrl,linkRequestId:this.linkRequestId,linkError:this.linkError,linkErrors:this.linkErrors,linkContact:this.linkContact,linkAck:this.linkAck,linkPending:this.linkPending},t=this.historyViews.get(this.historyEntry);if(t?.view.screen===e.screen&&t.view.selectedId===e.selectedId){t.view=e;return}if(t&&e.screen!==`setup`&&e.screen!==`explore`){t.view=e,t.focus=null,this.writeHistory(!1);return}t&&(t.focus=this.captureFocus());let n=t?this.historyEntry:null;this.historyEntry=++this.nextHistoryEntry,this.historyViews.set(this.historyEntry,{view:e,previous:n,focus:null}),this.writeHistory(!!t)}writeHistory(e){let t=window.history.state;if(t===null||typeof t==`object`&&!Array.isArray(t))try{let n={...t,[this.historyKey]:this.historyEntry};e?window.history.pushState(n,``):window.history.replaceState(n,``)}catch{}}restoreView(e){let t=this.historyViews.get(e);if(!t)return;this.rememberView();let n=this.historyViews.get(this.historyEntry);n&&(n.focus=this.captureFocus()),this.cancelSearch(),this.historyEntry=e,Object.assign(this,t.view),this.setups=[...t.view.setups],this.customizedTiers=[...t.view.customizedTiers],this.swap=null,this.quote=null,this.quoteTarget=null,this.askPending=!1,this.message=null,this.pendingFocus=t.focus??{kind:`fallback`},this.render(),this.selectedId&&this.screen===`explore`&&!this.graph&&this.openExplore(this.selectedId),this.selectedId&&this.screen===`setup`&&!this.setups.length&&this.openSetup(this.selectedId)}backToSetups(){let e=this.historyViews.get(this.historyEntry)?.previous;e&&this.historyViews.get(e)?.view.screen===`setup`?window.history.state?.[this.historyKey]===this.historyEntry?window.history.back():(this.restoreView(e),this.writeHistory(!1)):this.selectedId&&this.openSetup(this.selectedId)}drawConnectors(){let e=this.root?.querySelector(`.graph-canvas`),t=e?.querySelector(`svg`),n=e?.querySelector(`.orb`);if(!e||!t||!n)return;let r=e.getBoundingClientRect(),i=[],a=[],o=(e,t,n,o=!1)=>{let s=e.getBoundingClientRect(),c=t.getBoundingClientRect(),l=(o?s.left+s.width/2:s.right)-r.left,u=(o?s.bottom:s.top+s.height/2)-r.top,d=(o?c.left+c.width/2:c.left)-r.left,f=(o?c.top:c.top+c.height/2)-r.top,p=o?(u+f)/2:(l+d)/2,m=o?`M${l},${u} V${u+16} H4 V${f+c.height/2} H${d-c.width/2}`:`M${l},${u} C${p},${u} ${p},${f} ${d},${f}`;(n?a:i).push(`<path${n?` class="on"`:``} d="${m}"/>`)};for(let t of e.querySelectorAll(`.branch-row`)){let r=t.querySelector(`.branch`);if(!r)continue;let i=getComputedStyle(e).gridTemplateColumns.split(` `).length===1;o(i?e.querySelector(`.centre`)??n:n,r,r.classList.contains(`on`),i);for(let e of t.querySelectorAll(`.g-chip`))o(r,e,e.classList.contains(`on`))}t.setAttribute(`viewBox`,`0 0 ${r.width} ${r.height}`),t.innerHTML=[...i,...a].join(``)}focusFallback(){if(!this.root)return!1;let e=this.root.querySelector(`[role='dialog'] h2`)??this.root.querySelector(`h2`);return e?(e.setAttribute(`tabindex`,`-1`),e.dataset.focusFallback=``,e.focus(),this.shadowRoot?.activeElement===e):!1}captureFocus(){let e=this.shadowRoot?.activeElement;if(!(e instanceof HTMLElement))return null;if(e.id&&(e instanceof HTMLInputElement||e instanceof HTMLTextAreaElement))return{kind:`id`,id:e.id,start:e.selectionStart,end:e.selectionEnd};let t=e.closest(`[data-action]`);return t instanceof HTMLElement&&t.dataset.action?{kind:`action`,action:t.dataset.action,id:t.dataset.id??``,tier:t.dataset.tier??``,role:t.dataset.role??``,category:t.dataset.category??``,q:t.dataset.q??``}:e.id?{kind:`id`,id:e.id,start:null,end:null}:e.hasAttribute(`data-focus-fallback`)?{kind:`fallback`}:null}restoreFocus(e){if(!e||!this.root||e.kind===`fallback`)return!1;if(e.kind===`id`){let t=this.root.querySelector(`#${CSS.escape(e.id)}`);return t instanceof HTMLElement&&(t.focus(),(t instanceof HTMLInputElement||t instanceof HTMLTextAreaElement)&&e.start!==null&&e.end!==null&&t.setSelectionRange(e.start,e.end),!0)}let t=this.root.querySelectorAll(`[data-action]`);for(let n of t)if((n.dataset.action??``)===e.action&&(n.dataset.id??``)===e.id&&(n.dataset.tier??``)===e.tier&&(n.dataset.role??``)===e.role&&(n.dataset.category??``)===e.category&&(n.dataset.q??``)===e.q)return n.focus(),!0;return!1}swapButtonKey(e,t){return{kind:`action`,action:`swap`,id:``,tier:e,role:t,category:``,q:``}}onClick(e){let t=e.target;if(!(t instanceof Element))return;let n=t.closest(`[data-action]`);if(!(n instanceof HTMLElement))return;let r=n.dataset.id??``,i=n.dataset.tier??``;switch(n.dataset.action){case`back-setup`:e.preventDefault(),this.backToSetups();break;case`popular`:this.query=n.dataset.q??``,this.searchNow();break;case`complete`:this.settleSearch(),this.openSetup(r);break;case`explore`:this.openExplore(r);break;case`quote-product`:this.settleSearch(),this.openQuoteProduct(r);break;case`quote-setup`:this.openQuoteSetup(i);break;case`swap`:this.openSwap(i,n.dataset.role??``);break;case`pick-swap`:this.pickSwap(i,r);break;case`tier`:this.activeTier=i,this.swap=null,this.render();break;case`branch`:this.toggleBranch(n.dataset.category??``);break;case`pick-graph`:this.pickGraph(r);break;case`close-quote`:this.closeQuote()}}onSubmit(e){e.preventDefault();let t=e.target;t instanceof HTMLFormElement&&(t.classList.contains(`link-form`)?this.submitLink(t):t.classList.contains(`ask`)?this.submitAsk():t.classList.contains(`quote`)?this.submitQuote(t):this.searchNow())}onInput(e){let t=e.target;if(!(t instanceof HTMLInputElement||t instanceof HTMLTextAreaElement))return;t.id===`q`?(this.query=t.value,this.scheduleSearch()):t.id===`link-url`?this.linkUrl=t.value:t.id===`link-name`?this.linkContact.name=t.value:t.id===`link-email`?this.linkContact.email=t.value:t.id===`link-phone`?this.linkContact.phone=t.value:t.id===`ask-q`?this.askQuestion=t.value:t.id===`quote-name`&&this.quote?this.quote={...this.quote,name:t.value}:t.id===`quote-email`&&this.quote&&(this.quote={...this.quote,email:t.value});let n=t.id.replace(/^link-/,``);if(t instanceof HTMLInputElement&&this.linkErrors[n]){let e=this.linkFieldError(n,t);e?this.linkErrors[n]=e:delete this.linkErrors[n],this.render()}}onKey(e){e instanceof KeyboardEvent&&(e.key===`Enter`&&!e.shiftKey&&!e.isComposing&&e.target instanceof HTMLTextAreaElement&&e.target.id===`ask-q`?(e.preventDefault(),e.repeat||e.target.form?.requestSubmit()):e.key===`Tab`&&this.quote?this.trapQuoteFocus(e):e.key===`Escape`&&(this.quote?this.closeQuote():this.swap?(this.pendingFocus=this.swapButtonKey(this.swap.tier,this.swap.role),this.swap=null,this.render()):this.screen===`explore`&&(e.preventDefault(),this.backToSetups())))}trapQuoteFocus(e){let t=this.root?.querySelector(`[role='dialog']`);if(!(t instanceof HTMLElement))return;let n=[...t.querySelectorAll(`button, input, textarea, select, a[href]`)].filter(e=>!e.hasAttribute(`disabled`));if(n.length===0)return;let r=n.findIndex(e=>e===this.shadowRoot?.activeElement);e.preventDefault(),r===-1?(e.shiftKey?n[n.length-1]:n[0])?.focus():n[(r+(e.shiftKey?-1:1)+n.length)%n.length]?.focus()}closeQuote(){this.pendingFocus=this.quoteOpener,this.quoteOpener=null,this.quote=null,this.quoteTarget=null,this.render()}scheduleSearch(){window.clearTimeout(this.searchTimer),window.clearTimeout(this.settleTimer),this.pendingSearch=null,this.askPending=!1,this.loadGen+=1,this.query.trim()?this.searchTimer=window.setTimeout(()=>void this.searchNow(!1),250):(this.loadGen+=1,this.screen=`home`,this.results=[],this.message=null,this.linkError=null,this.render())}cancelSearch(){window.clearTimeout(this.searchTimer),window.clearTimeout(this.settleTimer),this.pendingSearch=null,this.askPending=!1,this.loadGen+=1}settleSearch(){window.clearTimeout(this.settleTimer);let e=this.pendingSearch;if(!e||e.query===this.countedSearchQuery)return;let t=()=>{this.dispatchEvent(new CustomEvent(`rig-analytics-error`,{detail:{code:`unavailable`}}))};try{let n=i();this.countedSearchQuery=e.query,this.client.settledSearch(n,e.noResults).catch(t)}catch{t()}}async searchNow(e=!0){window.clearTimeout(this.searchTimer),window.clearTimeout(this.settleTimer);let t=this.query.trim();if(this.pendingSearch=null,!t){this.screen=`home`,this.results=[],this.message=null,this.render();return}let n=++this.loadGen;this.message=this.currentTheme().copy.loading,this.render();try{let r=await this.client.search(t,12);if(n!==this.loadGen)return;this.results=r.results,this.pendingSearch={query:t,noResults:r.results.length===0},e?this.settleSearch():this.settleTimer=window.setTimeout(()=>this.settleSearch(),750),this.screen=r.results.length?`results`:`missing`,this.swap=null,this.quote=null,this.message=null,this.screen===`missing`&&(this.linkUrl=``,this.linkRequestId=null,this.linkPending=!1,this.linkError=null,this.linkErrors={},this.linkAck=void 0,this.linkContact={name:``,email:``})}catch(e){if(n!==this.loadGen)return;this.message=this.errorText(e)}this.render()}async openSetup(e){this.cancelSearch();let t=this.findProduct(e);this.selectedId=e,this.product=t,this.screen=`setup`,this.swap=null,this.quote=null,this.graph=null,this.setups=[],this.message=this.currentTheme().copy.loading,this.render();let n=++this.loadGen;try{let[t,r]=await Promise.all([this.client.product(e),this.client.setups(e)]);if(n!==this.loadGen)return;this.product=t,this.setups=r.setups,this.activeTier=r.setups.find(e=>e.badge)?.tier??r.setups[0]?.tier??null,this.customizedTiers=[],this.message=null}catch(e){if(n!==this.loadGen)return;this.message=this.errorText(e)}this.render()}async openExplore(e){this.cancelSearch(),this.selectedId=e,this.screen=`explore`,this.swap=null,this.quote=null,this.askAnswer=null,this.askCites=``,this.askPending=!1,this.graph=null,this.message=this.currentTheme().copy.loading,this.render();let t=++this.loadGen;try{let[n,r]=await Promise.all([this.client.graph(e),this.client.setups(e)]);if(t!==this.loadGen)return;this.graph=n,this.product=n.centre,this.setups=r.setups,this.customizedTiers=[],this.activeTier=r.setups.find(e=>e.badge)?.tier??r.setups[0]?.tier??null;let i=this.setups.find(e=>e.tier===this.activeTier)??this.setups[0],a=new Set(i?.parts.map(e=>e.product.id)??[]);this.expanded=n.branches.filter(e=>e.products.some(e=>a.has(e.id))).map(e=>e.category),this.message=null}catch(e){if(t!==this.loadGen)return;this.message=this.errorText(e)}this.render()}async openSwap(e,t){if(this.swap?.tier===e&&this.swap.role===t){this.swap=null,this.render();return}let n=this.setups.find(t=>t.tier===e);if(!n)return;this.message=this.currentTheme().copy.loading,this.render();let r=this.loadGen;try{let i=await this.client.swap(n,t);if(r!==this.loadGen)return;if(!i.setup?.total){this.message=this.currentTheme().copy.errorGeneric,this.render();return}this.replaceSetup(i.setup),this.swap={tier:e,role:t,options:i.options},this.message=null}catch(e){if(r!==this.loadGen)return;this.message=this.errorText(e)}this.render()}async pickSwap(e,t){let n=this.setups.find(t=>t.tier===e),r=this.swap?.role??``,i=this.swap?.options.find(e=>e.id===t);if(!n||!i||this.swap?.tier!==e||!r)return;let a=$(n,r,i),o=this.loadGen;try{let t=await this.client.swap(a,r,!0);if(o!==this.loadGen)return;t.setup?.total?(this.replaceSetup(t.setup),this.customizedTiers.includes(e)||this.customizedTiers.push(e),this.message=null):this.message=this.currentTheme().copy.errorGeneric}catch(e){if(o!==this.loadGen)return;this.message=this.errorText(e)}this.swap=null,this.pendingFocus=this.swapButtonKey(e,r),this.render()}replaceSetup(e){let t=this.setups.findIndex(t=>t.tier===e.tier);t>=0&&(this.setups[t]=e)}async pickGraph(e){let t=this.setups.find(e=>e.tier===this.activeTier)??this.setups[0],n=this.findProduct(e);if(!t||!n||n.id===this.selectedId||t.parts.some(e=>e.product.id===n.id))return;let r=t.parts.find(e=>e.product.category===n.category);if(!r)return;let i=this.loadGen;try{let e=await this.client.swap(t,r.role);if(i!==this.loadGen)return;let a=e.options.find(e=>e.id===n.id);if(!a){this.message=this.currentTheme().copy.notAlternative,this.render();return}let o=await this.client.swap($(t,r.role,a),r.role,!0);if(i!==this.loadGen)return;if(!o.setup?.total){this.message=this.currentTheme().copy.errorGeneric,this.render();return}this.replaceSetup(o.setup),this.customizedTiers.includes(t.tier)||this.customizedTiers.push(t.tier),this.message=null}catch(e){if(i!==this.loadGen)return;this.message=this.errorText(e)}this.render()}toggleBranch(e){this.expanded=this.expanded.includes(e)?this.expanded.filter(t=>t!==e):[...this.expanded,e],this.render()}openQuoteProduct(e){this.cancelSearch();let t=this.findProduct(e);t&&(this.quoteOpener=this.captureFocus(),this.quoteTarget={kind:`product`,productId:e},this.quote={kind:`product`,title:t.name,totalLabel:y(t.price),name:``,email:``,error:null,requestId:null},this.pendingFocus={kind:`id`,id:`quote-name`,start:null,end:null},this.render())}openQuoteSetup(e){this.cancelSearch();let t=this.setups.find(t=>t.tier===e);t&&(this.quoteOpener=this.captureFocus(),this.quoteTarget={kind:`setup`,tier:e},this.quote={kind:`setup`,title:t.parts.map(e=>e.product.name).join(` + `),totalLabel:y(t.total),name:``,email:``,error:null,requestId:null},this.pendingFocus={kind:`id`,id:`quote-name`,start:null,end:null},this.render())}async submitQuote(e){if(!this.quote||!this.quoteTarget||this.quote.pending||this.quote.requestId)return;let t=new FormData(e),n=String(t.get(`name`)??``).trim(),r=String(t.get(`email`)??``).trim();this.quote={...this.quote,name:n,email:r,error:null,pending:!0};let i={name:n,email:r},o=this.quoteTarget,s=this.quote;this.render();try{let e=o.kind===`setup`?this.setups.find(e=>e.tier===o.tier):void 0;if(o.kind===`setup`&&!e)throw new a(`invalid_quote`,this.currentTheme().copy.unavailable,400);let t=o.kind===`product`?await this.client.quote({contact:i,product_id:o.productId}):await this.client.quote({contact:i,setup:e});if(this.quote!==s)return;this.quote={...s,requestId:t.request_id,ack:t,pending:!1},this.pendingFocus={kind:`action`,action:`close-quote`,id:``,tier:``,role:``,category:``,q:``}}catch(e){if(this.quote!==s)return;this.quote={...s,error:this.errorText(e),pending:!1}}this.render()}linkFieldError(e,t){let n=t.value.trim(),r=this.currentTheme().copy,i={url:r.linkRequired,name:r.nameRequired,email:r.emailRequired,phone:r.phoneRequired},a={url:r.linkInvalid,name:r.nameInvalid,email:r.emailInvalid,phone:r.phoneInvalid};if(!n)return i[e];if(e===`url`)try{let e=new URL(n);if(![`http:`,`https:`].includes(e.protocol)||!e.hostname||e.username||e.password||n.length>2048)return a.url}catch{return a.url}else if(e===`email`){if(t.validity.typeMismatch||n.length>254||!/^[^\s@]+@[^\s@.]+(?:\.[^\s@.]+)+$/.test(n))return a.email}else if(e===`phone`){let e=n.replace(/\D/g,``);if(!/^\+?(?:\d|\(\d{1,5}\)|[ .-])+$/.test(n)||e.length<7||e.length>15||n.length>40)return a.phone}else if(n.length>120)return a.name}async submitLink(e){if(this.linkPending||this.linkRequestId)return;this.linkError=null,this.linkErrors={};for(let t of[`url`,`name`,`email`,`phone`]){let n=e.querySelector(`#link-${t}`);if(!n)return;let r=this.linkFieldError(t,n);r&&(this.linkErrors[t]=r)}let t=Object.keys(this.linkErrors)[0];if(t){this.pendingFocus={kind:`id`,id:`link-${t}`,start:null,end:null},this.render();return}this.linkContact={name:this.linkContact.name.trim(),email:this.linkContact.email.trim(),phone:this.linkContact.phone?.trim()},this.linkPending=!0,this.render();let n=this.linkContact,r=e=>{let t={...e,linkPending:!1};for(let e of this.historyViews.values())e.view.linkContact===n&&Object.assign(e.view,t);this.linkContact===n&&(Object.assign(this,t),this.render())};try{let e=await this.client.linkQuote({url:this.linkUrl.trim(),note:``,contact:n});r({linkRequestId:e.request_id,linkAck:e})}catch(e){r({linkError:this.errorText(e)})}}async submitAsk(){let e=this.graph?.centre.id??this.selectedId;if(!e||!this.askQuestion.trim()||this.askPending)return;let t=this.loadGen;this.askPending=!0;let n=this.setups.find(e=>e.tier===this.activeTier)??this.setups[0];this.message=this.currentTheme().copy.loading,this.render();try{let r=await this.client.ask({product_id:e,...n?{setup:n}:{},question:this.askQuestion});if(t!==this.loadGen)return;this.askAnswer=r.answer,this.askCites=this.citeLabel(r.cites),this.message=null}catch(e){if(t!==this.loadGen)return;this.message=this.errorText(e)}this.askPending=!1,this.render()}citeLabel(e){let t=new Map;if(this.graph){t.set(this.graph.centre.id,this.graph.centre.name);for(let e of this.graph.branches)for(let n of e.products)t.set(n.id,n.name)}return e.map(e=>t.get(e)??e).join(`, `)}findProduct(e){if(this.product?.id===e)return this.product;let t=this.results.find(t=>t.id===e);if(t)return t;for(let t of this.setups){let n=t.parts.find(t=>t.product.id===e);if(n)return n.product}if(this.graph){if(this.graph.centre.id===e)return this.graph.centre;for(let t of this.graph.branches){let n=t.products.find(t=>t.id===e);if(n)return n}}return this.swap?.options.find(t=>t.id===e)??null}errorText(e){return e instanceof a||e instanceof Error&&e.message?e.message:this.currentTheme().copy.errorGeneric}};function $(e,t,n){let r={tier:e.tier,label:e.label,parts:e.parts.map(e=>e.role===t?{role:t,product:n}:e),total:e.total,why:e.why};return e.badge&&(r.badge=e.badge),r}function ae(e){let t=document.querySelectorAll(`link[data-tervory-rig-font]`);for(let n of t)if(n.getAttribute(`data-tervory-rig-font`)===e)return;let n=document.createElement(`link`);n.rel=`stylesheet`,n.href=e,n.setAttribute(`data-tervory-rig-font`,e),document.head.appendChild(n)}customElements.get(`tervory-rig`)||customElements.define(`tervory-rig`,Q),e.RigClient=_,e.TervoryRig=Q,e.customNation=w,e.neutral=T,e.resolveTheme=E});
(() => {
  'use strict';
  let state;
  const $ = id => document.getElementById(id);
  const escape = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const stages = {installed:'APP MODULE INCLUDED', adapter_files:'ADAPTER FILES / WIRING PENDING', setup_slot:'SETUP SLOT / IMPLEMENTATION PENDING'};
  async function refresh() {
    const res = await fetch('/api/integrations', {cache:'no-store'});
    if (!res.ok) throw new Error('Could not load integrations');
    state = await res.json();
    $('total').textContent = state.cards.length;
    $('saved').textContent = state.cards.filter(card => card.saved_fields > 0).length;
    const runtime = state.runtime;
    $('runtime').textContent = `PYTHON ${runtime.python} / FFMPEG ${runtime.ffmpeg ? 'AVAILABLE' : 'NOT INSTALLED'} / OLLAMA ${runtime.ollama ? 'AVAILABLE' : 'NOT INSTALLED'} / ACCOUNT CONNECTIONS DEFERRED`;
    if ($('category').options.length === 1) {
      [...new Set(state.cards.map(card => card.category))].sort().forEach(name => $('category').add(new Option(name,name)));
    }
    render();
  }
  function render() {
    const search = $('search').value.trim().toLowerCase();
    const category = $('category').value;
    const cards = state.cards.filter(card => (category === 'All categories' || card.category === category) && `${card.name} ${card.category} ${card.note}`.toLowerCase().includes(search));
    $('cards').innerHTML = cards.map(card => `
      <article class="card"><span class="tag">${escape(card.category.toUpperCase())}</span>
      <h2>${escape(card.name)}</h2><span class="state">${card.saved_fields ? 'SETTINGS SAVED / ACCESS NOT VERIFIED' : 'NOT CONFIGURED'}</span>
      <p>${escape(card.note)}</p><p class="tag">${escape(stages[card.stage])}</p>
      ${card.fields.length ? `<details><summary>Configure later or add settings</summary><form data-id="${escape(card.id)}">
      ${card.fields.map(field => `<label>${escape(field.label)}${field.saved ? ' (saved)' : ''}<input name="${escape(field.id)}" type="${field.secret ? 'password' : 'text'}" value="${escape(field.value)}" placeholder="${field.secret && field.saved ? 'Leave blank to keep saved credential' : 'Not configured'}" autocomplete="off" spellcheck="false"></label>`).join('')}
      <div class="actions"><button class="primary" type="submit">Save settings</button><button type="button" data-clear="${escape(card.id)}">Clear settings</button></div></form></details>` : ''}
      <a class="portal" href="${escape(card.portal)}" target="_blank" rel="noopener noreferrer">Provider setup &nearr;</a></article>`).join('') || '<p class="empty">No integrations match your search.</p>';
  }
  async function save(form, clear=false) {
    const buttons = [...form.querySelectorAll('button')];
    buttons.forEach(button => button.disabled = true);
    try {
      const res = await fetch('/api/integrations', {method:'POST',headers:{'Content-Type':'application/json','X-U1-CSRF':state.csrf_token},body:JSON.stringify({integration:form.dataset.id,values:Object.fromEntries(new FormData(form)),clear})});
      const result = await res.json();
      if (!res.ok || !result.success) throw new Error(result.error || 'Settings could not be saved');
      form.reset();
      await refresh();
      $('notice').textContent = clear ? 'Saved settings cleared.' : 'Settings saved locally. Account access has not been tested or enabled.';
    } catch (error) { $('notice').textContent = error.message; }
    finally {buttons.forEach(button => button.disabled = false);}
  }
  $('search').addEventListener('input',render);
  $('category').addEventListener('change',render);
  $('cards').addEventListener('submit',event => {event.preventDefault();save(event.target);});
  $('cards').addEventListener('click',event => {const button=event.target.closest('[data-clear]');if(button && window.confirm('Clear saved settings for this integration?')) save(button.closest('form'),true);});
  refresh().catch(error => {$('notice').textContent=error.message;});
})();

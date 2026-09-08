/* Operator-led publishing. PDF previews and downloads share the same bytes. */
(function () {
  'use strict';
  var API = '/api/workspace/studio-pro', DRAFT = 'u1.studio.pro.draft.v1', BRAND = 'u1.studio.pro.brand.v1';
  var dispose = null;
  function esc(value) { return String(value == null ? '' : value).replace(/[&<>"']/g, function (c) { return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]; }); }
  function read(key) { try { return JSON.parse(localStorage.getItem(key) || 'null'); } catch (_) { return null; } }
  function store(key, value) { try { localStorage.setItem(key, JSON.stringify(value)); return true; } catch (_) { return false; } }
  function section(title) { return {title:title || 'Untitled section', content:'', activity:'', quizzes:[], answer_notes:''}; }
  function blank() { return {title:'', subtitle:'', audience:'', template:'course', version:'1.0', source:'', brand:read(BRAND) || {name:'', accent:'#176B64', font:'serif'}, sections:[section('Learning outcome')], fillable:true, include_answer_notes:false, instructions:'', licence:''}; }
  function decode(artifact) {
    if (!artifact || typeof artifact.content !== 'string' || !['application/pdf','application/zip','image/svg+xml','image/png'].includes(artifact.mime)) throw Error('No supported generated file was returned.');
    var raw = atob(artifact.content), bytes = new Uint8Array(raw.length);
    for (var i = 0; i < raw.length; i++) bytes[i] = raw.charCodeAt(i);
    return new Blob([bytes], {type:artifact.mime});
  }
  function download(blob, name) {
    var url = URL.createObjectURL(blob), link = document.createElement('a'); link.href = url; link.download = name;
    document.body.append(link); link.click(); link.remove(); setTimeout(function () { URL.revokeObjectURL(url); }, 60000);
  }
  async function saveFile(artifact, progress) {
    progress = progress || function () {};
    var blob = decode(artifact);
    if (!artifact.filename || /[\\/\x00-\x1f]/.test(artifact.filename) || artifact.filename.length > 200) throw Error('The generated filename is invalid.');
    if (!blob.size || blob.size > 25*1024*1024) throw Error('The generated file is outside the managed Files size limit.');
    var start = await window.U1Data.post('/api/workspace/prism/upload-start', {name:artifact.filename, mime:artifact.mime, size:blob.size, folder:'Digital Studio'});
    if (start.success === false || !start.id) throw Error(start.error || 'Files could not start this upload.');
    try {
      for (var offset = 0; offset < blob.size; offset += 32768) {
        var bytes = new Uint8Array(await blob.slice(offset, offset+32768).arrayBuffer()), binary = '';
        for (var i = 0; i < bytes.length; i++) binary += String.fromCharCode(bytes[i]);
        var result = await window.U1Data.post('/api/workspace/prism/upload-chunk', {id:start.id, offset:offset, content:btoa(binary)});
        if (result.success === false || result.received !== offset+bytes.length || (result.received === blob.size && result.status !== 'ready')) throw Error(result.error || 'Files did not confirm the complete upload.');
        progress(Math.round(result.received/blob.size*100));
      }
      return {id:start.id, filename:artifact.filename, size:blob.size};
    } catch (error) {
      throw Error('Save incomplete for ' + artifact.filename + ' (upload ' + start.id + '). Files may contain an unfinished upload; move it to Trash before retrying. ' + error.message);
    }
  }
  function input(label, key, maximum, type) { return '<label>'+label+'<input data-doc="'+key+'" type="'+(type || 'text')+'" maxlength="'+maximum+'"></label>'; }
  function area(label, key, maximum, rows) { return '<label>'+label+'<textarea data-doc="'+key+'" maxlength="'+maximum+'" rows="'+rows+'"></textarea></label>'; }
  function render(host) {
    if (dispose) dispose();
    host.classList.add('u1-native-workspace','u1-studio-pro');
    var draft = read(DRAFT), state = draft && draft.format === 'u1-studio-pro' && draft.document && Array.isArray(draft.document.sections) && draft.document.sections.length ? draft.document : blank();
    var selected = 0, revision = 0, renderedRevision = -1, pdf = null, zip = null, urls = [], busy = false, alive = true, removed = null, templates = [], timer = null, previewSerial = 0, pageNumber = 1, pageUrl = null, savedArtifact = null, handoffReview = null;
    function release() { urls.forEach(function (url) { URL.revokeObjectURL(url); }); urls = []; if (pageUrl) URL.revokeObjectURL(pageUrl); pageUrl = null; previewSerial++; }
    dispose = function () { alive = false; clearTimeout(timer); release(); host.classList.remove('u1-studio-pro'); };
    host.innerHTML = '<header class="sp-hero"><div><p class="sp-kicker">DIGITAL STUDIO / LOCAL EDITION</p><h2>Your knowledge.<br><em>Your finished product.</em></h2><p>Write, arrange and publish an original workbook, with a real PDF at every review.</p></div><div class="sp-hero-actions"><button type="button" data-sp="legacy">Original printable library</button><button type="button" data-sp="prompts">Prompt Builder</button><span data-capability>Checking local PDF tools...</span></div></header>'+
      '<div class="sp-status" data-status role="status" aria-live="polite">Start with your title and your own content.</div>'+
      '<div class="sp-properties"><div class="sp-title">'+input('Product title','title',120)+input('Subtitle','subtitle',280)+'</div>'+input('Version','version',24)+'<label>Structure<select data-doc="template"><option value="course">Course workbook</option></select></label><button type="button" data-sp="structure">Use empty structure</button></div>'+
      '<div class="sp-workbench"><aside class="sp-outline"><div class="sp-panel-heading"><h3>01 / Arrange</h3><span data-count></span></div><p>Choose a section to edit. Move it with the arrow buttons.</p><ol data-outline></ol><button type="button" data-sp="add-section">Add section</button><button type="button" data-sp="undo" hidden>Undo section removal</button><details><summary>Brand preferences</summary><label>Brand name<input data-brand="name" maxlength="80"></label><label>Accent<input data-brand="accent" type="color"></label><label>Typography<select data-brand="font"><option value="serif">Editorial serif</option><option value="sans">Clear sans</option></select></label><button type="button" data-sp="brand">Save brand for future drafts</button><small>Stored in this browser.</small></details><details><summary>Project &amp; source</summary>'+input('Audience','audience',240)+area('Content source / provenance','source',300,3)+'<button type="button" data-sp="project">Export editable project</button><label class="sp-import">Import project<input type="file" data-import accept=".json,application/json"></label><button type="button" data-sp="new">New blank draft</button><small data-draft>Draft stored in this browser.</small></details></aside>'+
      '<section class="sp-editor"><div class="sp-panel-heading"><h3>02 / Create</h3><span>YOUR WORDS, YOUR ORDER</span></div><div data-editor></div><details class="sp-export-settings"><summary>Workbook &amp; bundle settings</summary><label class="sp-check"><input type="checkbox" data-doc="fillable"> Fillable response fields</label><label class="sp-check"><input type="checkbox" data-doc="include_answer_notes"> Include operator answer notes in the exported PDF</label><p>Answer notes stay out of the learner PDF and ZIP unless you include them here. Project JSON always contains your full draft.</p>'+area('Your reader instructions (required for ZIP)','instructions',12000,4)+area('Your licence text (required for ZIP)','licence',12000,5)+'</details></section>'+
      '<section class="sp-review"><div class="sp-panel-heading"><h3>03 / Review &amp; publish</h3><span data-preview-state>NO PDF YET</span></div><button type="button" class="sp-primary" data-sp="generate">Generate accurate PDF preview</button><div class="sp-preview-empty" data-empty><b>A real preview belongs here.</b><p>Add your content, then generate the exact PDF you can download or save.</p></div><div class="sp-page-controls" data-page-controls hidden><button type="button" data-sp="previous" data-current>Previous</button><label>PDF page<select data-page></select></label><button type="button" data-sp="next" data-current>Next</button></div><img class="sp-pdf-page" data-page-image alt="Exact rendered PDF page" hidden><details data-interactive hidden><summary>Interactive PDF viewer (compatible browsers)</summary><iframe data-pdf title="Generated workbook PDF, including form fields and section links" hidden></iframe></details><div class="sp-preview-meta" data-preview-meta></div><a data-open hidden target="_blank" rel="noopener">Open this PDF in a new tab</a><p class="sp-reader-note">The page image is rendered from your exact PDF bytes. Use a form-capable PDF reader to fill and save answers; some browsers do not support the embedded interactive viewer.</p><div class="sp-export-buttons"><button type="button" data-sp="pdf" data-current disabled>Download PDF</button><button type="button" data-sp="bundle" data-current disabled>Build &amp; download ZIP</button><button type="button" data-sp="cover" data-current disabled>Download cover SVG</button><button type="button" data-sp="mockup" data-current disabled>Download mockup SVG</button></div><div class="sp-save"><label>Save to managed Files<select data-save-kind><option value="pdf">Reviewed PDF</option><option value="bundle">Complete ZIP bundle</option></select></label><button type="button" data-sp="save" data-current disabled>Save to Files</button><p data-saved></p></div><div class="sp-art"><img data-cover alt="Original local vector cover" hidden><img data-mockup alt="Original local product mockup" hidden></div></section></div>'+
      '<section class="sp-connections"><div><span class="sp-kicker">CREATIVE CONNECTIONS</span><h3>Choose what leaves your workspace.</h3><p>AI images and Canva sync are not connected. Cover and mockup artwork above is generated locally as original SVG geometry.</p></div><div><h4>AI image authorisation</h4><p>Open Connections, choose a supported image provider, review its account and usage permissions, and authorise it there. Until an image provider is integrated with this editor, use Prompt Builder to prepare your brief and run it yourself in that provider.</p><button type="button" data-go="integrations">Open Connections</button>'+(window.U1CoreViews && typeof window.U1CoreViews.supports === 'function' && window.U1CoreViews.supports('images') ? '<button type="button" data-go="images">AI image provider setup</button>' : '')+'</div><div><h4>Canva hand-off</h4><p>Open your own Canva account and import the downloaded PDF or SVG. Review account permissions before authorising any future connector. Automatic sync is unavailable in this editor.</p><a href="https://www.canva.com/" target="_blank" rel="noopener noreferrer">Open Canva</a></div></section>';
    host.querySelector('.sp-save').insertAdjacentHTML('afterend','<section class="sp-handoff"><h4>Saved file to product catalogue</h4><p>Create a private product record from the current file after Files confirms it is ready.</p><button type="button" data-sp="handoff-review" disabled>Review catalogue handoff</button><div data-handoff-review hidden><p data-handoff-file></p><label>Catalogue title<input data-handoff-title maxlength="160"></label><label>Audience<input data-handoff-audience maxlength="300"></label><label>Description<textarea data-handoff-description maxlength="4000" rows="3"></textarea></label><fieldset><legend>Optional launch checklist</legend><p>Select only the planning tasks you approve. All start in Backlog.</p>'+['Review lesson accuracy and accessibility','Review licence and asset rights','Test PDF fields and downloaded bundle','Choose pricing and an authorised sales channel','Review listing copy before manual publication'].map(function(title){return '<label class="sp-check"><input type="checkbox" data-launch-title="'+esc(title)+'">'+esc(title)+'</label>';}).join('')+'</fieldset><label class="sp-check"><input type="checkbox" data-handoff-approved>I reviewed this saved file and approve the private catalogue handoff.</label><button type="button" data-sp="handoff-create" disabled>Confirm catalogue handoff</button></div><p data-handoff-result role="status"></p><button type="button" data-go="income">Open product catalogue</button></section>');
    function status(message, error) { if (!alive) return; var node = host.querySelector('[data-status]'); if(node){node.textContent = message; node.dataset.error = String(!!error);} }
    function persist() { var okay = store(DRAFT, {format:'u1-studio-pro', schema:1, document:state}); host.querySelector('[data-draft]').textContent = okay ? 'Draft saved in this browser.' : 'Browser storage unavailable. Export your editable project to keep it.'; }
    function controls() { var stale = !pdf || renderedRevision !== revision; host.querySelectorAll('[data-current]').forEach(function (button) { button.disabled = busy || stale; }); host.querySelector('[data-sp="generate"]').disabled = busy; host.querySelector('[data-page]').disabled = busy || stale; host.querySelector('[data-sp="previous"]').disabled = busy || stale || pageNumber <= 1; host.querySelector('[data-sp="next"]').disabled = busy || stale || pageNumber >= (pdf ? pdf.pages : 1); var savedCurrent = !stale && savedArtifact && savedArtifact.revision === revision && savedArtifact.receipt; host.querySelector('[data-sp="handoff-review"]').disabled = busy || !savedCurrent; host.querySelector('[data-sp="handoff-create"]').disabled = busy || !savedCurrent || !handoffReview || !host.querySelector('[data-handoff-approved]').checked; }
    function changed() { revision++; zip = null; handoffReview = null; host.querySelector('[data-handoff-review]').hidden = true; host.querySelector('[data-handoff-approved]').checked = false; host.querySelector('[data-preview-state]').textContent = pdf ? 'PREVIEW OUT OF DATE' : 'NO PDF YET'; if (pdf) status('Draft changed. Generate a new PDF to review, download or save this version.'); controls(); clearTimeout(timer); timer = setTimeout(persist, 250); }
    function outline() {
      host.querySelector('[data-count]').textContent = state.sections.length + ' / 24';
      host.querySelector('[data-outline]').innerHTML = state.sections.map(function (s, index) { return '<li><button type="button" data-select="'+index+'" aria-current="'+String(index === selected)+'"><span>'+String(index+1).padStart(2,'0')+'</span><b>'+esc(s.title || 'Untitled section')+'</b></button><div><button type="button" data-move="'+index+'" data-direction="-1" aria-label="Move section '+(index+1)+' up" '+(index === 0 ? 'disabled' : '')+'>Up</button><button type="button" data-move="'+index+'" data-direction="1" aria-label="Move section '+(index+1)+' down" '+(index === state.sections.length-1 ? 'disabled' : '')+'>Down</button></div></li>'; }).join('');
      host.querySelector('[data-sp="add-section"]').disabled = state.sections.length >= 24;
      host.querySelector('[data-sp="undo"]').hidden = !removed;
    }
    function editor() {
      var s = state.sections[selected];
      host.querySelector('[data-editor]').innerHTML = '<label>Section title<input data-section="title" maxlength="160" value="'+esc(s.title)+'"></label><label>Lesson / section content<textarea data-section="content" maxlength="6000" rows="12" placeholder="Write your original explanations, examples and steps here.">'+esc(s.content)+'</textarea></label><label>Practice activity<textarea data-section="activity" maxlength="2000" rows="4" placeholder="Describe the activity your reader will complete.">'+esc(s.activity)+'</textarea></label><details><summary>Operator answer notes</summary><label>Notes for this section<textarea data-section="answer_notes" maxlength="3000" rows="4">'+esc(s.answer_notes)+'</textarea></label></details><div class="sp-panel-heading"><h4>Quiz questions</h4><span>'+s.quizzes.length+' / 8</span></div><div data-quizzes>'+s.quizzes.map(function (q, index) { return '<fieldset><legend>Question '+(index+1)+'</legend><label>Question<textarea data-quiz="'+index+'" data-key="question" maxlength="600" rows="3">'+esc(q.question)+'</textarea></label><label>Operator answer / explanation<textarea data-quiz="'+index+'" data-key="answer_notes" maxlength="1500" rows="3">'+esc(q.answer_notes)+'</textarea></label><button type="button" data-remove-quiz="'+index+'">Remove question</button></fieldset>'; }).join('')+'</div><div class="sp-section-actions"><button type="button" data-sp="quiz" '+(s.quizzes.length >= 8 ? 'disabled' : '')+'>Add quiz question</button><button type="button" data-sp="duplicate" '+(state.sections.length >= 24 ? 'disabled' : '')+'>Duplicate section</button><button type="button" data-sp="remove" '+(state.sections.length <= 1 ? 'disabled' : '')+'>Remove section</button></div>';
    }
    function sync() {
      host.querySelectorAll('[data-doc]').forEach(function (node) { if (node.type === 'checkbox') node.checked = !!state[node.dataset.doc]; else node.value = state[node.dataset.doc] || ''; });
      host.querySelectorAll('[data-brand]').forEach(function (node) { node.value = state.brand[node.dataset.brand]; });
      host.style.setProperty('--sp-accent', state.brand.accent); outline(); editor();
    }
    function clearPreview() { release(); pdf = null; zip = null; renderedRevision = -1; host.querySelector('[data-pdf]').hidden = true; host.querySelector('[data-pdf]').removeAttribute('src'); host.querySelector('[data-empty]').hidden = false; host.querySelector('[data-open]').hidden = true; host.querySelector('[data-preview-meta]').textContent = ''; ['cover','mockup','page-image','page-controls','interactive'].forEach(function (key) { host.querySelector('[data-'+key+']').hidden = true; }); changed(); }
    function paintPage(artifact) { if (pageUrl) URL.revokeObjectURL(pageUrl); pageUrl = URL.createObjectURL(decode(artifact)); var img = host.querySelector('[data-page-image]'); img.src = pageUrl; img.alt = 'Exact rendered PDF page '+artifact.page+' of '+pdf.pages; img.hidden = false; pageNumber = artifact.page; host.querySelector('[data-page]').value = String(pageNumber); controls(); }
    async function showPage(page) {
      if (!pdf || renderedRevision !== revision || page < 1 || page > pdf.pages) return;
      host.querySelector('[data-pdf]').src = urls[0]+'#page='+page;
      if (!pdf.preview) return;
      var serial = ++previewSerial, current = revision;
      try {
        status('Rendering PDF page '+page+' from the reviewed file...');
        var result = page === 1 ? pdf.preview : await window.U1Data.post(API,{action:'preview',content:pdf.content,signature:pdf.preview_signature,page:page});
        if (!alive || serial !== previewSerial || current !== revision) return;
        paintPage(result); status('Showing page '+page+' of the current PDF.');
      } catch (error) { status(error.message,true); }
    }
    async function request(action) {
      if (!state.title.trim()) throw Error('Add a product title first.');
      var snapshot = JSON.parse(JSON.stringify(state)), current = revision;
      if (new TextEncoder().encode(JSON.stringify({action:action, document:snapshot})).length > 262144) throw Error('This draft is too large. Shorten the content before exporting.');
      var result = await window.U1Data.post(API, {action:action, document:snapshot});
      if (!alive) return null;
      if (current !== revision) throw Error('The draft changed during generation. Generate again to review the current version.');
      if (result.success === false) throw Error(result.error || 'Generation failed.');
      return result;
    }
    async function generate() {
      status('Building your PDF, interactive fields, section links and vector artwork locally...');
      var result = await request('render'); if (!result) return;
      var blob = decode(result); if (result.mime !== 'application/pdf') throw Error('The server did not return a PDF.');
      release(); var url = URL.createObjectURL(blob); urls.push(url); pdf = result; renderedRevision = revision; zip = null;
      if(savedArtifact && result.handoff_receipt && savedArtifact.receipt.artifact.document_key === result.handoff_receipt.artifact.document_key) savedArtifact.revision = revision;
      else savedArtifact = null;
      var frame = host.querySelector('[data-pdf]'); frame.src = url+'#page=1'; frame.hidden = false; host.querySelector('[data-empty]').hidden = true;
      host.querySelector('[data-interactive]').hidden = false;
      host.querySelector('[data-page-controls]').hidden = !result.preview;
      host.querySelector('[data-page-image]').hidden = !result.preview;
      host.querySelector('[data-page]').innerHTML = Array.from({length:result.pages},function (_,index) { return '<option value="'+(index+1)+'">'+(index+1)+' / '+result.pages+'</option>'; }).join('');
      pageNumber = 1;
      if (result.preview) paintPage(result.preview);
      else { host.querySelector('[data-interactive]').open = true; status('Page-image rendering is unavailable. Use the interactive viewer or open the downloaded PDF in a compatible reader.',true); }
      var open = host.querySelector('[data-open]'); open.href = url; open.hidden = false;
      ['cover','mockup'].forEach(function (key) { var artUrl = URL.createObjectURL(decode(result.artifacts[key])); urls.push(artUrl); var img = host.querySelector('[data-'+key+']'); img.src = artUrl; img.hidden = false; });
      host.querySelector('[data-preview-state]').textContent = 'CURRENT PDF';
      host.querySelector('[data-preview-meta]').textContent = result.pages+' pages / '+result.fields.length+' form fields / Version '+state.version+' / '+Math.ceil(blob.size/1024)+' KB';
      if (result.preview) status('Preview generated from the exact PDF bytes. Contents links work in the downloaded PDF; selecting a section opens its first preview page.');
    }
    async function bundle() {
      if (!state.instructions.trim() || !state.licence.trim()) throw Error('Add your own reader instructions and licence in Workbook & bundle settings.');
      if (!zip) { status('Building the PDF, cover, mockup, instructions, licence and metadata into a ZIP...'); zip = await request('bundle'); }
      return zip;
    }
    host.oninput = function (event) {
      var node = event.target;
      if(node.hasAttribute('data-handoff-approved')){controls();return;}
      if (node.dataset.doc) state[node.dataset.doc] = node.type === 'checkbox' ? node.checked : node.value;
      else if (node.dataset.brand) { state.brand[node.dataset.brand] = node.value; host.style.setProperty('--sp-accent', state.brand.accent); }
      else if (node.dataset.section) { state.sections[selected][node.dataset.section] = node.value; if (node.dataset.section === 'title') outline(); }
      else if (node.dataset.quiz !== undefined) state.sections[selected].quizzes[Number(node.dataset.quiz)][node.dataset.key] = node.value;
      else return;
      changed();
    };
    host.onclick = async function (event) {
      var node = event.target.closest('button'); if (!node || !host.contains(node) || node.disabled) return;
      if (node.dataset.select !== undefined) { selected = Number(node.dataset.select); outline(); editor(); if (pdf && renderedRevision === revision) await showPage(pdf.section_pages[selected].page); return; }
      if (node.dataset.move !== undefined) { var from = Number(node.dataset.move), to = from+Number(node.dataset.direction); var moved = state.sections.splice(from,1)[0]; state.sections.splice(to,0,moved); selected = to; changed(); outline(); editor(); return; }
      if (node.dataset.removeQuiz !== undefined) { state.sections[selected].quizzes.splice(Number(node.dataset.removeQuiz),1); changed(); editor(); return; }
      var action = node.dataset.sp; if (!action) return;
      if (action === 'previous' || action === 'next') { await showPage(pageNumber+(action === 'next' ? 1 : -1)); return; }
      if (action === 'legacy') { if (window.U1Life && window.U1Life.renderStudio) { persist(); dispose(); host.onclick = null; host.oninput = null; window.U1Life.renderStudio(host); var back = document.createElement('button'); back.type = 'button'; back.className = 'u1-life-button'; back.textContent = 'Return to Studio Pro editor'; back.onclick = function () { render(host); }; host.prepend(back); } else status('The original printable library has not been loaded by the host.', true); return; }
      if (action === 'prompts') { var platform = window.U1Platform || window.platform; if (platform && typeof platform.open === 'function') platform.open('prompts'); else { var launcher = document.querySelector('[data-platform="prompts"]'); if (launcher) launcher.click(); else status('Prompt Builder is not available in this host yet.', true); } return; }
      if (action === 'brand') { var brandSaved = store(BRAND,state.brand); status(brandSaved ? 'Brand preferences saved for new drafts in this browser.' : 'Brand preferences could not be saved in this browser.', !brandSaved); return; }
      if (action === 'project') { download(new Blob([JSON.stringify({format:'u1-studio-pro',schema:1,document:state},null,2)],{type:'application/json'}),'u1-studio-project.json'); status('Editable project download requested. This file includes operator answer notes.'); return; }
      if (action === 'new') { if (!window.confirm('Replace this browser draft with an empty project? Export the project first if you want to keep it.')) return; state = blank(); selected = 0; removed = null; clearPreview(); sync(); persist(); return; }
      if (action === 'structure') { var template = templates.find(function (t) { return t.id === state.template; }); if (!template) return; if (!window.confirm('Replace all sections with the selected empty structure? Your title, brand and bundle settings will be kept.')) return; state.sections = template.sections.map(function (title) { return section(title); }); selected = 0; removed = null; changed(); outline(); editor(); return; }
      if (action === 'add-section') { state.sections.push(section()); selected = state.sections.length-1; }
      else if (action === 'duplicate') { state.sections.splice(selected+1,0,JSON.parse(JSON.stringify(state.sections[selected]))); selected++; }
      else if (action === 'remove') { removed = {index:selected,section:state.sections.splice(selected,1)[0]}; selected = Math.max(0,selected-1); }
      else if (action === 'undo') { if (state.sections.length >= 24) { status('Make room before restoring this section.',true); return; } state.sections.splice(removed.index,0,removed.section); selected = removed.index; removed = null; }
      else if (action === 'quiz') state.sections[selected].quizzes.push({question:'',answer_notes:''});
      else {
        if (busy) return;
        if (action !== 'generate' && (!pdf || renderedRevision !== revision)) { status('Generate and review the current PDF first.',true); return; }
        busy = true; controls();
        try {
          if (action === 'generate') await generate();
          else if (action === 'pdf') { download(decode(pdf),pdf.filename); status('Reviewed PDF download requested.'); }
          else if (action === 'cover' || action === 'mockup') { download(decode(pdf.artifacts[action]),pdf.artifacts[action].filename); status('Original local '+action+' SVG download requested.'); }
          else if (action === 'bundle') { var built = await bundle(); if (built) { download(decode(built),built.filename); status('ZIP download requested with your instructions and licence.'); } }
          else if(action === 'handoff-review') {
            if(!savedArtifact || savedArtifact.revision !== revision) throw Error('Save the current reviewed PDF or ZIP to Files first.');
            var reviewRevision = revision;
            var review = await window.U1Data.post(API,{action:'handoff-review',file_id:savedArtifact.id,receipt:savedArtifact.receipt});
            if(!alive || reviewRevision !== revision) return;
            handoffReview = review;
            host.querySelector('[data-handoff-review]').hidden = false;
            host.querySelector('[data-handoff-approved]').checked = false;
            host.querySelector('[data-handoff-file]').textContent = (review.existing ? 'Existing product will be reused. ' : 'New private product, status Review. ')+review.file.name+' / Version '+review.artifact.version+' / Ready file '+review.file.id+' / SHA-256 '+review.file.checksum;
            ['title','audience','description'].forEach(function(key){var field=host.querySelector('[data-handoff-'+key+']');field.value=review.product[key];field.readOnly=!!review.existing;});
            status('Review the saved file, catalogue details and any optional launch tasks, then explicitly confirm.');
          }
          else if(action === 'handoff-create') {
            if(!savedArtifact || savedArtifact.revision !== revision || !handoffReview || !host.querySelector('[data-handoff-approved]').checked) throw Error('Review and approve the current saved file first.');
            var handoffRevision=revision, product={};
            ['title','audience','description'].forEach(function(key){product[key]=host.querySelector('[data-handoff-'+key+']').value;});
            var approvedTasks=Array.from(host.querySelectorAll('[data-launch-title]:checked')).map(function(box){return box.dataset.launchTitle;});
            var handed = await window.U1Data.post(API,{action:'handoff',file_id:savedArtifact.id,receipt:savedArtifact.receipt,reviewed:true,product:product,expected_product_version:handoffReview.expected_product_version,checklist:approvedTasks});
            if(!alive) return;
            host.querySelector('[data-handoff-result]').textContent=(handed.reused?'Reused':'Created')+' product '+handed.product.title+' / ID '+handed.product.id+' / Version '+handed.product.payload.current_version+'. '+handed.launches.length+' approved launch task(s) linked. '+(handed.partial ? 'Some tasks remain: '+handed.pending_checklist.join('; ')+'. Retry the handoff to add only missing tasks. ' : '')+handed.warnings.join(' ');
            if(handoffRevision === revision && handoffReview){handoffReview.expected_product_version=handed.product.version;if(!handed.partial){host.querySelector('[data-handoff-approved]').checked=false;handoffReview=null;}}
            status(handed.partial?'Product saved; some approved checklist tasks need a retry.':'Private catalogue handoff saved. Nothing was published or scheduled for publication.',handed.partial);
          }
          else if (action === 'save') {
            var saveRevision = revision;
            var artifact = host.querySelector('[data-save-kind]').value === 'bundle' ? await bundle() : pdf;
            if (!artifact || !alive) return;
            var saved = await saveFile(artifact,function (percent) { status('Saving to managed Files: '+percent+'%'); });
            savedArtifact = artifact.handoff_receipt ? {id:saved.id,receipt:artifact.handoff_receipt,revision:saveRevision} : null;
            handoffReview = null; host.querySelector('[data-handoff-review]').hidden = true;
            if (alive) { host.querySelector('[data-saved]').textContent = 'Saved '+saved.filename+' / File ID '+saved.id; status('Saved to managed Files / Digital Studio. Title, version and source are embedded in the PDF or ZIP metadata.'); }
          }
        } catch (error) { status(error.message,true); }
        finally { busy = false; if (alive) controls(); }
        return;
      }
      changed(); outline(); editor();
    };
    host.querySelector('[data-import]').onchange = async function (event) {
      var file = event.target.files[0]; if (!file) return;
      try {
        if (file.size > 262144) throw Error('Choose a project JSON file no larger than 256 KB.');
        var data = JSON.parse(await file.text());
        if (data.format !== 'u1-studio-pro' || data.schema !== 1 || !data.document) throw Error('This is not a Studio Pro project.');
        var current = revision;
        var validated = await window.U1Data.post(API,{action:'artwork',document:data.document});
        if (!alive || current !== revision) throw Error('The current draft changed during import. Choose the file again.');
        if (!window.confirm('Replace this browser draft with the imported project?')) return;
        state = validated.document; selected = 0; removed = null; clearPreview(); sync(); persist(); status('Project imported and validated locally. Generate a new PDF to review it.');
      } catch (error) { status(error.message,true); }
      finally { event.target.value = ''; }
    };
    host.querySelector('[data-page]').onchange = function (event) { showPage(Number(event.target.value)); };
    sync();
    window.U1Data.get(API,{fresh:true}).then(function (result) {
      if (!alive) return; templates = result.templates || [];
      host.querySelector('[data-doc="template"]').innerHTML = templates.map(function (t) { return '<option value="'+esc(t.id)+'">'+esc(t.title)+'</option>'; }).join(''); host.querySelector('[data-doc="template"]').value = state.template;
      host.querySelector('[data-capability]').textContent = result.capabilities.pdf ? 'LOCAL PDF + SVG / NO AI CREDITS' : 'SVG READY / PDF DEPENDENCY MISSING';
      if (!result.capabilities.pdf) status(result.notice+' PDF generation requires reportlab in the application runtime.',true);
    }).catch(function (error) { status('Studio Pro endpoint unavailable: '+error.message,true); host.querySelector('[data-capability]').textContent = 'LOCAL ENDPOINT NOT READY'; });
  }
  window.U1StudioPro = Object.freeze({render:render,saveFile:saveFile});
  if (window.U1CoreViews) window.U1CoreViews.register('studio',render);
})();

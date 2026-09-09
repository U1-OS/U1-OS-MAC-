/* Native Create / Earn. Browse with GET; mutate only after a reviewed confirmation. */
(function (root) {
  'use strict';
  var PERSONAL='/api/workspace/personal', PRISM='/api/workspace/prism', STUDIO='/api/workspace/studio-pro';
  var PRODUCT_STATES=['idea','building','review','ready','launched'], TASK_STATES=['backlog','doing','review','done'];
  var hosts=new WeakMap(), active=null, writing=false;
  function esc(value){return String(value==null?'':value).replace(/[&<>"']/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];});}
  function title(value){return String(value||'').replace(/_/g,' ').replace(/^./,function(c){return c.toUpperCase();});}
  function validId(value){return typeof value==='string'&&/^[a-f0-9]{32}$/.test(value);}
  function text(value,max,required){if(typeof value!=='string'||value.length>max||/[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]/.test(value))throw Error('Use text within the stated field limit.');value=value.trim();if(required&&!value)throw Error('Complete the required fields.');return value;}
  function checked(value){if(!value||typeof value!=='object'||value.success===false)throw Error(value&&value.error||'The local service did not return usable data.');return value;}
  function record(value,kind){if(!value||!validId(value.id)||value.kind!==kind||!Number.isSafeInteger(value.version)||value.version<1||typeof value.title!=='string'||!value.payload||typeof value.payload!=='object')throw Error('The catalogue response is incomplete. Refresh before editing.');return value;}
  function readyFile(file){return !!(file&&validId(file.id)&&file.status==='ready'&&file.deleted==null&&Number.isSafeInteger(file.size)&&file.size>0&&file.size<=25*1024*1024&&file.received===file.size&&/^[a-f0-9]{64}$/.test(file.checksum||'')&&['application/pdf','application/zip'].includes(file.mime));}
  async function readKind(transport,kind){
    var rows=[],seen=new Set(),total=null;
    for(var page=0;page<10;page++){
      var response=checked(await transport.get(PERSONAL+'/snapshot?kind='+kind+'&archived=active&limit=200&offset='+rows.length,{fresh:true}));
      if(!Array.isArray(response.records)||!Number.isInteger(response.total)||response.total<0||response.total>2000||typeof response.has_more!=='boolean')throw Error('The catalogue count is unavailable.');
      if(total!==null&&total!==response.total)throw Error('The catalogue changed while loading. Refresh to see a consistent list.');total=response.total;
      response.records.forEach(function(row){record(row,kind);if(row.archived||seen.has(row.id))throw Error('The catalogue changed while paging. Refresh the list.');seen.add(row.id);rows.push(row);});
      if(!response.has_more){if(rows.length!==total)throw Error('The catalogue page is incomplete.');return rows;}
      if(!response.records.length||rows.length>=total)throw Error('The catalogue pagination did not advance.');
    }
    throw Error('The catalogue exceeds this view\'s bounded pagination. Use the advanced editor.');
  }
  function derive(products,launches,files,templates,errors){
    var counts={};PRODUCT_STATES.forEach(function(status){counts[status]=products?products.filter(function(row){return row.payload.status===status;}).length:null;});
    return {products:products,launches:launches,files:files,templates:templates||[],errors:errors||[],counts:counts,
      pending:launches?launches.filter(function(row){return row.payload.status!=='done';}).length:null,
      readyFiles:files?files.filter(readyFile):null,loadedAt:Date.now()};
  }
  function selected(model,id){return model.products&&model.products.find(function(row){return row.id===id;});}
  function fileFor(model,id){return model.readyFiles&&model.readyFiles.find(function(file){return file.id===id;});}
  function currentFile(model,product){return (product.payload.versions||[]).filter(function(version){return version.version===product.payload.current_version;}).map(function(version){return fileFor(model,version.file_id);}).find(Boolean);}
  function prepare(type,values,model,id){
    var product=selected(model,id),body,intent={type:type},status;
    if(type==='product'){
      if(!model.products)throw Error('Load the real catalogue before creating a product plan.');
      body={action:'create',kind:'product',title:text(values.title,160,true),payload:{status:'idea',audience:text(values.audience||'',300),description:text(values.description||'',4000)}};
      intent.label='Create a private product plan';
    }else if(type==='launch-status'){
      var task=model.launches&&model.launches.find(function(row){return row.id===id;});if(!task)throw Error('Select an available launch task.');
      status=text(values.status,20,true);if(!TASK_STATES.includes(status))throw Error('Choose a supported launch status.');
      if(status===task.payload.status)throw Error('Choose a different status before reviewing.');
      body={action:'update',id:task.id,expected_version:task.version,payload:{status:status}};intent.recordKind='launch';intent.name=task.title;intent.before=task.payload.status;intent.label='Update an approved launch task';
    }else{
      if(!product)throw Error('Select an available product first.');intent.productId=product.id;intent.name=product.title;
      if(type==='launch'){
        body={action:'create',kind:'launch',title:text(values.title,160,true),payload:{product_id:product.id,status:'backlog',due:text(values.due||'',10)}};
        if(body.payload.due&&!/^\d{4}-\d{2}-\d{2}$/.test(body.payload.due))throw Error('Use a calendar date in YYYY-MM-DD format.');
        intent.label='Create an operator-approved launch task';
      }else if(type==='version'){
        var file=fileFor(model,values.file_id),version=text(values.version,60,true);if(!file)throw Error('Choose a complete, ready PDF or ZIP from the loaded Files inventory.');
        var versions=product.payload.versions||[];if(versions.length>=20)throw Error('This product already has 20 version-file links. Review them in Income.');
        if(versions.some(function(row){return row.version===version&&row.file_id===file.id;}))throw Error('That file is already linked to this version.');
        body={action:'update',id:product.id,expected_version:product.version,payload:{current_version:version,versions:versions.concat([{version:version,file_id:file.id,notes:'Operator-reviewed managed file. SHA-256: '+file.checksum+'\n'+text(values.notes||'',400)}])}};
        intent.file={id:file.id,name:file.name,mime:file.mime,size:file.size,checksum:file.checksum};intent.label='Link a saved file and make this version current';intent.version=version;
      }else if(type==='product-status'){
        status=text(values.status,20,true);if(!PRODUCT_STATES.includes(status))throw Error('Choose a supported product status.');
        if(status===product.payload.status)throw Error('Choose a different status before reviewing.');
        if(status==='ready'||status==='launched'){var ready=currentFile(model,product);if(!ready)throw Error('Link a ready file to the current version first. Older files may need review in Files.');intent.file={id:ready.id,name:ready.name,mime:ready.mime,size:ready.size,checksum:ready.checksum};}
        body={action:'update',id:product.id,expected_version:product.version,payload:{status:status}};intent.before=product.payload.status;intent.label='Record your product status';
      }else throw Error('Choose a supported local review.');
      intent.recordKind='product';
    }
    intent.body=body;return intent;
  }
  async function verifiedDownload(transport,file){
    var result=checked(await transport.get(PRISM+'/file?id='+encodeURIComponent(file.id),{fresh:true}));
    if(result.id!==file.id||result.name!==file.name||result.mime!==file.mime||typeof result.content!=='string'||result.content.length>34952536)throw Error('The file response changed. Refresh and review it again.');
    var binary=root.atob(result.content),bytes=new Uint8Array(binary.length);for(var i=0;i<binary.length;i++)bytes[i]=binary.charCodeAt(i);
    if(bytes.length!==file.size)throw Error('The file size changed. No download or catalogue mutation was made.');
    if(!root.crypto||!root.crypto.subtle)throw Error('Byte verification is unavailable in this browser. Use the managed Files workspace.');
    var digest=Array.from(new Uint8Array(await root.crypto.subtle.digest('SHA-256',bytes))).map(function(n){return n.toString(16).padStart(2,'0');}).join('');
    if(digest!==file.checksum)throw Error('The file checksum changed. Refresh and review the saved file again.');
    return {bytes:bytes,name:result.name,mime:result.mime};
  }
  function createController(transport){
    var attempted=new WeakSet();
    return {
      load:async function(){
        var results=await Promise.allSettled([readKind(transport,'product'),readKind(transport,'launch'),transport.get(PRISM+'/summary',{fresh:true}).then(function(v){v=checked(v);if(!Array.isArray(v.files))throw Error('The recent Files inventory is unavailable.');return v.files;}),transport.get(STUDIO,{fresh:true}).then(function(v){v=checked(v);if(!Array.isArray(v.templates))throw Error('Studio structures are unavailable.');return v.templates.filter(function(t){return t&&typeof t.id==='string'&&typeof t.title==='string'&&Array.isArray(t.sections)&&t.sections.every(function(s){return typeof s==='string';});});})]);
        var names=['Products','Launch tasks','Recent Files','Studio structures'],errors=[];
        function value(i){if(results[i].status==='fulfilled')return results[i].value;errors.push(names[i]+': '+results[i].reason.message);return null;}
        return derive(value(0),value(1),value(2),value(3),errors);
      },
      commit:async function(intent,approved,stillActive){
        if(approved!==true)throw Error('Explicitly approve the reviewed private-record change.');
        if(writing||attempted.has(intent))throw Error('This review is already submitted. Refresh before starting another review.');
        writing=true;var posted=false;
        try{
          var body=intent.body;
          if(body.action==='update'){
            var response=checked(await transport.get(PERSONAL+'/snapshot?id='+body.id+'&archived=all',{fresh:true}));
            var current=Array.isArray(response.records)&&response.records.find(function(r){return r.id===body.id;});
            if(!current||current.archived||current.version!==body.expected_version)throw Error('This record changed after review. Your form is preserved; refresh and review the latest version.');
          }else if(body.kind==='product'){
            var products=await readKind(transport,'product');
            if(products.some(function(p){return p.title.toLocaleLowerCase()===body.title.toLocaleLowerCase()&&p.payload.audience===body.payload.audience&&p.payload.description===body.payload.description;}))throw Error('A matching private product plan already exists. Select it instead of creating a duplicate.');
          }else{
            var parent=checked(await transport.get(PERSONAL+'/snapshot?id='+intent.productId+'&archived=all',{fresh:true}));
            if(!Array.isArray(parent.records)||!parent.records.some(function(p){return p.id===intent.productId&&!p.archived;}))throw Error('The product is no longer active. Review the catalogue.');
            var tasks=await readKind(transport,'launch');
            if(tasks.some(function(task){return task.payload.product_id===intent.productId&&task.title===body.title;}))throw Error('That launch task already exists for this product. Review the existing task.');
          }
          if(intent.file)await verifiedDownload(transport,intent.file);
          if(stillActive&&stillActive()!==true)throw Error('The workspace was left before submission. Review again when you return.');
          attempted.add(intent);posted=true;
          var result=checked(await transport.post(PERSONAL,body));record(result.record,body.kind||intent.recordKind);return result.record;
        }catch(error){if(posted)error.uncertain=true;throw error;}finally{writing=false;}
      }
    };
  }
  function button(label,action,extra){return '<button type="button" class="ce-button" data-ce-action="'+action+'" '+(extra||'')+'>'+esc(label)+'</button>';}
  function nav(label,id,primary){return '<button type="button" class="ce-button'+(primary?' ce-primary':'')+'" data-go="'+id+'">'+esc(label)+'</button>';}
  function empty(message){return '<p class="ce-empty">'+esc(message)+'</p>';}
  function badge(status){return '<span class="ce-badge">'+esc(title(status))+'</span>';}
  function card(label,content,classes){return '<section class="ce-card '+(classes||'')+'"><h2>'+esc(label)+'</h2>'+content+'</section>';}
  function count(value){return value===null?'Unavailable':String(value);}
  function productRows(model,query,filter,selectedId){
    if(!model.products)return empty('Products could not be loaded. No empty catalogue or zero count is assumed.');
    var rows=model.products.filter(function(row){return (filter==='all'||row.payload.status===filter)&&(row.title+' '+row.payload.audience+' '+row.payload.description).toLocaleLowerCase().includes(query.toLocaleLowerCase());});
    if(!rows.length)return empty(model.products.length?'No products match this filter.':'Your catalogue is empty. Plan a product or create an original workbook in Studio.');
    return '<ul class="ce-list">'+rows.map(function(row){return '<li><button type="button" class="ce-product" data-ce-action="select" data-id="'+row.id+'" aria-pressed="'+(row.id===selectedId)+'"><span><strong>'+esc(row.title)+'</strong><small>'+esc(row.payload.audience||'Audience not recorded')+'</small></span><span>'+badge(row.payload.status)+'<small>'+esc(row.payload.current_version?'Version '+row.payload.current_version:'No version linked')+'</small></span></button></li>';}).join('')+'</ul><p class="ce-caption">'+rows.length+' of '+model.products.length+' active products. Recently updated first.</p>';
  }
  function mainMarkup(model,state){
    var product=selected(model,state.selected),version=product&&currentFile(model,product);
    var metrics='<dl class="ce-metrics"><div><dt>Active products</dt><dd>'+count(model.products?model.products.length:null)+'</dd></div><div><dt>In review</dt><dd>'+count(model.counts.review)+'</dd></div><div><dt>Ready records</dt><dd>'+count(model.counts.ready)+'</dd></div><div><dt>Open launch tasks</dt><dd>'+count(model.pending)+'</dd></div></dl>';
    var flow='<ol class="ce-flow"><li><b>01</b><strong>Create original content</strong><span>Write and arrange your workbook in Studio.</span>'+nav('Open Studio','studio')+'</li><li><b>02</b><strong>Save the reviewed file</strong><span>Use Studio\'s explicit save; confirm Files reports ready.</span>'+nav('Open managed Files','files')+'</li><li><b>03</b><strong>Review a real version</strong><span>Use Studio\'s signed handoff, or explicitly link a saved file to your selected plan.</span>'+button('Link saved version','version',product?'':'disabled')+'</li><li><b>04</b><strong>Work the launch list</strong><span>Approve tasks, review work and publish only outside this hub.</span>'+button('Add launch task','launch',product?'':'disabled')+'</li></ol><p class="ce-caption">Local PDF/SVG creation makes no model request and spends no API credits. Opening Studio preserves its existing draft; applying a structure requires your review there.</p>';
    var pipeline='<div class="ce-pipeline">'+PRODUCT_STATES.map(function(status){var rows=model.products?model.products.filter(function(p){return p.payload.status===status;}):[];return '<section><h3>'+esc(title(status))+' <span>'+count(model.counts[status])+'</span></h3>'+rows.slice(0,4).map(function(p){return button(p.title,'select','data-id="'+p.id+'"');}).join('')+(rows.length>4?button('Show all '+rows.length,'filter','data-status="'+status+'"'):'')+'</section>';}).join('')+'</div><p class="ce-caption">Statuses are operator records, not evidence of sales, connected stores or verified earnings. No sample revenue or estimated income is mixed into this board.</p>';
    var filters='<div class="ce-filters"><label>Find a product<input data-ce-search maxlength="160" value="'+esc(state.query)+'" type="search" placeholder="Title, audience or outcome"></label><label>Status<select data-ce-filter>'+['all'].concat(PRODUCT_STATES).map(function(s){return '<option value="'+s+'" '+(state.filter===s?'selected':'')+'>'+esc(title(s))+'</option>';}).join('')+'</select></label></div><div data-ce-products>'+productRows(model,state.query,state.filter,state.selected)+'</div>';
    var detail=product?'<h3>'+esc(product.title)+'</h3><p>'+esc(product.payload.description||'No outcome has been recorded yet.')+'</p><dl class="ce-details"><dt>Status</dt><dd>'+esc(title(product.payload.status))+'</dd><dt>Record revision</dt><dd>'+product.version+'</dd><dt>Current version</dt><dd>'+esc(product.payload.current_version||'Not linked')+'</dd><dt>Current file</dt><dd>'+esc(version?version.name:'No matching ready file in the recent inventory')+'</dd></dl><div class="ce-actions">'+button('Review product status','product-status')+button('Link saved version','version')+button('Add launch task','launch')+'</div><details><summary>Version files and provenance notes</summary><ul class="ce-list">'+(product.payload.versions||[]).map(function(v){return '<li><strong>'+esc(v.version)+'</strong><code>'+esc(v.file_id)+'</code><p>'+esc(v.notes)+'</p></li>';}).join('')+'</ul></details><p class="ce-caption">File readiness here is loaded metadata, not a content-quality approval. Linking or marking ready verifies file bytes again before submission.</p>':empty('Select a product to review its current version, linked files and next launch work.');
    var tasks=model.launches&&model.launches.filter(function(row){return !state.selected||row.payload.product_id===state.selected;});
    var taskList=!tasks?empty('Launch tasks are unavailable. Refresh to load real records.'):!tasks.length?empty('No launch tasks for this selection. Add only the planning work you approve.'):'<ul class="ce-list">'+tasks.slice(0,24).map(function(task){var owner=selected(model,task.payload.product_id);return '<li class="ce-task"><div><strong>'+esc(task.title)+'</strong><small>'+esc(owner?owner.title:'Linked product unavailable')+(task.payload.due?' / Due '+esc(task.payload.due):'')+'</small></div>'+badge(task.payload.status)+button('Review status','launch-status','data-id="'+task.id+'"')+'</li>';}).join('')+'</ul><p class="ce-caption">Showing '+Math.min(tasks.length,24)+' of '+tasks.length+' tasks for this selection. '+(state.selected?'Select a different product to change the work list.':'Use Income for the full task editor.')+'</p>';
    var templates=model.templates.length?'<div class="ce-templates">'+model.templates.map(function(t){return button(t.title,'template','data-template="'+esc(t.id)+'"');}).join('')+'</div><div data-ce-template>'+empty('Inspect a real local structure before opening the advanced editor.')+'</div>':empty('Studio structures are unavailable. The advanced Studio editor remains accessible.');
    var files=model.readyFiles?model.readyFiles.slice(0,8):null;
    var fileList=!files?empty('The recent Files inventory is unavailable.'):!files.length?empty('No complete PDF or ZIP in the loaded recent Files inventory. Save one explicitly from Studio first.'):'<ul class="ce-list">'+files.map(function(file){return '<li><strong>'+esc(file.name)+'</strong><small>'+Math.ceil(file.size/1024)+' KiB / '+(file.mime==='application/pdf'?'PDF':'ZIP')+' / Ready record</small>'+button('Verify & download','download','data-file="'+file.id+'"')+'</li>';}).join('')+'</ul><p class="ce-caption">Showing '+files.length+' of '+model.readyFiles.length+' candidate PDFs/ZIPs in the recent loaded inventory. This is not a whole-library total; older files may be outside the response window.</p>';
    return metrics+'<div class="ce-grid">'+card(state.mode==='earn'?'Your product pipeline':'From original idea to a reviewed release',state.mode==='earn'?pipeline:flow,'ce-wide')+card('Your product shelf',filters,'ce-main')+card('Selected product',detail,'ce-side')+card('Approved launch work',taskList,'ce-main')+card(state.mode==='create'?'Original structures':'Production desk',state.mode==='create'?templates:flow,'ce-side')+card('Saved file inbox',fileList,'ce-main')+card('Advanced tools, explicit connections','<p>Keep full editing, original templates and detailed personal records within reach.</p><div class="ce-actions">'+nav('Advanced Studio','studio')+nav('Advanced Income','income')+nav('Managed Files','files')+'</div><hr><h3>Optional provider setup</h3><p>Authorisation is required before any provider can access an account. Chat/model subscriptions do not include separate provider API billing. This hub does not connect accounts, generate AI images or sync Canva.</p>'+nav('Review Connections','integrations'),'ce-side')+'</div>';
  }
  function field(label,name,max,value,area){return '<label>'+label+(area?'<textarea name="'+name+'" maxlength="'+max+'" rows="4">'+esc(value||'')+'</textarea>':'<input name="'+name+'" maxlength="'+max+'" value="'+esc(value||'')+'">')+'</label>';}
  function editorMarkup(editor,model){
    if(editor.intent){var intent=editor.intent,body=intent.body;return '<h2>Review before saving</h2><p>'+esc(intent.label)+'</p><dl class="ce-details"><dt>Record</dt><dd>'+esc(body.title||intent.name)+'</dd>'+(body.expected_version?'<dt>Expected revision</dt><dd>'+body.expected_version+'</dd>':'')+(body.payload.status?'<dt>Recorded status</dt><dd>'+esc(title(body.payload.status))+'</dd>':'')+(intent.file?'<dt>Managed file</dt><dd>'+esc(intent.file.name)+'<code>'+intent.file.id+'</code></dd><dt>SHA-256</dt><dd><code>'+intent.file.checksum+'</code></dd><dt>Version</dt><dd>'+esc(intent.version||'Current linked version')+'</dd>':'')+'</dl><p>This changes a private local record only. It does not publish, schedule a post, make a sale or access a provider account.</p>'+(body.payload.status==='launched'?'<p><strong>Launched means you report publication performed elsewhere; it is not verified sales or revenue.</strong></p>':'')+'<label class="ce-check"><input type="checkbox" data-ce-approve>I reviewed these exact details and approve this private-record change.</label><div class="ce-actions">'+button('Confirm private save','commit')+button('Back to form','edit')+button('Close review','cancel')+'</div><p data-ce-review-error role="alert"></p>';}
    var product=selected(model,editor.id),values=editor.values||{},content='';
    if(editor.type==='product')content=field('Product title','title',160,values.title)+field('Audience','audience',300,values.audience)+field('Useful outcome / description','description',4000,values.description,true)+'<p class="ce-caption">This creates an Idea record, not a generated asset. Existing Studio work remains untouched.</p>';
    if(editor.type==='version')content='<label>Ready PDF or ZIP<select name="file_id"><option value="">Choose a saved file</option>'+(model.readyFiles||[]).map(function(f){return '<option value="'+f.id+'" '+(values.file_id===f.id?'selected':'')+'>'+esc(f.name)+'</option>';}).join('')+'</select></label>'+field('Version label (becomes current)','version',60,values.version)+field('Your version notes','notes',400,values.notes,true)+'<p class="ce-caption">The file will be read and its checksum verified when you explicitly confirm. This manual link does not claim the file originated in Studio; use Studio\'s signed handoff for that provenance.</p>';
    if(editor.type==='launch')content=field('Approved launch task','title',160,values.title)+field('Optional due date (YYYY-MM-DD)','due',10,values.due)+'<p class="ce-caption">Starts in Backlog. Nothing is published or scheduled automatically.</p>';
    if(editor.type==='product-status'||editor.type==='launch-status'){var states=editor.type==='product-status'?PRODUCT_STATES:TASK_STATES;var current=editor.type==='product-status'?product:(model.launches||[]).find(function(t){return t.id===editor.id;});content='<label>Recorded status<select name="status">'+states.map(function(s){return '<option value="'+s+'" '+((values.status||current&&current.payload.status)===s?'selected':'')+'>'+esc(title(s))+'</option>';}).join('')+'</select></label>';}
    return '<h2>'+esc(editor.type==='product'?'Plan a private product':editor.type==='version'?'Review a saved version':editor.type==='launch'?'Add approved launch work':'Review a status change')+'</h2>'+(product?'<p>For '+esc(product.title)+' / record revision '+product.version+'</p>':'')+'<form data-ce-form><div class="ce-form-grid">'+content+'</div><div class="ce-actions"><button class="ce-button ce-primary" type="submit">Review details</button>'+button('Keep browsing','cancel')+'</div><p data-ce-review-error role="alert"></p></form>';
  }
  function render(host,mode){
    var old=hosts.get(host);if(old){old.activate();return;}if(active)active.deactivate();
    var alive=true,serial=0,model=null,editor=null,dirty=false,mutating=false,needsPaint=false;
    var state={mode:mode,selected:'',query:'',filter:'all'},transport=root.U1Data,client=transport&&createController(transport);
    host.classList.add('u1-native-workspace','u1-create-earn');
    host.innerHTML='<header class="ce-hero"><div><p class="ce-eyebrow">'+(mode==='create'?'CREATE / ORIGINAL WORK':'EARN / OPERATOR-LED WORK')+'</p><h1>'+(mode==='create'?'Make something<br><em>worth keeping.</em>':'Your work.<br><em>Your next move.</em>')+'</h1><p>'+(mode==='create'?'A production desk for your own ideas, real files and reviewed releases.':'A real product catalogue and launch workbench. Progress, not invented earnings.')+'</p></div><div class="ce-hero-tools">'+nav('Open advanced Studio','studio',true)+button('Plan a private product','product')+nav('Open advanced Income','income')+'<p>Local tools. No model request, paid API call or account action starts here.</p><span class="ce-badge">Private by intent / explicit saves</span></div></header><div class="ce-toolbar">'+button('Refresh local records','refresh')+'<p data-ce-updated>Loading local records...</p></div><p class="ce-notice" data-ce-notice role="status" aria-live="polite"></p><section class="ce-composer" data-ce-editor hidden aria-label="Private record review"></section><main data-ce-content aria-label="'+(mode==='create'?'Create':'Earn')+' workflows">'+empty('Loading real catalogue records. Counts will appear only when their source responds.')+'</main>';
    function notice(message,bad){var n=host.querySelector('[data-ce-notice]');n.textContent=message;n.dataset.error=String(!!bad);}
    function paint(){if(!model)return;host.querySelector('[data-ce-content]').innerHTML=mainMarkup(model,state);host.querySelector('[data-ce-updated]').textContent='Local snapshot / '+new Date(model.loadedAt).toLocaleTimeString();needsPaint=false;}
    async function refresh(){if(!client){notice('U1Data is unavailable. No data or counts were invented.',true);return;}var token=++serial;notice('Refreshing local records; no changes are being saved.');try{var result=await client.load();if(token!==serial)return;model=result;if(state.selected&&!selected(model,state.selected))state.selected='';if(alive){paint();notice(result.errors.join(' '),result.errors.length>0);}else needsPaint=true;}catch(error){if(alive)notice(error.message,true);}}
    function formPaint(){var pane=host.querySelector('[data-ce-editor]');pane.hidden=!editor;if(editor){pane.innerHTML=editorMarkup(editor,model);var focus=pane.querySelector&&pane.querySelector('input,select,textarea,button');if(focus&&focus.focus)focus.focus();}}
    function openEditor(type,id){if(!model){notice('Wait for the real catalogue before reviewing changes.',true);return;}if(mutating)return;if(editor&&dirty&&root.confirm&&!root.confirm('Replace this unsaved review form? No changes have been saved.'))return;editor={type:type,id:id||state.selected,values:{},intent:null};dirty=false;formPaint();}
    function formError(message){var n=host.querySelector('[data-ce-review-error]');if(n)n.textContent=message;notice(message,true);}
    async function click(event){var node=event.target.closest('[data-ce-action]');if(!node||!host.contains(node)||node.disabled)return;var action=node.dataset.ceAction;
      if(action==='refresh'){await refresh();return;}
      if(action==='select'){state.selected=node.dataset.id;paint();return;}
      if(action==='filter'){state.filter=node.dataset.status;paint();return;}
      if(action==='cancel'){if(mutating)return;editor=null;dirty=false;formPaint();return;}
      if(action==='edit'){if(mutating||!editor)return;editor.intent=null;formPaint();return;}
      if(action==='template'){var structure=model&&model.templates.find(function(t){return t.id===node.dataset.template;});if(structure)host.querySelector('[data-ce-template]').innerHTML='<h3>'+esc(structure.title)+'</h3><ol>'+structure.sections.map(function(s){return '<li>'+esc(s)+'</li>';}).join('')+'</ol>'+nav('Open Studio to apply this structure','studio')+'<p class="ce-caption">Your Studio draft is not replaced from this hub. Review the structure and apply it explicitly in the editor. Local PDF/SVG tools do not use model credits.</p>';return;}
      if(action==='download'){if(!model)return;var file=fileFor(model,node.dataset.file);if(!file)return;node.disabled=true;try{notice('Reading and verifying the selected managed file...');var result=await verifiedDownload(transport,file);if(!alive)return;var url=URL.createObjectURL(new Blob([result.bytes],{type:result.mime})),link=document.createElement('a');link.href=url;link.download=result.name;document.body.append(link);link.click();link.remove();setTimeout(function(){URL.revokeObjectURL(url);},60000);notice('Verified file download requested.');}catch(error){if(alive)notice(error.message,true);}finally{node.disabled=false;}return;}
      if(action==='commit'){
        if(mutating||!editor||!editor.intent)return;var review=editor,intent=review.intent,approved=host.querySelector('[data-ce-approve]').checked;mutating=true;node.disabled=true;
        try{var saved=await client.commit(intent,approved,function(){return alive;});editor=null;dirty=false;if(alive){formPaint();await refresh();notice('Saved private '+saved.kind+' record: '+saved.title+'. Nothing was published or sent to a provider.');}else{needsPaint=true;await refresh();}}
        catch(error){if(alive)formError((error.uncertain?'Save outcome is not confirmed. Refresh and inspect the catalogue before starting another review. ':'')+error.message);}
        finally{mutating=false;node.disabled=false;}return;
      }
      if(['product','version','launch','product-status','launch-status'].includes(action))openEditor(action,node.dataset.id);
    }
    function input(event){var node=event.target;if(node.hasAttribute('data-ce-search')){state.query=node.value;host.querySelector('[data-ce-products]').innerHTML=productRows(model,state.query,state.filter,state.selected);}else if(node.hasAttribute('data-ce-filter')){state.filter=node.value;host.querySelector('[data-ce-products]').innerHTML=productRows(model,state.query,state.filter,state.selected);}else if(editor&&node.name){editor.values[node.name]=node.value;dirty=true;}}
    function submit(event){if(!event.target.hasAttribute('data-ce-form'))return;event.preventDefault();if(!editor||mutating)return;try{var values={};new FormData(event.target).forEach(function(value,key){values[key]=String(value);});editor.values=values;editor.intent=prepare(editor.type,values,model,editor.id);dirty=true;formPaint();}catch(error){formError(error.message);}}
    function attach(){host.onclick=click;host.oninput=input;host.onchange=input;host.onsubmit=submit;}
    var controller={deactivate:function(){alive=false;},activate:function(){if(active&&active!==controller)active.deactivate();active=controller;alive=true;attach();host.classList.add('u1-native-workspace','u1-create-earn');if(needsPaint)paint();if(!model)refresh();}};
    hosts.set(host,controller);active=controller;attach();refresh();
  }
  function activate(host){var c=host&&hosts.get(host);if(c)c.activate();}
  function deactivate(host){var c=host&&hosts.get(host);if(c)c.deactivate();}
  var api=Object.freeze({renderCreate:function(host){render(host,'create');},renderEarn:function(host){render(host,'earn');},activate:activate,deactivate:deactivate,dispose:deactivate});
  root.U1CreateEarn=api;
  if(root.U1CoreViews){root.U1CoreViews.register('create',api.renderCreate,{activate:activate,deactivate:deactivate});root.U1CoreViews.register('earn',api.renderEarn,{activate:activate,deactivate:deactivate});}
  if(typeof module!=='undefined'&&module.exports)module.exports={api:api,derive:derive,prepare:prepare,readKind:readKind,readyFile:readyFile,createController:createController,verifiedDownload:verifiedDownload,mainMarkup:mainMarkup,editorMarkup:editorMarkup,esc:esc};
})(typeof window!=='undefined'?window:globalThis);

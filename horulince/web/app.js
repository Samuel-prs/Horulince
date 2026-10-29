"use strict";
const $ = id => document.getElementById(id);
const token = document.querySelector('meta[name="horulince-token"]').content;
const labels = {monitor:"Central de testes",targets:"Alvos de teste",alerts:"Central de alertas",evaluation:"Validação experimental",audit:"Trilha de auditoria",system:"Estado do sistema",demos:"Demonstrações legadas",archive:"Acervo de capturas"};
const statusLabels = {ocioso:"PRONTO",iniciando:"PREPARANDO",executando:"EM ANDAMENTO",parando:"ENCERRANDO",concluida:"CONCLUÍDO",interrompida:"INTERROMPIDO",erro:"FALHA"};
const reviewLabels = {pendente:"Pendente",confirmado_para_analise:"Confirmado para análise",revisao_solicitada:"Revisão solicitada",descartado:"Descartado"};
const colorNames = {branco:"Branco",preto:"Preto","cinza/prata":"Cinza / prata",vermelho:"Vermelho",laranja:"Laranja",amarelo:"Amarelo",verde:"Verde",azul:"Azul","roxo/rosa":"Roxo / rosa"};
let state = null, page = "monitor", selectedAlert = null, detailVersion = "", targetVersion = "", selectedEvaluation = null, busyRequest = false, polling = false, frameBusy = false, frameURL = null, toastTimeout;
const esc = value => String(value ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const date = value => value ? new Date(value).toLocaleString("pt-BR",{day:"2-digit",month:"2-digit",hour:"2-digit",minute:"2-digit"}) : "—";
const short = value => String(value || "").slice(0,8);
const percent = value => value == null ? "A medir" : (value*100).toLocaleString("pt-BR",{maximumFractionDigits:1})+"%";
const active = () => state && ["iniciando","executando","parando"].includes(state.job.status);

async function api(path, data) {
  const options = data === undefined ? {} : {method:"POST",headers:{"Content-Type":"application/json","X-Horulince-Token":token},body:JSON.stringify(data)};
  const response = await fetch(path, options);
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || "Não foi possível concluir a operação");
  return result;
}
function toast(message, error=false) {
  clearTimeout(toastTimeout); $("toast").textContent = message; $("toast").className = "toast" + (error ? " error" : ""); $("toast").hidden = false;
  toastTimeout = setTimeout(() => $("toast").hidden = true, error ? 9000 : 5000);
}
function showPage(value) {
  page = labels[value] ? value : "monitor";
  document.querySelectorAll(".page").forEach(p => p.hidden = p.id !== "page-"+page);
  document.querySelectorAll("[data-page]").forEach(b => b.classList.toggle("active",b.dataset.page === page));
  $("breadcrumb-page").textContent = labels[page];
  history.replaceState(null,"","#"+page);
  renderCurrent();
  if (page === "system") health();
  if (page === "archive") loadArchive().catch(error => toast(error.message,true));
}
document.querySelectorAll("[data-page],[data-go]").forEach(button => button.addEventListener("click",() => showPage(button.dataset.page || button.dataset.go)));
window.addEventListener("hashchange",() => showPage(location.hash.slice(1)));

function fillVideos() {
  const signature = JSON.stringify(state.videos);
  for (const id of ["video-select","demo-video"]) {
  const select = $(id), previous = select.value;
  if (select.dataset.signature === signature) continue;
  select.innerHTML = state.videos.map(v => `<option value="${esc(v.id)}">${esc(v.name)} · ${(v.bytes/1048576).toFixed(1)} MB</option>`).join("") || '<option value="">Envie um vídeo para começar</option>';
  if (state.videos.some(v => v.id === previous)) select.value = previous;
  select.dataset.signature = signature;
  }
}
function renderMonitor() {
  if (!state) return;
  const counts = state.counts, job = state.job, p = job.progress || {};
  for (const [key,value] of Object.entries({runs:counts.runs,alerts:counts.alerts,pending:counts.pending,reviewed:counts.reviewed})) $("stat-"+key).textContent = value;
  $("nav-count").textContent = counts.pending;
  $("job-badge").textContent = statusLabels[job.status] || job.status;
  $("job-badge").className = "badge" + (active() ? " running" : job.status === "erro" ? " error" : "");
  $("job-message").textContent = job.message + (job.status === "parando" ? ". A operação de rede atual pode levar alguns segundos." : "");
  $("job-message").className = "job-message" + (job.status === "erro" ? " error" : "");
  $("feed-source").textContent = job.source || "SEM FONTE ATIVA";
  const seconds = p.instante_video ?? 0;
  $("feed-time").textContent = String(Math.floor(seconds/60)).padStart(2,"0")+":"+String(Math.floor(seconds%60)).padStart(2,"0");
  $("live-frames").textContent = p.quadros_processados ?? (job.mode === "conexao" ? p.quadros_lidos : null) ?? "—";
  $("live-ms").textContent = p.processamento_medio_ms != null ? p.processamento_medio_ms.toLocaleString("pt-BR",{maximumFractionDigits:0})+" ms" : "—";
  $("live-vehicles").textContent = p.veiculos_no_quadro ?? "—";
  renderDetections("live-results", job.mode === "analise" ? p.deteccoes : [], false);
  $("target-count").textContent = `${state.targets.length} ${state.targets.length === 1 ? "alvo configurado" : "alvos configurados"}`;
  $("start-button").disabled = active() || busyRequest;
  $("test-source").disabled = active() || busyRequest;
  $("stop-button").disabled = !active() || job.status === "parando";
  fillVideos();
  const modelSignature = JSON.stringify(state.models || []);
  if ($("vehicle-model").dataset.signature !== modelSignature) {
    const oldModel = $("vehicle-model").value, oldPlate = $("plate-model").value;
    $("vehicle-model").innerHTML = (state.models || []).map(name => `<option value="${esc(name)}">${esc(name)}</option>`).join("");
    $("plate-model").innerHTML = '<option value="">Contornos experimentais</option>' + (state.models || []).filter(name => name !== "yolov8n.pt").map(name => `<option value="${esc(name)}">${esc(name)}</option>`).join("");
    if ((state.models || []).includes(oldModel)) $("vehicle-model").value = oldModel;
    if ((state.models || []).includes(oldPlate)) $("plate-model").value = oldPlate;
    $("vehicle-model").dataset.signature = modelSignature;
  }
  $("run-table").innerHTML = state.runs.length ? `<table><thead><tr><th>EXECUÇÃO / ORIGEM</th><th>QUADROS</th><th>ALERTAS</th><th>ESTADO</th><th></th></tr></thead><tbody>${state.runs.slice(0,7).map(r => `<tr><td><code>${esc(short(r.id))}</code><br><small>${esc(r.summary.origem)}</small></td><td>${esc(r.summary.quadros_processados ?? "—")}</td><td>${esc(r.summary.alertas ?? "—")}</td><td><span class="badge ${r.summary.estado_execucao === "erro" ? "error" : ""}">${esc(r.summary.estado_execucao || "concluida")}</span></td><td><button class="text-button" data-evaluate-run="${esc(r.id)}">Avaliar ↗</button></td></tr>`).join("")}</tbody></table>` : '<div class="empty-state">Nenhuma execução registrada.<br>Inicie uma análise para construir seu histórico.</div>';
}
function renderTargets() {
  const signature = JSON.stringify(state.targets);
  if (targetVersion === signature) return;
  targetVersion = signature;
  $("targets-list").innerHTML = state.targets.map((t,i) => `<div class="target-row"><div><strong>${esc(t.id)}</strong><p>${esc(t.tipo)} · ${esc(colorNames[t.cor] || t.cor)} · ${esc(t.placa || "Por características")}</p></div><button data-remove-target="${i}" aria-label="Remover ${esc(t.id)}">Remover</button></div>`).join("");
}
function renderAlerts() {
  const filtered = state.alerts.filter(a => !$("alert-filter").value || a.state === $("alert-filter").value);
  const listVersion = JSON.stringify([selectedAlert,filtered.map(a => [a.id,a.state])]);
  if ($("alerts-list").dataset.version !== listVersion) {
  $("alerts-list").innerHTML = filtered.map(a => `<button class="alert-item ${selectedAlert === a.id ? "selected" : ""}" data-alert="${esc(a.id)}"><h3><span>${esc(a.payload.placa || a.payload.tipo || "Veículo")}</span><span class="badge">${esc(a.payload.correspondencia || "candidato")}</span></h3><p>${esc(a.source)} · ${Number(a.video_seconds).toFixed(2)}s</p><p>${esc(reviewLabels[a.state])} · ${esc(date(a.created_at))}</p></button>`).join("") || '<div class="empty-state">Nenhum alerta neste filtro.<br>Os candidatos surgirão após uma análise.</div>';
  $("alerts-list").dataset.version = listVersion;
  }
  const alert = state.alerts.find(a => a.id === selectedAlert);
  if (!alert) { if (selectedAlert) {selectedAlert = null; detailVersion = "";} return; }
  const version = alert.id+alert.state;
  if (detailVersion === version) return;
  detailVersion = version;
  const payload = alert.payload;
  $("alert-detail").innerHTML = `<div class="card-title-row"><h2>Evidência do candidato</h2><span class="badge">${esc(reviewLabels[alert.state])}</span></div><img class="evidence-image" src="/api/evidence/${encodeURIComponent(alert.id)}" alt="Recorte do veículo candidato"><div class="data-grid">${[["Placa observada",payload.placa || "Sem leitura consolidada"],["Correspondência",payload.correspondencia],["Origem / instante",alert.source+" / "+Number(alert.video_seconds).toFixed(2)+"s"],["Caso / execução",alert.target+" / "+short(alert.run)],["Confiança da detecção",payload.confianca_deteccao != null ? percent(payload.confianca_deteccao) : "—"],["Compatibilidade de características",payload.compatibilidade_caracteristicas ?? "—"],["Confiança média do OCR",payload.consolidacao?.confianca_ocr_media ?? "Sem consenso"],["Leituras consistentes",payload.consolidacao?.leituras ?? "—"]].map(([k,v]) => `<div><small>${esc(k)}</small><strong>${esc(v)}</strong></div>`).join("")}</div><form id="review-form" class="review-form"><h2>Registrar decisão humana</h2><div class="form-pair"><label>Operador<input id="review-actor" required placeholder="Seu nome" maxlength="100"></label><label>Decisão<select id="review-state"><option value="revisao_solicitada">Solicitar revisão</option><option value="confirmado_para_analise">Confirmar para análise</option><option value="descartado">Descartar</option></select></label></div><label>Justificativa<textarea id="review-reason" rows="3" required placeholder="Descreva o que a evidência permite concluir"></textarea></label><button class="button primary" type="submit">Salvar decisão</button><p class="field-note">A confirmação registra apenas a decisão neste laboratório. Os valores do algoritmo não são probabilidade de identidade.</p></form>`;
  $("review-actor").value = localStorage.getItem("horulince-operator") || "";
  $("review-form").addEventListener("submit", async event => {event.preventDefault();try {await api("/api/review",{id:alert.id,actor:$("review-actor").value,reason:$("review-reason").value,state:$("review-state").value});localStorage.setItem("horulince-operator",$("review-actor").value);toast("Decisão registrada na auditoria");await refresh();} catch(error){toast(error.message,true);}});
}
function evaluationContext() {
  const run = state?.runs.find(r => r.id === $("evaluation-run").value);
  $("evaluation-context").textContent = run ? `Origem: ${run.summary.origem} · ${run.summary.quadros_processados ?? 0} quadros analisados · ${run.summary.alertas ?? 0} alertas. Use esta origem nas anotações.` : "Conclua uma análise para disponibilizar uma execução.";
  $("export-report").disabled = !run;
  const result = selectedEvaluation?.execucao === run?.id ? selectedEvaluation : run?.evaluation;
  if (result) renderEvaluationResult(result);
  else $("evaluation-results").innerHTML = '<div class="empty-state">Informe as ocorrências anotadas e calcule os resultados.<br>O desempenho ainda está a medir.</div>';
}
function renderEvaluation() {
  const select = $("evaluation-run"), current = select.value;
  const options = state.runs.filter(r => r.summary.estado_execucao !== "erro");
  const signature = options.map(r => r.id).join(",");
  if (select.dataset.signature !== signature) {
    select.innerHTML = options.map(r => `<option value="${esc(r.id)}">${esc(short(r.id))} · ${esc(r.summary.origem)}</option>`).join("") || '<option value="">Nenhuma execução disponível</option>';
    if (options.some(r => r.id === current)) select.value = current;
    select.dataset.signature = signature;
  }
  evaluationContext();
}
function renderEvaluationResult(result) {
  const metrics = [[percent(result.precisao_eventos),"Precisão de eventos"],[percent(result.revocacao_eventos),"Revocação de eventos"],[result.verdadeiros_positivos,"Verdadeiros positivos"],[result.falsos_positivos,"Falsos positivos"],[result.falsos_negativos,"Falsos negativos"],[percent(result.acerto_placa_completa_em_eventos_pareados),"Placa completa · eventos pareados"]];
  $("evaluation-results").innerHTML = `<div class="metrics-grid">${metrics.map(([v,l]) => `<div class="metric"><strong>${esc(v)}</strong><small>${esc(l)}</small></div>`).join("")}</div><p class="result-note">${esc(result.nota)}</p><p class="result-note">${result.ocorrencias_referencia} ocorrências anotadas · ${result.alertas} alertas · ${result.placas_avaliadas_em_eventos_pareados} placas avaliadas</p>`;
}
function renderAudit() {
  $("audit-table").innerHTML = state.audit.length ? `<table><thead><tr><th>DATA / HORA</th><th>OPERADOR</th><th>AÇÃO</th><th>ALERTA</th><th>JUSTIFICATIVA</th></tr></thead><tbody>${state.audit.map(a => `<tr><td>${esc(date(a.at))}</td><td>${esc(a.actor)}</td><td>${esc(reviewLabels[a.action] || a.action)}</td><td><code>${esc(short(a.alert_id))}</code></td><td style="white-space:normal;min-width:230px">${esc(a.reason)}</td></tr>`).join("")}</tbody></table>` : '<div class="empty-state">Os registros aparecerão quando um alerta for criado ou revisado.</div>';
}
function renderCurrent() {if (!state) return;renderMonitor();renderDemo();if (page === "targets") renderTargets();if (page === "alerts") renderAlerts();if (page === "evaluation") renderEvaluation();if (page === "audit") renderAudit();if(page === "archive") loadArchive().catch(error=>toast(error.message,true));}
async function refresh() {
  if (polling) return;
  polling = true;
  try { state = await api("/api/state");$("connection").className="connection online";$("connection").innerHTML="<i></i> Servidor local conectado";renderCurrent(); }
  catch(error) {$("connection").className="connection";$("connection").textContent="Servidor indisponível";}
  finally {polling=false;}
}
async function refreshFrame() {
  if (frameBusy || !["monitor","demos"].includes(page) || !state || state.job.status === "ocioso") return;
  const demo = page === "demos", imageId = demo ? "demo-frame" : "live-frame", emptyId = demo ? "demo-empty" : "video-empty";
  if (demo !== state.job.mode?.startsWith("demo_")) {$(imageId).hidden=true;$(emptyId).hidden=false;return;}
  frameBusy = true;
  try {
    const response = await fetch("/api/frame.jpg");
    if (response.status === 204) {$(imageId).hidden = true;$(emptyId).hidden = false;return;}
    if (!response.ok) return;
    const next = URL.createObjectURL(await response.blob());
    $(imageId).src=next;$(imageId).hidden=false;$(emptyId).hidden=true;
    if (frameURL) URL.revokeObjectURL(frameURL);
    frameURL=next;
  } finally {frameBusy=false;}
}
function config() {return {source_type:$("source-type").value,video:$("video-select").value,url:$("stream-url").value,camera:$("camera-index").value,origin:$("source-origin").value,no_ocr:!$("ocr-enabled").checked,every:$("every").value,ocr_every:$("ocr-every").value,max_frames:$("max-frames").value,image_size:$("image-size").value,threshold:$("threshold").value,model:$("vehicle-model").value,plate_model:$("plate-model").value};}
async function start(testOnly) {
  busyRequest = true;renderMonitor();
  try {await api(testOnly ? "/api/test-source" : "/api/start",config());toast(testOnly ? "Teste de imagem iniciado" : "Análise iniciada");await refresh();}
  catch(error){toast(error.message,true);}
  finally {busyRequest=false;renderMonitor();}
}
$("analysis-form").addEventListener("submit",event => {event.preventDefault();start(false);});
$("test-source").addEventListener("click",() => start(true));
$("stop-button").addEventListener("click",async () => {try {await api("/api/stop",{});await refresh();}catch(error){toast(error.message,true);}});
$("source-type").addEventListener("change",() => {const mode=$("source-type").value;for(const value of ["video","iphone","webcam"]) $(value+"-fields").hidden=mode!==value;$("video-select").required=mode==="video";$("stream-url").required=mode==="iphone";$("every").value=mode==="iphone"?1:3;});
$("video-upload").addEventListener("change",async event => {
  const file=event.target.files[0];if(!file)return;if(file.size>250*1024*1024){toast("O vídeo deve ter até 250 MB",true);return;}
  $("upload-note").textContent="Enviando vídeo…";
  try {const response=await fetch("/api/upload?name="+encodeURIComponent(file.name),{method:"POST",headers:{"X-Horulince-Token":token},body:file});const result=await response.json();if(!response.ok)throw new Error(result.error);await refresh();$("video-select").value=result.id;$("upload-note").textContent=file.name+" enviado";toast("Vídeo disponível para análise");}catch(error){toast(error.message,true);$("upload-note").textContent="Falha no envio";}finally{event.target.value="";}
});
$("target-color").innerHTML=Object.entries(colorNames).map(([value,label])=>`<option value="${value}">${label}</option>`).join("");
$("target-form").addEventListener("submit",async event=>{event.preventDefault();try{await api("/api/targets",{targets:[...state.targets,{id:$("target-id").value.trim(),tipo:$("target-type").value,cor:$("target-color").value,placa:$("target-plate").value}]});$("target-form").reset();await refresh();toast("Alvo salvo para a próxima análise");}catch(error){toast(error.message,true);}});
$("targets-list").addEventListener("click",async event=>{const b=event.target.closest("[data-remove-target]");if(!b)return;try{await api("/api/targets",{targets:state.targets.filter((_,i)=>i!==Number(b.dataset.removeTarget))});await refresh();}catch(error){toast(error.message,true);}});
$("load-example").addEventListener("click",async()=>{try{await api("/api/targets",{targets:[{id:"caso_ficticio_01",tipo:"carro",cor:"branco",placa:"ABC1D23"},{id:"caso_ficticio_02",tipo:"moto",cor:"preto",placa:"XYZ1234"}]});await refresh();toast("Exemplos fictícios carregados; habilite OCR para usá-los");}catch(error){toast(error.message,true);}});
$("alert-filter").addEventListener("change",renderAlerts);
$("alerts-list").addEventListener("click",event=>{const b=event.target.closest("[data-alert]");if(b){selectedAlert=b.dataset.alert;detailVersion="";renderAlerts();}});
document.addEventListener("click",event=>{const b=event.target.closest("[data-evaluate-run]");if(b){showPage("evaluation");$("evaluation-run").value=b.dataset.evaluateRun;evaluationContext();}});
$("evaluation-run").addEventListener("change",evaluationContext);
$("reference-example").addEventListener("click",()=>{const run=state?.runs.find(r=>r.id===$("evaluation-run").value);if(!run){toast("Selecione uma execução",true);return;}$("reference-json").value=JSON.stringify([{id:"passagem_01",alvo_id:run.configuration.alvos?.[0]?.id || "alvo_teste_01",origem:run.summary.origem,inicio:0,fim:1}],null,2);toast("Estrutura sugerida: substitua os tempos pelas ocorrências reais anotadas");});
$("reference-upload").addEventListener("change",async event=>{const file=event.target.files[0];if(!file)return;try{const content=await file.text();JSON.parse(content);$("reference-json").value=content;toast("Referência importada");}catch(error){toast("O arquivo não contém JSON válido",true);}finally{event.target.value="";}});
$("evaluation-form").addEventListener("submit",async event=>{event.preventDefault();try{let reference;try{reference=JSON.parse($("reference-json").value);}catch(error){throw new Error("Revise o JSON das ocorrências anotadas");}selectedEvaluation=await api("/api/evaluate",{run:$("evaluation-run").value,reference});renderEvaluationResult(selectedEvaluation);toast("Avaliação calculada e salva");await refresh();}catch(error){toast(error.message,true);}});
function download(name,data){const url=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{type:"application/json"}));const a=document.createElement("a");a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
$("export-report").addEventListener("click",async()=>{try{const id=$("evaluation-run").value;download("horulince-"+short(id)+".json",await api("/api/report/"+encodeURIComponent(id)));}catch(error){toast(error.message,true);}});
$("export-audit").addEventListener("click",async()=>{try{download("horulince-auditoria.json",await api("/api/audit"));}catch(error){toast(error.message,true);}});
async function health(){try{const result=await api("/api/health");$("health-grid").innerHTML=[...Object.entries(result.dependencies).map(([name,version])=>({name,ok:!!version,note:version?"Versão "+version:"Dependência não instalada"})),{name:"Modelo de veículos",ok:result.model,note:result.model?"YOLOv8n disponível localmente":"models/yolov8n.pt não encontrado"},{name:"Tesseract OCR",ok:result.tesseract,note:result.tesseract?"Executável encontrado":"Instale ou configure TESSERACT_CMD"}].map(c=>`<article class="card health-card"><span class="badge ${c.ok?"":"error"}">${c.ok?"DISPONÍVEL":"VERIFICAR"}</span><h3>${esc(c.name)}</h3><p>${esc(c.note)}</p></article>`).join("");}catch(error){toast(error.message,true);}}
$("refresh-health").addEventListener("click",health);
function renderDetections(id, results, facial) {
  const items = results || [];
  $(id).innerHTML = items.length ? items.map((r,i)=>`<div class="detection-row"><strong>${facial ? "Rosto "+(i+1)+" neste quadro" : esc(r.tipo || "Veículo")}</strong><span>${facial ? "Posição: "+esc(r.box?.join(", ")) : esc(r.placa || "Sem leitura de placa")+" · "+esc(r.cores?.[0]?.[0] || "Cor não definida")+" · detecção "+percent(r.confianca_deteccao)}</span><small>${facial ? "Identidade não analisada · emoções não suportadas" : esc(r.correspondencias?.join(", ") || "Detecção observada")}</small></div>`).join("") : '<p class="field-note">Nenhuma detecção no último quadro analisado.</p>';
}
function renderDemo() {
  const job=state.job, own=job.mode?.startsWith("demo_"), p=own ? job.progress || {} : {};
  $("demo-badge").textContent=own ? statusLabels[job.status] : "PRONTO";
  $("demo-message").textContent=own ? [job.message,p.captura_status].filter(Boolean).join(" · ") : active() ? "Outra análise está em andamento. Pare-a para iniciar uma demonstração." : "Pronto para demonstrar";
  $("demo-detections").textContent=p.rostos_no_quadro ?? p.veiculos_no_quadro ?? "—";
  $("demo-frames").textContent=(p.quadros_processados ?? "—")+" / "+(p.fps_processamento ?? "—")+" fps";
  $("demo-saved").textContent=p.imagens_salvas ?? 0;
  $("demo-latency").textContent=p.processamento_medio_ms != null ? p.processamento_medio_ms+" ms / quadro" : "";
  $("demo-start").disabled=active() || busyRequest;
  $("demo-stop").disabled=!active() || job.status === "parando";
  $("demo-capture").disabled=job.mode !== "demo_facial" || job.status !== "executando";
  renderDetections("demo-results",p.deteccoes,job.mode === "demo_facial");
  const runs=state.demo_runs || [], signature=JSON.stringify(runs);
  if($("demo-history").dataset.signature !== signature) {
    $("demo-history").innerHTML=runs.length ? `<table><thead><tr><th>INÍCIO / ORIGEM</th><th>CAPACIDADE</th><th>QUADROS / IMAGENS</th><th>ESTADO</th><th></th></tr></thead><tbody>${runs.map(r=>`<tr><td>${esc(date(r.started_at))}<br>${esc(r.source)}</td><td>${r.mode === "facial" ? "Detecção facial" : "Extração de veículos"}</td><td>${r.summary.quadros_processados ?? "—"} / ${r.summary.imagens_salvas ?? "—"}</td><td>${esc(r.state)}</td><td><button class="text-button" data-archive-run="${esc(r.id)}">Consultar ↗</button> <button class="text-button" data-demo-report="${esc(r.id)}">↓ Relatório</button></td></tr>`).join("")}</tbody></table>` : '<div class="empty-state">Nenhuma demonstração registrada.</div>';
    $("demo-history").dataset.signature=signature;
  }
}
$("demo-mode").addEventListener("change",()=>{const facial=$("demo-mode").value === "facial";$("demo-authorization").hidden=!facial;$("demo-authorized").required=facial;$("demo-capability").textContent=facial ? "Detector frontal Haar Cascade, como no legado. Mostra caixas e quantidade de rostos. Identidade e emoções não são analisadas." : "Detecção YOLO e cores heurísticas, com recortes periódicos como no legado. Use a Central de testes para OCR e comparação de alvos.";});
$("demo-mode").dispatchEvent(new Event("change"));
$("demo-source").addEventListener("change",()=>{for(const type of ["video","iphone","webcam"]) $("demo-"+type+"-fields").hidden=$("demo-source").value !== type;});
$("demo-form").addEventListener("submit",async event=>{event.preventDefault();busyRequest=true;renderDemo();try{await api("/api/demo/start",{mode:$("demo-mode").value,source_type:$("demo-source").value,video:$("demo-video").value,url:$("demo-url").value,camera:$("demo-camera").value,origin:$("demo-origin").value,max_frames:$("demo-max").value,every:$("demo-every").value,authorized:$("demo-authorized").checked});await refresh();toast("Demonstração iniciada");}catch(error){toast(error.message,true);}finally{busyRequest=false;renderDemo();}});
$("demo-stop").addEventListener("click",async()=>{try{await api("/api/stop",{});await refresh();}catch(error){toast(error.message,true);}});
$("demo-capture").addEventListener("click",async()=>{try{const result=await api("/api/demo/capture",{});toast(result.message);}catch(error){toast(error.message,true);}});

const kindLabels={alerta_veiculo:"Alerta de veículo",deteccao_veiculo:"Extração de veículo",deteccao_facial:"Detecção facial",captura_facial:"Captura facial",revisao_alerta:"Evento de auditoria"};
let archiveOffset=0, archiveResult=null, archiveBusy=false, archiveSelected=null, archiveVersion="", archiveDetailVersion="", archiveFocus=false;
function archiveParams(offset=archiveOffset,limit=30) {
  const params=new URLSearchParams({offset,limit});
  for(const key of ["kind","source","run","since","until","q"]) {const v=$("archive-"+key).value;if(v)params.set(key,v);}
  if($("archive-images").checked)params.set("images","1");
  return params;
}
async function loadArchive() {
  if(archiveBusy)return;
  archiveBusy=true;
  const query=archiveParams().toString();
  try {
    const result=await api("/api/captures?"+query);
    if(query !== archiveParams().toString())return;
    archiveResult=result;
    $("archive-total").textContent=`${result.total} registros · ${result.total ? result.offset+1 : 0}–${Math.min(result.offset+result.limit,result.total)}`;
    $("archive-prev").disabled=!result.offset;$("archive-next").disabled=result.offset+result.limit>=result.total;
    const version=JSON.stringify([result,archiveSelected]);
    if(version !== archiveVersion) {
      archiveVersion=version;
      $("archive-list").innerHTML=result.items.map(item=>`<button class="card capture-tile ${item.id === archiveSelected ? "selected" : ""}" data-capture="${esc(item.id)}">${item.has_image ? `<img src="/api/capture-image/${esc(item.id)}" alt="Imagem capturada pela análise" loading="lazy">` : '<div class="capture-placeholder">≡<small>Registro de processamento</small></div>'}<div><strong>${esc(kindLabels[item.kind])}</strong><p>${esc(item.source)} · ${Number(item.video_seconds).toFixed(2)}s</p><small>${esc(date(item.created_at))} · ${esc(short(item.run))}</small></div></button>`).join("") || '<div class="card empty-state">Nenhum registro encontrado para estes filtros.</div>';
    }
    const item=result.items.find(i=>i.id===archiveSelected);
    if(item && archiveDetailVersion !== JSON.stringify(item)) {
      archiveDetailVersion=JSON.stringify(item);
      $("archive-detail").innerHTML=`<h2>${esc(kindLabels[item.kind])}</h2>${item.has_image ? `<img class="evidence-image" src="/api/capture-image/${esc(item.id)}" alt="Imagem do registro selecionado"><a class="button" href="/api/capture-image/${esc(item.id)}" download="horulince-${esc(item.id.replace(":","-"))}.jpg">↓ Baixar imagem</a>` : '<p class="field-note">Este evento contém dados, sem imagem armazenada.</p>'}<dl class="archive-metadata"><dt>Execução</dt><dd>${esc(item.run)}</dd><dt>Origem</dt><dd>${esc(item.source)}</dd><dt>Instante / estado</dt><dd>${Number(item.video_seconds).toFixed(2)}s · ${esc(reviewLabels[item.category] || item.category)}</dd></dl><h3>Dados completos</h3><pre class="json-record">${esc(JSON.stringify(item.payload,null,2))}</pre>`;
    } else if(!item && archiveDetailVersion) {
      archiveDetailVersion="";$("archive-detail").innerHTML='<div class="empty-state">Selecione um registro desta página.</div>';
    }
    if(item && archiveFocus){archiveFocus=false;if(window.innerWidth<=1100)$("archive-detail").scrollIntoView({behavior:"smooth",block:"start"});}
  } finally {archiveBusy=false;}
}
$("archive-form").addEventListener("submit",event=>{event.preventDefault();archiveOffset=0;loadArchive().catch(error=>toast(error.message,true));});
$("archive-clear").addEventListener("click",()=>{$("archive-form").reset();archiveOffset=0;loadArchive().catch(error=>toast(error.message,true));});
$("archive-prev").addEventListener("click",()=>{archiveOffset=Math.max(0,archiveOffset-30);loadArchive().catch(error=>toast(error.message,true));});
$("archive-next").addEventListener("click",()=>{archiveOffset+=30;loadArchive().catch(error=>toast(error.message,true));});
$("archive-list").addEventListener("click",event=>{const button=event.target.closest("[data-capture]");if(button){archiveSelected=button.dataset.capture;archiveFocus=true;loadArchive().catch(error=>toast(error.message,true));}});
document.addEventListener("click",event=>{const button=event.target.closest("[data-demo-report]");if(button){const run=state.demo_runs.find(r=>r.id===button.dataset.demoReport);if(run)download("horulince-demo-"+short(run.id)+".json",run);}});
document.addEventListener("click",event=>{const button=event.target.closest("[data-archive-run]");if(button){$("archive-form").reset();$("archive-run").value=button.dataset.archiveRun;archiveOffset=0;showPage("archive");}});
$("archive-export").addEventListener("click",async()=>{const button=$("archive-export");button.disabled=true;try{const params=archiveParams(0,200),result=await api("/api/captures-export?"+params);download("horulince-acervo.json",{exportado_em:new Date().toISOString(),filtros:Object.fromEntries(params),total:result.total,registros:result.items});toast("Consulta exportada com metadados; baixe as imagens no detalhe de cada registro");}catch(error){toast(error.message,true);}finally{button.disabled=false;}});
function clock(){$("clock").textContent=new Date().toLocaleDateString("pt-BR",{day:"2-digit",month:"short"})+" · "+new Date().toLocaleTimeString("pt-BR",{hour:"2-digit",minute:"2-digit"});}
clock();showPage(location.hash.slice(1));refresh();setInterval(refresh,1500);setInterval(()=>refreshFrame().catch(()=>{}),650);setInterval(clock,30000);

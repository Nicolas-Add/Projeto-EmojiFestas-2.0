const API = "";
const state = { halls: [], combos: [], extras: [], clients: [], bookings: [], payments: [], calendarDate: new Date() };
const $ = (id) => document.getElementById(id);
const money = (value) => Number(value || 0).toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
const dateBR = (value) => value ? new Date(`${value}T12:00:00`).toLocaleDateString("pt-BR") : "—";
const initials = (name="") => name.split(/\s+/).filter(Boolean).slice(0,2).map(p=>p[0]).join("").toUpperCase();

// Aceita valores como 125.50, 125,50 e 1.250,50.
function parseMoneyInput(value) {
  let text = String(value ?? "").trim().replace(/\s/g, "").replace(/R\$/gi, "");
  if (!text) return NaN;

  // Quando ponto e vírgula aparecem juntos, o último separador é o decimal.
  if (text.includes(".") && text.includes(",")) {
    if (text.lastIndexOf(",") > text.lastIndexOf(".")) {
      text = text.replace(/\./g, "").replace(",", ".");
    } else {
      text = text.replace(/,/g, "");
    }
  } else if (text.includes(",")) {
    text = text.replace(",", ".");
  }

  if (!/^\d+(\.\d{1,2})?$/.test(text)) return NaN;
  return Number(text);
}

async function api(path, options={}) {
  let response;
  try {
    response = await fetch(`${API}/api${path}`, {
      ...options,
      headers: { "Content-Type": "application/json", ...(options.headers || {}) }
    });
  } catch (erro) {
    throw new Error("Não foi possível conectar ao servidor. Inicie a aplicação com: python web_app.py");
  }

  const texto = await response.text();
  let data = {};
  try {
    data = texto ? JSON.parse(texto) : {};
  } catch (_) {
    data = { error: texto || `O servidor respondeu sem detalhes (HTTP ${response.status}).` };
  }

  if (!response.ok) {
    throw new Error(data.error || data.message || `Erro HTTP ${response.status}. Consulte o terminal do Flask.`);
  }
  return data;
}
function toast(message, error=false) {
  const el=$("toast"); el.textContent=message; el.classList.toggle("error",error); el.classList.add("show");
  clearTimeout(toast.timer); toast.timer=setTimeout(()=>el.classList.remove("show"),3200);
}
function goTo(page) {
  document.querySelectorAll(".page-section").forEach(el=>el.classList.toggle("active",el.id===`page-${page}`));
  document.querySelectorAll(".nav-link").forEach(el=>el.classList.toggle("active",el.dataset.page===page));
  const active=document.querySelector(`.nav-link[data-page="${page}"]`);
  $("breadcrumbCurrent").textContent=active ? active.textContent.trim() : page;
  $("sidebar").classList.remove("open");
  if(page==="agendamentos") renderBookings();
  if(page==="clientes") renderClients();
  if(page==="saloes") renderCatalog();
  if(page==="pagamentos") renderPayments();
  if(page==="relatorios") renderReports();
}
document.querySelectorAll("[data-page]").forEach(el=>el.addEventListener("click",()=>goTo(el.dataset.page)));
document.querySelectorAll("[data-goto]").forEach(el=>el.addEventListener("click",()=>goTo(el.dataset.goto)));
$("mobileMenu").addEventListener("click",()=>$("sidebar").classList.toggle("open"));
$("refreshButton").addEventListener("click",loadAll);
$("todayLabel").textContent=new Date().toLocaleDateString("pt-BR",{weekday:"long",day:"2-digit",month:"long",year:"numeric"});

async function loadAll() {
  try {
    const [dashboard,halls,combos,extras,clients,bookings,payments] = await Promise.all([
      api("/dashboard"),api("/saloes"),api("/combos"),api("/extras"),api("/clientes"),api("/festas"),api("/pagamentos")
    ]);
    state.halls=halls; state.combos=combos; state.extras=extras; state.clients=clients; state.bookings=bookings; state.payments=payments;
    renderDashboard(dashboard); renderBookings(); renderClients(); renderCatalog(); renderPayments(); renderReports(); renderCalendar();
  } catch(error) { toast(error.message,true); console.error(error); }
}
function renderDashboard(data) {
  $("statBookings").textContent=data.total_festas ?? state.bookings.length;
  $("statClients").textContent=data.total_clientes ?? state.clients.length;
  $("statRevenue").textContent=money(data.valor_contratado ?? state.bookings.reduce((s,b)=>s+Number(b.total||0),0));
  $("statHalls").textContent=state.halls.length;
  const upcoming=[...state.bookings].sort((a,b)=>`${a.data} ${a.inicio}`.localeCompare(`${b.data} ${b.inicio}`)).slice(0,5);
  $("dashboardAgenda").innerHTML=upcoming.length ? upcoming.map(b=>`<div class="agenda-item"><div class="agenda-time">${escapeHTML((b.inicio||"").slice(0,5))}</div><div class="agenda-marker"></div><div class="agenda-info"><strong>${escapeHTML(b.titulo||"Festa")}</strong><small>${escapeHTML(b.cliente_nome||"Cliente")} · ${dateBR(b.data)}</small></div><span class="agenda-hall">${escapeHTML(b.salao_nome||"Salão")}</span></div>`).join("") : `<div class="empty-state">Nenhum agendamento cadastrado ainda.</div>`;
  $("dashboardHalls").innerHTML=state.halls.map(h=>hallCard(h)).join("") || `<div class="empty-state">Nenhum salão cadastrado.</div>`;
}
function hallCard(h){return `<div class="hall-card"><div class="hall-symbol">⌂</div><div><strong>${escapeHTML(h.nome)}</strong><small>Capacidade: ${h.capacidade} pessoas · Acréscimo: ${money(h.acrescimo)}</small></div></div>`;}
function renderBookings(filter="") {
  const q=filter.toLocaleLowerCase("pt-BR");
  const rows=state.bookings.filter(b=>`${b.cliente_nome} ${b.salao_nome} ${b.titulo}`.toLocaleLowerCase("pt-BR").includes(q));
  $("bookingsTable").innerHTML=rows.length?rows.map(b=>`<tr><td><strong>${escapeHTML(b.titulo||"Festa")}</strong><span class="sub-cell">#${b.id}</span></td><td>${person(b.cliente_nome)}</td><td>${escapeHTML(b.salao_nome||"—")}</td><td>${dateBR(b.data)}<span class="sub-cell">${escapeHTML((b.inicio||"").slice(0,5))}</span></td><td><strong>${money(b.total)}</strong></td><td><span class="status agendado">Agendado</span></td></tr>`).join(""):`<tr><td colspan="6" class="empty-state">Nenhum agendamento encontrado.</td></tr>`;
}
function renderClients(filter="") {
  const q=filter.toLocaleLowerCase("pt-BR");
  const rows=state.clients.filter(c=>`${c.nome} ${c.contato} ${c.documento}`.toLocaleLowerCase("pt-BR").includes(q));
  $("clientsTable").innerHTML=rows.length?rows.map(c=>`<tr><td>${person(c.nome)}</td><td>${escapeHTML(c.contato||"—")}</td><td>${escapeHTML(c.documento||"—")}</td><td>#${c.id}</td></tr>`).join(""):`<tr><td colspan="4" class="empty-state">Nenhum cliente encontrado.</td></tr>`;
}
function person(name){return `<div class="person-cell"><span class="person-dot">${escapeHTML(initials(name))}</span><strong>${escapeHTML(name||"—")}</strong></div>`;}
function renderCatalog() {
  $("hallsGrid").innerHTML=state.halls.map(h=>hallCard(h)).join("")||`<div class="empty-state">Nenhum salão cadastrado.</div>`;
  $("combosList").innerHTML=state.combos.map(c=>`<div class="catalog-item"><div><strong>${escapeHTML(c.nome)}</strong><small>${escapeHTML(c.descricao||"Pacote de serviços")}</small></div><span class="catalog-price">${money(c.preco)}</span></div>`).join("")||`<div class="empty-state">Nenhum combo cadastrado.</div>`;
  $("extrasList").innerHTML=state.extras.map(e=>`<div class="catalog-item"><div><strong>${escapeHTML(e.nome)}</strong><small>Serviço adicional</small></div><span class="catalog-price">${money(e.preco)}</span></div>`).join("")||`<div class="empty-state">Nenhum extra cadastrado.</div>`;
}
function renderPayments() {
  const total=state.bookings.reduce((s,b)=>s+Number(b.total||0),0);
  const received=state.payments.reduce((s,p)=>s+Number(p.valor||0),0);
  $("payTotal").textContent=money(total); $("payReceived").textContent=money(received); $("payPending").textContent=money(Math.max(0,total-received));
  const rows=state.bookings.map(b=>{
    const paid=state.payments.filter(p=>Number(p.festa_id)===Number(b.id)).reduce((s,p)=>s+Number(p.valor||0),0);
    const rest=Math.max(0,Number(b.total)-paid); const status=rest<=0?"Quitado":paid>0?"Pago":"Pendente";
    return {b,paid,rest,status};
  });
  $("paymentsTable").innerHTML=rows.length?rows.map(({b,paid,rest,status})=>`<tr><td>${person(b.cliente_nome)}</td><td>${escapeHTML(b.titulo||"Festa")}<span class="sub-cell">${dateBR(b.data)}</span></td><td>${money(b.total)}</td><td>${money(paid)}</td><td>${money(rest)}</td><td><span class="status ${status.toLowerCase()}">${status}</span></td></tr>`).join(""):`<tr><td colspan="6" class="empty-state">Nenhum evento para exibir.</td></tr>`;
}
function renderReports() {
  $("reportBookings").textContent=state.bookings.length; $("reportClients").textContent=state.clients.length;
  $("reportRevenue").textContent=money(state.bookings.reduce((s,b)=>s+Number(b.total||0),0)); $("reportExtras").textContent=state.extras.length;
  const counts=state.halls.map(h=>({name:h.nome,count:state.bookings.filter(b=>Number(b.salao_id)===Number(h.id)).length}));
  const max=Math.max(1,...counts.map(x=>x.count));
  $("reportHallRows").innerHTML=counts.map(x=>`<div class="report-row"><span>${escapeHTML(x.name)}</span><div class="bar-track"><div class="bar-fill" style="width:${x.count/max*100}%"></div></div><strong>${x.count}</strong></div>`).join("")||`<div class="empty-state">Sem dados para exibir.</div>`;
}
function renderCalendar() {
  const d=state.calendarDate, year=d.getFullYear(), month=d.getMonth();
  $("calendarMonth").textContent=d.toLocaleDateString("pt-BR",{month:"long",year:"numeric"});
  const first=new Date(year,month,1), start=first.getDay(), days=new Date(year,month+1,0).getDate(), prevDays=new Date(year,month,0).getDate();
  const today=new Date(); let html="";
  for(let i=0;i<42;i++){
    let day, date, muted=false;
    if(i<start){day=prevDays-start+i+1;date=new Date(year,month-1,day);muted=true;}
    else if(i>=start+days){day=i-start-days+1;date=new Date(year,month+1,day);muted=true;}
    else{day=i-start+1;date=new Date(year,month,day);}
    const iso=`${date.getFullYear()}-${String(date.getMonth()+1).padStart(2,"0")}-${String(date.getDate()).padStart(2,"0")}`;
    const isToday=date.toDateString()===today.toDateString();
    const has=state.bookings.some(b=>b.data===iso);
    html+=`<button class="calendar-day ${muted?"muted-day":""} ${isToday?"today":""} ${has?"has-event":""}" title="${has?"Há evento nesta data":""}">${day}</button>`;
  }
  $("calendarDays").innerHTML=html;
}
$("prevMonth").addEventListener("click",()=>{state.calendarDate.setMonth(state.calendarDate.getMonth()-1);renderCalendar();});
$("nextMonth").addEventListener("click",()=>{state.calendarDate.setMonth(state.calendarDate.getMonth()+1);renderCalendar();});
$("bookingSearch").addEventListener("input",e=>renderBookings(e.target.value));
$("clientSearch").addEventListener("input",e=>renderClients(e.target.value));

function escapeHTML(value){return String(value??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));}
function openModal(title,html,onSubmit) {
  $("modalTitle").textContent=title; $("modalBody").innerHTML=html; $("modalBackdrop").classList.add("open");
  const form=$("modalBody").querySelector("form");
  if(form)form.addEventListener("submit",async e=>{e.preventDefault();const submit=form.querySelector('[type="submit"]');if(submit)submit.disabled=true;try{await onSubmit(new FormData(form));$("modalBackdrop").classList.remove("open");}catch(err){toast(err.message,true);}finally{if(submit)submit.disabled=false;}});
}
function closeModal(){$("modalBackdrop").classList.remove("open");}
$("closeModal").addEventListener("click",closeModal);
$("modalBackdrop").addEventListener("click",e=>{if(e.target===$("modalBackdrop"))closeModal();});
document.addEventListener("keydown",e=>{if(e.key==="Escape")closeModal();});

$("newClientButton").addEventListener("click",()=>openModal("Cadastrar cliente",`
<form><div class="form-grid">
<div class="form-field full"><label>Nome completo</label><input class="form-control" name="nome" required maxlength="100" placeholder="Nome do cliente"></div>
<div class="form-field"><label>Contato / telefone</label><input class="form-control" name="contato" required placeholder="(00) 00000-0000"></div>
<div class="form-field"><label>Documento (CPF)</label><input class="form-control" name="documento" required placeholder="000.000.000-00"></div>
</div><div class="form-actions"><button type="button" class="secondary-button cancel-modal">Cancelar</button><button class="primary-button" type="submit">Salvar cliente</button></div></form>`,async fd=>{
 await api("/clientes",{method:"POST",body:JSON.stringify(Object.fromEntries(fd))});toast("Cliente cadastrado com sucesso!");await loadAll();goTo("clientes");
}));
$("newHallButton").addEventListener("click",()=>openModal("Cadastrar salão",`
<form><div class="form-grid">
<div class="form-field full"><label>Nome do salão</label><input class="form-control" name="nome" required placeholder="Ex.: Jardim Encantado"></div>
<div class="form-field"><label>Capacidade de pessoas</label><input class="form-control" type="number" name="capacidade" min="1" required placeholder="Ex.: 80"></div>
<div class="form-field"><label>Acréscimo (R$)</label><input class="form-control" type="number" name="acrescimo" min="0" step="0.01" required value="0"></div>
</div><div class="form-actions"><button type="button" class="secondary-button cancel-modal">Cancelar</button><button class="primary-button" type="submit">Salvar salão</button></div></form>`,async fd=>{
 const nome=String(fd.get("nome")||"").trim();
 const capacidade=Number(fd.get("capacidade"));
 const acrescimo=Number(fd.get("acrescimo")||0);
 if(!nome) throw new Error("Informe o nome do salão.");
 if(!Number.isInteger(capacidade)||capacidade<=0) throw new Error("A capacidade deve ser um número inteiro maior que zero.");
 if(!Number.isFinite(acrescimo)||acrescimo<0) throw new Error("Informe um acréscimo válido, igual ou maior que zero.");
 await api("/saloes",{method:"POST",body:JSON.stringify({nome,capacidade,acrescimo})});
 await loadAll();
 goTo("saloes");
 toast("Salão cadastrado com sucesso!");
}));
$("newBookingButton").addEventListener("click",showBookingModal);
$("quickNewBooking").addEventListener("click",showBookingModal);
function showBookingModal(){
 if(!state.halls.length||!state.clients.length){toast("Cadastre pelo menos um salão e um cliente antes de agendar.",true);return;}
 const hallOptions=state.halls.map(h=>`<option value="${h.id}">${escapeHTML(h.nome)} — até ${h.capacidade} pessoas</option>`).join("");
 const clientOptions=state.clients.map(c=>`<option value="${c.id}">${escapeHTML(c.nome)}</option>`).join("");
 const comboOptions=`<option value="">Sem combo</option>`+state.combos.map(c=>`<option value="${c.id}">${escapeHTML(c.nome)} — ${money(c.preco)}</option>`).join("");
 const extraOptions=state.extras.map(e=>`<label class="check-option"><input type="checkbox" name="extras" value="${e.id}"> ${escapeHTML(e.nome)} (${money(e.preco)})</label>`).join("");
 openModal("Novo agendamento",`
 <form><div class="form-grid">
 <div class="form-field full"><label>Cliente</label><select class="form-control" name="cliente_id" required>${clientOptions}</select></div>
 <div class="form-field"><label>Salão</label><select class="form-control" name="salao_id" required>${hallOptions}</select></div>
 <div class="form-field"><label>Data do evento</label><input class="form-control" type="date" name="data" min="${new Date().toISOString().slice(0,10)}" required></div>
 <div class="form-field"><label>Horário de início</label><input class="form-control" type="time" name="inicio" required></div>
 <div class="form-field"><label>Horas extras</label><input class="form-control" type="number" name="horas_extra" min="0" value="0"></div>
 <div class="form-field full"><label>Combo</label><select class="form-control" name="combo_id">${comboOptions}</select></div>
 <div class="form-field full"><label>Serviços adicionais</label><div class="extras-options">${extraOptions||"Nenhum extra cadastrado."}</div></div>
 <div class="form-field full"><label>Observações</label><textarea class="form-control" name="obs" rows="2" placeholder="Informações adicionais sobre a festa"></textarea></div>
 </div><div class="form-actions"><button type="button" class="secondary-button cancel-modal">Cancelar</button><button class="primary-button" type="submit">Confirmar agendamento</button></div></form>`,async fd=>{
 const payload={cliente_id:Number(fd.get("cliente_id")),salao_id:Number(fd.get("salao_id")),data:fd.get("data"),inicio:fd.get("inicio"),combo_id:fd.get("combo_id")?Number(fd.get("combo_id")):null,horas_extra:Number(fd.get("horas_extra")||0),extras_ids:fd.getAll("extras").map(Number),obs:fd.get("obs")||""};
 await api("/festas",{method:"POST",body:JSON.stringify(payload)});toast("Festa agendada com sucesso!");await loadAll();goTo("agendamentos");
 });
}
$("newPaymentButton").addEventListener("click",()=>{
 if(!state.bookings.length){toast("Não há festas cadastradas para receber pagamentos.",true);return;}
 const options=state.bookings.map(b=>`<option value="${b.id}">#${b.id} — ${escapeHTML(b.cliente_nome)} — ${dateBR(b.data)} (Total: ${money(b.total)})</option>`).join("");
 openModal("Registrar pagamento",`<form><div class="form-grid">
 <div class="form-field full"><label>Evento</label><select class="form-control" name="festa_id" required>${options}</select></div>
 <div class="form-field"><label>Valor recebido (R$)</label><input class="form-control" type="text" name="valor" inputmode="decimal" autocomplete="off" required placeholder="Ex.: 150.50 ou 150,50" pattern="[0-9.,]+"></div>
 <div class="form-field"><label>Data do pagamento</label><input class="form-control" type="date" name="data" value="${new Date().toISOString().slice(0,10)}" required></div>
 <div class="form-field full"><label>Tipo</label><select class="form-control" name="tipo"><option value="Sinal">Sinal</option><option value="Parcela">Parcela</option><option value="Quitação">Quitação</option></select></div>
 </div><div class="form-actions"><button type="button" class="secondary-button cancel-modal">Cancelar</button><button class="primary-button" type="submit">Registrar pagamento</button></div></form>`,async fd=>{
 const valor=parseMoneyInput(fd.get("valor"));
 if(!Number.isFinite(valor)||valor<=0) throw new Error("Informe um valor válido maior que zero. Use ponto ou vírgula para os centavos (ex.: 150.50).");
 await api("/pagamentos",{method:"POST",body:JSON.stringify({festa_id:Number(fd.get("festa_id")),valor,data:fd.get("data"),tipo:fd.get("tipo")})});toast("Pagamento registrado!");await loadAll();goTo("pagamentos");
 });
});
document.addEventListener("click",e=>{if(e.target.classList.contains("cancel-modal"))closeModal();});
loadAll();

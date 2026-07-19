const qs = (s) => document.querySelector(s);
const out = (sel, txt) => { const e = qs(sel); e.textContent = txt; };
const j = (x) => { try { return JSON.stringify(x, null, 2); } catch { return String(x); } };
const api = async (path, opts={}) => {
  const r = await fetch(path, {headers:{'Content-Type':'application/json'}, ...opts});
  const text = await r.text();
  let data; try { data = JSON.parse(text); } catch { data = text; }
  return { ok: r.ok, status: r.status, data };
};

async function loadStats(){
  const s = (await api('/api/claim/stats')).data || {};
  qs('#stats').innerHTML = [
    `NPO 总量 <b>${s.npos_total??0}</b>`,
    `認定 ${s.npos_recognized??0}`,
    `未用 ${s.npos_unused??0}`,
    `未用/認定 ${s.npos_unused_recognized??0}`,
    `已提交 ${s.submissions??0}`,
  ].map(t => `<span>${t}</span>`).join('');
}

qs('#refresh').onclick = async () => {
  out('#npo-out', '下载导入中…（gyousei_000.zip 全国一括，10MB+，约30秒）');
  const r = await api('/api/npo/refresh', {method:'POST'});
  out('#npo-out', j(r.data));
  loadStats();
};
qs('#preview').onclick = async () => {
  const r = await api('/api/npo/preview?limit=10');
  out('#npo-out', j(r.data));
};
qs('#one').onclick = async () => {
  out('#one-out', '提交中…');
  const r = await api('/api/claim/one', {method:'POST'});
  out('#one-out', j(r.data));
  loadStats(); loadHistory();
};
qs('#batch').onclick = async () => {
  const n = parseInt(qs('#n').value || '1', 10);
  out('#one-out', `批量 ${n} 中…`);
  const r = await api('/api/claim/batch?count='+n, {method:'POST'});
  out('#one-out', j(r.data));
  loadStats(); loadHistory();
};
qs('#load-history').onclick = loadHistory;

qs('#confirm-all').onclick = async () => {
  out('#confirm-out', '正在遍历历史记录查收确认邮件并点击确认链接…（每条间隔约1-2秒）');
  const r = await api('/api/claim/confirm-all', {method:'POST'});
  const d = r.data || {};
  out('#confirm-out',
    `总数 ${d.total??0} ｜ 已确认 ${d.confirmed??0} ｜ 暂无确认邮件 ${d.no_verify_mail??0} ｜ 失败 ${d.failed??0}\n\n` + j(d.results || d));
  loadHistory();
};

async function loadHistory(){
  const r = await api('/api/claim/history?limit=50');
  const tb = qs('#history tbody');
  if (!r.ok) { tb.innerHTML = '<tr><td colspan="7">加载失败</td></tr>'; return; }
  const rows = r.data?.data || [];
  tb.innerHTML = rows.map(x => `
    <tr>
      <td>${x.id}</td>
      <td><small>${(x.created_at||'').slice(0,19)}</small></td>
      <td>${escapeHtml(x.organisation_name||'')}<br><small>${x.corporate_number||''}</small></td>
      <td class="${x.status==='submitted'?'ok':'err'}">${x.status}</td>
      <td>${escapeHtml(x.email||'')}</td>
      <td>${x.confirmed_at ? '<span class="ok">✓ 已确认</span><br><small>'+(x.confirmed_at||'').slice(0,19)+'</small>' : '<span class="muted">未确认</span>'}</td>
      <td>
        <button class="ghost" data-id="${x.id}" data-act="mails">收信</button>
        <button class="ghost" data-id="${x.id}" data-act="code">验证码</button>
        ${x.confirmed_at ? '' : `<button class="ghost" data-id="${x.id}" data-act="confirm">确认</button>`}
      </td>
    </tr>`).join('') || '<tr><td colspan="7" class="muted">暂无</td></tr>';
  tb.querySelectorAll('button').forEach(b => b.onclick = onRowAction);
}

async function onRowAction(e){
  const id = e.currentTarget.dataset.id;
  const act = e.currentTarget.dataset.act;
  if (act === 'confirm') {
    out('#confirm-out', `确认 #${id} 中…`);
    const r = await api(`/api/claim/${id}/confirm`, {method:'POST'});
    out('#confirm-out', j(r.data));
    loadHistory();
    return;
  }
  const r = await api(`/api/claim/${id}/${act}`);
  out('#mail-out', j(r.data));
}

qs('#mails').onclick = async () => {
  const a = qs('#addr').value.trim();
  if (!a) return;
  const r = await api('/api/mail/inbox?address='+encodeURIComponent(a)+'&limit=20');
  out('#mail-out', j(r.data));
};
qs('#code').onclick = async () => {
  const a = qs('#addr').value.trim();
  if (!a) return;
  const r = await api('/api/mail/code?address='+encodeURIComponent(a));
  out('#mail-out', j(r.data));
};

function escapeHtml(s){ return (s||'').replace(/[&<>"']/g, m => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m])); }

loadStats(); loadHistory();
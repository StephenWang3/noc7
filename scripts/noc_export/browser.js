/* 已共享 NOC 标签页中的只读采集器；不调用页面业务方法，不执行源材料中的脚本。 */
function createNocCollector(options = {}) {
  const base = '/bit-bpc-extend-web';
  const esb = base + '/esbProcess';
  const allowed = new Map([
    [base + '/hk/query/query/getProcessList', 'POST'],
    [esb + '/getEsbProcessInfo', 'GET'], [esb + '/log', 'GET'],
    [esb + '/emailLog', 'GET'], [esb + '/getAuthParams', 'GET'],
    [esb + '/busfault/order/detail/getDetailByPage', 'POST'],
    [esb + '/busfault/deal/buildPage', 'POST'], [esb + '/busfault/download', 'GET'],
    [base + '/mailbox/email/findEmailById', 'POST'],
    [base + '/mailbox/email/downloadAttachment', 'GET'],
    ['/bit-bpc-process/process/viewInfo', 'GET'],
    [base + '/bpcOrderExtend/getLog', 'POST'],
    [base + '/networkFault/getNetworkFaultInfo','GET'],
    [base + '/networkFault/getNetworkFaultLog','GET'],
  ]);
  const interval = Math.max(1000, Number(options.intervalMs) || 1500);
  const maxRequests = Math.min(500, Math.max(1, Number(options.maxRequests) || 300));
  const maxBytes = Math.min(100 * 1024 * 1024, Number(options.maxBytes) || 25 * 1024 * 1024);
  let count = 0, last = 0, state = {status:'idle'}, running = false, cancelled = false;
  const origin = location.origin;
  const delay = ms => new Promise(r => setTimeout(r, ms));
  const clean = value => JSON.parse(JSON.stringify(value, (key, val) =>
    /^(authParams|globalUniqueID|authorization|cookie|token|jwt|pageInitFunction)$/i.test(key) ? undefined : val));
  function check(path, method) {
    const u = new URL(path, origin);
    if (u.origin !== origin || u.username || u.password || u.hash ||
        !(allowed.get(u.pathname) === method ||
          (method === 'GET' && /^\/bit-bpc-process\/processLog\/[a-zA-Z0-9_-]+$/.test(u.pathname))))
      throw new Error('读取白名单拒绝该路径或方法');
    return u;
  }
  async function request(path, method = 'GET', data, binary = false) {
    const u = check(path, method);
    if (location.origin !== origin || cancelled) throw new Error('采集已停止');
    if (count >= maxRequests) throw new Error('已达到本会话请求预算');
    count++;
    await delay(Math.max(0, last + interval + Math.random()*250 - Date.now()));
    if (cancelled) throw new Error('采集已停止');
    last = Date.now();
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 20000);
    try {
      const r = await fetch(u.href, {method, credentials:'same-origin', redirect:'error',
        signal:controller.signal, headers:{'X-Requested-With':'XMLHttpRequest',
          ...(data === undefined ? {} : {'Content-Type':'application/json'})},
        ...(data === undefined ? {} : {body:JSON.stringify(data)})});
      if (!r.ok) throw new Error('读取失败 HTTP ' + r.status + '；' + u.pathname);
      const length = Number(r.headers.get('content-length'));
      if (length > maxBytes) throw new Error('响应超过单材料大小上限');
      const reader = r.body.getReader(); let size=0; const chunks=[];
      while (true) { const {done,value}=await reader.read(); if(done)break;
        size+=value.byteLength; if(size>maxBytes){await reader.cancel();throw new Error('响应超过单材料大小上限');} chunks.push(value); }
      const bytes=new Uint8Array(size);let off=0;for(const chunk of chunks){bytes.set(chunk,off);off+=chunk.length;}
      if (binary) {
        const mime=r.headers.get('content-type')||'application/octet-stream';
        const head=new TextDecoder().decode(bytes.slice(0,500)).trim();
        if (!size || /^(?:<!doctype|<html|\{\s*"(?:code|error|message)")/i.test(head) || /text\/html|application\/json/i.test(mime))
          throw new Error('附件返回空内容、登录页或错误对象');
        let text=''; for(let i=0;i<bytes.length;i+=32768) text+=String.fromCharCode(...bytes.subarray(i,i+32768));
        return {base64:btoa(text),media_type:mime,size_bytes:size};
      }
      let j;try{j=JSON.parse(new TextDecoder().decode(bytes));}catch{throw new Error('读取返回非 JSON，可能登录已失效');}
      if (!j || (j.code !== undefined && ![0,200,'0','200'].includes(j.code)))
        throw new Error('读取返回业务错误；' + u.pathname + '；code=' + String(j?.code));
      return j;
    } finally { clearTimeout(timer); }
  }
  const validTotal = v => v !== null && v !== undefined && Number.isInteger(Number(v)) && Number(v) >= 0;
  const q = (path, params) => path+'?'+new URLSearchParams(params);
  async function list(params) {
    if (!params || !(params.title || params.orderId || params.orderStatusList?.length || (params.sta && params.end)))
      throw new Error('列表查询必须限定时间、编号、标题或状态');
    if(('sta' in params)!==('end' in params))throw new Error('时间查询必须同时指定 sta 和 end');
    const accepted=new Set(['orderId','title','customerName','orderTypeList','orderStatusList','guZhangTongDao','haiLuLanName','failureInfo','sta','end','pageNo','pageSize']);
    if(Object.keys(params).some(k=>!accepted.has(k)))throw new Error('列表含未允许的查询参数');
    const body={orderId:'',title:'',customerName:'',orderTypeList:[],orderStatusList:[],
      guZhangTongDao:'',haiLuLanName:'',failureInfo:'',sourceName:'db',isCount:'count',
      processCatalogCode:'faultTypeProcess',...params};
    if (!Number.isInteger(body.pageNo)||body.pageNo<1||body.pageNo>10||!Number.isInteger(body.pageSize)||body.pageSize<1||body.pageSize>50)
      throw new Error('分页必须显式指定：页码 1–10，每页 1–50');
    const j=await request(base+'/hk/query/query/getProcessList','POST',body);
    if (!Array.isArray(j.data?.datas)) throw new Error('工单列表结构已变化');
    if(body.sta&&body.end&&j.data.datas.some(r=>!Number.isFinite(Number(r.createTimeStamp))||Number(r.createTimeStamp)<body.sta||Number(r.createTimeStamp)>body.end))throw new Error('服务端未遵守时间范围，停止查询');
    return {capture_version:1,kind:'list',captured_at:new Date().toISOString(),params,rows:clean(j.data.datas),total:j.data.totle};
  }
  async function inspect(job) {
    const row=job.row;
    if(!['bpc','common'].includes(row?.dataType)||!/^[a-zA-Z0-9_-]+$/.test(row.flowId||''))throw new Error('预检仅支持流程布局');
    const data=(await request(q('/bit-bpc-process/process/viewInfo',{instanceId:row.flowId}))).data;
    if(!data?.formData)throw new Error('流程预检结构已变化');
    return {capture_version:1,kind:'inspection',row:clean(row),info:clean({formData:data.formData,processInstance:data.processInstance}),captured_at:new Date().toISOString()};
  }
  async function discover(job) {
    const row=job.row;
    if(row?.dataType!=='esb'||!row.orderId)throw new Error('附件预检仅支持业务布局');
    const info=(await request(q(esb+'/getEsbProcessInfo',{id:row.orderId}))).data;
    if(!info?.faultNo)throw new Error('预检缺少工单编号');
    const auth=(await request(q(esb+'/getAuthParams',{faultNo:info.faultNo}))).data;
    if(!auth?.globalUniqueID)throw new Error('预检无法取得读取参数');
    const files=[];
    for(const type of ['追单记录','派单记录']) {
      let read=0;const seen=new Set();
      for(let pageNo=1;pageNo<=10;pageNo++) {
        const j=await request(esb+'/busfault/order/detail/getDetailByPage','POST',{authParams:auth,type,faultNo:info.faultNo,pageNo,pageSize:50});
        const d=j.data?.data;
        if(!Array.isArray(d?.rows)||!validTotal(d.totalElements))throw new Error('预检详情结构已变化');
        for(const item of d.rows){
          if(!item.objectId||seen.has(String(item.objectId)))throw new Error('预检详情编号缺失或重复');
          seen.add(String(item.objectId));
          for(const f of [...(item.files||[]),...(item.attachmentList||[])])files.push({source:type,file:clean(f)});
        }
        read+=d.rows.length;
        if(read>=Number(d.totalElements))break;
        if(!d.rows.length||pageNo===10)throw new Error('预检分页不完整');
      }
    }
    const logs=(await request(q(esb+'/log',{id:row.orderId}))).data;
    const elogs=(await request(q(esb+'/emailLog',{esbProcessId:row.orderId}))).data;
    if(!Array.isArray(logs)||!Array.isArray(elogs))throw new Error('预检邮件日志结构已变化');
    const ids=new Set();
    for(const l of [...logs,...elogs]) {
      for(const f of l.attachments||[])files.push({source:'过程日志',file:clean(f)});
      for(const id of String(l.emailIds||l.emailId||'').split(/[,;\s]+/).filter(Boolean))ids.add(id);
    }
    if(ids.size>20)throw new Error('单张预检邮件超过20封，需进一步缩小范围');
    for(const id of ids){const e=(await request(base+'/mailbox/email/findEmailById','POST',{emailId:id})).data;
      if(!e)throw new Error('预检邮件为空');
      for(const f of e.attachments||[])files.push({source:'邮件',email_id:id,file:clean(f)});
    }
    return {capture_version:1,kind:'discovery',captured_at:new Date().toISOString(),row:clean(row),files:clean(files),
      note:'仅附件元数据预检，不是完整工单包；不能据此断言其他详情控件或源系统没有附件'};
  }
  async function exportRow(job) {
    const row=job.row;
    if(!row?.id||!row.orderId)throw new Error('缺少已查询的工单行');
    const out={capture_version:1,kind:'ticket',captured_at:new Date().toISOString(),
      alias:job.alias||null,match:job.match||null,row:clean(row),logs:[],details:[],emails:[],files:[],warnings:[]};
    state.partial=out;
    const seen=new Map();
    async function download(path, name, source) {
      // 参数含临时授权信息，仅在浏览器内使用；不写入工单包。
      if(seen.has(path)){const f=seen.get(path);f.sources.push(source);return;}
      const f={name:String(name||'attachment.bin'),sources:[source],...(await request(path,'GET',undefined,true))};
      seen.set(path,f);out.files.push(f);
    }
    if(row.dataType==='esb') {
      out.layout='business';
      const info=(await request(q(esb+'/getEsbProcessInfo',{id:row.orderId}))).data;
      if(!info?.faultNo)throw new Error('工单详情缺少编号');
      out.info=clean(info);
      out.logs=(await request(q(esb+'/log',{id:row.orderId}))).data;
      out.email_logs=(await request(q(esb+'/emailLog',{esbProcessId:row.orderId}))).data;
      if(!Array.isArray(out.logs)||!Array.isArray(out.email_logs))throw new Error('日志结构已变化');
      const auth=(await request(q(esb+'/getAuthParams',{faultNo:info.faultNo}))).data;
      if(!auth?.globalUniqueID)throw new Error('无法取得详情读取参数');
      // 不依赖 hasAttachments：枚举两类详情每一页，再逐条读取表单。
      for(const type of ['追单记录','派单记录']) {
        let read=0; const objects=new Set();
        for(let page=1;page<=10;page++) {
          const j=await request(esb+'/busfault/order/detail/getDetailByPage','POST',
            {authParams:auth,type,faultNo:info.faultNo,pageNo:page,pageSize:50});
          const data=j.data?.data;
          if(!Array.isArray(data?.rows)||!validTotal(data.totalElements))throw new Error('详情分页结构已变化');
          for(const d of data.rows) {
            if(!d.objectId)throw new Error('详情记录缺少 objectId');
            if(objects.has(String(d.objectId)))throw new Error('详情分页返回重复记录');
            objects.add(String(d.objectId));
            const b=await request(esb+'/busfault/deal/buildPage','POST',{authParams:auth,faultNo:info.faultNo,objectId:d.objectId});
            const fields=b.data?.data?.BuildPageList;
            if(!Array.isArray(fields))throw new Error('详情表单结构已变化');
            out.details.push({type,row:clean(d),fields:clean(fields)});
            const files=[...(d.files||[]),...(d.attachmentList||[])];
            for(const f of files){
              if(!f.attId)throw new Error('详情附件字段未识别，不能静默漏件');
              await download(q(esb+'/busfault/download',{attId:f.attId,globalUniqueID:auth.globalUniqueID,fileName:f.attOrigName||'attachment.bin'}),f.attOrigName,{detail_index:out.details.length-1});
            }
            // 尚未核实的表单附件结构不能当作无附件。
            for(const f of fields)if(/file|attach|upload/i.test(f.fieldType||'')&&f.defaultValue)
              throw new Error('详情表单存在尚未核实的附件控件，停止以免漏件');
          }
          read+=data.rows.length;
          if(read>=Number(data.totalElements))break;
          if(!data.rows.length||page===10)throw new Error('详情分页未完整，停止导出');
        }
      }
      for(let li=0;li<out.logs.length;li++)for(const f of out.logs[li].attachments||[]){
        if(!f.attId)throw new Error('日志附件字段尚未识别');
        await download(q(esb+'/busfault/download',{attId:f.attId,globalUniqueID:auth.globalUniqueID,fileName:f.attOrigName||'attachment.bin'}),f.attOrigName,{log_index:li});
      }
      const ids=new Set();
      for(const log of [...out.logs,...out.email_logs])for(const id of String(log.emailIds||log.emailId||'').split(/[,;\s]+/).filter(Boolean))ids.add(id);
      for(const id of ids){
        const e=(await request(base+'/mailbox/email/findEmailById','POST',{emailId:id})).data;
        if(!e || (!e.htmlContent&&!e.textContent))throw new Error('邮件详情为空，不能用摘要替代');
        out.emails.push(clean(e));
        for(const f of e.attachments||[]){
          const aid=f.attachmentId||f.id;
          if(!aid)throw new Error('邮件附件字段未识别');
          await download(q(base+'/mailbox/email/downloadAttachment',{attachmentId:aid}),f.fileName||f.name||f.attachmentName,{email_id:String(id)});
        }
      }
      out.logs=clean(out.logs);out.email_logs=clean(out.email_logs);
    } else if(row.dataType==='net') {
      out.layout='network';
      out.info=clean((await request(q(base+'/networkFault/getNetworkFaultInfo',{woId:row.orderId}))).data);
      out.logs=clean((await request(q(base+'/networkFault/getNetworkFaultLog',{woId:row.orderId}))).data);
      if(!out.info?.sheetNo||!Array.isArray(out.logs))throw new Error('网络故障详情结构已变化');
      const nonempty=v=>v!=null && !['','无','[]','{}','null'].includes(String(v).trim());
      for(const k of ['attId','appendix','appendixFileUrl'])if(nonempty(out.info[k]))
        throw new Error('网络故障有未核实附件，停止发布');
      for(const log of out.logs)if(log.hasAttachments||log.hasFeedbackHistory||nonempty(log.emailIds)||
          nonempty(log.attachments)||nonempty(log.uploadFaultReport)||nonempty(log.allSelectedStorage))
        throw new Error('网络故障有未核实的附件、反馈详情或邮件，停止发布');
    } else if(['bpc','common'].includes(row.dataType)) {
      out.layout='workflow';
      const id=row.flowId;
      if(!/^[a-zA-Z0-9_-]+$/.test(id||''))throw new Error('流程编号无效');
      const view=(await request(q('/bit-bpc-process/process/viewInfo',{instanceId:id}))).data;
      if(!view?.formData||!view.processInstance)throw new Error('流程详情结构已变化');
      // 只保留表单值、标签定义与状态，不保留可执行的页面初始化函数。
      out.info=clean({formData:view.formData,formDefinition:view.formDefinition,processInstance:view.processInstance});
      out.logs=(await request('/bit-bpc-process/processLog/'+id)).data;
      if(!Array.isArray(out.logs))throw new Error('流程日志结构已变化');
      out.extra_logs=(await request(base+'/bpcOrderExtend/getLog','POST',{processInstanceId:id})).data;
      if(!Array.isArray(out.extra_logs))throw new Error('追加日志结构已变化');
      // 流程附件存储规则尚未核实：非空附件控件必须显式中止，不能发出完整包。
      const scan=x=>{if(!x||typeof x!=='object')return;for(const [k,v]of Object.entries(x)){
        if(/file|attach/i.test(k)&&v&&(!Array.isArray(v)||v.length)&&typeof v!=='boolean')
          out.warnings.push('流程含附件字段 '+k+'，当前适配器未下载，需补验');
        if(v&&typeof v==='object')scan(v);}};
      scan(view.formData);scan(out.extra_logs);
      if(out.warnings.length)throw new Error('流程存在未核实附件，保留失败记录，不发布完整包');
    } else throw new Error('该工单布局尚未核实：'+row.dataType);
    out.finished_at=new Date().toISOString();
    out.requests=count;
    return clean(out);
  }
  return {
    // 只允许一个任务；失败结果带部分材料，包装端不会将其发布为有效包。
    start(job){if(running)throw new Error('已有采集任务');running=true;cancelled=false;state={status:'running'};
      (async()=>{try{if(job.kind&&!['list','inspect','discover','export'].includes(job.kind))throw new Error('未知采集任务');const result=job.kind==='list'?await list(job.params):(job.kind==='inspect'?await inspect(job):(job.kind==='discover'?await discover(job):await exportRow(job)));state={status:'done',result};}
      catch(e){state={status:'failed',error:String(e.message||e),partial:state.partial?clean(state.partial):undefined};}
      finally{running=false;}})();return {status:'running'};},
    status(){return {status:state.status,requests:count,error:state.error};},
    take(){if(running)throw new Error('采集未完成');const result=state;state={status:'idle'};return result;},
    cancel(){cancelled=true;return {status:'stopping'};},
    check,
  };
}
if(typeof module!=='undefined') module.exports={createNocCollector};

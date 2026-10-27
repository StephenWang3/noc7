// 离线模拟服务端：白名单、假登录页、无附件标志和分页失败。
const assert = require('node:assert/strict');
const {createNocCollector} = require('../../scripts/noc_export/browser.js');
global.location = {origin:'https://noc.example.test'};
const realTimeout=global.setTimeout;
global.setTimeout=(f,ms)=>realTimeout(f,ms===20000?ms:0);
let clock=Date.now();Date.now=()=>clock+=2000;
const esb='/bit-bpc-extend-web/esbProcess';
const calls=[];
let mode='normal';
global.fetch=async(url, options)=>{
  const u=new URL(url);calls.push({url:u,options});
  const p=u.pathname;
  let data;
  if(mode==='rateLimit')return new Response('busy',{status:429});
  if(mode==='login')return new Response('<html>login</html>');
  if(p.endsWith('/getNetworkFaultInfo'))data={sheetNo:'FAKE-VOID',sheetStatus:'作废',attId:mode==='networkFiles'?'fake-attachment':'无'};
  else if(p.endsWith('/getNetworkFaultLog'))data=[{actionName:'作废',hasAttachments:false,attachments:null,hasFeedbackHistory:false}];
  else if(p.endsWith('/getEsbProcessInfo'))data={faultNo:'FAKE-001'};
  else if(p.endsWith('/emailLog')||p.endsWith('/log'))data=[{nodeCnName:'信息追加',remark:'虚构',hasAttachments:false,
    ...(mode==='mailIds'?{emailIds:['FAKE-A;FAKE-B','FAKE-A'],emailId:'FAKE-C'}:{})}];
  else if(p.endsWith('/findEmailById'))data={emailId:JSON.parse(options.body).emailId,textContent:'虚构邮件'};
  else if(p.endsWith('/getAuthParams'))data={globalUniqueID:'fake-ephemeral-token'};
  else if(p.endsWith('/getDetailByPage')){
    const params=JSON.parse(options.body);
    data={data:{rows:params.type==='追单记录'&&mode!=='truncated'?[{objectId:'fake-object',files:[{attId:'fake-file',attOrigName:'fake.pdf'}]}]:[],totalElements:mode==='truncated'?2:(params.type==='追单记录'?1:0)}};
  } else if(p.endsWith('/buildPage'))data={data:{BuildPageList:[]}};
  else if(p.endsWith('/download'))return new Response('%PDF-1.4\nFAKE',{headers:{'Content-Type':'application/octet-stream'}});
  else throw new Error('意外请求 '+p);
  return Response.json({code:200,data});
};
async function finish(c){for(let i=0;i<200;i++){if(c.status().status!=='running')return c.take();await new Promise(r=>realTimeout(r,2));}throw new Error('未完成');}
(async()=>{
  let c=createNocCollector();
  for(const [path,method] of [['https://evil.example.test/a','GET'],[esb+'/addLog','POST'],[esb+'/getAuthParams','POST'],[esb+'/getEsbProcessInfo/../addLog','GET']])assert.throws(()=>c.check(path,method));
  c.start({kind:'export',row:{id:'fake',orderId:'fake',dataType:'esb'}});
  assert.throws(()=>c.start({kind:'list'}),/已有/);
  let r=await finish(c);
  assert.equal(r.status,'done');assert.equal(r.result.files.length,1);
  assert.equal(r.result.logs[0].hasAttachments,false);
  assert(!JSON.stringify(r).includes('fake-ephemeral-token'));
  assert(calls.every(c=>c.options.redirect==='error'));
  assert(calls.some(c=>c.url.pathname.endsWith('/buildPage')));
  mode='login';c=createNocCollector();c.start({row:{id:'fake',orderId:'fake',dataType:'esb'}});
  r=await finish(c);assert.equal(r.status,'failed');assert.match(r.error,/非 JSON/);
  mode='truncated';c=createNocCollector();c.start({row:{id:'fake',orderId:'fake',dataType:'esb'}});
  r=await finish(c);assert.equal(r.status,'failed');assert.match(r.error,/分页未完整/);
  mode='normal';c=createNocCollector({maxRequests:1});c.start({row:{id:'fake',orderId:'fake',dataType:'esb'}});
  r=await finish(c);assert.equal(r.status,'failed');assert.match(r.error,/预算/);
  mode='rateLimit';const before=calls.length;c=createNocCollector();c.start({kind:'export',row:{id:'fake',orderId:'fake',dataType:'esb'}});
  r=await finish(c);assert.equal(r.status,'failed');assert.match(r.error,/HTTP 429/);assert.equal(calls.length-before,1);
  mode='normal';c=createNocCollector();c.start({kind:'export',row:{id:'fake',orderId:'fake',dataType:'net'}});
  r=await finish(c);assert.equal(r.status,'failed');assert.match(r.error,/逐条详情及附件读取尚未核实/);
  assert.equal(r.partial.logs[0].hasAttachments,false);assert.equal(r.partial.logs[0].attachments,null);assert.equal(r.partial.info.sheetStatus,'作废');
  mode='networkFiles';c=createNocCollector();c.start({kind:'export',row:{id:'fake',orderId:'fake',dataType:'net'}});
  r=await finish(c);assert.equal(r.status,'failed');assert.match(r.error,/逐条详情及附件读取尚未核实/);
  mode='normal';c=createNocCollector();c.start({kind:'list',params:{title:'fake',end:1,pageNo:1,pageSize:1}});
  r=await finish(c);assert.equal(r.status,'failed');assert.match(r.error,/同时指定/);
  c=createNocCollector();c.start({kind:'list',params:{title:'fake',pageNo:1,pageSize:1,sourceName:'unexpected'}});
  r=await finish(c);assert.equal(r.status,'failed');assert.match(r.error,/未允许/);
  c=createNocCollector();c.start({kind:'discover',row:{id:'fake',orderId:'fake',dataType:'esb'}});
  r=await finish(c);assert.equal(r.status,'done');assert.equal(r.result.files.length,1);
  assert(!JSON.stringify(r).includes('fake-ephemeral-token'));
  mode='mailIds';c=createNocCollector();c.start({kind:'export',row:{id:'fake',orderId:'fake',dataType:'esb'}});
  r=await finish(c);assert.equal(r.status,'done');
  assert.deepEqual(r.result.emails.map(e=>e.emailId),['FAKE-A','FAKE-B','FAKE-C']);
  console.log('浏览器采集边界离线验证通过');
})().catch(e=>{console.error(e);process.exitCode=1});

const fs = require('fs');
const path = require('path');
const root = __dirname;
const files = ['index.html', ...fs.readdirSync(path.join(root,'compositions')).map(f=>'compositions/'+f).sort()];
let errors=[];
function attrs(tag){
  const out={};
  const re=/([a-zA-Z0-9_-]+)\s*=\s*"([^"]*)"/g;
  let m; while((m=re.exec(tag))) out[m[1]]=m[2];
  return out;
}
for(const rel of files){
  const txt=fs.readFileSync(path.join(root, rel),'utf8');
  if(rel==='index.html'){
    if(!txt.includes('id="main"')) errors.push('index missing id main');
    if(!txt.includes('data-composition-id="dashboard"')) errors.push('index missing dashboard id');
    if(!txt.includes('data-width="1080"') || !txt.includes('data-height="1920"')) errors.push('index missing 1080x1920');
  } else {
    if(!txt.includes('<template')) errors.push(rel+' missing template');
  }
  if(/data-layer|data-end/.test(txt)) errors.push(rel+' uses deprecated attr');
  if(/\.play\(|\.pause\(|currentTime/.test(txt)) errors.push(rel+' controls media');
  if(!txt.includes('gsap.timeline({ paused: true })')) errors.push(rel+' missing paused gsap timeline');
  const ids=[];
  for(const m of txt.matchAll(/<([a-zA-Z0-9]+)\b[^>]*>/g)){
    const tag=m[0];
    const at=attrs(tag);
    if(at.id){
      if(ids.includes(at.id)) errors.push(rel+' duplicate id '+at.id);
      ids.push(at.id);
    }
    const cls=at.class || '';
    if(cls.split(/\s+/).includes('clip')){
      if(!at.id) errors.push(rel+' clip missing id: '+tag.slice(0,80));
      if(!('data-start' in at)) errors.push(rel+' clip '+(at.id||'?')+' missing data-start');
      if(!('data-track-index' in at)) errors.push(rel+' clip '+(at.id||'?')+' missing data-track-index');
      if(at['data-composition-src']){
        if('data-duration' in at) errors.push(rel+' composition clip '+at.id+' has data-duration');
      } else {
        if(!('data-duration' in at)) errors.push(rel+' primitive clip '+(at.id||'?')+' missing data-duration');
      }
    }
    if(m[1].toLowerCase()==='audio'){
      for(const k of ['id','src','data-start','data-duration','data-track-index','data-volume']) if(!(k in at)) errors.push(rel+' audio missing '+k);
    }
  }
  const cid=(txt.match(/data-composition-id="([^"]+)"/)||[])[1];
  if(cid){
    if(!txt.includes(`window.__timelines["${cid}"]`)) errors.push(rel+' timeline key mismatch/missing for '+cid);
  }
}
if(errors.length){
  console.error(errors.join('\n'));
  process.exit(1);
}
console.log('static validation ok for '+files.length+' html files');

import { chromium } from 'playwright';
const BASE='http://127.0.0.1:8765';
const b=await chromium.launch();
for (const [p,perfil] of [['/',0],['/diagnostico/#resultado',1],['/faculdade/pitagoras-eunapolis/',0],['/edital/unime-externa-2027-1-3d14f3/',0]]) {
  const ctx=await b.newContext({viewport:{width:375,height:812},isMobile:true,hasTouch:true});
  if(perfil) await ctx.addInitScript(()=>localStorage.setItem('tm_perfil',JSON.stringify({origem:'brasil',curso:'medicina',faculdade:'',semestre:3,transferiu:'nao',cidade:'Salvador - BA',coords:[-12.97,-38.5],raio:400,tipo:'todas',taxaMax:null})));
  const pg=await ctx.newPage(); await pg.goto(BASE+p,{waitUntil:'networkidle'});
  const r=await pg.evaluate(()=>[...document.querySelectorAll('a,button,input,select,summary')].filter(el=>{const s=getComputedStyle(el);if(s.display==='none'||s.visibility==='hidden')return false;const r=el.getBoundingClientRect();if(!r.width)return false;const noTexto=el.tagName==='A'&&s.display==='inline'&&/^(P|LI|SPAN|SMALL|TD|DD)$/.test(el.parentElement.tagName);return !noTexto&&(r.width<24||r.height<24)}).map(el=>{const r=el.getBoundingClientRect();return `${el.tagName} ${Math.round(r.width)}x${Math.round(r.height)} disp=${getComputedStyle(el).display} pai=${el.parentElement.tagName}.${el.parentElement.className} "${(el.textContent||el.name||el.type).trim().slice(0,40)}"`}));
  console.log('##',p); [...new Set(r)].slice(0,12).forEach(x=>console.log('  ',x));
  await ctx.close();
}
await b.close();

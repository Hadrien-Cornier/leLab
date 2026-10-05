const { chromium } = await import(process.env.PLAYWRIGHT_MODULE ?? 'playwright');
import fs from 'node:fs';
import { dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const directory = dirname(fileURLToPath(import.meta.url));
const profile = {name:'rotation_demo', leader_port:'supplied', follower_port:'supplied', leader_config:'supplied', follower_config:'supplied', is_clean:true,
  cameras:[{id:'wrist',name:'wrist',type:'opencv',camera_index:0,device_id:'supplied',width:640,height:480,fps:30,rotation:0}]};
const browser = await chromium.launch({headless:true,executablePath:process.env.CHROMIUM_EXECUTABLE});
const page = await browser.newPage({viewport:{width:1360,height:1100}});
const errors=[];
page.on('pageerror', error=>errors.push(error.message));
await page.addInitScript(()=>{
  localStorage.setItem('lelab.apiBaseUrl','http://127.0.0.1:18027');
  localStorage.setItem('lelab.selectedRobot','rotation_demo');
  history.replaceState({usr:{robot_name:'rotation_demo'},key:'evidence'},'',location.href);
  navigator.mediaDevices.getUserMedia=async()=>{
    const canvas=document.createElement('canvas');canvas.width=640;canvas.height=480;
    const ctx=canvas.getContext('2d');
    const draw=()=>{
      ctx.save();ctx.translate(640,480);ctx.rotate(Math.PI);
      ctx.fillStyle='#dc2626';ctx.fillRect(0,0,320,240);
      ctx.fillStyle='#16a34a';ctx.fillRect(320,0,320,240);
      ctx.fillStyle='#2563eb';ctx.fillRect(0,240,320,240);
      ctx.fillStyle='#ca8a04';ctx.fillRect(320,240,320,240);
      ctx.fillStyle='white';ctx.font='bold 44px sans-serif';ctx.fillText('TOP LEFT',30,65);ctx.fillText('TOP RIGHT',330,65);
      ctx.fillText('BOTTOM LEFT',20,430);ctx.fillText('BOTTOM RIGHT',325,430);ctx.restore();
    };draw();setInterval(draw,50);return canvas.captureStream(20);
  };
  navigator.mediaDevices.enumerateDevices=async()=>[{kind:'videoinput',deviceId:'supplied',groupId:'supplied',label:'Supplied camera'}];
});
await page.route('http://127.0.0.1:18027/**', async route=>{
  const path=new URL(route.request().url()).pathname;
  let data={success:true,status:'success'};
  if(path==='/robots')data={robots:[profile]};
  else if(path.startsWith('/robots/')) {
    if(route.request().method()==='POST')Object.assign(profile,route.request().postDataJSON());
    data={status:'success',robot:profile};
  } else if(path==='/available-cameras')data={cameras:[{index:0,name:'Supplied camera',available:true}]};
  else if(path==='/calibration-status')data={calibration_active:false,status:'idle',device_type:null,error:null,message:'',step:0,total_steps:1};
  else if(path.includes('config'))data={files:[],configs:[]};
  else if(path.includes('port'))data={port:'supplied',ports:[]};
  await route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(data)});
});
await page.goto(`${process.env.LELAB_UI_URL ?? 'http://127.0.0.1:8088'}/calibration`);
await page.waitForTimeout(2500);
fs.writeFileSync(directory+'/browser-initial.txt', await page.locator('body').innerText());
fs.writeFileSync(directory+'/browser-initial-errors.json',JSON.stringify(errors));
await page.screenshot({path:directory+'/browser-initial.png',fullPage:true});
await page.getByRole('button', {name:'Maybe later',exact:true}).click();
await page.getByRole('switch', {name:'Turn cameras on or off'}).click({timeout:5000});
await page.getByLabel('Rotation').waitFor();
await page.getByLabel('Rotation').selectOption('180');
await page.waitForFunction(()=>document.querySelector('video[autoplay]')?.readyState>=2);
await page.waitForTimeout(700);
await page.screenshot({path:directory+'/rotation-180.png',fullPage:true});
const angles=[];
for(const rotation of [0,90,180,270]) {
  await page.getByLabel('Rotation').selectOption(String(rotation));
  await page.waitForTimeout(650);
  const geometry=await page.locator('video[autoplay]').evaluate(video=>{
    const frame=video.parentElement.getBoundingClientRect();
    const rect=video.getBoundingClientRect();
    return {transform:video.style.transform,objectFit:video.style.objectFit,
      aspectRatio:video.parentElement.style.aspectRatio,native:[video.videoWidth,video.videoHeight],
      contained:rect.left>=frame.left-1&&rect.top>=frame.top-1&&rect.right<=frame.right+1&&rect.bottom<=frame.bottom+1};
  });
  if(!geometry.contained||!geometry.transform.includes(`rotate(${rotation}deg)`))throw Error(JSON.stringify(geometry));
  if(profile.cameras[0].rotation!==rotation)throw Error('Rotation not persisted');
  angles.push({rotation,...geometry});
  if(rotation===90)await page.screenshot({path:directory+'/rotation-90.png',fullPage:true});
}
await page.reload();
await page.getByRole('switch', {name:'Turn cameras on or off'}).click();
await page.getByLabel('Rotation').waitFor();
if(await page.getByLabel('Rotation').inputValue()!=='270')throw Error('Rotation lost after reload');
fs.writeFileSync(directory+'/browser.json',JSON.stringify({angles,profile_reload:true,page_errors:errors},null,2));
console.log(JSON.stringify({angles,profile_reload:true,page_errors:errors}));
await browser.close();

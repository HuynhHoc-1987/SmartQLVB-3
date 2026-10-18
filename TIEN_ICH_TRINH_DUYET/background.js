// Liên kết dữ liệu trang QLVB đang xem với lượt tải từ cùng tab.
const API='http://127.0.0.1:8765';
chrome.runtime.onMessage.addListener((msg,sender)=>{
 if(msg?.type!=='SMARTDOC_PAGE_METADATA'||!sender.tab?.id||!sender.tab.url?.startsWith('https://qlvbdh.vinhlong.gov.vn/'))return;
 chrome.storage.session.set({['page_'+sender.tab.id]:{meta:msg.metadata,at:Date.now()}});
});
chrome.downloads.onChanged.addListener(async change=>{
 if(change.state?.current!=='complete')return;
 const saved=await chrome.storage.local.get(['token','enabled']);if(!saved.enabled||!saved.token)return;
 const [item]=await chrome.downloads.search({id:change.id});if(!item?.filename)return;
 try{
  const response=await fetch(API+'/api/browser-import',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({token:saved.token,filename:item.filename,url:item.finalUrl||item.url||''})});
  const result=await response.json();if(!response.ok)throw Error(result.error||response.status);
  let status=(result.duplicate?'Tệp đã có: ':'Đã nhập: ')+item.filename;
  // Chỉ gắn metadata khi lượt tải xuất phát từ tab QLVB và metadata mới trong 10 phút.
  const url=item.finalUrl||item.url||'';
  if(item.tabId>=0 && result.id){
   const tab=await chrome.tabs.get(item.tabId).catch(()=>null);
   if(tab?.url?.startsWith('https://qlvbdh.vinhlong.gov.vn/')){
    const store=await chrome.storage.session.get('page_'+item.tabId);
    const page=store['page_'+item.tabId];
    if(page&&Date.now()-page.at<10*60*1000){
     const r=await fetch(API+'/api/metadata',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({token:saved.token,id:result.id,metadata:page.meta})});
     if(r.ok)status+=' | Đã điền thông tin trang QLVB';
     else status+=' | Chưa điền thông tin (cần kiểm tra)';
    }else status+=' | Chưa có thông tin trang chi tiết';
   }
  }
  await chrome.storage.local.set({lastResult:status,lastTime:new Date().toLocaleString('vi-VN')});
 }catch(e){await chrome.storage.local.set({lastResult:'Chưa nhập: '+e.message,lastTime:new Date().toLocaleString('vi-VN')});}
});

const $=id=>document.getElementById(id);
chrome.storage.local.get(['token','enabled','lastResult']).then(x=>{$('token').value=x.token||'';$('enabled').checked=!!x.enabled;$('status').textContent=x.lastResult||'Chưa có lượt tải'});
$('save').onclick=async()=>{await chrome.storage.local.set({token:$('token').value.trim(),enabled:$('enabled').checked});$('status').textContent='Đã lưu cấu hình'};
$('download').onclick=async()=>{
 const [tab]=await chrome.tabs.query({active:true,currentWindow:true});
 if(!tab?.id||!tab.url?.startsWith('https://qlvbdh.vinhlong.gov.vn/')){$('status').textContent='Hãy mở tab QLVB Vĩnh Long, vào chi tiết văn bản rồi nhấn lại.';return;}
 try{const result=await chrome.tabs.sendMessage(tab.id,{type:'SMARTDOC_DOWNLOAD_VISIBLE'});$('status').textContent=result?.message||'Không có phản hồi';}
 catch(e){$('status').textContent='Không kết nối được trang QLVB. Hãy tải lại trang QLVB rồi thử.';}
};
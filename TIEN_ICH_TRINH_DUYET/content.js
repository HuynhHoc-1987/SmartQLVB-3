// Chỉ đọc văn bản đang hiển thị trong trang mà người dùng đã đăng nhập.
// Không truy cập cookie, mật khẩu, token đăng nhập, hoặc gọi API nội bộ của tỉnh.
function extract(){
 const txt=s=>(s||'').replace(/\s+/g,' ').trim();
 const data={};
 for(const tr of document.querySelectorAll('tr')){
  const cells=[...tr.querySelectorAll(':scope > td, :scope > th')];
  for(let i=0;i+1<cells.length;i+=2){
   const key=txt(cells[i].innerText).replace(/[:：]$/,'').toLowerCase();
   const val=txt(cells[i+1].innerText);
   if(!val||val.length>1600)continue;
   if(key==='số ký hiệu')data.number=val;
   if(key==='số đến')data.incoming_no=val;
   if(key==='trích yếu')data.summary=val;
   if(key==='đơn vị ban hành')data.agency=val;
   if(key==='ngày đến')data.received_date=val;
   if(key==='ngày văn bản')data.issued_date=val;
   if(key==='ngày hết hạn'||key==='hạn xử lý'){
    const m=val.match(/^(\d{2})\/(\d{2})\/(\d{4})/);
    if(m)data.due=`${m[3]}-${m[2]}-${m[1]}`;
   }
  }
 }
 if(!data.number&&!data.incoming_no)return null;
 data.source_system='QLVB tỉnh Vĩnh Long';data.metadata_source='Trang chi tiết QLVB (Chrome)';
 return data;
}
let prev='';function capture(){const meta=extract();if(!meta)return;const str=JSON.stringify(meta);if(str===prev)return;prev=str;chrome.runtime.sendMessage({type:'SMARTDOC_PAGE_METADATA',metadata:meta},()=>{void chrome.runtime.lastError});}
const obs=new MutationObserver(()=>{clearTimeout(window.__smartdocDebounce);window.__smartdocDebounce=setTimeout(capture,500)});
obs.observe(document.documentElement,{subtree:true,childList:true,characterData:true});capture();

// Chỉ kích hoạt bởi thao tác bấm nút của người dùng trong popup tiện ích.
// Không gọi API nội bộ, không đọc cookie, không tự duyệt hay tải hàng loạt.
chrome.runtime.onMessage.addListener((msg,sender,reply)=>{
 if(msg?.type!=='SMARTDOC_DOWNLOAD_VISIBLE')return;
 const section=[...document.querySelectorAll('tr')].find(tr=>/File đính kèm/i.test(tr.innerText||''));
 if(!section){reply({ok:false,message:'Chưa thấy mục File đính kèm. Hãy mở trang chi tiết một văn bản.'});return;}
 const scope=section.querySelector('td:last-child')||section;
 const candidates=[...scope.querySelectorAll('a,button,[role="button"]')].filter(el=>{
  const t=(el.innerText||el.textContent||'').trim();const h=el.getAttribute('href')||'';
  return /\.pdf|\.docx?|\.xlsx?/i.test(t+' '+h) && !/xem tất cả|xem tab mới/i.test(t);
 });
 if(candidates.length!==1){reply({ok:false,message:candidates.length?'Có nhiều tệp. Hãy nhấn tải đúng tệp trực tiếp trên trang QLVB.':'Không xác định được nút tải tệp. Hãy nhấn tải trực tiếp trên trang QLVB.'});return;}
 const el=candidates[0];
 // Không tự bấm liên kết ngoài hệ thống tỉnh hoặc javascript: không rõ chức năng.
 const href=el.getAttribute('href');
 if(href && !href.startsWith('#') && !href.startsWith('javascript:')){
  try{if(new URL(href,location.href).origin!==location.origin){reply({ok:false,message:'Tệp dùng liên kết ngoài hệ thống. Hãy tải trực tiếp trên trang.'});return;}}catch(e){reply({ok:false,message:'Liên kết không hợp lệ'});return;}
 }
 capture();el.click();reply({ok:true,message:'Đã nhấn tệp đính kèm. Nếu trang chỉ mở chế độ xem, hãy nhấn nút Tải xuống của hệ thống.'});
});

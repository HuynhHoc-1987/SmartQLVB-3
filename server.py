import secrets,os,sys,json,sqlite3,hashlib,datetime,zipfile,io,html,mimetypes,urllib.parse,shutil
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
from pathlib import Path
from xml.sax.saxutils import escape
# PyInstaller onedir: dữ liệu cạnh file .exe, giao diện ở thư mục _internal.
if getattr(sys,'frozen',False):
 ROOT=Path(sys.executable).resolve().parent
 ASSETS=Path(getattr(sys,'_MEIPASS',ROOT))
else:
 ROOT=Path(__file__).resolve().parent
 ASSETS=ROOT
DATA=ROOT/'DU_LIEU'; DOCS=DATA/'TEP'; EXPORT=DATA/'BAO_CAO_XLSX'; CLASSIFIED=DATA/'PHAN_LOAI'; DB=DATA/'smartdoc.sqlite3'
for p in (DATA,DOCS,EXPORT,CLASSIFIED):p.mkdir(exist_ok=True,parents=True)
def conn():
 c=sqlite3.connect(DB);c.row_factory=sqlite3.Row;c.execute('PRAGMA journal_mode=WAL');return c
def init():
 with conn() as c:c.execute('CREATE TABLE IF NOT EXISTS docs (id TEXT PRIMARY KEY, name TEXT, kind TEXT, level TEXT, agency TEXT, number TEXT, grp TEXT, due TEXT, state TEXT, related TEXT, notes TEXT, created TEXT, size INTEGER)')
init()
# Bổ sung cột mà không xóa hoặc tạo lại dữ liệu phiên bản cũ.
EXTRA={'incoming_no':'TEXT','summary':'TEXT','received_date':'TEXT','issued_date':'TEXT','source_system':'TEXT','metadata_source':'TEXT','doc_type':'TEXT','classified_path':'TEXT'}
with conn() as c:
 existing={r['name'] for r in c.execute('PRAGMA table_info(docs)')}
 for col,typ in EXTRA.items():
  if col not in existing:c.execute(f'ALTER TABLE docs ADD COLUMN {col} {typ}')

# Phân loại chỉ áp dụng cho bản sao do SmartQLVB quản lý.
import re,unicodedata
TYPES={'QD':'Quyet_dinh','KH':'Ke_hoach','CV':'Cong_van','TTR':'To_trinh'}
def slug(value,limit=65):
 value=unicodedata.normalize('NFKD',str(value or ''))
 value=''.join(c for c in value if not unicodedata.combining(c))
 value=re.sub(r'[^A-Za-z0-9]+','_',value).strip('_')[:limit]
 return value or 'Chua_xac_dinh'
def document_type(number,name,summary=''):
 # Ưu tiên ký hiệu hành chính; không phân loại theo chuỗi tùy ý trong trích yếu.
 n=unicodedata.normalize('NFKD',str(number or '').upper())
 m=re.search(r'(?:^|[/\-])(QD|KH|CV|TTR)(?:[/\-]|$)',n)
 if m:return TYPES[m.group(1)]
 label=unicodedata.normalize('NFKD',str(name or '').upper())
 label=''.join(c for c in label if not unicodedata.combining(c))
 m=re.search(r'(^|[ _.-])(QD|KH|CV|TTR)(?=[ _.-]|$)',label)
 if m:return TYPES[m.group(2)]
 for key,val in [('QUYET DINH','Quyet_dinh'),('KE HOACH','Ke_hoach'),('CONG VAN','Cong_van'),('TO TRINH','To_trinh')]:
  if label.startswith(key):return val
 return 'Khac'
def issuing_level(agency,level):
 a=slug(agency).upper();lv=slug(level).upper()
 if lv in ('TRUNG_UONG','CAP_TRUNG_UONG'):return 'Cap_Trung_uong'
 if lv in ('TINH','CAP_TINH'):return 'Cap_Tinh'
 if lv in ('XA','CAP_XA'):return 'Cap_Xa'
 if not a:return 'Chua_xac_dinh'
 if any(x in a for x in ('BO_', 'CHINH_PHU','THU_TUONG','QUOC_HOI','TRUNG_UONG')):return 'Cap_Trung_uong'
 if any(x in a for x in ('TINH','SO_','UBND_TINH')):return 'Cap_Tinh'
 if any(x in a for x in ('XA_','UBND_XA','PHONG_VAN_HOA_XA_HOI')):return 'Cap_Xa'
 return 'Chua_xac_dinh'
def classify(ident):
 with conn() as c:r=c.execute('SELECT * FROM docs WHERE id=?',(ident,)).fetchone()
 if not r or not (DOCS/ident).is_file():return
 typ=document_type(r['number'],r['name'],r['summary'])
 level=issuing_level(r['agency'],r['level'])
 agency=slug(r['agency']) if r['agency'] else 'Chua_xac_dinh'
 folder=classification_root()/level/agency/typ
 folder.mkdir(parents=True,exist_ok=True)
 safe_name=Path(r['name']).name
 safe_name=re.sub(r'[<>:"/\\|?*\x00-\x1f]','_',safe_name).strip(' .') or 'tai_lieu'
 dest=folder/(ident[:12]+'_'+safe_name[:180])
 old=r['classified_path'] or ''
 if old:
  old_path=Path(old) if Path(old).is_absolute() else DATA/old
  # Không tự xóa bản sao cũ khi thay đổi thư mục lưu hoặc phân loại.
 if not dest.exists():shutil.copy2(DOCS/ident,dest)
 with conn() as c:c.execute('UPDATE docs SET doc_type=?,classified_path=? WHERE id=?',(typ,str(dest),ident))
def reclassify_all():
 with conn() as c:ids=[r[0] for r in c.execute('SELECT id FROM docs')]
 for ident in ids:classify(ident)
 return len(ids)


# Cấu hình nơi lưu bản sao phân loại và nhận diện nội dung cục bộ.
SETTINGS_FILE=DATA/'cau_hinh_luu_tru.json'
def settings():
 default={'classification_root':str(CLASSIFIED.resolve()),'ai_mode':'rules','ollama_model':'qwen2.5:3b'}
 try:
  raw=json.loads(SETTINGS_FILE.read_text(encoding='utf-8'))
  if isinstance(raw,dict):
   for key in default:
    if isinstance(raw.get(key),str) and raw[key].strip():default[key]=raw[key]
 except (OSError,ValueError):pass
 return default

def classification_root():
 raw=settings()['classification_root']
 path=Path(os.path.expandvars(str(raw))).expanduser()
 if not path.is_absolute():raise ValueError('Đường dẫn lưu phải là đường dẫn tuyệt đối')
 path.mkdir(parents=True,exist_ok=True)
 if not path.is_dir():raise ValueError('Đường dẫn không phải thư mục')
 return path.resolve()

def save_settings(obj):
 if not isinstance(obj,dict):raise ValueError('Cấu hình không hợp lệ')
 cfg=settings()
 if 'classification_root' in obj:
  value=str(obj['classification_root']).strip()
  # Để trống = quay lại đường dẫn mặc định
  if not value:value=str(CLASSIFIED.resolve())
  folder=Path(os.path.expandvars(value)).expanduser()
  if not folder.is_absolute():raise ValueError('Hãy nhập đường dẫn tuyệt đối, ví dụ D:\\VanBan')
  folder.mkdir(parents=True,exist_ok=True)
  if not folder.is_dir():raise ValueError('Không thể tạo thư mục')
  probe=folder/'.smartqlvb_write_test'
  try:
   with probe.open('w',encoding='utf-8') as f:f.write('ok')
  finally:
   probe.unlink(missing_ok=True)
  cfg['classification_root']=str(folder.resolve())
 if 'ai_mode' in obj:
  if obj['ai_mode'] not in ('rules','ollama'):raise ValueError('Chế độ không hợp lệ')
  cfg['ai_mode']=obj['ai_mode']
 if 'ollama_model' in obj:
  model=str(obj['ollama_model']).strip()
  if not re.fullmatch(r'[a-zA-Z0-9_.:/-]{1,80}',model):raise ValueError('Tên mô hình không hợp lệ')
  cfg['ollama_model']=model
 tmp=SETTINGS_FILE.with_suffix('.tmp')
 tmp.write_text(json.dumps(cfg,ensure_ascii=False,indent=2),encoding='utf-8')
 tmp.replace(SETTINGS_FILE)
 return cfg

def read_content(path,filename):
 """Đọc text PDF có lớp chữ, DOCX, TXT; không OCR ảnh quét."""
 name=filename.lower()
 try:
  if name.endswith('.pdf'):
   try:
    import fitz
    with fitz.open(str(path)) as doc:return '\n'.join(p.get_text() for p in list(doc)[:8])[:30000]
   except ImportError:
    try:
     from pypdf import PdfReader
     reader=PdfReader(str(path))
     return '\n'.join(p.extract_text() or '' for p in reader.pages[:8])[:30000]
    except ImportError:return ''
  if name.endswith('.docx'):
   import xml.etree.ElementTree as ET
   with zipfile.ZipFile(path) as z:
    xml=z.read('word/document.xml')
   root=ET.fromstring(xml)
   return ' '.join(e.text or '' for e in root.iter() if e.tag.endswith('}t'))[:30000]
  if name.endswith(('.txt','.md')):return path.read_text(encoding='utf-8',errors='replace')[:30000]
 except Exception:return ''
 return ''
TOPIC_RULES={
 'Nghị quyết 57':['nghị quyết 57','57-nq/tw'],
 'Đề án 06':['đề án 06','đề án 6','06/cp','dữ liệu dân cư'],
 'Chuyển đổi số':['chuyển đổi số','chính quyền số','kinh tế số','xã hội số','hạ tầng số'],
 'Khoa học và công nghệ':['khoa học và công nghệ','đổi mới sáng tạo','nghiên cứu khoa học'],
 'Cải cách hành chính':['cải cách hành chính','thủ tục hành chính','dịch vụ công trực tuyến'],
 'Văn hóa – Xã hội':['an sinh xã hội','giáo dục','y tế','văn hóa','bảo trợ xã hội']
}
def suggest_topic(content,filename):
 plain=unicodedata.normalize('NFC',(content or '')[:20000]+' '+filename).lower()
 scores={topic:sum(plain.count(term) for term in terms) for topic,terms in TOPIC_RULES.items()}
 top=max(scores,key=scores.get)
 return (top,'quy_tac',scores[top]) if scores[top] else ('Khác','khong_du_du_lieu',0)
def local_ai(content,filename):
 topic,method,score=suggest_topic(content,filename)
 cfg=settings()
 if cfg.get('ai_mode')!='ollama' or not content.strip():return topic,method,score
 try:
  import urllib.request
  prompt=('Phân loại văn bản hành chính Việt Nam vào đúng MỘT nhóm: '+
   ', '.join(TOPIC_RULES)+', Khác. Chỉ trả tên nhóm, không giải thích.\n'+content[:7000])
  payload=json.dumps({'model':cfg.get('ollama_model','qwen2.5:3b'),'prompt':prompt,'stream':False,
                      'options':{'temperature':0}}).encode()
  req=urllib.request.Request('http://127.0.0.1:11434/api/generate',payload,
                            {'Content-Type':'application/json'},method='POST')
  with urllib.request.urlopen(req,timeout=18) as res:
   result=json.loads(res.read(50000)).get('response','').strip()
  if result in list(TOPIC_RULES)+['Khác']:return result,'ollama_cuc_bo',1
 except Exception:pass
 return topic,method,score
def analyze_doc(ident):
 with conn() as c:row=c.execute('SELECT * FROM docs WHERE id=?',(ident,)).fetchone()
 if not row:return None
 content=read_content(DOCS/ident,row['name'])
 topic,method,score=local_ai(content,row['name'])
 # Không tự ghi đè nhóm do người dùng đã chọn.
 if row['grp'] in ('','Khác') and topic!='Khác':
  with conn() as c:c.execute('UPDATE docs SET grp=? WHERE id=?',(topic,ident))
 classify(ident)
 return {'topic':topic,'method':method,'score':score,'text_found':bool(content.strip()),
         'text_length':len(content),'note':'Kết quả gợi ý; cần kiểm tra trước khi sử dụng chính thức'}

TOKEN_FILE=DATA/'browser_token.txt'
if not TOKEN_FILE.exists(): TOKEN_FILE.write_text(secrets.token_hex(24),encoding='utf-8')
TOKEN=TOKEN_FILE.read_text(encoding='utf-8').strip()
# Đường dẫn tải xuống được phép: ưu tiên thư mục cấu hình, sau đó Downloads chuẩn của Windows.
def allowed_download_dirs():
 dirs=[]
 cfg=DATA/'thu_muc_tai_xuong.txt'
 if cfg.exists():
  for line in cfg.read_text(encoding='utf-8-sig').splitlines():
   line=line.strip().strip('"')
   if line and not line.startswith('#'):dirs.append(Path(os.path.expandvars(line)).expanduser())
 if os.name=='nt':
  try:
   import winreg
   with winreg.OpenKey(winreg.HKEY_CURRENT_USER,r'Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders') as key:
    value,_=winreg.QueryValueEx(key,'{374DE290-123F-4565-9164-39C4925E467B}')
    dirs.append(Path(os.path.expandvars(value)))
  except OSError:pass
 dirs.append(Path.home()/'Downloads')
 out=[]
 for d in dirs:
  try:
   resolved=d.resolve(strict=True)
   if resolved.is_dir() and resolved not in out:out.append(resolved)
  except OSError:pass
 return out
# Làm mới danh sách Downloads mỗi lần nhập; hỗ trợ đổi cấu hình không cần khởi động lại.
HEAD=['Mã SHA256','Tên tệp','Loại','Cấp','Cơ quan','Số ký hiệu','Nhóm nhiệm vụ','Hạn xử lý','Trạng thái','Liên kết','Ghi chú','Ngày nhập','Dung lượng (byte)','Số đến','Trích yếu','Ngày đến','Ngày văn bản','Nguồn hệ thống','Nguồn siêu dữ liệu','Loại văn bản phân loại','Đường dẫn phân loại']
FIELDS=['id','name','kind','level','agency','number','grp','due','state','related','notes','created','size']
def xlsx(path,records):
 rows=[HEAD]+[[str(r[k] if r[k] is not None else '') for k in FIELDS+list(EXTRA)] for r in records]
 def col(i):
  s='';i+=1
  while i:s=chr(65+(i-1)%26)+s;i=(i-1)//26
  return s
 lines=[]
 for ri,row in enumerate(rows,1):
  cells=[]
  for ci,v in enumerate(row):
   ref=f'{col(ci)}{ri}';safe=escape(v).replace('"','&quot;')
   cells.append(f'<c r="{ref}" t="inlineStr" s="{1 if ri==1 else 0}"><is><t xml:space="preserve">{safe}</t></is></c>')
  lines.append(f'<row r="{ri}">'+''.join(cells)+'</row>')
 sheet='<?xml version="1.0" encoding="UTF-8" standalone="yes"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetViews><sheetView workbookViewId="0"/></sheetViews><cols>'+''.join(f'<col min="{i}" max="{i}" width="{(44 if i==2 else 24)}" customWidth="1"/>' for i in range(1,len(HEAD)+1))+'</cols><sheetData>'+''.join(lines)+'</sheetData><autoFilter ref="A1:M'+str(len(rows))+'"/></worksheet>'
 with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED) as z:
  z.writestr('[Content_Types].xml','<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/><Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/></Types>')
  z.writestr('_rels/.rels','<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>')
  z.writestr('xl/workbook.xml','<?xml version="1.0"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Danh muc van ban" sheetId="1" r:id="rId1"/></sheets></workbook>')
  z.writestr('xl/_rels/workbook.xml.rels','<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>')
  z.writestr('xl/styles.xml','<?xml version="1.0"?><styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><fonts count="2"><font/><font><b/><color rgb="FFFFFFFF"/></font></fonts><fills count="2"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="solid"><fgColor rgb="FF174B78"/><bgColor indexed="64"/></patternFill></fill></fills><borders count="1"><border/></borders><cellStyleXfs count="1"><xf/></cellStyleXfs><cellXfs count="2"><xf fontId="0" fillId="0" borderId="0" xfId="0"/><xf fontId="1" fillId="1" borderId="0" xfId="0" applyFill="1" applyFont="1"/></cellXfs></styleSheet>')
  z.writestr('xl/worksheets/sheet1.xml',sheet)
def export():
 with conn() as c:rows=c.execute('SELECT * FROM docs ORDER BY created DESC').fetchall()
 stamp=datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S');p=EXPORT/f'SmartQLVB_TongHop_{stamp}.xlsx';xlsx(p,rows);return p,len(rows)
class Handler(BaseHTTPRequestHandler):
 def reply(self,code,data,typ='application/json; charset=utf-8',name=None):
  if isinstance(data,(dict,list)):data=json.dumps(data,ensure_ascii=False).encode()
  if isinstance(data,str):data=data.encode()
  self.send_response(code);self.send_header('Content-Type',typ);self.send_header('Content-Length',str(len(data)));self.send_header('Cache-Control','no-store');
  if name:self.send_header('Content-Disposition',f'attachment; filename="{name}"')
  self.end_headers();self.wfile.write(data)
 def do_GET(self):
  u=urllib.parse.urlparse(self.path);p=u.path
  if p=='/':return self.reply(200,(ASSETS/'index.html').read_bytes(),'text/html; charset=utf-8')
  if p=='/api/browser-token':return self.reply(200,{'token':TOKEN,'downloads':[str(p) for p in DOWNLOADS]})
  if p=='/api/settings':return self.reply(200,settings())
  if p=='/api/reclassify':
   return self.reply(200,{'ok':True,'count':reclassify_all()})
  if p=='/api/docs':
   with conn() as c:rows=[dict(r) for r in c.execute('SELECT * FROM docs ORDER BY created DESC')]
   return self.reply(200,rows)
  if p=='/api/export':
   f,n=export();return self.reply(200,f.read_bytes(),'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',f.name)
  if p.startswith('/api/file/'):
   ident=p.rsplit('/',1)[-1]
   with conn() as c:r=c.execute('SELECT name FROM docs WHERE id=?',(ident,)).fetchone()
   if not r or not (DOCS/ident).is_file():return self.reply(404,{'error':'Không tìm thấy tệp'})
   return self.reply(200,(DOCS/ident).read_bytes(),'application/octet-stream',urllib.parse.quote(r['name']))
  return self.reply(404,{'error':'Không tìm thấy'})
 def do_POST(self):
  p=urllib.parse.urlparse(self.path).path
  length=int(self.headers.get('Content-Length','0'))
  if length>100*1024*1024:return self.reply(413,{'error':'Tệp vượt 100 MB'})
  try:raw=self.rfile.read(length)
  except Exception:return self.reply(400,{'error':'Dữ liệu không hợp lệ'})
  if p=='/api/settings':
   try:return self.reply(200,{'ok':True,'settings':save_settings(json.loads(raw))})
   except Exception as e:return self.reply(400,{'error':str(e)})
  if p=='/api/analyze':
   try:
    obj=json.loads(raw);ident=str(obj.get('id',''))
    if not re.fullmatch('[0-9a-f]{64}',ident):raise ValueError('Mã tệp không hợp lệ')
    result=analyze_doc(ident)
    if result is None:return self.reply(404,{'error':'Không tìm thấy văn bản'})
    return self.reply(200,result)
   except Exception as e:return self.reply(400,{'error':str(e)})
  if p=='/api/metadata':
   try:
    obj=json.loads(raw)
    if not secrets.compare_digest(str(obj.get('token','')),TOKEN):return self.reply(403,{'error':'Mã ghép nối không đúng'})
    ident=str(obj.get('id',''))
    if len(ident)!=64 or any(c not in '0123456789abcdef' for c in ident):return self.reply(400,{'error':'Mã tệp không hợp lệ'})
    meta=obj.get('metadata') or {}
    if not isinstance(meta,dict):return self.reply(400,{'error':'Dữ liệu không hợp lệ'})
    allowed=['number','agency','due','incoming_no','summary','received_date','issued_date','source_system','metadata_source']
    values={k:str(meta[k])[:1200] for k in allowed if isinstance(meta.get(k),str) and meta[k].strip()}
    if values.get('due') and not __import__('re').fullmatch(r'\d{4}-\d{2}-\d{2}',values['due']):values.pop('due')
    if not values:return self.reply(200,{'ok':True,'updated':False})
    with conn() as c:
     if not c.execute('SELECT 1 FROM docs WHERE id=?',(ident,)).fetchone():return self.reply(404,{'error':'Không có tệp cần cập nhật'})
     # Không ghi đè thông tin người dùng đã nhập; chỉ điền ô còn trống.
     c.execute('UPDATE docs SET '+','.join(f'{k}=CASE WHEN COALESCE({k},\'\')=\'\' THEN ? ELSE {k} END' for k in values)+' WHERE id=?',list(values.values())+[ident])
    classify(ident)
    return self.reply(200,{'ok':True,'updated':True})
   except Exception as e:return self.reply(400,{'error':str(e)})
  if p=='/api/browser-import':
   try:
    obj=json.loads(raw)
    if not secrets.compare_digest(str(obj.get('token','')),TOKEN):return self.reply(403,{'error':'Mã ghép nối không đúng'})
    path=Path(str(obj.get('filename',''))).resolve(strict=True)
    if not path.is_file() or not any(path.is_relative_to(d) for d in allowed_download_dirs()):return self.reply(403,{'error':'Tệp không nằm trong thư mục tải xuống được phép. Kiểm tra DU_LIEU/thu_muc_tai_xuong.txt'})
    if path.stat().st_size>50*1024*1024:return self.reply(413,{'error':'Tệp lớn hơn 50 MB; hãy nhập thủ công'})
    b=path.read_bytes();ident=hashlib.sha256(b).hexdigest()
    with conn() as c:
     if c.execute('SELECT 1 FROM docs WHERE id=?',(ident,)).fetchone():return self.reply(200,{'duplicate':True,'id':ident})
     (DOCS/ident).write_bytes(b)
     vals=[ident,path.name,'Đến','Khác','', '', 'Khác','', 'Chưa xử lý','', 'Tải từ Chrome/Edge; nguồn: '+str(obj.get('url',''))[:800],datetime.datetime.now().isoformat(timespec='seconds'),len(b)]
     c.execute('INSERT INTO docs ('+','.join(FIELDS)+') VALUES ('+','.join('?' for _ in FIELDS)+')',vals)
    analyze_doc(ident)
    return self.reply(200,{'ok':True,'name':path.name,'id':ident})
   except Exception as e:return self.reply(400,{'error':str(e)})
  if p=='/api/add':
   try:
    obj=json.loads(raw);import base64
    mandatory={'kind':'Loại văn bản','agency':'Cơ quan ban hành','number':'Số văn bản','due':'Hạn xử lý','received_date':'Ngày đến'}
    missing=[label for key,label in mandatory.items() if not str(obj.get(key,'')).strip()]
    if missing:return self.reply(422,{'error':'Thiếu trường bắt buộc: '+', '.join(missing)})
    import re
    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}',str(obj['due'])) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}',str(obj['received_date'])):return self.reply(422,{'error':'Ngày không hợp lệ'})
    if obj['due']<obj['received_date']:return self.reply(422,{'error':'Hạn xử lý không được trước ngày đến'})
    b=base64.b64decode(obj['base64'],validate=True);ident=hashlib.sha256(b).hexdigest()
    if len(b)>50*1024*1024:return self.reply(413,{'error':'Giới hạn mỗi tệp 50 MB'})
    name=Path(obj.get('name','tailieu')).name[:250]
    with conn() as c:
     if c.execute('SELECT 1 FROM docs WHERE id=?',(ident,)).fetchone():return self.reply(200,{'duplicate':True,'id':ident})
     (DOCS/ident).write_bytes(b)
     vals=[ident,name]+[str(obj.get(k,''))[:1000] for k in FIELDS[2:11]]+[datetime.datetime.now().isoformat(timespec='seconds'),len(b)]
     c.execute('INSERT INTO docs ('+','.join(FIELDS)+') VALUES ('+','.join('?' for _ in FIELDS)+')',vals)
     c.execute('UPDATE docs SET received_date=? WHERE id=?',(obj['received_date'],ident))
    analyze_doc(ident)
    return self.reply(200,{'ok':True})
   except Exception as e:return self.reply(400,{'error':str(e)})
  if p=='/api/status':
   try:
    obj=json.loads(raw);state=obj['state']
    if state not in ('Chưa xử lý','Đang xử lý','Hoàn thành'):raise ValueError('Trạng thái không hợp lệ')
    with conn() as c:c.execute('UPDATE docs SET state=? WHERE id=?',(state,obj['id']))
    return self.reply(200,{'ok':True})
   except Exception as e:return self.reply(400,{'error':str(e)})
  return self.reply(404,{'error':'Không tìm thấy'})
 def log_message(self,*args):pass
if __name__=='__main__':
 if '--export' in sys.argv:
  p,n=export();print(f'Da xuat {n} van ban: {p}')
 else:
  import webbrowser,threading
  url='http://127.0.0.1:8765'
  print('SmartQLVB:',url)
  server=ThreadingHTTPServer(('127.0.0.1',8765),Handler)
  threading.Timer(1.0,lambda:webbrowser.open(url)).start()
  server.serve_forever()

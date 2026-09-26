import os, uuid, hashlib, secrets, subprocess, base64, json, time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from fastapi import FastAPI, Depends, HTTPException, Request, UploadFile, File, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
import jwt
from passlib.hash import bcrypt

DB=os.environ['DATABASE_URL']; REDIS=os.getenv('REDIS_URL',''); UPLOAD=Path(os.getenv('UPLOAD_DIR','/data/uploads')); UPLOAD.mkdir(parents=True,exist_ok=True)
engine=create_engine(DB,pool_pre_ping=True); SessionLocal=sessionmaker(bind=engine)
app=FastAPI(title='California Commerce',version='2.0-lab')
app.add_middleware(CORSMiddleware,allow_origins=['*'],allow_credentials=True,allow_methods=['*'],allow_headers=['*'])

SCHEMA='''
CREATE TABLE IF NOT EXISTS roles(id SERIAL PRIMARY KEY,name TEXT UNIQUE NOT NULL);
CREATE TABLE IF NOT EXISTS users(id UUID PRIMARY KEY,email TEXT UNIQUE NOT NULL,password_hash TEXT NOT NULL,name TEXT,phone TEXT,active BOOLEAN DEFAULT TRUE,mfa_secret TEXT,reset_token TEXT,created_at TIMESTAMPTZ DEFAULT now());
CREATE TABLE IF NOT EXISTS user_roles(user_id UUID REFERENCES users(id) ON DELETE CASCADE,role_id INT REFERENCES roles(id) ON DELETE CASCADE,PRIMARY KEY(user_id,role_id));
CREATE TABLE IF NOT EXISTS sessions(id UUID PRIMARY KEY,user_id UUID REFERENCES users(id),token_hash TEXT,expires_at TIMESTAMPTZ,created_at TIMESTAMPTZ DEFAULT now());
CREATE TABLE IF NOT EXISTS categories(id SERIAL PRIMARY KEY,name TEXT UNIQUE);
CREATE TABLE IF NOT EXISTS products(id SERIAL PRIMARY KEY,category_id INT REFERENCES categories(id),sku TEXT UNIQUE,name TEXT,description TEXT,price NUMERIC(10,2),inventory INT DEFAULT 10,active BOOLEAN DEFAULT TRUE);
CREATE TABLE IF NOT EXISTS addresses(id SERIAL PRIMARY KEY,user_id UUID REFERENCES users(id),label TEXT,line1 TEXT,city TEXT,state TEXT,zip TEXT);
CREATE TABLE IF NOT EXISTS orders(id SERIAL PRIMARY KEY,user_id UUID REFERENCES users(id),address_id INT REFERENCES addresses(id),status TEXT,subtotal NUMERIC(10,2),discount NUMERIC(10,2) DEFAULT 0,total NUMERIC(10,2),coupon TEXT,created_at TIMESTAMPTZ DEFAULT now());
CREATE TABLE IF NOT EXISTS order_items(id SERIAL PRIMARY KEY,order_id INT REFERENCES orders(id),product_id INT REFERENCES products(id),quantity INT,unit_price NUMERIC(10,2));
CREATE TABLE IF NOT EXISTS invoices(id SERIAL PRIMARY KEY,order_id INT REFERENCES orders(id),invoice_no TEXT UNIQUE,total NUMERIC(10,2),status TEXT,created_at TIMESTAMPTZ DEFAULT now());
CREATE TABLE IF NOT EXISTS payments(id SERIAL PRIMARY KEY,order_id INT REFERENCES orders(id),user_id UUID REFERENCES users(id),brand TEXT,last4 TEXT,token TEXT,status TEXT);
CREATE TABLE IF NOT EXISTS reviews(id SERIAL PRIMARY KEY,product_id INT REFERENCES products(id),user_id UUID REFERENCES users(id),rating INT,body TEXT,created_at TIMESTAMPTZ DEFAULT now());
CREATE TABLE IF NOT EXISTS support_tickets(id SERIAL PRIMARY KEY,user_id UUID REFERENCES users(id),subject TEXT,message TEXT,status TEXT DEFAULT 'open',priority TEXT DEFAULT 'normal',created_at TIMESTAMPTZ DEFAULT now());
CREATE TABLE IF NOT EXISTS ticket_messages(id SERIAL PRIMARY KEY,ticket_id INT REFERENCES support_tickets(id),author_id UUID REFERENCES users(id),message TEXT,internal BOOLEAN DEFAULT FALSE,created_at TIMESTAMPTZ DEFAULT now());
CREATE TABLE IF NOT EXISTS uploaded_files(id UUID PRIMARY KEY,user_id UUID REFERENCES users(id),ticket_id INT REFERENCES support_tickets(id),filename TEXT,path TEXT,sha256 TEXT,content_type TEXT,verified BOOLEAN DEFAULT FALSE,created_at TIMESTAMPTZ DEFAULT now());
CREATE TABLE IF NOT EXISTS employees(id UUID PRIMARY KEY,user_id UUID REFERENCES users(id),department TEXT,title TEXT);
CREATE TABLE IF NOT EXISTS audit_logs(id SERIAL PRIMARY KEY,user_id UUID,event TEXT,object_type TEXT,object_id TEXT,ip TEXT,details JSONB,created_at TIMESTAMPTZ DEFAULT now());
CREATE TABLE IF NOT EXISTS api_keys(id SERIAL PRIMARY KEY,user_id UUID REFERENCES users(id),name TEXT,key_hash TEXT,active BOOLEAN DEFAULT TRUE,created_at TIMESTAMPTZ DEFAULT now());
CREATE TABLE IF NOT EXISTS notifications(id SERIAL PRIMARY KEY,user_id UUID REFERENCES users(id),title TEXT,body TEXT,read_at TIMESTAMPTZ);
CREATE TABLE IF NOT EXISTS coupons(code TEXT PRIMARY KEY,percent INT,uses INT DEFAULT 0,max_uses INT DEFAULT 1,active BOOLEAN DEFAULT TRUE);
CREATE TABLE IF NOT EXISTS lab_flags(id SERIAL PRIMARY KEY,code TEXT UNIQUE,category TEXT,level INT,points INT,objective TEXT,secret TEXT);
CREATE TABLE IF NOT EXISTS lab_submissions(id SERIAL PRIMARY KEY,user_id UUID REFERENCES users(id),flag_id INT REFERENCES lab_flags(id),evidence TEXT,submitted_at TIMESTAMPTZ DEFAULT now(),UNIQUE(user_id,flag_id));
CREATE TABLE IF NOT EXISTS inventory_reservations(id SERIAL PRIMARY KEY,order_id INT,product_id INT,quantity INT,created_at TIMESTAMPTZ DEFAULT now());
'''

def db():
 s=SessionLocal()
 try: yield s
 finally: s.close()

def init():
 with engine.begin() as c: c.execute(text(SCHEMA))
 seed()

def seed():
 with SessionLocal() as s:
  for r in ['Guest','Customer','Employee','Manager','Administrator']:
   s.execute(text('INSERT INTO roles(name) VALUES(:r) ON CONFLICT DO NOTHING'),{'r':r})
  roles={x['name']:x['id'] for x in s.execute(text('select id,name from roles')).mappings()}
  users=[('admin@californiacommerce.test','Admin Lab','Administrator'),('manager@californiacommerce.test','Morgan Lee','Manager'),('employee@californiacommerce.test','Taylor Reed','Employee'),('alice@californiacommerce.test','Alice Moreno','Customer'),('bob@californiacommerce.test','Bob Chen','Customer')]
  ids={}
  for e,n,r in users:
   u=s.execute(text('select id from users where email=:e'),{'e':e}).scalar()
   if not u:
    u=uuid.uuid4(); s.execute(text('insert into users(id,email,password_hash,name,mfa_secret) values(:id,:e,:p,:n,:m)'),{'id':u,'e':e,'p':bcrypt.hash('LabPass123!'),'n':n,'m':'1234567890'})
   ids[e]=u
   s.execute(text('insert into user_roles(user_id,role_id) values(:u,:r) on conflict do nothing'),{'u':u,'r':roles[r]})
  for n in ['Office Services','Technology','Business Support']:
   s.execute(text('insert into categories(name) values(:n) on conflict do nothing'),{'n':n})
  cats={x['name']:x['id'] for x in s.execute(text('select id,name from categories')).mappings()}
  products=[('CC-100','Managed Office Support','On-demand workplace and business operations support.',129.00,42,'Office Services'),('CC-220','Endpoint Care Plan','Synthetic endpoint management and reporting package.',249.00,18,'Technology'),('CC-310','Security Assessment','Authorized application and configuration assessment package.',599.00,7,'Technology'),('CC-410','Business Continuity Review','Tabletop continuity planning and documentation service.',399.00,11,'Business Support'),('CC-510','Document Processing','Secure document intake and workflow service.',89.00,33,'Business Support')]
  for sku,n,d,p,inv,cat in products:
   s.execute(text('insert into products(category_id,sku,name,description,price,inventory) values(:c,:sku,:n,:d,:p,:i) on conflict(sku) do nothing'),{'c':cats[cat],'sku':sku,'n':n,'d':d,'p':p,'i':inv})
  if not s.execute(text('select 1 from addresses limit 1')).first():
   s.execute(text("insert into addresses(user_id,label,line1,city,state,zip) values (:u,'Home','100 Market Street','San Jose','CA','95113')"),{'u':ids['alice@californiacommerce.test']})
  for code,pct,maxu in [('WELCOME10',10,3),('PARTNER20',20,1),('SERVICE15',15,2)]:
   s.execute(text('insert into coupons(code,percent,max_uses) values(:c,:p,:m) on conflict do nothing'),{'c':code,'p':pct,'m':maxu})
  flags=[('FLAG{CC_A01_ORDERBOUNDARY}','A01',1,100,'Access another customer order through a legitimate order workflow.'),('FLAG{CC_A01_ADMINBOUNDARY}','A01',2,150,'Reach an administrative function without the intended role.'),('FLAG{CC_A02_DEBUGSURFACE}','A02',1,75,'Identify an accidentally exposed diagnostic surface.'),('FLAG{CC_A03_DEPENDENCY}','A03',2,100,'Identify the intentionally pinned vulnerable dependency.'),('FLAG{CC_A04_SESSION}','A04',2,125,'Identify weak protection around session material.'),('FLAG{CC_A05_SEARCH}','A05',1,100,'Find the unsafe search query behavior.'),('FLAG{CC_A05_DIAGNOSTICS}','A05',2,150,'Find the isolated diagnostic command surface.'),('FLAG{CC_A06_COUPON}','A06',2,150,'Abuse a business-rule assumption in coupon redemption.'),('FLAG{CC_A07_RESET}','A07',2,150,'Identify the account recovery design weakness.'),('FLAG{CC_A08_FILE}','A08',2,125,'Identify unsafe trust in uploaded file integrity.'),('FLAG{CC_A09_AUDIT}','A09',3,150,'Demonstrate a sensitive action absent from audit coverage.'),('FLAG{CC_A10_STATE}','A10',3,175,'Trigger and observe an inconsistent exceptional state.')]
  for code,cat,lev,pts,obj in flags:
   s.execute(text('insert into lab_flags(code,category,level,points,objective,secret) values(:c,:cat,:l,:p,:o,:s) on conflict(code) do nothing'),{'c':code,'cat':cat,'l':lev,'p':pts,'o':obj,'s:':code,'s':secrets.token_hex(24)})
  # Employee records
  for e,dep,title in [('employee@californiacommerce.test','Customer Operations','Support Specialist'),('manager@californiacommerce.test','Operations','Operations Manager')]:
   s.execute(text('insert into employees(id,user_id,department,title) values(:id,:u,:d,:t) on conflict(id) do nothing'),{'id':ids[e],'u':ids[e],'d':dep,'t':title})
  if not s.execute(text('select 1 from orders limit 1')).first():
   alice=ids['alice@californiacommerce.test']; bob=ids['bob@californiacommerce.test'];
   p=s.execute(text("select id,price from products order by id limit 2")).mappings().all()
   for uid,pi in [(alice,p[0]),(bob,p[1])]:
    o=s.execute(text('insert into orders(user_id,status,subtotal,total) values(:u,\'processing\',:v,:v) returning id'),{'u':uid,'v':pi['price']}).scalar()
    s.execute(text('insert into order_items(order_id,product_id,quantity,unit_price) values(:o,:p,1,:v)'),{'o':o,'p':pi['id'],'v':pi['price']})
    s.execute(text('insert into invoices(order_id,invoice_no,total,status) values(:o,:n,:v,\'issued\')'),{'o':o,'n':f'CC-INV-{o:05d}','v':pi['price']})
  s.commit()

@app.on_event('startup')
def startup(): init()

def roles_for(uid,s): return [r[0] for r in s.execute(text('select r.name from roles r join user_roles ur on ur.role_id=r.id where ur.user_id=:u'),{'u':uid}).all()]
def current_user(request:Request,s:Session=Depends(db)):
 tok=request.cookies.get('cc_session') or request.headers.get('Authorization','').replace('Bearer ','')
 if not tok: raise HTTPException(401,'authentication required')
 try: p=jwt.decode(tok,os.getenv('JWT_SECRET','lab'),algorithms=['HS256'])
 except Exception as e: raise HTTPException(401,'invalid session')
 u=s.execute(text('select * from users where id=:id'),{'id':p.get('sub')}).mappings().first()
 if not u: raise HTTPException(401,'unknown user')
 return dict(u)|{'roles':roles_for(u['id'],s),'jwt_role':p.get('role')}
def require(*allowed):
 def dep(user=Depends(current_user)):
  if not set(user['roles']).intersection(allowed): raise HTTPException(403,'forbidden')
  return user
 return dep

def audit(s,user,event,obj=None,oid=None,request=None,details=None):
 s.execute(text('insert into audit_logs(user_id,event,object_type,object_id,ip,details) values(:u,:e,:t,:o,:ip,:d)'),{'u':user['id'] if user else None,'e':event,'t':obj,'o':str(oid) if oid else None,'ip':request.client.host if request else None,'d':json.dumps(details or {})})

@app.get('/api/health')
def health(): return {'status':'ok','lab':True}
@app.get('/api/products')
def products(q:str|None=None,s:Session=Depends(db)):
 if q is None: return list(s.execute(text('select * from products where active=true order by id')).mappings())
 # A05
 sql=f"select * from products where active=true and (name ilike '%{q}%' or description ilike '%{q}%') order by id"
 return list(s.execute(text(sql)).mappings())
@app.get('/api/products/{pid}')
def product(pid:int,s:Session=Depends(db)):
 p=s.execute(text('select * from products where id=:id'),{'id':pid}).mappings().first()
 if not p: raise HTTPException(404,'product not found')
 p=dict(p); p['reviews']=list(s.execute(text('select r.*,u.name from reviews r join users u on u.id=r.user_id where product_id=:p order by r.id desc'),{'p':pid}).mappings()); return p

@app.post('/api/auth/register')
def register(b:dict,s:Session=Depends(db)):
 uid=uuid.uuid4();
 try: s.execute(text('insert into users(id,email,password_hash,name) values(:id,:e,:p,:n)'),{'id':uid,'e':b['email'],'p':bcrypt.hash(b['password']),'n':b.get('name','New Customer')}); s.execute(text('insert into user_roles(user_id,role_id) select :u,id from roles where name=\'Customer\''),{'u':uid}); s.commit()
 except Exception: s.rollback(); raise HTTPException(400,'registration failed')
 return {'created':True}
@app.post('/api/auth/login')
def login(b:dict,s:Session=Depends(db),request:Request=None):
 u=s.execute(text('select * from users where email=:e'),{'e':b.get('email')}).mappings().first()
 if not u: raise HTTPException(404,'account not found') # A07 enumeration
 if not bcrypt.verify(b.get('password',''),u['password_hash']): raise HTTPException(401,'wrong password')
 # A04/A07 lab: long-lived token; weak cookie defaults.
 token=jwt.encode({'sub':str(u['id']),'role':roles_for(u['id'],s)[0],'iat':int(time.time())},os.getenv('JWT_SECRET','lab'),algorithm='HS256')
 s.execute(text('insert into sessions(id,user_id,token_hash,expires_at) values(:i,:u,:h,:x)'),{'i':uuid.uuid4(),'u':u['id'],'h':hashlib.sha256(token.encode()).hexdigest(),'x':datetime.now(timezone.utc)+timedelta(days=30)}); s.commit()
 return {'token':token,'user':{'id':str(u['id']),'name':u['name'],'email':u['email'],'roles':roles_for(u['id'],s)}}
@app.post('/api/auth/reset/request')
def reset_request(b:dict,s:Session=Depends(db)):
 u=s.execute(text('select id,email from users where email=:e'),{'e':b.get('email')}).mappings().first()
 if not u: raise HTTPException(404,'email not found') # A07
 tok=secrets.token_urlsafe(10); s.execute(text('update users set reset_token=:t where id=:u'),{'t':tok,'u':u['id']}); s.commit(); return {'message':'reset issued','debug_token':tok} # A02/A07 lab-only
@app.post('/api/auth/reset/complete')
def reset_complete(b:dict,s:Session=Depends(db)):
 u=s.execute(text('select id from users where reset_token=:t'),{'t':b.get('token')}).mappings().first()
 if not u: raise HTTPException(400,'invalid token')
 s.execute(text('update users set password_hash=:p,reset_token=null where id=:u'),{'p':bcrypt.hash(b['password']),'u':u['id']}); s.commit(); return {'reset':True}
@app.post('/api/auth/mfa/verify')
def mfa(b:dict,user=Depends(current_user)): return {'verified':b.get('code')=='123456'} # deliberately weak static lab workflow

@app.get('/api/me')
def me(user=Depends(current_user)): return {k:user[k] for k in ['id','email','name','phone','roles']}
@app.get('/api/users/{uid}')
def user_profile(uid:str,user=Depends(current_user),s:Session=Depends(db)):
 # A01 horizontal boundary weakness
 u=s.execute(text('select id,email,name,phone from users where id=:u'),{'u':uid}).mappings().first()
 if not u: raise HTTPException(404,'not found')
 return u
@app.get('/api/orders')
def my_orders(user=Depends(current_user),s:Session=Depends(db)):
 return list(s.execute(text('select * from orders where user_id=:u order by id desc'),{'u':user['id']}).mappings())
@app.get('/api/orders/{oid}')
def get_order(oid:int,user=Depends(current_user),s:Session=Depends(db)):
 # A01 BOLA
 o=s.execute(text('select * from orders where id=:id'),{'id':oid}).mappings().first()
 if not o: raise HTTPException(404,'order not found')
 return o
@app.post('/api/orders')
def create_order(b:dict,user=Depends(current_user),s:Session=Depends(db),request:Request=None):
 p=s.execute(text('select * from products where id=:p'),{'p':b['product_id']}).mappings().first()
 if not p: raise HTTPException(404,'product not found')
 qty=int(b.get('quantity',1)); subtotal=float(p['price'])*qty; discount=0
 coupon=b.get('coupon')
 if coupon:
  c=s.execute(text('select * from coupons where code=:c'),{'c':coupon}).mappings().first()
  if c and c['active'] and c['uses']<c['max_uses']: discount=subtotal*c['percent']/100; s.execute(text('update coupons set uses=uses+1 where code=:c'),{'c':coupon})
  # A06: no atomic redemption/unique ownership semantics
 total=subtotal-discount
 o=s.execute(text('insert into orders(user_id,status,subtotal,discount,total,coupon) values(:u,\'pending\',:s,:d,:t,:c) returning id'),{'u':user['id'],'s':subtotal,'d':discount,'t':total,'c':coupon}).scalar()
 s.execute(text('insert into order_items(order_id,product_id,quantity,unit_price) values(:o,:p,:q,:v)'),{'o':o,'p':p['id'],'q':qty,'v':p['price']}); s.commit()
 return {'id':o,'total':total,'status':'pending'}
@app.post('/api/orders/{oid}/cancel')
def cancel(oid:int,user=Depends(current_user),s:Session=Depends(db)):
 # A09: sensitive state change intentionally not audited
 s.execute(text("update orders set status='cancelled' where id=:o"),{'o':oid}); s.commit(); return {'cancelled':True}

@app.get('/api/invoices')
def invoices(user=Depends(current_user),s:Session=Depends(db)):
 return list(s.execute(text('select i.* from invoices i join orders o on o.id=i.order_id where o.user_id=:u'),{'u':user['id']}).mappings())
@app.get('/api/payments')
def payments(user=Depends(current_user),s:Session=Depends(db)):
 return list(s.execute(text('select id,brand,last4,status from payments where user_id=:u'),{'u':user['id']}).mappings())
@app.post('/api/reviews')
def review(b:dict,user=Depends(current_user),s:Session=Depends(db)):
 # A05 stored XSS through unsanitized body
 r=s.execute(text('insert into reviews(product_id,user_id,rating,body) values(:p,:u,:r,:b) returning *'),{'p':b['product_id'],'u':user['id'],'r':b['rating'],'b':b['body']}).mappings().first(); s.commit(); return r

@app.post('/api/support')
def ticket(b:dict,user=Depends(current_user),s:Session=Depends(db)):
 r=s.execute(text('insert into support_tickets(user_id,subject,message) values(:u,:s,:m) returning *'),{'u':user['id'],'s':b['subject'],'m':b['message']}).mappings().first(); s.commit(); return r
@app.get('/api/support')
def tickets(user=Depends(current_user),s:Session=Depends(db)):
 return list(s.execute(text('select * from support_tickets where user_id=:u order by id desc'),{'u':user['id']}).mappings())
@app.post('/api/files')
async def upload(file:UploadFile=File(...),user=Depends(current_user),s:Session=Depends(db)):
 fid=str(uuid.uuid4()); data=await file.read(); path=UPLOAD/(fid+'-'+file.filename); path.write_bytes(data); digest=hashlib.sha256(data).hexdigest()
 # A08: client metadata/integrity trust and executable content allowed.
 s.execute(text('insert into uploaded_files(id,user_id,filename,path,sha256,content_type,verified) values(:i,:u,:f,:p,:h,:ct,false)'),{'i':fid,'u':user['id'],'f':file.filename,'p':str(path),'h':digest,'ct':file.content_type}); s.commit(); return {'id':fid,'filename':file.filename,'sha256':digest}
@app.get('/api/files/{fid}')
def file_download(fid:str,user=Depends(current_user),s:Session=Depends(db)):
 f=s.execute(text('select * from uploaded_files where id=:i'),{'i':fid}).mappings().first()
 if not f: raise HTTPException(404,'file not found')
 # A01: file object authorization weakness
 return FileResponse(f['path'],filename=f['filename'],media_type=f['content_type'] or 'application/octet-stream')

@app.get('/api/admin/users')
def admin_users(user=Depends(current_user),s:Session=Depends(db)):
 # A01 vertical check uses JWT claim instead of DB role
 if user.get('jwt_role') not in ('Administrator','Manager'): raise HTTPException(403,'forbidden')
 return list(s.execute(text('select id,email,name from users order by created_at')).mappings())
@app.patch('/api/admin/users/{uid}/role')
def change_role(uid:str,b:dict,user=Depends(require('Administrator')),s:Session=Depends(db)):
 r=b.get('role'); rid=s.execute(text('select id from roles where name=:r'),{'r':r}).scalar()
 if not rid: raise HTTPException(400,'unknown role')
 s.execute(text('delete from user_roles where user_id=:u'),{'u':uid}); s.execute(text('insert into user_roles(user_id,role_id) values(:u,:r)'),{'u':uid,'r':rid}); audit(s,user,'role_change','user',uid,None,{'new_role':r}); s.commit(); return {'updated':True}
@app.get('/api/admin/orders')
def admin_orders(user=Depends(require('Employee','Manager','Administrator')),s:Session=Depends(db)):
 return list(s.execute(text('select * from orders order by id desc')).mappings())
@app.post('/api/admin/refunds/{oid}')
def refund(oid:int,user=Depends(require('Employee','Manager','Administrator')),s:Session=Depends(db)):
 # A06/A09: refund endpoint doesn't verify payment/refund state; no audit for Employee
 s.execute(text("update orders set status='refunded' where id=:o"),{'o':oid}); s.commit(); return {'status':'refunded'}
@app.get('/api/admin/audit')
def audit_logs(user=Depends(require('Manager','Administrator')),s:Session=Depends(db)):
 return list(s.execute(text('select * from audit_logs order by id desc limit 200')).mappings())
@app.get('/api/admin/files')
def admin_files(user=Depends(require('Employee','Manager','Administrator')),s:Session=Depends(db)):
 return list(s.execute(text('select id,user_id,filename,sha256,verified,created_at from uploaded_files order by created_at desc')).mappings())
@app.post('/api/admin/diagnostics')
def diagnostics(b:dict,user=Depends(require('Administrator'))):
 # A05 isolated command injection lab surface. Keep container unprivileged.
 host=b.get('host','127.0.0.1'); out=subprocess.check_output(f'ping -c 1 {host}',shell=True,text=True,stderr=subprocess.STDOUT,timeout=5); return {'output':out}
@app.get('/api/debug/config')
def debug_config():
 # A02: intentionally exposed debug information
 return {'lab_mode':os.getenv('LAB_MODE'),'database':DB,'jwt_secret':os.getenv('JWT_SECRET'),'debug':os.getenv('DEBUG'),'dependencies':'see backend/requirements.txt'}
@app.get('/api/dev/routes')
def dev_routes(): return [r.path for r in app.routes] # A02 exposed development endpoint

@app.get('/api/lab/objectives')
def objectives(user=Depends(current_user),s:Session=Depends(db)):
 # Player sees objectives but never secrets/flags.
 rows=list(s.execute(text('select id,category,level,points,objective from lab_flags order by level,id')).mappings()); done={x['flag_id'] for x in s.execute(text('select flag_id from lab_submissions where user_id=:u'),{'u':user['id']}).mappings()}; return [{**dict(x),'completed':x['id'] in done} for x in rows]
@app.post('/api/lab/submit')
def submit(b:dict,user=Depends(current_user),s:Session=Depends(db)):
 code=b.get('flag',''); f=s.execute(text('select * from lab_flags where code=:c'),{'c':code}).mappings().first()
 if not f: raise HTTPException(400,'invalid flag')
 try: s.execute(text('insert into lab_submissions(user_id,flag_id,evidence) values(:u,:f,:e)'),{'u':user['id'],'f':f['id'],'e':b.get('evidence','')}); s.commit()
 except Exception: s.rollback(); raise HTTPException(409,'already submitted')
 return {'accepted':True,'points':f['points']}
@app.get('/api/lab/score')
def score(user=Depends(current_user),s:Session=Depends(db)):
 r=s.execute(text('select coalesce(sum(f.points),0) points,count(*) completed from lab_submissions x join lab_flags f on f.id=x.flag_id where x.user_id=:u'),{'u':user['id']}).mappings().first(); return r
@app.post('/api/admin/lab/reset/{uid}')
def reset_lab(uid:str,user=Depends(require('Administrator')),s:Session=Depends(db)):
 s.execute(text('delete from lab_submissions where user_id=:u'),{'u':uid}); s.commit(); return {'reset':True}

import getpass
from sqlalchemy import select
from app.main import DB, User, hasher, audit, Register
with DB() as s:
    if s.scalar(select(User).where(User.role == 'SUPER_ADMIN')):
        raise SystemExit('A super administrator already exists.')
    email = input('Administrator email: ').strip().lower()
    name = input('Administrator name: ').strip()
    password = getpass.getpass('Password (12+ characters, mixed case, digit and symbol): ')
    Register(name=name,email=email,password=password,terms=True,privacy=True)
    if s.scalar(select(User).where(User.email == email)):
        raise SystemExit('This email already exists. No account changed.')
    u = User(email=email,name=name,password=hasher.hash(password),verified=True,role='SUPER_ADMIN')
    s.add(u); s.flush(); audit(s,u.id,'super_admin_bootstrap'); s.commit()
    print('Super administrator created.')

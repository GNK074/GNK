"""Create a pending internal review case; never assert broker approval.

No app Settings import: this repair must work when app configuration is invalid.
Only the execution reference is edited. Flags, tick units and secrets are kept.
"""
from datetime import datetime,timezone
from pathlib import Path
import json,os,re,stat,tempfile,uuid

PATTERN=re.compile(r'^\s*(?:export\s+)?DHAN_EXECUTION_REFERENCE\s*=\s*(.*?)\s*$',re.I)

def reference_value(raw):
    value=raw.strip()
    if value.startswith(('"',"'")):
        quote=value[0];end=value.find(quote,1)
        return value[1:end].strip() if end>=1 else ''
    return value.split(' #',1)[0].strip()

def configure(root):
    root=Path(root).resolve();env=root/'.env'
    if env.is_symlink() or not env.is_file():raise ValueError('A regular .env file is required; no settings were changed.')
    text=env.read_text(encoding='utf-8');lines=text.splitlines()
    matches=[reference_value(m.group(1)) for line in lines if (m:=PATTERN.match(line))]
    current=matches[-1] if matches else ''
    if current and current.lower() not in ('true','false','pending'):
        print('DHAN_EXECUTION_REFERENCE is already configured; no changes made.')
        return None
    reference='GNK-DHAN-REVIEW-'+uuid.uuid4().hex.upper()
    directory=root/'deploy'/'review_records'
    if directory.is_symlink() or (root/'deploy').is_symlink():raise ValueError('Review directory must be local; no settings were changed.')
    directory.mkdir(mode=0o700,parents=True,exist_ok=True)
    record=directory/(reference+'.json')
    body={'reference':reference,'created_at':datetime.now(timezone.utc).isoformat(),'status':'PENDING','broker':'dhan','scope':'NSE EQ intraday LIMIT DAY; no short selling','broker_approved':False,'review_completed':False,'purpose':'Internal configuration-review tracking only. Complete GNK production approval and real broker acceptance separately.'}
    with record.open('x',encoding='utf-8') as f:
        os.chmod(record,0o600);json.dump(body,f,indent=2);f.write('\n')
    found=False;updated=[]
    for line in lines:
        if PATTERN.match(line):
            if not found:updated.append('DHAN_EXECUTION_REFERENCE='+reference);found=True
        else:updated.append(line)
    if not found:updated.append('DHAN_EXECUTION_REFERENCE='+reference)
    temporary=None
    try:
        with tempfile.NamedTemporaryFile(mode='w',encoding='utf-8',dir=root,prefix='.gnk-env-',delete=False,newline='\n') as f:
            temporary=Path(f.name);os.chmod(temporary,stat.S_IMODE(env.stat().st_mode))
            f.write('\n'.join(updated)+'\n');f.flush();os.fsync(f.fileno())
        os.replace(temporary,env)
    finally:
        if temporary and temporary.exists():temporary.unlink()
    print('Created PENDING Dhan review record: deploy/review_records/'+record.name)
    print('Updated DHAN_EXECUTION_REFERENCE only. Trading flags, tick multiplier and secrets preserved.')
    print('Broker approval, account authorization and arming were NOT changed. No orders were sent.')
    return reference

if __name__=='__main__':
    try:configure(Path(__file__).resolve().parents[2])
    except (ValueError,OSError):raise SystemExit('Reference setup failed. Check .env/review directory permissions; no approval was granted. Details suppressed.') from None

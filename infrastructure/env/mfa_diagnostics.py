"""Print only redacted, read-only MFA diagnostic flags for an operator."""
import json
import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'backend'))

def main():
    email=os.environ.get('GNK_MFA_EMAIL','').strip()
    if not email:
        print('Account email is required locally. No MFA code or setup key is needed.',file=sys.stderr)
        return 1
    try:
        from app.database.session import DB
        from app.security.mfa_diagnostics import diagnose_mfa
        with DB() as s:
            result=diagnose_mfa(s,email)
        print(json.dumps(result,indent=2))
    except Exception:
        print('MFA inspection failed. Check database connectivity/schema and mounted encryption-key configuration. Details suppressed.',file=sys.stderr)
        return 1
    return 0
if __name__=='__main__':
    sys.exit(main())

"""Generate new secret files/profile. Existing files are never overwritten."""
import argparse, base64, os, secrets
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]

def write_new(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 384)
    with os.fdopen(fd, 'w') as out:
        out.write(content)

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--production', action='store_true')
    p.add_argument('--output', default='.env.generated')
    args = p.parse_args()
    target = (ROOT / args.output).resolve()
    if target.exists():
        raise SystemExit('Output already exists; no files changed.')
    template = (ROOT / ('.env.production.example' if args.production else '.env.example')).read_text()
    replacements = {'JWT_SECRET': secrets.token_urlsafe(48), 'SECRET_KEY': secrets.token_urlsafe(48), 'FIELD_ENCRYPTION_KEY': base64.urlsafe_b64encode(secrets.token_bytes(32)).decode(), 'POSTGRES_PASSWORD': secrets.token_urlsafe(32)}
    result = []
    for line in template.splitlines():
        key = line.split('=', 1)[0]
        if key in replacements:
            line = key + '=' + replacements[key]
        result.append(line)
    if args.production:
        paths = [ROOT / 'secrets/postgres_password', ROOT / 'secrets/redis_password', ROOT / 'secrets/app_db_password']
        if any((path.exists() for path in paths)):
            raise SystemExit('Production secret files already exist. Use the documented rotation procedure; no files changed.')
        (ROOT / 'secrets').mkdir(mode=448, exist_ok=True)
        (ROOT / 'secrets').chmod(448)
        created = []
        try:
            for path in paths:
                write_new(path, secrets.token_urlsafe(40) + '\n')
                created.append(path)
                path.chmod(292)
            write_new(target, '\n'.join(result) + '\n')
        except Exception:
            for path in created:
                path.unlink()
            raise
    else:
        write_new(target, '\n'.join(result) + '\n')
    print('New secret profile written. Review SMTP and domain settings before activation. Secret values were not printed.')
if __name__ == '__main__':
    main()

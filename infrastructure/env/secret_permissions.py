"""Check/repair file-backed Compose secret permissions without reading contents.

Only direct, regular files inside this project's real secrets/ directory qualify.
Compose file secrets preserve host permissions; uid/gid/mode overrides do not
remap file-backed sources in ordinary local Docker Compose.
"""
import argparse,json,os,stat,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
NAMES=('postgres_password','app_db_password','redis_password')

def plan(root,config):
    directory=root/'secrets'
    if directory.is_symlink() or not directory.is_dir():raise ValueError('Managed secrets directory is missing or a symlink')
    allowed=directory.resolve()
    paths=[]
    for name in NAMES:
        value=config.get('secrets',{}).get(name,{}).get('file')
        if not value:raise ValueError('Required file-backed secret is not configured: '+name)
        path=Path(value)
        if not path.is_absolute():path=root/path
        if path.is_symlink() or path.resolve().parent!=allowed or not path.is_file():
            raise ValueError('Secret must be a regular direct file in the managed secrets directory: '+name)
        paths.append((name,path))
    return directory,paths

def apply_permissions(root,config,apply=False):
    directory,paths=plan(root,config)
    changes=[]
    if stat.S_IMODE(directory.stat().st_mode)!=0o700:changes.append(('secrets directory',directory,0o700))
    for name,path in paths:
        if stat.S_IMODE(path.stat().st_mode)!=0o444:changes.append((name,path,0o444))
    if apply:
        # Tighten the host directory before allowing mounted files to be read by
        # container UIDs. No recursive chmod/chown and no secret rewrites.
        directory.chmod(0o700)
        for name,path in paths:path.chmod(0o444)
    return [name for name,_,_ in changes]

def main():
    p=argparse.ArgumentParser();p.add_argument('--apply',action='store_true');args=p.parse_args()
    if os.name!='posix':raise SystemExit('Run this permission check on the Ubuntu Docker host.')
    command=['docker','compose','--project-directory',str(ROOT),'--env-file',str(ROOT/'.env'),'-f',str(ROOT/'docker-compose.yml'),'-f',str(ROOT/'docker-compose.prod.yml'),'config','--format','json']
    try:
        result=subprocess.run(command,cwd=ROOT,text=True,capture_output=True,check=False)
        if result.returncode:raise ValueError('Compose configuration failed; output suppressed to protect environment values')
        changes=apply_permissions(ROOT,json.loads(result.stdout),args.apply)
    except (OSError,ValueError):
        print('Secret permission check failed. Check ownership, Compose configuration and real files under secrets/. No values are printed. Use an operator account with Docker/file access.',file=sys.stderr)
        return 1
    if changes and not args.apply:
        print('Permission repair required for: '+', '.join(changes)+'. Run this command with --apply on the host.')
        return 1
    print('Secret permissions '+('repaired' if args.apply else 'verified')+'. Password contents were not read or changed.')
    return 0
if __name__=='__main__':sys.exit(main())
